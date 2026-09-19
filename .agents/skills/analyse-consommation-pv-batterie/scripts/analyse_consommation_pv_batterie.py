#!/usr/bin/env python3
"""Analyse consommation quart-horaire et pré-dimensionnement PV + batterie.

Ce script:
- lit un CSV Romande Energie quart-horaire (timestamp ; kWh par quart d'heure),
- calcule des statistiques mensuelles par plages horaires (semaine/week-end),
- calcule la puissance de pointe (kW) par plage,
- simule une production PV standard Vaud (profil simplifié) et une batterie,
- compare plusieurs scénarios de dimensionnement pour maximiser l'autoconsommation,
- calcule les métriques économiques (CAPEX, économies annuelles, retour sur investissement, VAN).
"""

from __future__ import annotations

import argparse
import csv
import logging
import json
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

TS_FORMAT = "%d.%m.%Y %H:%M:%S"
MONTHS_FR = {
    1: "janvier",
    2: "fevrier",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "aout",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "decembre",
}
SLOTS = ("22h-6h", "6h-9h", "9h-16h", "16h-22h")
DAY_TYPES = ("semaine", "weekend")
ORIENTATIONS = ("north", "south", "east", "west")
SLOT_EXPECTED_HOURS = {
    "22h-6h": 8,
    "6h-9h": 3,
    "9h-16h": 7,
    "16h-22h": 6,
}

# Hypothèse standard 2026 (canton de Vaud): production journalière moyenne par kWp installé
# en kWh/kWp/jour, par mois (ordres de grandeur climatiques).
MONTHLY_DAILY_YIELD_KWH_PER_KWP = {
    1: 1.6,
    2: 2.5,
    3: 3.6,
    4: 4.7,
    5: 5.4,
    6: 5.9,
    7: 5.9,
    8: 5.3,
    9: 4.1,
    10: 2.9,
    11: 1.8,
    12: 1.4,
}

# Répartition horaire simplifiée de la production diurne (6h..19h). Somme = 84.
PV_HOURLY_WEIGHTS = {
    6: 1,
    7: 2,
    8: 4,
    9: 6,
    10: 8,
    11: 10,
    12: 11,
    13: 11,
    14: 10,
    15: 8,
    16: 6,
    17: 4,
    18: 2,
    19: 1,
}
PV_WEIGHT_SUM = sum(PV_HOURLY_WEIGHTS.values())
ORIENTATION_YIELD_FACTOR = {
    "north": 0.60,
    "south": 1.00,
    "east": 0.92,
    "west": 0.92,
}
# Décalage du profil sud "de référence" pour approximer un pic plus matinal (est)
# ou plus tardif (ouest). Un décalage positif interroge un poids plus tardif du profil sud.
ORIENTATION_LOOKUP_SHIFT = {
    "north": 0,
    "south": 0,
    "east": 2,
    "west": -2,
}
PANEL_REMOVAL_ORDER = ("north", "east", "west", "south")

# Inclinaison du toit (degres). 50 degres correspond a une pente relativement forte.
DEFAULT_ROOF_TILT_DEG: float = 50.0
# Inclinaison de reference simplifiee (production max) pour la Suisse romande.
REFERENCE_OPTIMAL_TILT_DEG: float = 35.0

# === Paramètres économiques (marché vaudois, Suisse, 2026) ===
# Sources : devis installateurs romands, tarifs VD-L Romande Énergie, Pronovo 2026.
# Prix achat réseau tout compris (réseau + énergie + taxes VD, tarif ménage standard).
ELECTRICITY_PRICE_CHF_PER_KWH: float = 0.29
# Prix de reprise énergie injectée (rétribution au prix du marché, Pronovo/swissgrid 2026).
BUYBACK_PRICE_CHF_PER_KWH: float = 0.06
# Subvention Pronovo supposée par kWp installé.
PRONOVO_SUBSIDY_CHF_PER_KWP: float = 360.0
# Déduction fiscale estimée sur la facture totale brute de l'installation.
TAX_DEDUCTION_RATE: float = 0.13
# Coût fixe installation PV (hors logistique chantier): onduleur string résidentiel, smart meter,
# raccordement réseau, compteur bidirectionnel, frais d'annonce/permis, câblage DC/AC, mise en service, contrôle final.
PV_FIXED_COST_CHF: float = 4_500.0
# Coût de mise en place chantier (échafaudage, protections, logistique accès toiture, système de levage).
# Ordre de grandeur vaudois 2026 pour maison individuelle: 3'500-6'000 CHF.
PV_SITE_SETUP_COST_CHF: float = 4_000.0
# Coût par panneau, pose incluse (module premium ~170-210 CHF +
# optimiseur/logistique/structure/montage/câblage/main d'oeuvre ~280-320 CHF) en contexte suisse.
PV_COST_PER_PANEL_CHF: float = 510.0
# Coût fixe batterie : BMS intégré, câblage AC/DC, mise en service.
BATTERY_FIXED_COST_CHF: float = 1_000.0
# Coût par kWh de capacité nominale installée (technologie LFP, marché romand 2026).
BATTERY_COST_PER_KWH_CHF: float = 275.0
# Répartiteur/EMS pour pilotage énergétique global bâtiment
# (PAC chauffage, gros consommateurs, recharge véhicule électrique, etc.).
ENERGY_MANAGER_FIXED_COST_CHF: float = 2_500.0
# Horizon d'analyse / durée de vie estimée du système (ans).
ANALYSIS_YEARS: int = 25
# Taux d'actualisation annuel (réel, inflation déduite).
DISCOUNT_RATE: float = 0.03
# Rendement annuel de référence pour un placement alternatif en fonds d'investissement.
FUND_RETURN_RATE: float = 0.03
# Hypothèse de maintenance annuelle: pourcentage du CAPEX brut (avant réductions).
ANNUAL_MAINTENANCE_RATE: float = 0.01


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QuarterRecord:
    ts: datetime
    kwh: float


@dataclass(frozen=True)
class HourRecord:
    ts_hour: datetime
    month: int
    day_type: str
    slot: str
    kwh: float


@dataclass(frozen=True)
class PvSystemConfig:
    name: str
    orientation_panels: dict[str, int]
    orientation_kwp: dict[str, float]

    @property
    def total_panels(self) -> int:
        return sum(self.orientation_panels.values())

    @property
    def total_kwp(self) -> float:
        return sum(self.orientation_kwp.values())

    @property
    def effective_kwp(self) -> float:
        """Puissance equivalente sud, ponderee par les facteurs d'orientation."""
        return sum(
            kwp * ORIENTATION_YIELD_FACTOR.get(orientation, 1.0)
            for orientation, kwp in self.orientation_kwp.items()
        )

    def orientation_summary(self) -> str:
        parts: list[str] = []
        labels = {"north": "N", "south": "S", "east": "E", "west": "O"}
        for orientation in ORIENTATIONS:
            panels = self.orientation_panels.get(orientation, 0)
            if panels > 0:
                parts.append(f"{labels[orientation]}={panels}")
        return ", ".join(parts) if parts else "equivalent sud"


def classify_slot(hour: int) -> str:
    if hour >= 22 or hour < 6:
        return "22h-6h"
    if 6 <= hour < 9:
        return "6h-9h"
    if 9 <= hour < 16:
        return "9h-16h"
    return "16h-22h"


def classify_day_type(ts: datetime) -> str:
    return "semaine" if ts.weekday() < 5 else "weekend"


def slot_anchor_ts(ts: datetime) -> datetime:
    # La tranche 22h-6h est rattachée au jour de début de plage (22h).
    if ts.hour < 6:
        return ts - timedelta(days=1)
    return ts


def parse_float(value: str) -> float:
    return float(value.strip().replace(",", "."))


def parse_non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("la valeur doit etre un entier >= 0")
    return parsed


def parse_tilt_deg(value: str) -> float:
    parsed = float(value)
    if not (0.0 <= parsed <= 90.0):
        raise argparse.ArgumentTypeError("l'inclinaison du toit doit etre comprise entre 0 et 90 degres")
    return parsed


