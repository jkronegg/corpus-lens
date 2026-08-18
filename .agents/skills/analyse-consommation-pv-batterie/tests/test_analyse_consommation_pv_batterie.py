import csv
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
import importlib.util
import sys


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "analyse_consommation_pv_batterie.py"
spec = importlib.util.spec_from_file_location("analyse_consommation_pv_batterie", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class AnalyseConsommationPvBatterieTests(unittest.TestCase):
    def test_classify_slot_boundaries(self):
        self.assertEqual(module.classify_slot(0), "22h-6h")
        self.assertEqual(module.classify_slot(5), "22h-6h")
        self.assertEqual(module.classify_slot(6), "6h-9h")
        self.assertEqual(module.classify_slot(8), "6h-9h")
        self.assertEqual(module.classify_slot(9), "9h-16h")
        self.assertEqual(module.classify_slot(15), "9h-16h")
        self.assertEqual(module.classify_slot(16), "16h-22h")
        self.assertEqual(module.classify_slot(21), "16h-22h")
        self.assertEqual(module.classify_slot(22), "22h-6h")

    def test_parse_and_stats_constant_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "input.csv"
            start = datetime(2026, 1, 5, 0, 0, 0)  # lundi
            rows = [("Date", "Consommation")]

            # 2 jours complets, consommation constante: 0.5 kWh par quart d'heure.
            for i in range(2 * 96):
                ts = start + timedelta(minutes=15 * i)
                rows.append((ts.strftime("%d.%m.%Y %H:%M:%S"), "0.5"))

            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerows(rows)

            records = module.parse_csv(csv_path)
            hourly = module.build_hourly_records(records)
            stats = module.compute_consumption_stats(records, hourly)

            # Janvier + semaine + 22h-6h
            row = next(
                x for x in stats
                if x["month"] == 1 and x["day_type"] == "semaine" and x["slot"] == "22h-6h"
            )
            # 0.5*4 = 2 kWh par heure
            self.assertAlmostEqual(row["hourly_floor_kwh"], 2.0, places=6)
            self.assertAlmostEqual(row["hourly_ceiling_kwh"], 2.0, places=6)
            # plage 22h-6h = 8h -> 16 kWh/jour
            self.assertAlmostEqual(row["daily_slot_total_min_kwh"], 16.0, places=6)
            self.assertAlmostEqual(row["daily_slot_total_median_kwh"], 16.0, places=6)
            self.assertAlmostEqual(row["daily_slot_total_max_kwh"], 16.0, places=6)
            # puissance quart-horaire: 0.5*4 = 2 kW
            self.assertAlmostEqual(row["peak_power_kw_max"], 2.0, places=6)

    def test_simulation_without_pv_or_battery(self):
        records = [
            module.QuarterRecord(ts=datetime(2026, 6, 1, 12, 0, 0), kwh=1.0),
            module.QuarterRecord(ts=datetime(2026, 6, 1, 12, 15, 0), kwh=1.0),
        ]
        pv_config = module.build_legacy_pv_config(0.0, 430.0)
        result = module.simulate_scenario(
            quarter_records=records,
            pv_config=pv_config,
            battery_kwh=0.0,
            battery_dod=0.8,
            battery_roundtrip_efficiency=0.9,
        )
        self.assertAlmostEqual(result["total_load_kwh"], 2.0, places=6)
        self.assertAlmostEqual(result["total_pv_kwh"], 0.0, places=6)
        self.assertAlmostEqual(result["self_sufficiency_rate"], 0.0, places=6)
        self.assertAlmostEqual(result["grid_import_kwh"], 2.0, places=6)

    def test_orientation_profiles_and_layout_config(self):
        east_morning = module.pv_kwh_per_kwp_quarter(datetime(2026, 6, 1, 8, 0, 0), "east")
        west_morning = module.pv_kwh_per_kwp_quarter(datetime(2026, 6, 1, 8, 0, 0), "west")
        south_noon = module.pv_kwh_per_kwp_quarter(datetime(2026, 6, 1, 12, 0, 0), "south")
        north_noon = module.pv_kwh_per_kwp_quarter(datetime(2026, 6, 1, 12, 0, 0), "north")

        self.assertGreater(east_morning, west_morning)
        self.assertGreater(south_noon, north_noon)

        panel_counts = module.build_panel_counts(4, 10, 6, 8)
        pv_configs, pv_mode = module.build_pv_configs([5.0, 10.0], panel_counts, 430.0)
        self.assertEqual(pv_mode, "panel_layout")
        self.assertEqual(len(pv_configs), 1)
        self.assertEqual(pv_configs[0].total_panels, 28)
        self.assertAlmostEqual(pv_configs[0].total_kwp, 28 * 430.0 / 1000.0, places=6)


if __name__ == "__main__":
    unittest.main()


