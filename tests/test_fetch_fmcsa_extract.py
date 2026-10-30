import unittest

from analysis.fetch_fmcsa_extract import require_complete


class FetchCompleteTests(unittest.TestCase):
    def test_matching_counts_pass(self):
        require_complete(3, 3, 3)

    def test_short_page_or_drift_fails(self):
        with self.assertRaises(SystemExit):
            require_complete(2, 3, 3)
        with self.assertRaises(SystemExit):
            require_complete(3, 3, 4)


if __name__ == '__main__':
    unittest.main()
