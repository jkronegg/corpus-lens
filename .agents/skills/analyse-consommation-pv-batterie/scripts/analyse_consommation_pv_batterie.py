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
import json
import math
import statistics
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
# Coût fixe installation PV (hors logistique chantier): onduleur string résidentiel,
# raccordement réseau, compteur bidirectionnel, frais d'annonce/permis, câblage DC/AC.
PV_FIXED_COST_CHF: float = 3_000.0
# Coût de mise en place chantier (échafaudage + protections + logistique accès toiture).
# Ordre de grandeur vaudois 2026 pour maison individuelle: 3'500-6'000 CHF.
PV_SITE_SETUP_COST_CHF: float = 4_500.0
# Coût par panneau 430-450 Wc, pose incluse (module premium ~170-210 CHF +
# structure/montage/câblage/part variable MO ~280-320 CHF) en contexte suisse.
PV_COST_PER_PANEL_CHF: float = 500.0
# Coût fixe batterie : BMS intégré, câblage AC/DC, mise en service.
BATTERY_FIXED_COST_CHF: float = 1_000.0
# Coût par kWh de capacité nominale installée (technologie LFP, marché romand 2026).
BATTERY_COST_PER_KWH_CHF: float = 700.0
# Répartiteur/EMS pour pilotage énergétique global bâtiment
# (PAC chauffage, gros consommateurs, recharge véhicule électrique, etc.).
ENERGY_MANAGER_FIXED_COST_CHF: float = 2_500.0
# Horizon d'analyse / durée de vie estimée du système (ans).
ANALYSIS_YEARS: int = 25
# Taux d'actualisation annuel (réel, inflation déduite).
DISCOUNT_RATE: float = 0.03
# Rendement annuel de référence pour un placement alternatif en fonds d'investissement.
FUND_RETURN_RATE: float = 0.03


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
) -> tuple[list[PvSystemConfig], str]:
    total_installable_panels = sum(panel_counts.values())
    if total_installable_panels > 0:
        return [build_layout_pv_config(panel_counts, panel_watt_peak)], "panel_layout"
    return [build_legacy_pv_config(pv_kwp, panel_watt_peak) for pv_kwp in pv_kwp_values], "pv_kwp_list"


def pv_system_kwh_quarter(
    ts: datetime,
    pv_config: PvSystemConfig,
    roof_tilt_deg: float = DEFAULT_ROOF_TILT_DEG,
) -> float:
    total = 0.0
    for orientation, kwp in pv_config.orientation_kwp.items():
        total += kwp * pv_kwh_per_kwp_quarter(ts, orientation, roof_tilt_deg=roof_tilt_deg)
    return total


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
    energy_manager_fixed_cost: float = ENERGY_MANAGER_FIXED_COST_CHF,
    analysis_years: int = ANALYSIS_YEARS,
    discount_rate: float = DISCOUNT_RATE,
    fund_return_rate: float = FUND_RETURN_RATE,
) -> dict[str, Any]:
    if not (0 < battery_dod <= 1):
        raise ValueError("battery_dod doit etre dans ]0,1]")
    if not (0 < battery_roundtrip_efficiency <= 1):
        raise ValueError("battery_roundtrip_efficiency doit etre dans ]0,1]")

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

    for rec in quarter_records:
        load = rec.kwh
        pv = pv_system_kwh_quarter(rec.ts, pv_config, roof_tilt_deg=roof_tilt_deg)

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
    # Le repartiteur/EMS est un socle de pilotage transverse PV+batterie+charges.
    capex_total = capex_pv + capex_battery + energy_manager_fixed_cost

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
        "capex_energy_manager_chf": energy_manager_fixed_cost,
        "capex_total_chf": capex_total,
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


