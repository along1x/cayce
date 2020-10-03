from collections import namedtuple
import datetime as dt
import re
from typing import Any, Dict, Union, Tuple

from bs4 import BeautifulSoup
from bs4.element import Tag
import pandas as pd


def _parse_relevant_contexts(
    soup: BeautifulSoup,
) -> Dict[str, Union[dt.date, Tuple[dt.date, dt.date]]]:
    """
    Get a list of contexts that provide data on a date period
    (today, QTD, YTD, etc)
    """
    re_date_strip = re.compile("[^\d]+")

    def _parse_date(date_str: str) -> dt.date:
        stripped_date_str = re_date_strip.sub("", date_str)[:8]
        return dt.datetime.strptime(stripped_date_str, "%Y%m%d").date()

    # get relevant contexts
    context_elements = soup.find_all(
        name=re.compile("context", re.IGNORECASE | re.MULTILINE)
    )
    relevant_contexts = {}
    for context_element in context_elements:
        context_id = context_element.attrs["id"]

        entity_element = context_element.find("entity")
        if entity_element is not None:
            if entity_element.find("segment") is not None:
                # don't care about contexts that apply to a given segment
                continue

        period_element = context_element.find("period")
        if period_element is not None:
            instant_element = period_element.find("instant")
            if instant_element is not None:
                relevant_contexts[context_id] = _parse_date(instant_element.text)
            else:
                start_date_element = period_element.find("startdate")
                start_date = (
                    _parse_date(start_date_element.text)
                    if start_date_element is not None
                    else None
                )

                end_date_element = period_element.find("enddate")
                end_date = (
                    _parse_date(end_date_element.text)
                    if end_date_element is not None
                    else None
                )

                relevant_contexts[context_id] = (start_date, end_date)
    return relevant_contexts


ParsedTag = namedtuple(
    "ParsedTag", ["period_start", "period_end", "attribute", "value", "currency"]
)


def _parse_tag(
    tag: Tag, ticker: str, relevant_contexts: Dict[str, Tuple[dt.date, dt.date]],
) -> ParsedTag:
    """
    Take a tag and pull out the context, value, and currency (if applicable)
    """
    if "contextref" not in tag.attrs or tag["contextref"] not in relevant_contexts:
        return None

    # get context period
    period = relevant_contexts[tag["contextref"]]
    start_date, end_date = (None, period) if type(period) == dt.date else period
    # get currency, if available
    currency = tag["unitref"].upper() if "unitref" in tag.attrs else None

    value = float(tag.text) if tag.text.isnumeric() else tag.text
    return ParsedTag(
        period_start=start_date,
        period_end=end_date,
        attribute=tag.name[len(ticker) + 1 :],
        value=value,
        currency=currency,
    )


def _extract_company_specific_attributes(
    ticker: str,
    soup: BeautifulSoup,
    relevant_contexts: Dict[str, Tuple[dt.date, dt.date]],
) -> pd.DataFrame:
    """
    Find all bespoke tags for a company and extract numeric values
    into a denormalized name/value DataFrame
    """
    company_specific_tags = soup.find_all(
        name=re.compile(f"{ticker}:.*", re.IGNORECASE)
    )

    rows = []
    for tag in company_specific_tags:
        if tag.text.isnumeric():
            parsed_tag = _parse_tag(tag, ticker, relevant_contexts)
            if parsed_tag is not None:
                rows.append(
                    [
                        ticker,
                        parsed_tag.period_start,
                        parsed_tag.period_end,
                        parsed_tag.attribute,
                        parsed_tag.value,
                        parsed_tag.currency,
                    ]
                )
    return pd.DataFrame(
        rows,
        columns=[
            "Ticker",
            "PeriodStart",
            "PeriodEnd",
            "AttributeName",
            "AttributeValue",
            "Currency",
        ],
    )

