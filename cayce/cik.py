import requests
from typing import Dict


def get_ticker_to_cik_map() -> Dict[str, str]:
    url = "https://www.sec.gov/include/ticker.txt"
    cik_codes = requests.get(url).content.decode("utf-8")

    cik_code_map = [line.split("\t") for line in cik_codes.splitlines()]
    return {entry[0].upper(): entry[1] for entry in cik_code_map}
