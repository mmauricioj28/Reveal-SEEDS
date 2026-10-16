import unittest
import pandas as pd
from analysis.build_safety_dataset import canonicalize_dot

class TestBuildSafetyDataset(unittest.TestCase):
    def test_canonicalize_dot(self):
        sample = pd.Series(["1001", "1002.0", "  1003  ", "invalid", None])
        clean = canonicalize_dot(sample)
        self.assertEqual(list(clean), ["1001", "1002", "1003"])

    def test_unreviewed_carrier_left_join(self):
        census = pd.DataFrame({
            "DOT_NUMBER": ["99999"],
            "POWER_UNITS": [10],
            "TOTAL_DRIVERS": [5],
            "PHY_STATE": ["NJ"],
            "PHY_COUNTRY": ["US"],
        })
        crashes = pd.DataFrame(columns=["DOT_NUMBER", "TOTAL_CRASHES", "TOTAL_FATALITIES", "TOTAL_INJURIES"])
        merged = census.merge(crashes, on="DOT_NUMBER", how="left").fillna(0)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged.loc[0, "TOTAL_CRASHES"], 0)

if __name__ == "__main__":
    unittest.main()