def parse_csv(input_csv: Path) -> list[QuarterRecord]:
    records: list[QuarterRecord] = []
    with input_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader, None)
        if not header or len(header) < 2:
            raise ValueError("En-tete CSV invalide (2 colonnes attendues)")

        for idx, row in enumerate(reader, start=2):
            if not row or len(row) < 2:
                continue
            raw_ts = row[0].strip()
            raw_kwh = row[1].strip()
            if not raw_ts or not raw_kwh:
                continue
            try:
                ts = datetime.strptime(raw_ts, TS_FORMAT)
                kwh = parse_float(raw_kwh)
            except Exception as exc:  # pragma: no cover - garde robuste
                raise ValueError(f"Ligne CSV invalide {idx}: {row}") from exc
            records.append(QuarterRecord(ts=ts, kwh=kwh))

    records.sort(key=lambda r: r.ts)
    if not records:
        raise ValueError("Aucune donnee lisible dans le CSV")
    return records


def build_hourly_records(quarter_records: Iterable[QuarterRecord]) -> list[HourRecord]:
    hourly: dict[datetime, float] = defaultdict(float)
    for rec in quarter_records:
        hour_ts = rec.ts.replace(minute=0, second=0, microsecond=0)
        hourly[hour_ts] += rec.kwh

    out: list[HourRecord] = []
    for ts_hour, kwh in sorted(hourly.items(), key=lambda item: item[0]):
        anchor = slot_anchor_ts(ts_hour)
        out.append(
            HourRecord(
                ts_hour=ts_hour,
                month=anchor.month,
                day_type=classify_day_type(anchor),
                slot=classify_slot(ts_hour.hour),
                kwh=kwh,
            )
        )
    return out


def compute_month_completeness(quarter_records: Iterable[QuarterRecord]) -> dict[int, dict[str, int]]:
    counts_by_day: dict[tuple[int, date], int] = defaultdict(int)
    for rec in quarter_records:
        counts_by_day[(rec.ts.month, rec.ts.date())] += 1

    per_month: dict[int, dict[str, int]] = {m: {"days_total": 0, "days_complete": 0} for m in range(1, 13)}
    for (month, _day), count in counts_by_day.items():
        per_month[month]["days_total"] += 1
        if count >= 96:
            per_month[month]["days_complete"] += 1
    return per_month


