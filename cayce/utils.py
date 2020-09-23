"""
utils.py is a kitchen sink of helper functions that I don't have a better place for for now.
If this gets large enough, I'll separate out into reference_date/int/float/string utils...
"""
import datetime as dt
from math import ceil
from typing import Any, List

from pandas import isna


def split_fixed_length(s: str, lengths: List[int], strip: bool = True) -> List[str]:
    """
    Take a string and split it into fixed-length chunks

    Args:
        s (str): The string
        lengths (List[int]): 
            Ordered list of each fixed-length chunk size
            sum(lengths) <= len(s)
            if sum(lengths) < len(s), the last element 
            returned will be the remainder of the string
        strip (bool, optional): 
            Do I strip whitespace for each parsed element? 
            Defaults to True.
    """
    # fmt: off
    assert sum(lengths) <= len(s), \
        'Sum of each chunk length is greater than the length of the input string'
    # fmt: on

    def get_value(v):
        return v.strip() if strip else v

    start_idx = 0
    chunks = []
    for length in lengths:
        end_idx = start_idx + length
        chunks.append(get_value(s[start_idx:end_idx]))
        start_idx = end_idx

    if end_idx < len(s):
        chunks.append(get_value(s[end_idx:]))

    return chunks


def ifna(value: Any, default: Any) -> Any:
    """
    If a value is NaN, None, or NaT, then return a default value

    Args:
        value (Any): The value
        default (Any): The default
    """
    return value if not isna(value) else default


def is_leap_year(year: int) -> bool:
    """Determine if a year is a leap year"""
    if year % 4 == 0:
        if year % 100 == 0:
            return year % 400 == 0
        else:
            return True
    else:
        return False


def add_months(reference_date: dt.date, months: int) -> dt.date:
    """Find a new date that is `months` months from `reference_date`"""
    target_month = reference_date.month + months

    year = reference_date.year + target_month // 12
    month = target_month % 12
    if month == 0:
        month = 12
        year -= 1
    day = reference_date.day

    # if the reference reference_date is EOM, make sure the adjusted date is EOM also
    is_leap = is_leap_year(year)
    if month == 2:
        if is_leap and day > 29:
            day = 29
        elif not is_leap and day > 28:
            day = 28
    if month in [4, 6, 9, 11] and day > 30:
        day = 30

    return dt.date(year, month, day)


def get_quarter(reference_date: dt.date) -> int:
    """Get the quarter (1-4) of the specified date"""
    return int(ceil(reference_date.month / 3))


def get_start_of_quarter(reference_date: dt.date) -> dt.date:
    year = reference_date.year
    month = (get_quarter(reference_date) - 1) * 3 + 1
    return dt.date(year, month, 1)

