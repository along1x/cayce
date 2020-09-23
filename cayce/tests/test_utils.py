import datetime as dt
import unittest

from numpy import NaN
import pandas as pd

from cayce.utils import ifna, is_leap_year, add_months, get_quarter, split_fixed_length


class TestUtils(unittest.TestCase):
    def test_split_fixed_length(self):
        test_string_1 = "abcdefghijklmnopqrstuvwxyz"

        # test basics
        # make sure to materialize the list, as this is a generator
        self.assertSequenceEqual(
            ["abc", "defg", "hijkl", "mnopqr", "stuvwxyz"],
            split_fixed_length(test_string_1, [3, 4, 5, 6, 8]),
        )
        self.assertSequenceEqual(
            ["abc", "defg", "hijkl", "mnopqr", "stuvwxy", "z"],
            split_fixed_length(test_string_1, [3, 4, 5, 6, 7]),
        )
        self.assertRaises(
            AssertionError, split_fixed_length, test_string_1, [3, 4, 5, 6, 7, 8]
        )

        # test string strip options
        test_string_2 = "The cow jumps over the moon"
        self.assertSequenceEqual(
            ["The", "cow", "jumps", "over", "the", "moon"],
            split_fixed_length(test_string_2, [4, 4, 6, 5, 4]),
        )
        self.assertSequenceEqual(
            ["The ", "cow ", "jumps ", "over ", "the ", "moon"],
            split_fixed_length(test_string_2, [4, 4, 6, 5, 4], strip=False),
        )

    def test_ifna(self):
        self.assertEqual(1, ifna(1, 2))
        self.assertEqual(2, ifna(None, 2))
        self.assertEqual(2, ifna(NaN, 2))
        self.assertEqual(2, ifna(pd.NaT, 2))

        self.assertEqual("1", ifna("1", "2"))
        self.assertEqual("", ifna("", "2"))  # Test with a value that resolves to False
        self.assertEqual("2", ifna(None, "2"))

        self.assertEqual(True, ifna(True, False))
        self.assertEqual(False, ifna(False, True))
        self.assertEqual(False, ifna(None, False))

        self.assertEqual(dt.date(1999, 12, 31), ifna(None, dt.date(1999, 12, 31)))
        self.assertEqual(
            dt.date(2000, 1, 1), ifna(dt.date(2000, 1, 1), dt.date(1999, 12, 31))
        )

    def test_is_leap_year(self):
        self.assertTrue(is_leap_year(2000))
        self.assertFalse(is_leap_year(2100))
        self.assertTrue(is_leap_year(2020))
        self.assertFalse(is_leap_year(2018))
        self.assertFalse(is_leap_year(2021))

    def test_add_months(self):
        ref_date = dt.date(2020, 3, 31)

        # test identity
        self.assertEqual(ref_date, add_months(ref_date, 0))

        # test addition
        self.assertEqual(dt.date(2020, 4, 30), add_months(ref_date, 1))
        self.assertEqual(dt.date(2021, 2, 28), add_months(ref_date, 11))
        self.assertEqual(dt.date(2023, 5, 31), add_months(ref_date, 38))
        self.assertEqual(dt.date(2024, 2, 29), add_months(ref_date, 47))

        # test subtraction
        self.assertEqual(dt.date(2020, 2, 29), add_months(ref_date, -1))
        self.assertEqual(dt.date(2019, 12, 31), add_months(ref_date, -3))
        self.assertEqual(dt.date(2018, 12, 31), add_months(ref_date, -15))
        self.assertEqual(dt.date(2018, 11, 30), add_months(ref_date, -16))
        self.assertEqual(dt.date(2017, 2, 28), add_months(ref_date, -37))

    def test_get_quarter(self):
        self.assertEqual(1, get_quarter(dt.date(2020, 1, 1)))
        self.assertEqual(1, get_quarter(dt.date(2020, 2, 1)))
        self.assertEqual(1, get_quarter(dt.date(2020, 3, 1)))
        self.assertEqual(2, get_quarter(dt.date(2020, 4, 1)))
        self.assertEqual(2, get_quarter(dt.date(2020, 5, 1)))
        self.assertEqual(2, get_quarter(dt.date(2020, 6, 1)))
        self.assertEqual(3, get_quarter(dt.date(2020, 7, 1)))
        self.assertEqual(3, get_quarter(dt.date(2020, 8, 1)))
        self.assertEqual(3, get_quarter(dt.date(2020, 9, 1)))
        self.assertEqual(4, get_quarter(dt.date(2020, 10, 1)))
        self.assertEqual(4, get_quarter(dt.date(2020, 11, 1)))
        self.assertEqual(4, get_quarter(dt.date(2020, 12, 1)))


if __name__ == "__main__":
    unittest.main()