def median_or_none(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def min_or_none(values: list[float]) -> float | None:
    return min(values) if values else None


def max_or_none(values: list[float]) -> float | None:
    return max(values) if values else None


def compute_consumption_stats(
    quarter_records: list[QuarterRecord],
    hour_records: list[HourRecord],
) -> list[dict[str, Any]]:
    hourly_values: dict[tuple[int, str, str], list[float]] = defaultdict(list)
    daily_slot_totals: dict[tuple[int, str, str, date], float] = defaultdict(float)
    daily_slot_hours: dict[tuple[int, str, str, date], int] = defaultdict(int)
    quarter_peak_kw: dict[tuple[int, str, str], list[float]] = defaultdict(list)

    for hr in hour_records:
        gk = (hr.month, hr.day_type, hr.slot)
        hourly_values[gk].append(hr.kwh)
        daily_key = (hr.month, hr.day_type, hr.slot, slot_anchor_ts(hr.ts_hour).date())
        daily_slot_totals[daily_key] += hr.kwh
        daily_slot_hours[daily_key] += 1

    for rec in quarter_records:
        anchor = slot_anchor_ts(rec.ts)
        gk = (anchor.month, classify_day_type(anchor), classify_slot(rec.ts.hour))
        quarter_peak_kw[gk].append(rec.kwh * 4.0)

    out: list[dict[str, Any]] = []
    for month in range(1, 13):
        for day_type in DAY_TYPES:
            for slot in SLOTS:
                gk = (month, day_type, slot)
                hourly = hourly_values.get(gk, [])
                daily = [
                    v
                    for (m, d_type, s, _day), v in daily_slot_totals.items()
                    if (m, d_type, s) == gk
                    and daily_slot_hours[(m, d_type, s, _day)] == SLOT_EXPECTED_HOURS[s]
                ]
                peaks = quarter_peak_kw.get(gk, [])

                out.append(
                    {
                        "month": month,
                        "month_name": MONTHS_FR[month],
                        "day_type": day_type,
                        "slot": slot,
                        "hours_count": len(hourly),
                        "days_count": len(daily),
                        "hourly_floor_kwh": min_or_none(hourly),
                        "hourly_ceiling_kwh": max_or_none(hourly),
                        "daily_slot_total_min_kwh": min_or_none(daily),
                        "daily_slot_total_median_kwh": median_or_none(daily),
                        "daily_slot_total_max_kwh": max_or_none(daily),
                        "peak_power_kw_max": max_or_none(peaks),
                        "peak_power_kw_median": median_or_none(peaks),
                    }
                )
    return out


def orientation_hour_weight(hour: int, orientation: str) -> int:
    shift = ORIENTATION_LOOKUP_SHIFT[orientation]
    reference_hour = hour + shift
    return PV_HOURLY_WEIGHTS.get(reference_hour, 0)


def orientation_weight_sum(orientation: str) -> int:
    return sum(orientation_hour_weight(hour, orientation) for hour in range(24))


def roof_tilt_yield_factor(roof_tilt_deg: float) -> float:
    # Correction simplifiee: penalite progressive selon l'ecart a l'inclinaison de reference.
    delta = abs(roof_tilt_deg - REFERENCE_OPTIMAL_TILT_DEG)
    return max(0.2, math.cos(math.radians(delta)))


def pv_kwh_per_kwp_quarter(
    ts: datetime,
    orientation: str = "south",
    roof_tilt_deg: float = DEFAULT_ROOF_TILT_DEG,
) -> float:
    daily_yield = (
        MONTHLY_DAILY_YIELD_KWH_PER_KWP[ts.month]
        * ORIENTATION_YIELD_FACTOR[orientation]
        * roof_tilt_yield_factor(roof_tilt_deg)
    )
    hour_weight = orientation_hour_weight(ts.hour, orientation)
    if hour_weight == 0:
        return 0.0
    weight_sum = orientation_weight_sum(orientation)
    hourly_yield = daily_yield * hour_weight / weight_sum
    return hourly_yield / 4.0


def build_panel_counts(north: int, south: int, east: int, west: int) -> dict[str, int]:
    return {
        "north": north,
        "south": south,
        "east": east,
        "west": west,
    }


def build_layout_pv_config(panel_counts: dict[str, int], panel_watt_peak: float) -> PvSystemConfig:
    orientation_kwp = {
        orientation: panels * panel_watt_peak / 1000.0
        for orientation, panels in panel_counts.items()
        if panels > 0
    }
    orientation_panels = {orientation: panel_counts.get(orientation, 0) for orientation in ORIENTATIONS}
    return PvSystemConfig(
        name="layout_toiture",
        orientation_panels=orientation_panels,
        orientation_kwp=orientation_kwp,
    )


def make_panel_variant_name(panel_counts: dict[str, int]) -> str:
    return (
        f"N{panel_counts.get('north', 0)}_"
        f"S{panel_counts.get('south', 0)}_"
        f"E{panel_counts.get('east', 0)}_"
        f"O{panel_counts.get('west', 0)}"
    )


def build_panel_count_variants(
    panel_counts: dict[str, int],
    min_total_panels: int,
) -> list[dict[str, int]]:
    total_installable_panels = sum(panel_counts.values())
    if total_installable_panels <= 0:
        return []

    min_target = max(1, min(min_total_panels, total_installable_panels))
    current = {orientation: int(panel_counts.get(orientation, 0)) for orientation in ORIENTATIONS}
    variants: list[dict[str, int]] = []

    while True:
        current_total = sum(current.values())
        if current_total < min_target:
            break
        variants.append(dict(current))
        if current_total == min_target:
            break

        for orientation in PANEL_REMOVAL_ORDER:
            if current.get(orientation, 0) > 0:
                current[orientation] -= 1
                break
        else:
            break

    return variants


def build_legacy_pv_config(pv_kwp: float, panel_watt_peak: float) -> PvSystemConfig:
    approx_panels = math.ceil((pv_kwp * 1000.0) / panel_watt_peak) if pv_kwp > 0 else 0
    return PvSystemConfig(
        name=f"pv_{pv_kwp:.2f}_kwp",
        orientation_panels={"north": 0, "south": approx_panels, "east": 0, "west": 0},
        orientation_kwp={"south": pv_kwp} if pv_kwp > 0 else {},
    )


def build_pv_configs(
    pv_kwp_values: list[float],
    panel_counts: dict[str, int],
    panel_watt_peak: float,
    min_total_panels: int,
) -> tuple[list[PvSystemConfig], str]:
    total_installable_panels = sum(panel_counts.values())
    if total_installable_panels > 0:
        panel_variants = build_panel_count_variants(panel_counts, min_total_panels=min_total_panels)
        pv_variants = []
        for variant in panel_variants:
            config = build_layout_pv_config(variant, panel_watt_peak)
            pv_variants.append(
                PvSystemConfig(
                    name=f"layout_{make_panel_variant_name(variant)}",
                    orientation_panels=config.orientation_panels,
                    orientation_kwp=config.orientation_kwp,
                )
            )
        return pv_variants, "panel_variants"
    return [build_legacy_pv_config(pv_kwp, panel_watt_peak) for pv_kwp in pv_kwp_values], "pv_kwp_list"


def print_progress(current: int, total: int, prefix: str = "Simulation") -> None:
    if total <= 0:
        return
    width = 28
    ratio = max(0.0, min(1.0, current / total))
    filled = int(ratio * width)
    bar = "#" * filled + "-" * (width - filled)
    sys.stdout.write(f"\r{prefix}: [{bar}] {current}/{total} ({ratio * 100:5.1f}%)")
    if current >= total:
        sys.stdout.write("\n")
    sys.stdout.flush()


def pv_system_kwh_quarter(
    ts: datetime,
    pv_config: PvSystemConfig,
    roof_tilt_deg: float = DEFAULT_ROOF_TILT_DEG,
) -> float:
    total = 0.0
    for orientation, kwp in pv_config.orientation_kwp.items():
        total += kwp * pv_kwh_per_kwp_quarter(ts, orientation, roof_tilt_deg=roof_tilt_deg)
    return total


def build_pv_generation_series(
    quarter_records: list[QuarterRecord],
    pv_config: PvSystemConfig,
    roof_tilt_deg: float,
) -> list[float]:
    """Pré-calcule la production PV quart-horaire pour une configuration donnée."""
    return [
        pv_system_kwh_quarter(rec.ts, pv_config, roof_tilt_deg=roof_tilt_deg)
        for rec in quarter_records
    ]


def parse_float_list(csv_values: str) -> list[float]:
    values: list[float] = []
    for chunk in csv_values.split(","):
        val = chunk.strip()
        if not val:
            continue
        values.append(float(val))
    if not values:
        raise ValueError("Liste de valeurs vide")
    return sorted(set(values))


def simulate_scenario(
    quarter_records: list[QuarterRecord],
    pv_config: PvSystemConfig,
    battery_kwh: float,
    battery_dod: float,
    battery_roundtrip_efficiency: float,
    roof_tilt_deg: float = DEFAULT_ROOF_TILT_DEG,
    electricity_price: float = ELECTRICITY_PRICE_CHF_PER_KWH,
    buyback_price: float = BUYBACK_PRICE_CHF_PER_KWH,
    pv_fixed_cost: float = PV_FIXED_COST_CHF,
    pv_site_setup_cost: float = PV_SITE_SETUP_COST_CHF,
    pv_cost_per_panel: float = PV_COST_PER_PANEL_CHF,
    battery_fixed_cost: float = BATTERY_FIXED_COST_CHF,
    battery_cost_per_kwh: float = BATTERY_COST_PER_KWH_CHF,
    energy_manager_enabled: bool = False,
    energy_manager_fixed_cost: float = ENERGY_MANAGER_FIXED_COST_CHF,
    pronovo_subsidy_chf_per_kwp: float = PRONOVO_SUBSIDY_CHF_PER_KWP,
    tax_deduction_rate: float = TAX_DEDUCTION_RATE,
    analysis_years: int = ANALYSIS_YEARS,
    discount_rate: float = DISCOUNT_RATE,
    fund_return_rate: float = FUND_RETURN_RATE,
    annual_maintenance_rate: float = ANNUAL_MAINTENANCE_RATE,
    pv_generation_series: list[float] | None = None,
) -> dict[str, Any]:
    if not (0 < battery_dod <= 1):
        raise ValueError("battery_dod doit etre dans ]0,1]")
    if not (0 < battery_roundtrip_efficiency <= 1):
        raise ValueError("battery_roundtrip_efficiency doit etre dans ]0,1]")
    if pronovo_subsidy_chf_per_kwp < 0:
        raise ValueError("pronovo_subsidy_chf_per_kwp doit etre >= 0")
    if not (0 <= tax_deduction_rate <= 1):
        raise ValueError("tax_deduction_rate doit etre dans [0,1]")
    if not (0 <= annual_maintenance_rate <= 1):
        raise ValueError("annual_maintenance_rate doit etre dans [0,1]")

    charge_eff = math.sqrt(battery_roundtrip_efficiency)
    discharge_eff = math.sqrt(battery_roundtrip_efficiency)

    battery_usable_kwh = battery_kwh * battery_dod
    soc = battery_usable_kwh * 0.5

    total_load = 0.0
    total_pv = 0.0
    direct_self = 0.0
    battery_to_load_total = 0.0
    grid_import = 0.0
    grid_export = 0.0

    if pv_generation_series is not None and len(pv_generation_series) != len(quarter_records):
        raise ValueError("pv_generation_series doit avoir la meme longueur que quarter_records")

    for idx, rec in enumerate(quarter_records):
        load = rec.kwh
        pv = pv_generation_series[idx] if pv_generation_series is not None else pv_system_kwh_quarter(
            rec.ts,
            pv_config,
            roof_tilt_deg=roof_tilt_deg,
        )

        total_load += load
        total_pv += pv

        direct = min(load, pv)
        direct_self += direct

        excess = max(0.0, pv - load)
        deficit = max(0.0, load - pv)

        if battery_usable_kwh > 0 and excess > 0:
            max_store = battery_usable_kwh - soc
            stored = min(max_store, excess * charge_eff)
            energy_used_to_charge = stored / charge_eff if charge_eff > 0 else 0.0
            soc += stored
            excess -= energy_used_to_charge

        grid_export += max(0.0, excess)

        if battery_usable_kwh > 0 and deficit > 0:
            max_deliverable = soc * discharge_eff
            delivered = min(deficit, max_deliverable)
            battery_to_load_total += delivered
            soc -= delivered / discharge_eff if discharge_eff > 0 else 0.0
            deficit -= delivered

        grid_import += max(0.0, deficit)

    pv_used_on_site = direct_self + battery_to_load_total
    auto_consumption_rate = (pv_used_on_site / total_pv) if total_pv > 0 else 0.0
    self_sufficiency_rate = (pv_used_on_site / total_load) if total_load > 0 else 0.0

    # === Facteur d'annualisation ===
    # Les données couvrent potentiellement plusieurs années: on normalise à 1 an.
    ts_min = quarter_records[0].ts
    ts_max = quarter_records[-1].ts
    data_days = max(1.0, (ts_max - ts_min).total_seconds() / 86_400.0)
    annualization = 365.25 / data_days

    # === Calculs économiques ===
    # CAPEX: coût total d'installation (PV + batterie).
    # Coût fixe PV toujours présent dès qu'on installe des panneaux.
    capex_pv = pv_fixed_cost + pv_site_setup_cost + pv_config.total_panels * pv_cost_per_panel
    # Coût fixe batterie seulement si une batterie est installée.
    capex_battery = (battery_fixed_cost + battery_kwh * battery_cost_per_kwh) if battery_kwh > 0 else 0.0
    # Le repartiteur/EMS n'est facture que si la variante EMS est activee.
    capex_energy_manager = energy_manager_fixed_cost if energy_manager_enabled else 0.0
    capex_total_before_reductions = capex_pv + capex_battery + capex_energy_manager
    pronovo_subsidy = pv_config.total_kwp * pronovo_subsidy_chf_per_kwp if pv_config.total_kwp > 0 else 0.0
    tax_deduction = capex_total_before_reductions * tax_deduction_rate
    capex_total_reductions = pronovo_subsidy + tax_deduction
    capex_total = max(0.0, capex_total_before_reductions - capex_total_reductions)
    annual_maintenance_cost = capex_total_before_reductions * annual_maintenance_rate
    maintenance_cost_total = annual_maintenance_cost * analysis_years

    # Facturation de base (100 % réseau, sans PV) pour calculer les économies relatives.
    baseline_cost_period = total_load * electricity_price
    baseline_cost_annual = baseline_cost_period * annualization

    # Coûts annuels avec PV : import réduit − revenus d'injection.
    import_cost_annual = grid_import * electricity_price * annualization
    export_revenue_annual = grid_export * buyback_price * annualization

    # Économies nettes annuelles = référence − (import avec PV − revenu injection).
    annual_net_savings = baseline_cost_annual - import_cost_annual + export_revenue_annual

    # Délai de retour simple (payback) en années.
    payback_years = (capex_total / annual_net_savings) if annual_net_savings > 0 else float("inf")

    # Valeur actuelle nette (VAN) sur l'horizon d'analyse.
    # annuity_factor = (1 - (1+r)^-N) / r  pour r > 0
    if discount_rate > 0:
        annuity_factor = (1.0 - (1.0 + discount_rate) ** (-analysis_years)) / discount_rate
    else:
        annuity_factor = float(analysis_years)
    npv = -capex_total + annual_net_savings * annuity_factor

    # Comparaison avec le coût d'opportunité: investir le capital initial dans un fonds.
    if fund_return_rate > 0:
        fund_future_value = capex_total * ((1.0 + fund_return_rate) ** analysis_years)
        pv_savings_future_value = annual_net_savings * (((1.0 + fund_return_rate) ** analysis_years - 1.0) / fund_return_rate)
    else:
        fund_future_value = capex_total
        pv_savings_future_value = annual_net_savings * analysis_years
    opportunity_delta = pv_savings_future_value - fund_future_value

    return {
        "pv_kwp": pv_config.total_kwp,
        "pv_effective_kwp": pv_config.effective_kwp,
        "pv_config_name": pv_config.name,
        "pv_total_panels": pv_config.total_panels,
        "pv_orientation_summary": pv_config.orientation_summary(),
        "roof_tilt_deg": roof_tilt_deg,
        "pv_panels_north": pv_config.orientation_panels.get("north", 0),
        "pv_panels_south": pv_config.orientation_panels.get("south", 0),
        "pv_panels_east": pv_config.orientation_panels.get("east", 0),
        "pv_panels_west": pv_config.orientation_panels.get("west", 0),
        "battery_kwh": battery_kwh,
        "battery_usable_kwh": battery_usable_kwh,
        "energy_manager_enabled": energy_manager_enabled,
        "total_load_kwh": total_load,
        "total_pv_kwh": total_pv,
        "pv_used_on_site_kwh": pv_used_on_site,
        "direct_self_kwh": direct_self,
        "battery_to_load_kwh": battery_to_load_total,
        "grid_import_kwh": grid_import,
        "grid_export_kwh": grid_export,
        "auto_consumption_rate": auto_consumption_rate,
        "self_sufficiency_rate": self_sufficiency_rate,
        "data_days": data_days,
        "annualization_factor": annualization,
        "capex_pv_chf": capex_pv,
        "capex_pv_site_setup_chf": pv_site_setup_cost,
        "capex_battery_chf": capex_battery,
        "capex_energy_manager_chf": capex_energy_manager,
        "capex_before_reductions_chf": capex_total_before_reductions,
        "pronovo_subsidy_chf": pronovo_subsidy,
        "tax_deduction_chf": tax_deduction,
        "capex_total_reductions_chf": capex_total_reductions,
        "capex_after_reductions_chf": capex_total,
        "capex_total_chf": capex_total,
        "initial_investment_chf": capex_total_before_reductions,
        "annual_maintenance_cost_chf": annual_maintenance_cost,
        "maintenance_cost_total_chf": maintenance_cost_total,
        "baseline_cost_annual_chf": baseline_cost_annual,
        "import_cost_annual_chf": import_cost_annual,
        "export_revenue_annual_chf": export_revenue_annual,
        "annual_net_savings_chf": annual_net_savings,
        "payback_years": payback_years,
        "npv_chf": npv,
        "fund_return_rate": fund_return_rate,
        "fund_future_value_chf": fund_future_value,
        "pv_savings_future_value_chf": pv_savings_future_value,
        "opportunity_delta_vs_fund_chf": opportunity_delta,
    }


def rank_scenarios(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(item: dict[str, Any]) -> tuple[float, float, float, float]:
        return (
            item["self_sufficiency_rate"],
            item["auto_consumption_rate"],
            -item["grid_import_kwh"],
            -(item["pv_kwp"] + item["battery_kwh"]),
        )

    return sorted(results, key=sort_key, reverse=True)


def _payback_sort_value(scenario: dict[str, Any]) -> float:
    payback = float(scenario.get("payback_years", float("inf")))
    return payback if math.isfinite(payback) else float("inf")


def rank_scenarios_for_profile(results: list[dict[str, Any]], profile: str) -> list[dict[str, Any]]:
    if profile == "autonomy":
        # Autonomiste: autonomie (self-sufficiency) puis VAN.
        return sorted(
            results,
            key=lambda s: (
                -float(s.get("self_sufficiency_rate", 0.0)),
                -float(s.get("npv_chf", float("-inf"))),
                _payback_sort_value(s),
            ),
        )

    if profile == "financial":
        # Financier: VAN + capital puis payback.
        return sorted(
            results,
            key=lambda s: (
                -float(s.get("npv_plus_capital_chf", s.get("npv_chf", float("-inf")))),
                _payback_sort_value(s),
                -float(s.get("self_sufficiency_rate", 0.0)),
            ),
        )

    if profile == "ecological":
        # Ecologiste: payback puis VAN.
        return sorted(
            results,
            key=lambda s: (
                _payback_sort_value(s),
                -float(s.get("npv_chf", float("-inf"))),
                -float(s.get("self_sufficiency_rate", 0.0)),
            ),
        )

    raise ValueError(f"Profil inconnu: {profile}")


def find_best_scenarios(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not results:
        return {}

    return {
        "autonomy": rank_scenarios_for_profile(results, "autonomy")[0],
        "financial": rank_scenarios_for_profile(results, "financial")[0],
        "ecological": rank_scenarios_for_profile(results, "ecological")[0],
    }


def build_profile_variant_lists(
    results: list[dict[str, Any]],
    n_below_optimum: int,
) -> dict[str, list[dict[str, Any]]]:
    def add_if_present(
        target: list[dict[str, Any]],
        seen: set[int],
        candidate: dict[str, Any] | None,
        reason: str,
    ) -> None:
        if candidate is None:
            return
        cid = id(candidate)
        if cid in seen:
            return
        enriched = dict(candidate)
        enriched["selection_reason"] = reason
        target.append(enriched)
        seen.add(cid)

    out: dict[str, list[dict[str, Any]]] = {}
    for profile in ("autonomy", "financial", "ecological"):
        ranked = rank_scenarios_for_profile(results, profile)
        if not ranked:
            out[profile] = []
            continue

        selected: list[dict[str, Any]] = []
        seen: set[int] = set()

        optimum = ranked[0]
        add_if_present(selected, seen, optimum, "optimum")

        best_bat_no_ems = next((s for s in ranked if s.get("battery_kwh", 0.0) > 0 and not s.get("energy_manager_enabled", False)), None)
        best_bat_with_ems = next((s for s in ranked if s.get("battery_kwh", 0.0) > 0 and s.get("energy_manager_enabled", False)), None)
        best_no_bat_no_ems = next((s for s in ranked if s.get("battery_kwh", 0.0) <= 0 and not s.get("energy_manager_enabled", False)), None)

        add_if_present(selected, seen, best_bat_no_ems, "meilleure batterie sans EMS")
        add_if_present(selected, seen, best_bat_with_ems, "meilleure batterie avec EMS")
        add_if_present(selected, seen, best_no_bat_no_ems, "meilleure sans batterie")

        # N solutions juste sous l'optimum (en ordre de classement du profil).
        below_added = 0
        for candidate in ranked[1:]:
            if below_added >= n_below_optimum:
                break
            cid = id(candidate)
            if cid in seen:
                continue
            enriched = dict(candidate)
            enriched["selection_reason"] = "alternative sous optimum"
            selected.append(enriched)
            seen.add(cid)
            below_added += 1

        # Restitution triee selon le profil (et non selon l'ordre d'ajout des types).
        out[profile] = rank_scenarios_for_profile(selected, profile)

    return out


def fmt(value: float | int | None, ndigits: int = 3) -> str:
    if value is None:
        return "-"
    if isinstance(value, int):
        return str(value)
    return f"{value:.{ndigits}f}"


def to_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.1f}%"


def enrich_scenarios_with_capital_value(
    scenarios: list[dict[str, Any]],
    analysis_years: int = ANALYSIS_YEARS,
    fund_return_rate: float = FUND_RETURN_RATE,
) -> list[dict[str, Any]]:
    """Enrich scenarios with capital non-dépensé and VAN + capital values."""
    if not scenarios:
        return scenarios
    
    # Find max CAPEX across all scenarios
    max_capex = max(float(s.get("capex_total_chf", 0.0)) for s in scenarios)
    
    # Add the computed values to each scenario
    enriched = []
    for scenario in scenarios:
        s = dict(scenario)  # Create a copy
        capex_current = float(s.get("capex_total_chf", 0.0))
        
        # Capital non-dépensé: (max_capex - capex_current) * (1 + fund_return_rate)^analysis_years
        capital_not_spent = (max_capex - capex_current) * ((1.0 + fund_return_rate) ** analysis_years)
        
        # VAN + capital non-dépensé
        npv = float(s.get("npv_chf", 0.0))
        npv_plus_capital = npv + capital_not_spent
        
        s["capital_not_spent_value_chf"] = capital_not_spent
        s["npv_plus_capital_chf"] = npv_plus_capital
        enriched.append(s)
    
    return enriched


def build_markdown_report(
     input_csv: Path,
     output_md: Path,
     consumption_stats: list[dict[str, Any]],
     month_completeness: dict[int, dict[str, int]],
     scenarios_ranked: list[dict[str, Any]],
     panel_watt_peak: float,
     roof_tilt_deg: float,
     battery_dod: float,
     battery_roundtrip_efficiency: float,
     top_n_scenarios: int,
     pv_mode: str,
     panel_limits: dict[str, int] | None = None,
     pv_variant_count: int | None = None,
     best_scenarios: dict[str, dict[str, Any]] | None = None,
     profile_variant_lists: dict[str, list[dict[str, Any]]] | None = None,
     n_below_optimum: int = 3,
     electricity_price: float = ELECTRICITY_PRICE_CHF_PER_KWH,
     buyback_price: float = BUYBACK_PRICE_CHF_PER_KWH,
     pv_fixed_cost: float = PV_FIXED_COST_CHF,
     pv_site_setup_cost: float = PV_SITE_SETUP_COST_CHF,
     pv_cost_per_panel: float = PV_COST_PER_PANEL_CHF,
     battery_fixed_cost: float = BATTERY_FIXED_COST_CHF,
     battery_cost_per_kwh: float = BATTERY_COST_PER_KWH_CHF,
     energy_manager_fixed_cost: float = ENERGY_MANAGER_FIXED_COST_CHF,
     pronovo_subsidy_chf_per_kwp: float = PRONOVO_SUBSIDY_CHF_PER_KWP,
     tax_deduction_rate: float = TAX_DEDUCTION_RATE,
     analysis_years: int = ANALYSIS_YEARS,
     discount_rate: float = DISCOUNT_RATE,
     fund_return_rate: float = FUND_RETURN_RATE,
     annual_maintenance_rate: float = ANNUAL_MAINTENANCE_RATE,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d")
    best = scenarios_ranked[0] if scenarios_ranked else None

    lines: list[str] = []
    lines.append("---")
    lines.append("title: Analyse consommation electrique et dimensionnement PV+batterie")
    lines.append(f"date: {now}")
    lines.append("author: corpus-lens")
    lines.append(f"source_csv: {input_csv.as_posix()}")
    lines.append("---")
    lines.append("")
    lines.append("## Hypotheses techniques")
    lines.append("")
    lines.append("- Production PV standardisee Vaud, profil mensuel simplifie (kWh/kWp/jour).")
    lines.append("- Profil intrajournalier PV simplifie sur la plage 6h-19h (pas de meteo reelle, pas d'ombrage).")
    lines.append(
        f"- Inclinaison du toit: {roof_tilt_deg:.1f} degres (correction simplifiee autour d'une reference a {REFERENCE_OPTIMAL_TILT_DEG:.0f} degres)."
    )
    lines.append(f"- Batterie: DOD={battery_dod:.2f}, rendement aller-retour={battery_roundtrip_efficiency:.2f}.")
    lines.append(f"- Puissance nominale par panneau: {panel_watt_peak:.0f} Wc (gamme standard 2026).")
    lines.append("- Facteurs d'orientation PV standards: sud=1.00, est=0.92, ouest=0.92, nord=0.60.")
    lines.append("- kWp effectif = puissance equivalente sud, ponderee par ces facteurs d'orientation.")
    lines.append("")
    lines.append("## Hypotheses economiques (marche vaudois, Suisse, 2026)")
    lines.append("")
    lines.append(f"| Parametre | Valeur | Source / note |")
    lines.append("|---|---:|---|")
    lines.append(f"| Prix achat reseau | {electricity_price * 100:.1f} ct/kWh | Tarif VD-L Romande Energie tout compris (reseau + energie + taxes) |")
    lines.append(f"| Prix reprise injection | {buyback_price * 100:.1f} ct/kWh | Retribution au prix du marche (Pronovo/swissgrid 2026) |")
    lines.append(f"| Coût fixe installation PV | {pv_fixed_cost:.0f} CHF | Onduleur, raccordement reseau, compteur bidirectionnel, admin/permis |")
    lines.append(f"| Coût mise en place chantier (echafaudage) | {pv_site_setup_cost:.0f} CHF | Echafaudage, protections et logistique d'acces toiture |")
    lines.append(f"| Coût par panneau | {pv_cost_per_panel:.0f} CHF | Module premium (~170-210 CHF) + structure/montage/cablage/part variable MO (~280-320 CHF) |")
    lines.append(f"| Coût fixe batterie | {battery_fixed_cost:.0f} CHF | BMS integre, cablage AC/DC, mise en service |")
    lines.append(f"| Coût par kWh capacite batterie | {battery_cost_per_kwh:.0f} CHF/kWh | Technologie LFP installee, marche romand 2026 |")
    lines.append(f"| Coût fixe repartiteur/EMS batiment | {energy_manager_fixed_cost:.0f} CHF | Pilotage PAC, gros consommateurs et recharge VE |")
    lines.append(f"| Subvention Pronovo | {pronovo_subsidy_chf_per_kwp:.0f} CHF/kWp | Deduite du CAPEX brut selon la puissance PV installee |")
    lines.append(f"| Deduction d'impot | {tax_deduction_rate * 100:.1f} % de la facture | Estimation deduite du CAPEX brut pour le CAPEX net |")
    lines.append(f"| Horizon d'analyse | {analysis_years} ans | Duree de vie estimee du systeme |")
    lines.append(f"| Taux d'actualisation | {discount_rate * 100:.1f} % | Taux reel (inflation deduite) |")
    lines.append(f"| Rendement fonds alternatif | {fund_return_rate * 100:.1f} %/an | Hypothese de comparaison (coût d'opportunite du capital) |")
    lines.append(f"| Maintenance annuelle | {annual_maintenance_rate * 100:.1f} % du CAPEX brut/an | Hypothese pour le cout de maintenance cumule sur {analysis_years} ans |")
    lines.append("")

    lines.append("## Configuration PV prise en compte")
    lines.append("")
    if best is None:
        lines.append("Aucune configuration PV n'a pu etre calculee.")
    elif pv_mode in ("panel_layout", "panel_variants"):
        limits = panel_limits or {
            "north": best["pv_panels_north"],
            "south": best["pv_panels_south"],
            "east": best["pv_panels_east"],
            "west": best["pv_panels_west"],
        }
        lines.append(
            f"- Panneaux installables fournis: **N={limits.get('north', 0)} ; S={limits.get('south', 0)} ; "
            f"E={limits.get('east', 0)} ; O={limits.get('west', 0)}**."
        )
        if pv_variant_count is not None:
            lines.append(f"- Variantes PV testees (reduction panneau par panneau): **{pv_variant_count}**.")
        lines.append(f"- Exemple de configuration retenue dans les resultats: **{best['pv_total_panels']} panneaux ({best['pv_kwp']:.2f} kWp)**.")
    lines.append("")

    lines.append("## Qualite et couverture des donnees")
    lines.append("")
    lines.append("| Mois | Jours observes | Jours complets (96 quarts) |")
    lines.append("|---|---:|---:|")
    for m in range(1, 13):
        meta = month_completeness[m]
        lines.append(f"| {MONTHS_FR[m]} | {meta['days_total']} | {meta['days_complete']} |")
    lines.append("")

    lines.append("## Consommation horaire par mois, plage et type de jour")
    lines.append("")
    lines.append(
        "| Mois | Type jour | Plage | Jours | Plancher horaire (kWh/h) | "
        "Plafond horaire (kWh/h) | Pic puissance max (kW) | "
        "Total plage/jour min (kWh) | mediane (kWh) | max (kWh) |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|")

    for row in consumption_stats:
        lines.append(
            "| "
            f"{row['month_name']} | {row['day_type']} | {row['slot']} | {row['days_count']} | "
            f"{fmt(row['hourly_floor_kwh'])} | {fmt(row['hourly_ceiling_kwh'])} | "
            f"{fmt(row['peak_power_kw_max'])} | "
            f"{fmt(row['daily_slot_total_min_kwh'])} | {fmt(row['daily_slot_total_median_kwh'])} | "
            f"{fmt(row['daily_slot_total_max_kwh'])} |"
        )

    lines.append("")
    lines.append("## Scenarios PV+batterie (classement energetique)")
    lines.append("")
    lines.append(
        "| Rang | EMS | PV (kWp) | PV effectif (kWp eq. sud) | Batterie (kWh) | Batterie utile (kWh) | "
        "Panneaux | Orientation | Autoconsommation PV | Couverture conso | Import reseau (kWh) | Export reseau (kWh) |"
    )
    lines.append("|---:|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|")

    for idx, row in enumerate(scenarios_ranked[:top_n_scenarios], start=1):
        lines.append(
            f"| {idx} | {'Oui' if row.get('energy_manager_enabled', False) else 'Non'} | {fmt(row['pv_kwp'], 2)} | {fmt(row['pv_effective_kwp'], 2)} | {fmt(row['battery_kwh'], 2)} | "
            f"{fmt(row['battery_usable_kwh'], 2)} | {row['pv_total_panels']} | {row['pv_orientation_summary']} | "
            f"{to_percent(row['auto_consumption_rate'])} | "
            f"{to_percent(row['self_sufficiency_rate'])} | {fmt(row['grid_import_kwh'], 1)} | "
            f"{fmt(row['grid_export_kwh'], 1)} |"
        )

    lines.append("")
    lines.append("## Scenarios PV+batterie (analyse economique)")
    lines.append("")
    lines.append(
        "| Rang | EMS | PV (kWp) | PV effectif (kWp eq. sud) | Batterie (kWh) | CAPEX PV (CHF) | CAPEX Bat. (CHF) | CAPEX EMS (CHF) | CAPEX brut (CHF) | Pronovo (CHF) | Deduction impot (CHF) | CAPEX apres reduction (CHF) | "
        f"Economies nettes/an (CHF) | Retour invest. (ans) | VAN {analysis_years} ans (CHF) |"
    )
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

    for idx, row in enumerate(scenarios_ranked[:top_n_scenarios], start=1):
        payback_str = (
            f"{row['payback_years']:.1f}"
            if row["payback_years"] != float("inf")
            else "> horizon"
        )
        lines.append(
            f"| {idx} | {'Oui' if row.get('energy_manager_enabled', False) else 'Non'} | {fmt(row['pv_kwp'], 2)} | {fmt(row['pv_effective_kwp'], 2)} | {fmt(row['battery_kwh'], 2)} | "
            f"{fmt(row['capex_pv_chf'], 0)} | {fmt(row['capex_battery_chf'], 0)} | {fmt(row['capex_energy_manager_chf'], 0)} | {fmt(row['capex_before_reductions_chf'], 0)} | "
            f"{fmt(row['pronovo_subsidy_chf'], 0)} | {fmt(row['tax_deduction_chf'], 0)} | {fmt(row['capex_after_reductions_chf'], 0)} | "
            f"{fmt(row['annual_net_savings_chf'], 0)} | {payback_str} | {fmt(row['npv_chf'], 0)} |"
        )

    # lines.append("")
    # lines.append("## Comparaison vs investissement en fonds")
    # lines.append("")
    # lines.append(
    #     f"| Rang | CAPEX apres reduction (CHF) | FV fonds ({analysis_years} ans, {fund_return_rate * 100:.1f}%/an) | "
    #     f"FV economies PV ({analysis_years} ans) | Ecart PV - fonds (CHF) |"
    # )
    # lines.append("|---:|---:|---:|---:|---:|")
    # for idx, row in enumerate(scenarios_ranked[:top_n_scenarios], start=1):
    #     lines.append(
    #         f"| {idx} | {fmt(row['capex_total_chf'], 0)} | {fmt(row['fund_future_value_chf'], 0)} | "
    #         f"{fmt(row['pv_savings_future_value_chf'], 0)} | {fmt(row['opportunity_delta_vs_fund_chf'], 0)} |"
    #     )

    lines.append("")
    lines.append("## Variantes de solution par profil")
    lines.append("")
    lines.append(
        f"Chaque tableau contient: l'optimum du profil, les 3 variantes minimales imposees "
        f"(batterie sans EMS, batterie avec EMS, sans batterie sans EMS), puis {n_below_optimum} "
        "solutions juste en dessous de l'optimum."
    )
    lines.append("")
    if not profile_variant_lists:
        lines.append("Aucune variante de profil n'a pu etre construite.")
    else:
        profile_labels = {
            "autonomy": "Autonomiste (tri: autonomie puis VAN)",
            "financial": "Financier (tri: VAN + capital puis payback)",
            "ecological": "Ecologiste (tri: payback puis VAN)",
        }
        for profile in ("autonomy", "financial", "ecological"):
            rows = profile_variant_lists.get(profile, [])
            lines.append(f"### Profil {profile_labels[profile]}")
            lines.append("")
            lines.append(
                "| Rang profil | Type | Config PV | PV effectif (kWp eq. sud) | Batterie (kWh) | EMS | Autoconsommation | Autonomie | VAN (CHF) | Investissement initial (CHF) | Subvention/deduction (CHF) | Cout maintenance total (CHF) | Capital non-dépensé (CHF) | VAN + Capital (CHF) | Payback (ans) |"
            )
            lines.append("|---:|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
            if not rows:
                lines.append("| - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |")
                lines.append("")
                continue

            optimum = rows[0]
            for idx, s in enumerate(rows, start=1):
                payback_str = f"{s['payback_years']:.1f}" if s["payback_years"] != float("inf") else "> horizon"
                row_type = str(s.get("selection_reason", "alternative"))
                capital_not_spent = s.get("capital_not_spent_value_chf", 0.0)
                npv_plus_capital = s.get("npv_plus_capital_chf", s.get("npv_chf", 0.0))
                initial_investment = s.get("initial_investment_chf", s.get("capex_total_chf", 0.0))
                reductions = s.get("capex_total_reductions_chf", 0.0)
                maintenance_total = s.get("maintenance_cost_total_chf", 0.0)

                lines.append(
                    f"| {idx} | {row_type} | {s['pv_orientation_summary']} ({s['pv_total_panels']} panneaux / {s['pv_kwp']:.2f} kWp) | "
                    f"{fmt(s.get('pv_effective_kwp'), 2)} | {s['battery_kwh']:.1f} | {'Oui' if s.get('energy_manager_enabled', False) else 'Non'} | "
                    f"{s['auto_consumption_rate']*100:.1f}% | {s['self_sufficiency_rate']*100:.1f}% | {s['npv_chf']:.0f} | "
                    f"{fmt(initial_investment, 0)} | {fmt(reductions, 0)} | {fmt(maintenance_total, 0)} | {fmt(capital_not_spent, 0)} | {fmt(npv_plus_capital, 0)} | {payback_str} |"
                )

            # Aide a la lecture: explique pourquoi un optimum peut avoir moins de panneaux.
            pv_max = float(max(float(r["pv_kwp"]) for r in rows))
            optimum_pv_kwp = float(optimum["pv_kwp"])
            if optimum_pv_kwp + 1e-9 < pv_max:
                lines.append("")
                lines.append(
                    f"- Lecture: l'optimum de ce profil ({fmt(optimum_pv_kwp, 2)} kWp) est inferieur au maximum "
                    f"presente ({fmt(pv_max, 2)} kWp), car son critere prioritaire est mieux servi a ce niveau."
                )
            lines.append("")

    lines.append("")
    lines.append("## Limites et ameliorations proposees")
    lines.append("")
    lines.append("- Integrer ensuite une production PV horaire meteo-reelle (PVGIS ou mesure locale) pour un dimensionnement final.")
    lines.append("- Completer par l'analyse des pointes de puissance (abonnement, puissance onduleur/batterie en kW).")

    content = "\n".join(lines) + "\n"
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(content, encoding="utf-8")
    return content


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Analyse un CSV quart-horaire de consommation, calcule les statistiques mensuelles par plages "
            "(semaine/week-end), puis simule des scenarios PV+batterie standards Vaud."
        )
    )
    parser.add_argument("--input-csv", required=True, help="Chemin CSV quart-horaire (Date;Consommation)")
    parser.add_argument(
        "--output",
        default="sortie/analyse_consommation_pv_batterie.md",
        help="Chemin du rapport Markdown",
    )
    parser.add_argument("--json-output", default=None, help="Chemin optionnel de sortie JSON")
    parser.add_argument(
        "--pv-kwp-list",
        default="3,6,9,12,15",
        help="Liste puissances PV kWp separee par virgules (utilisee seulement sans configuration panneaux)",
    )
    parser.add_argument(
        "--battery-kwh-list",
        default="0,5,10,15,20,30",
        help="Liste batteries kWh separee par virgules",
    )
    parser.add_argument(
        "--battery-dod",
        type=float,
        default=0.8,
        help="Depth of discharge batterie (0..1)",
    )
    parser.add_argument(
        "--battery-roundtrip-efficiency",
        type=float,
        default=0.9,
        help="Rendement aller-retour batterie (0..1)",
    )
    parser.add_argument(
        "--panel-watt-peak",
        type=float,
        default=490.0,
        help="Puissance nominale d'un panneau standard 2026 (Wc)",
    )
    parser.add_argument(
        "--roof-tilt-deg",
        type=parse_tilt_deg,
        default=DEFAULT_ROOF_TILT_DEG,
        help=f"Inclinaison du toit en degres (0..90, defaut: {DEFAULT_ROOF_TILT_DEG})",
    )
    parser.add_argument("--panels-north", type=parse_non_negative_int, default=0, help="Nombre de panneaux installables au nord")
    parser.add_argument("--panels-south", type=parse_non_negative_int, default=0, help="Nombre de panneaux installables au sud")
    parser.add_argument("--panels-east", type=parse_non_negative_int, default=0, help="Nombre de panneaux installables a l'est")
    parser.add_argument("--panels-west", type=parse_non_negative_int, default=0, help="Nombre de panneaux installables a l'ouest")
    parser.add_argument(
        "--min-total-panels",
        type=parse_non_negative_int,
        default=4,
        help="Nombre minimal de panneaux total a simuler en mode variantes de toiture",
    )
    parser.add_argument(
        "--top-n-scenarios",
        type=int,
        default=12,
        help="Nombre de scenarios affiches dans le rapport",
    )
    parser.add_argument(
        "--n-below-optimum",
        type=int,
        default=3,
        help="Nombre d'alternatives a afficher juste en dessous de l'optimum par profil",
    )
    # === Paramètres économiques (surcharge optionnelle des constantes) ===
    parser.add_argument(
        "--electricity-price",
        type=float,
        default=ELECTRICITY_PRICE_CHF_PER_KWH,
        help=f"Prix achat reseau CHF/kWh (defaut: {ELECTRICITY_PRICE_CHF_PER_KWH})",
    )
    parser.add_argument(
        "--buyback-price",
        type=float,
        default=BUYBACK_PRICE_CHF_PER_KWH,
        help=f"Prix reprise injection CHF/kWh (defaut: {BUYBACK_PRICE_CHF_PER_KWH})",
    )
    parser.add_argument(
        "--pv-fixed-cost",
        type=float,
        default=PV_FIXED_COST_CHF,
        help=f"Coût fixe installation PV en CHF (defaut: {PV_FIXED_COST_CHF})",
    )
    parser.add_argument(
        "--pv-site-setup-cost",
        type=float,
        default=PV_SITE_SETUP_COST_CHF,
        help=f"Coût mise en place chantier (echafaudage) en CHF (defaut: {PV_SITE_SETUP_COST_CHF})",
    )
    parser.add_argument(
        "--pv-cost-per-panel",
        type=float,
        default=PV_COST_PER_PANEL_CHF,
        help=f"Coût par panneau en CHF (defaut: {PV_COST_PER_PANEL_CHF})",
    )
    parser.add_argument(
        "--battery-fixed-cost",
        type=float,
        default=BATTERY_FIXED_COST_CHF,
        help=f"Coût fixe batterie en CHF (defaut: {BATTERY_FIXED_COST_CHF})",
    )
    parser.add_argument(
        "--battery-cost-per-kwh",
        type=float,
        default=BATTERY_COST_PER_KWH_CHF,
        help=f"Coût par kWh capacite batterie en CHF (defaut: {BATTERY_COST_PER_KWH_CHF})",
    )
    parser.add_argument(
        "--energy-manager-fixed-cost",
        type=float,
        default=ENERGY_MANAGER_FIXED_COST_CHF,
        help=f"Coût fixe repartiteur/EMS batiment en CHF (defaut: {ENERGY_MANAGER_FIXED_COST_CHF})",
    )
    parser.add_argument(
        "--pronovo-subsidy-chf-per-kwp",
        type=float,
        default=PRONOVO_SUBSIDY_CHF_PER_KWP,
        help=f"Subvention Pronovo en CHF/kWp installe (defaut: {PRONOVO_SUBSIDY_CHF_PER_KWP})",
    )
    parser.add_argument(
        "--tax-deduction-rate",
        type=float,
        default=TAX_DEDUCTION_RATE,
        help=f"Deduction d'impot appliquee a la facture brute (defaut: {TAX_DEDUCTION_RATE})",
    )
    parser.add_argument(
        "--analysis-years",
        type=int,
        default=ANALYSIS_YEARS,
        help=f"Horizon d'analyse en annees (defaut: {ANALYSIS_YEARS})",
    )
    parser.add_argument(
        "--discount-rate",
        type=float,
        default=DISCOUNT_RATE,
        help=f"Taux d'actualisation annuel (defaut: {DISCOUNT_RATE})",
    )
    parser.add_argument(
        "--fund-return-rate",
        type=float,
        default=FUND_RETURN_RATE,
        help=f"Rendement annuel du fonds alternatif (defaut: {FUND_RETURN_RATE})",
    )
    parser.add_argument(
        "--annual-maintenance-rate",
        type=float,
        default=ANNUAL_MAINTENANCE_RATE,
        help=f"Maintenance annuelle exprimee en %% du CAPEX brut (defaut: {ANNUAL_MAINTENANCE_RATE})",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
    )


    input_csv = Path(args.input_csv)
    output_md = Path(args.output)
    output_json = Path(args.json_output) if args.json_output else None

    logger.info("Lecture et aggrégation des données de consommation")
    records = parse_csv(input_csv)
    hour_records = build_hourly_records(records)
    completeness = compute_month_completeness(records)
    consumption_stats = compute_consumption_stats(records, hour_records)

    pv_kwp_values = parse_float_list(args.pv_kwp_list)
    battery_kwh_values = parse_float_list(args.battery_kwh_list)
    panel_counts = build_panel_counts(args.panels_north, args.panels_south, args.panels_east, args.panels_west)
    pv_configs, pv_mode = build_pv_configs(
        pv_kwp_values,
        panel_counts,
        args.panel_watt_peak,
        min_total_panels=args.min_total_panels,
    )

    logger.info("Pre-calcul des profils de production PV pour chaque configuration")

    # Cache majeur de performance: la production PV depend uniquement de la config toiture.
    pv_generation_cache = {}
    for idx, pv_config in enumerate(pv_configs, start=1):
        pv_generation_cache[pv_config.name] = build_pv_generation_series(records, pv_config, args.roof_tilt_deg)
        print_progress(idx, len(pv_configs), prefix="Cache PV")

    total_scenarios = len(pv_configs) * len(battery_kwh_values) * 2

    scenarios: list[dict[str, Any]] = []
    processed_scenarios = 0
    for pv_config in pv_configs:
        for batt_kwh in battery_kwh_values:
            for ems_enabled in (False, True):
                scenarios.append(
                    simulate_scenario(
                        quarter_records=records,
                        pv_config=pv_config,
                        battery_kwh=batt_kwh,
                        battery_dod=args.battery_dod,
                        battery_roundtrip_efficiency=args.battery_roundtrip_efficiency,
                        roof_tilt_deg=args.roof_tilt_deg,
                        electricity_price=args.electricity_price,
                        buyback_price=args.buyback_price,
                        pv_fixed_cost=args.pv_fixed_cost,
                        pv_site_setup_cost=args.pv_site_setup_cost,
                        pv_cost_per_panel=args.pv_cost_per_panel,
                        battery_fixed_cost=args.battery_fixed_cost,
                        battery_cost_per_kwh=args.battery_cost_per_kwh,
                        energy_manager_enabled=ems_enabled,
                        energy_manager_fixed_cost=args.energy_manager_fixed_cost,
                        pronovo_subsidy_chf_per_kwp=args.pronovo_subsidy_chf_per_kwp,
                        tax_deduction_rate=args.tax_deduction_rate,
                        analysis_years=args.analysis_years,
                        discount_rate=args.discount_rate,
                        fund_return_rate=args.fund_return_rate,
                        annual_maintenance_rate=args.annual_maintenance_rate,
                        pv_generation_series=pv_generation_cache[pv_config.name],
                    )
                )
                processed_scenarios += 1
                print_progress(processed_scenarios, total_scenarios, prefix="Simulation")
    scenarios = enrich_scenarios_with_capital_value(
        scenarios,
        analysis_years=args.analysis_years,
        fund_return_rate=args.fund_return_rate,
    )
    scenarios = enrich_scenarios_with_capital_value(
        scenarios,
        analysis_years=args.analysis_years,
        fund_return_rate=args.fund_return_rate,
    )
    ranked = rank_scenarios(scenarios)
    best_scenarios = find_best_scenarios(ranked)
    profile_variant_lists = build_profile_variant_lists(ranked, args.n_below_optimum)

    build_markdown_report(
        input_csv=input_csv,
        output_md=output_md,
        consumption_stats=consumption_stats,
        month_completeness=completeness,
        scenarios_ranked=ranked,
        panel_watt_peak=args.panel_watt_peak,
        roof_tilt_deg=args.roof_tilt_deg,
        battery_dod=args.battery_dod,
        battery_roundtrip_efficiency=args.battery_roundtrip_efficiency,
        top_n_scenarios=args.top_n_scenarios,
        pv_mode=pv_mode,
        panel_limits=panel_counts,
        pv_variant_count=len(pv_configs) if pv_mode == "panel_variants" else None,
        best_scenarios=best_scenarios,
        profile_variant_lists=profile_variant_lists,
        n_below_optimum=args.n_below_optimum,
        electricity_price=args.electricity_price,
        buyback_price=args.buyback_price,
        pv_fixed_cost=args.pv_fixed_cost,
        pv_site_setup_cost=args.pv_site_setup_cost,
        pv_cost_per_panel=args.pv_cost_per_panel,
        battery_fixed_cost=args.battery_fixed_cost,
        battery_cost_per_kwh=args.battery_cost_per_kwh,
        energy_manager_fixed_cost=args.energy_manager_fixed_cost,
        pronovo_subsidy_chf_per_kwp=args.pronovo_subsidy_chf_per_kwp,
        tax_deduction_rate=args.tax_deduction_rate,
        analysis_years=args.analysis_years,
        discount_rate=args.discount_rate,
        fund_return_rate=args.fund_return_rate,
        annual_maintenance_rate=args.annual_maintenance_rate,
    )

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(
                {
                    "input_csv": str(input_csv),
                    "generated_at": datetime.now().isoformat(),
                    "assumptions": {
                        "monthly_daily_yield_kwh_per_kwp": MONTHLY_DAILY_YIELD_KWH_PER_KWP,
                        "pv_hourly_weights": PV_HOURLY_WEIGHTS,
                        "orientation_yield_factor": ORIENTATION_YIELD_FACTOR,
                        "orientation_lookup_shift": ORIENTATION_LOOKUP_SHIFT,
                        "battery_dod": args.battery_dod,
                        "battery_roundtrip_efficiency": args.battery_roundtrip_efficiency,
                        "panel_watt_peak": args.panel_watt_peak,
                        "roof_tilt_deg": args.roof_tilt_deg,
                        "panel_counts": panel_counts,
                        "pv_mode": pv_mode,
                        "economics": {
                            "electricity_price_chf_per_kwh": args.electricity_price,
                            "buyback_price_chf_per_kwh": args.buyback_price,
                            "pv_fixed_cost_chf": args.pv_fixed_cost,
                            "pv_site_setup_cost_chf": args.pv_site_setup_cost,
                            "pv_cost_per_panel_chf": args.pv_cost_per_panel,
                            "battery_fixed_cost_chf": args.battery_fixed_cost,
                            "battery_cost_per_kwh_chf": args.battery_cost_per_kwh,
                            "energy_manager_fixed_cost_chf": args.energy_manager_fixed_cost,
                            "pronovo_subsidy_chf_per_kwp": args.pronovo_subsidy_chf_per_kwp,
                            "tax_deduction_rate": args.tax_deduction_rate,
                            "analysis_years": args.analysis_years,
                            "discount_rate": args.discount_rate,
                            "fund_return_rate": args.fund_return_rate,
                            "annual_maintenance_rate": args.annual_maintenance_rate,
                        },
                    },
                    "month_completeness": completeness,
                    "consumption_stats": consumption_stats,
                    "scenarios_ranked": ranked,
                    "best_scenarios": {
                        profile: {
                            k: v for k, v in scenario.items() 
                            if k not in ["pv_config_name"]  # Exclure les clés redondantes
                        }
                        for profile, scenario in best_scenarios.items()
                    } if best_scenarios else {},
                    "profile_variant_lists": {
                        profile: [
                            {
                                k: v for k, v in scenario.items()
                                if k not in ["pv_config_name"]
                            }
                            for scenario in variants
                        ]
                        for profile, variants in profile_variant_lists.items()
                    } if profile_variant_lists else {},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    print(f"[OK] Rapport ecrit: {output_md}")
    if output_json is not None:
        print(f"[OK] JSON ecrit: {output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

