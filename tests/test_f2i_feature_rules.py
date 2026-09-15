"""Focused checks for the published and diagnostic F2-I taxonomies."""

from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "tools" / "build_f2i_features.py"
SPEC = importlib.util.spec_from_file_location("f2i_features", MODULE)
assert SPEC and SPEC.loader
F2I = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F2I)


class FeatureRulesTest(unittest.TestCase):
    def test_facility_priority_is_exclusive(self) -> None:
        self.assertEqual(F2I.classify_facility({"amenity": "hospital", "shop": "chemist"}), "health")
        self.assertEqual(F2I.classify_facility({"amenity": "school", "shop": "books"}), "education")
        self.assertEqual(F2I.classify_facility({"amenity": "restaurant"}), "food")

    def test_road_crosswalk_preserves_paper_and_macro_classes(self) -> None:
        self.assertEqual(F2I.classify_road({"highway": "primary"}), ("main", "main"))
        self.assertEqual(F2I.classify_road({"highway": "tertiary"}), ("main", "secondary"))
        self.assertEqual(F2I.classify_road({"highway": "residential"}), ("residential", None))

    def test_normalizations_follow_metric_area(self) -> None:
        values = F2I.initial_values({}, ["u"])["u"]
        values.update({"unit_area_km2": 2.0, "population_census_2024": 200.0,
                       "landuse_residential_area_km2": 0.5, "road_main_km": 3.0,
                       "transport_poi_count": 4.0, "transport_area_count": 2.0,
                       "main_roads_km": 3.0, "secondary_roads_km": 1.0})
        paper, macro = F2I.paper_row(values), F2I.macro_row(values)
        self.assertEqual(paper["population_census_2024_per_km2"], 100.0)
        self.assertEqual(paper["landuse_residential_share"], 0.25)
        self.assertEqual(paper["road_main_km_per_km2"], 1.5)
        self.assertEqual(paper["transport_poi_per_km2"], 2.0)
        self.assertEqual(macro["transport_per_km2"], 3.0)
        self.assertEqual(macro["main_roads_km_per_km2"], 1.5)
        self.assertFalse(math.isnan(macro["other_per_km2"]))


if __name__ == "__main__":
    unittest.main()