def find_best_scenarios(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Trouve le meilleur scénario selon 3 critères différents.
    
    Returns:
        dict avec clés 'autonomy', 'financial', 'ecological'
    """
    if not results:
        return {}
    
    # 1. Maximiser autonomie/auto-consommation (autonomiste)
    best_autonomy = max(results, key=lambda s: (s["self_sufficiency_rate"], s["auto_consumption_rate"]))
    
    # 2. Maximiser VAN à 25 ans (financier)
    best_financial = max(results, key=lambda s: s["npv_chf"])
    
    # 3. Minimiser temps d'amortissement avec économies positives (écolo)
    scenarios_with_savings = [s for s in results if s["annual_net_savings_chf"] > 0]
    if scenarios_with_savings:
        best_ecological = min(scenarios_with_savings, key=lambda s: s["payback_years"])
    else:
        best_ecological = results[0]
    
    return {
        "autonomy": best_autonomy,
        "financial": best_financial,
        "ecological": best_ecological,
    }


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
    best_scenarios: dict[str, dict[str, Any]] | None = None,
    electricity_price: float = ELECTRICITY_PRICE_CHF_PER_KWH,
    buyback_price: float = BUYBACK_PRICE_CHF_PER_KWH,
    pv_fixed_cost: float = PV_FIXED_COST_CHF,
    pv_site_setup_cost: float = PV_SITE_SETUP_COST_CHF,
    pv_cost_per_panel: float = PV_COST_PER_PANEL_CHF,
    battery_fixed_cost: float = BATTERY_FIXED_COST_CHF,
    battery_cost_per_kwh: float = BATTERY_COST_PER_KWH_CHF,
    energy_manager_fixed_cost: float = ENERGY_MANAGER_FIXED_COST_CHF,
    analysis_years: int = ANALYSIS_YEARS,
    discount_rate: float = DISCOUNT_RATE,
    fund_return_rate: float = FUND_RETURN_RATE,
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
    lines.append("")
    lines.append("## Hypotheses economiques (marche vaudois, Suisse, 2026)")
    lines.append("")
    lines.append(f"| Parametre | Valeur | Source / note |")
    lines.append("|---|---:|---|")
    lines.append(f"| Prix achat reseau | {electricity_price * 100:.1f} ct/kWh | Tarif VD-L Romande Energie tout compris (reseau + energie + taxes) |")
    lines.append(f"| Prix reprise injection | {buyback_price * 100:.1f} ct/kWh | Retribution au prix du marche (Pronovo/swissgrid 2026) |")
    lines.append(f"| Cout fixe installation PV | {pv_fixed_cost:.0f} CHF | Onduleur, raccordement reseau, compteur bidirectionnel, admin/permis |")
    lines.append(f"| Cout mise en place chantier (echafaudage) | {pv_site_setup_cost:.0f} CHF | Echafaudage, protections et logistique d'acces toiture |")
    lines.append(f"| Cout par panneau 430-450 Wc | {pv_cost_per_panel:.0f} CHF | Module premium (~170-210 CHF) + structure/montage/cablage/part variable MO (~280-320 CHF) |")
    lines.append(f"| Cout fixe batterie | {battery_fixed_cost:.0f} CHF | BMS integre, cablage AC/DC, mise en service |")
    lines.append(f"| Cout par kWh capacite batterie | {battery_cost_per_kwh:.0f} CHF/kWh | Technologie LFP installee, marche romand 2026 |")
    lines.append(f"| Cout fixe repartiteur/EMS batiment | {energy_manager_fixed_cost:.0f} CHF | Pilotage PAC, gros consommateurs et recharge VE |")
    lines.append(f"| Horizon d'analyse | {analysis_years} ans | Duree de vie estimee du systeme |")
    lines.append(f"| Taux d'actualisation | {discount_rate * 100:.1f} % | Taux reel (inflation deduite) |")
    lines.append(f"| Rendement fonds alternatif | {fund_return_rate * 100:.1f} %/an | Hypothese de comparaison (cout d'opportunite du capital) |")
    lines.append("")

    lines.append("## Configuration PV prise en compte")
    lines.append("")
    if best is None:
        lines.append("Aucune configuration PV n'a pu etre calculee.")
    elif pv_mode == "panel_layout":
        lines.append(
            f"- Panneaux installables fournis: **N={best['pv_panels_north']} ; S={best['pv_panels_south']} ; "
            f"E={best['pv_panels_east']} ; O={best['pv_panels_west']}**."
        )
        lines.append(f"- Total panneaux installables simules: **{best['pv_total_panels']}**.")
        lines.append(f"- Puissance PV totale correspondante: **{best['pv_kwp']:.2f} kWp**.")
    else:
        lines.append("- Mode legacy: liste de puissances PV equivalentes sud (`--pv-kwp-list`).")
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
        "| Rang | PV (kWp) | Batterie (kWh) | Batterie utile (kWh) | "
        "Panneaux | Orientation | Autoconsommation PV | Couverture conso | Import reseau (kWh) | Export reseau (kWh) |"
    )
    lines.append("|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|")

    for idx, row in enumerate(scenarios_ranked[:top_n_scenarios], start=1):
        lines.append(
            f"| {idx} | {fmt(row['pv_kwp'], 2)} | {fmt(row['battery_kwh'], 2)} | "
            f"{fmt(row['battery_usable_kwh'], 2)} | {row['pv_total_panels']} | {row['pv_orientation_summary']} | "
            f"{to_percent(row['auto_consumption_rate'])} | "
            f"{to_percent(row['self_sufficiency_rate'])} | {fmt(row['grid_import_kwh'], 1)} | "
            f"{fmt(row['grid_export_kwh'], 1)} |"
        )

    lines.append("")
    lines.append("## Scenarios PV+batterie (analyse economique)")
    lines.append("")
    lines.append(
        "| Rang | PV (kWp) | Batterie (kWh) | CAPEX PV (CHF) | CAPEX Bat. (CHF) | CAPEX EMS (CHF) | CAPEX total (CHF) | "
        f"Economies nettes/an (CHF) | Retour invest. (ans) | VAN {analysis_years} ans (CHF) |"
    )
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

    for idx, row in enumerate(scenarios_ranked[:top_n_scenarios], start=1):
        payback_str = (
            f"{row['payback_years']:.1f}"
            if row["payback_years"] != float("inf")
            else "> horizon"
        )
        lines.append(
            f"| {idx} | {fmt(row['pv_kwp'], 2)} | {fmt(row['battery_kwh'], 2)} | "
            f"{fmt(row['capex_pv_chf'], 0)} | {fmt(row['capex_battery_chf'], 0)} | {fmt(row['capex_energy_manager_chf'], 0)} | {fmt(row['capex_total_chf'], 0)} | "
            f"{fmt(row['annual_net_savings_chf'], 0)} | {payback_str} | {fmt(row['npv_chf'], 0)} |"
        )

    lines.append("")
    lines.append("## Comparaison vs investissement en fonds")
    lines.append("")
    lines.append(
        f"| Rang | CAPEX total (CHF) | FV fonds ({analysis_years} ans, {fund_return_rate * 100:.1f}%/an) | "
        f"FV economies PV ({analysis_years} ans) | Ecart PV - fonds (CHF) |"
    )
    lines.append("|---:|---:|---:|---:|---:|")
    for idx, row in enumerate(scenarios_ranked[:top_n_scenarios], start=1):
        lines.append(
            f"| {idx} | {fmt(row['capex_total_chf'], 0)} | {fmt(row['fund_future_value_chf'], 0)} | "
            f"{fmt(row['pv_savings_future_value_chf'], 0)} | {fmt(row['opportunity_delta_vs_fund_chf'], 0)} |"
        )

    lines.append("")
    lines.append("## Recommandation (selon ce modele simplifie)")
    lines.append("")
    if best is None:
        lines.append("Aucun scenario n'a pu etre calcule.")
    else:
        lines.append("### Synthèse: Trois profils d'utilisateurs")
        lines.append("")
        lines.append("Le tableau suivant résume les recommandations optimales selon 3 profils décisionnels distincts:")
        lines.append("")
        lines.append("| Profil | Priorité | Recommandation PV+Batterie | Auto-conso | Autonomie | Payback | VAN 25 ans |")
        lines.append("|---|---|---|---:|---:|---:|---:|")
        
        if best_scenarios:
            for profile, name, priority in [
                ("autonomy", "**Autonomiste**", "Maximiser autonomie & auto-consommation"),
                ("financial", "**Financier**", "Maximiser VAN 25 ans"),
                ("ecological", "**Écolo**", "Minimiser temps d'amortissement"),
            ]:
                if profile in best_scenarios:
                    s = best_scenarios[profile]
                    payback_str = f"{s['payback_years']:.1f} ans" if s["payback_years"] != float("inf") else "> horizon"
                    lines.append(
                        f"| {name} | {priority} | "
                        f"{s['pv_kwp']:.2f} kWp + {s['battery_kwh']:.1f} kWh | "
                        f"{s['auto_consumption_rate']*100:.1f}% | {s['self_sufficiency_rate']*100:.1f}% | "
                        f"{payback_str} | {s['npv_chf']:.0f} CHF |"
                    )
        
        lines.append("")
        lines.append("### Détail par profil")
        lines.append("")
        
        # Profil Autonomiste
        lines.append("#### 1️⃣ Profil AUTONOMISTE (maximiser autonomie énergétique)")
        lines.append("")
        if best_scenarios and "autonomy" in best_scenarios:
            s = best_scenarios["autonomy"]
            payback_str = f"{s['payback_years']:.1f} ans" if s["payback_years"] != float("inf") else "superieur a l'horizon d'analyse"
            lines.append(f"- **Configuration recommandée**: {s['pv_kwp']:.2f} kWp PV + {s['battery_kwh']:.1f} kWh batterie (~{s['pv_total_panels']} panneaux).")
            lines.append(f"- **Répartition panneaux**: {s['pv_orientation_summary']}.")
            lines.append(f"- **Auto-consommation estimée**: {s['auto_consumption_rate']*100:.1f}% (taux de réutilisation de sa propre production).")
            lines.append(f"- **Autonomie énergétique estimée**: {s['self_sufficiency_rate']*100:.1f}% (couverture de la consommation sans réseau).")
            lines.append(f"- **CAPEX total**: {s['capex_total_chf']:.0f} CHF (PV: {s['capex_pv_chf']:.0f} CHF, batterie: {s['capex_battery_chf']:.0f} CHF).")
            lines.append(f"- **Repartiteur/EMS**: {s['capex_energy_manager_chf']:.0f} CHF (inclus dans le CAPEX total).")
            lines.append(f"- **Économies nettes annuelles**: {s['annual_net_savings_chf']:.0f} CHF/an.")
            lines.append(f"- **Retour investissement**: {payback_str}.")
            lines.append(f"- **VAN 25 ans**: {s['npv_chf']:.0f} CHF.")
            lines.append("")
            lines.append("**Intérêt**: Minimise la dépendance réseau, idéal pour l'indépendance énergétique.")
        
        # Profil Financier
        lines.append("")
        lines.append("#### 2️⃣ Profil FINANCIER (maximiser le rendement VAN)")
        lines.append("")
        if best_scenarios and "financial" in best_scenarios:
            s = best_scenarios["financial"]
            payback_str = f"{s['payback_years']:.1f} ans" if s["payback_years"] != float("inf") else "superieur a l'horizon d'analyse"
            lines.append(f"- **Configuration recommandée**: {s['pv_kwp']:.2f} kWp PV + {s['battery_kwh']:.1f} kWh batterie (~{s['pv_total_panels']} panneaux).")
            lines.append(f"- **Répartition panneaux**: {s['pv_orientation_summary']}.")
            lines.append(f"- **Auto-consommation estimée**: {s['auto_consumption_rate']*100:.1f}%.")
            lines.append(f"- **Autonomie énergétique estimée**: {s['self_sufficiency_rate']*100:.1f}%.")
            lines.append(f"- **CAPEX total**: {s['capex_total_chf']:.0f} CHF (PV: {s['capex_pv_chf']:.0f} CHF, batterie: {s['capex_battery_chf']:.0f} CHF).")
            lines.append(f"- **Repartiteur/EMS**: {s['capex_energy_manager_chf']:.0f} CHF (inclus dans le CAPEX total).")
            lines.append(f"- **Économies nettes annuelles**: {s['annual_net_savings_chf']:.0f} CHF/an.")
            lines.append(f"- **Retour investissement**: {payback_str}.")
            lines.append(f"- **VAN 25 ans** (taux 3.0%): **{s['npv_chf']:.0f} CHF** ← MEILLEURE PERFORMANCE FINANCIÈRE.")
            if s["opportunity_delta_vs_fund_chf"] >= 0:
                lines.append(f"- **vs. fonds 3.0%/an**: PV favorable de {s['opportunity_delta_vs_fund_chf']:.0f} CHF sur 25 ans (valeur future).")
            lines.append("")
            lines.append("**Intérêt**: Meilleur retour sur investissement à long terme (25 ans), tenant compte de l'inflation actualisée.")
        
        # Profil Écolo
        lines.append("")
        lines.append("#### 3️⃣ Profil ÉCOLO (minimiser durée d'impact de consommation de ressources)")
        lines.append("")
        if best_scenarios and "ecological" in best_scenarios:
            s = best_scenarios["ecological"]
            payback_str = f"{s['payback_years']:.1f} ans" if s["payback_years"] != float("inf") else "superieur a l'horizon d'analyse"
            lines.append(f"- **Configuration recommandée**: {s['pv_kwp']:.2f} kWp PV + {s['battery_kwh']:.1f} kWh batterie (~{s['pv_total_panels']} panneaux).")
            lines.append(f"- **Répartition panneaux**: {s['pv_orientation_summary']}.")
            lines.append(f"- **Auto-consommation estimée**: {s['auto_consumption_rate']*100:.1f}%.")
            lines.append(f"- **Autonomie énergétique estimée**: {s['self_sufficiency_rate']*100:.1f}%.")
            lines.append(f"- **CAPEX total**: {s['capex_total_chf']:.0f} CHF (PV: {s['capex_pv_chf']:.0f} CHF, batterie: {s['capex_battery_chf']:.0f} CHF).")
            lines.append(f"- **Repartiteur/EMS**: {s['capex_energy_manager_chf']:.0f} CHF (inclus dans le CAPEX total).")
            lines.append(f"- **Économies nettes annuelles**: {s['annual_net_savings_chf']:.0f} CHF/an.")
            lines.append(f"- **Retour investissement** ← **{payback_str}** (PLUS RAPIDE).")
            lines.append(f"- **VAN 25 ans**: {s['npv_chf']:.0f} CHF.")
            lines.append("")
            lines.append("**Intérêt**: Rembourse l'investissement (ressources) le plus rapidement, minimisant l'impact écologique net de la ressource investie.")
        
        lines.append("")
        lines.append("### Conseil récapitulatif")
        lines.append("")
        lines.append("- Cette recommandation est un **pré-dimensionnement** énergétique et financier.")
        lines.append("- À affiner avec: inclinaison/orientation réelles, ombrage local, contraintes onduleur/batterie en kW, devis spécifiques.")
        lines.append("- Choisir le profil en fonction de vos priorités personnelles: indépendance (autonomiste), rendement (financier), ou impact écologique (écolo).")

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
        default="5,10,15,20,25",
        help="Liste PV kWp separee par virgules",
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
        default=430.0,
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
        "--top-n-scenarios",
        type=int,
        default=12,
        help="Nombre de scenarios affiches dans le rapport",
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
        help=f"Cout fixe installation PV en CHF (defaut: {PV_FIXED_COST_CHF})",
    )
    parser.add_argument(
        "--pv-site-setup-cost",
        type=float,
        default=PV_SITE_SETUP_COST_CHF,
        help=f"Cout mise en place chantier (echafaudage) en CHF (defaut: {PV_SITE_SETUP_COST_CHF})",
    )
    parser.add_argument(
        "--pv-cost-per-panel",
        type=float,
        default=PV_COST_PER_PANEL_CHF,
        help=f"Cout par panneau en CHF (defaut: {PV_COST_PER_PANEL_CHF})",
    )
    parser.add_argument(
        "--battery-fixed-cost",
        type=float,
        default=BATTERY_FIXED_COST_CHF,
        help=f"Cout fixe batterie en CHF (defaut: {BATTERY_FIXED_COST_CHF})",
    )
    parser.add_argument(
        "--battery-cost-per-kwh",
        type=float,
        default=BATTERY_COST_PER_KWH_CHF,
        help=f"Cout par kWh capacite batterie en CHF (defaut: {BATTERY_COST_PER_KWH_CHF})",
    )
    parser.add_argument(
        "--energy-manager-fixed-cost",
        type=float,
        default=ENERGY_MANAGER_FIXED_COST_CHF,
        help=f"Cout fixe repartiteur/EMS batiment en CHF (defaut: {ENERGY_MANAGER_FIXED_COST_CHF})",
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
    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    output_md = Path(args.output)
    output_json = Path(args.json_output) if args.json_output else None

    records = parse_csv(input_csv)
    hour_records = build_hourly_records(records)
    completeness = compute_month_completeness(records)
    consumption_stats = compute_consumption_stats(records, hour_records)

    pv_kwp_values = parse_float_list(args.pv_kwp_list)
    battery_kwh_values = parse_float_list(args.battery_kwh_list)
    panel_counts = build_panel_counts(args.panels_north, args.panels_south, args.panels_east, args.panels_west)
    pv_configs, pv_mode = build_pv_configs(pv_kwp_values, panel_counts, args.panel_watt_peak)

    scenarios: list[dict[str, Any]] = []
    for pv_config in pv_configs:
        for batt_kwh in battery_kwh_values:
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
                    energy_manager_fixed_cost=args.energy_manager_fixed_cost,
                    analysis_years=args.analysis_years,
                    discount_rate=args.discount_rate,
                    fund_return_rate=args.fund_return_rate,
                )
            )
    ranked = rank_scenarios(scenarios)
    best_scenarios = find_best_scenarios(ranked)

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
        best_scenarios=best_scenarios,
        electricity_price=args.electricity_price,
        buyback_price=args.buyback_price,
        pv_fixed_cost=args.pv_fixed_cost,
        pv_site_setup_cost=args.pv_site_setup_cost,
        pv_cost_per_panel=args.pv_cost_per_panel,
        battery_fixed_cost=args.battery_fixed_cost,
        battery_cost_per_kwh=args.battery_cost_per_kwh,
        energy_manager_fixed_cost=args.energy_manager_fixed_cost,
        analysis_years=args.analysis_years,
        discount_rate=args.discount_rate,
        fund_return_rate=args.fund_return_rate,
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
                            "analysis_years": args.analysis_years,
                            "discount_rate": args.discount_rate,
                            "fund_return_rate": args.fund_return_rate,
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

