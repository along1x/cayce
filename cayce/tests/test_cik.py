import unittest as ut
import cayce.cik as cik


class TestCik(ut.TestCase):
    def test_get_ticker_to_cik_map(self):
        mappings = cik.get_ticker_to_cik_map()
        assert isinstance(mappings, dict)
        # assumption: the world's largest company today won't disappear anytime soon
        assert "AAPL" in mappings
        # assumption: CIK codes will always be numeric
        assert mappings["AAPL"].isdigit()
        print(mappings["AAPL"])


if __name__ == "__main__":
    ut.main()
