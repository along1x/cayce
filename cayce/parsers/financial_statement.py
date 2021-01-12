import datetime as dt
import logging
import re
from typing import Tuple

from lxml import etree
from lxml.etree import Element
import pandas as pd

from cayce.log import get_logger


_LOG = get_logger(__name__, console_level=logging.ERROR)


def _strip_ns(tag: str) -> str:
    """Remove namespace information from an XML tag"""
    return tag[tag.find("}") + 1 :]


def _find_tag(root_element, tag: str) -> Element:
    """Find a child element with the specified tag (ignoring namespace)"""
    for child_element in root_element:
        if _strip_ns(child_element.tag).lower() == tag.lower():
            return child_element
    return None


def _parse_unit(unit_element: Element) -> Tuple[str, str]:
    """Parse a unit XML element into a more readable form"""

    def clean_measure(x: str) -> str:
        x = x.upper().strip()
        if ":" in x:
            return x.split(":")[-1]
        return x

    unit_id = unit_element.attrib["id"].upper()
    measure_element = _find_tag(unit_element, "measure")
    if measure_element is not None:
        return unit_id, clean_measure(measure_element.text)
    else:
        divide_element = _find_tag(unit_element, "divide")
        if divide_element is not None:
            numerator_element = _find_tag(divide_element, "unitNumerator")
            denominator_element = _find_tag(divide_element, "unitDenominator")
            if numerator_element is not None and denominator_element is not None:
                numerator_measure = _find_tag(numerator_element, "measure")
                numerator = clean_measure(
                    numerator_measure.text
                    if numerator_measure is not None
                    else numerator_element.text
                )
                denominator_measure = _find_tag(denominator_element, "measure")
                denominator = clean_measure(
                    denominator_measure.text
                    if denominator_measure is not None
                    else denominator_element.text
                )
                return unit_id, f"{numerator}/{denominator}"
    _LOG.warn(f"Something screwed up with {unit_element.tag}")
    return None


def _parse_context(context_element: Element):
    """
    Parse a context which represents a reporting period
    (today, QTD, YTD, etc)
    """
    re_date_strip = re.compile("[^\d]+")

    def _parse_date(date_str: str) -> dt.date:
        stripped_date_str = re_date_strip.sub("", date_str)[:8]
        return dt.datetime.strptime(stripped_date_str, "%Y%m%d").date()

    context_id = context_element.attrib["id"]

    entity_element = _find_tag(context_element, "entity")
    if entity_element is not None:
        if _find_tag(entity_element, "segment") is not None:
            _LOG.warn(f"Ignoring context {context_id}; refers to a specific segment")
            # don't care about contexts that apply to a given segment
            return None

    period_element = _find_tag(context_element, "period")
    if period_element is not None:
        instant_element = _find_tag(period_element, "instant")
        if instant_element is not None:
            return context_id, None, _parse_date(instant_element.text)
        else:
            start_date_element = _find_tag(period_element, "startdate")
            start_date = (
                _parse_date(start_date_element.text)
                if start_date_element is not None
                else None
            )

            end_date_element = _find_tag(period_element, "enddate")
            end_date = (
                _parse_date(end_date_element.text)
                if end_date_element is not None
                else None
            )

            return context_id, start_date, end_date

    _LOG.warn(f"Ignoring context {context_id}; has no period defined")
    return None


def _parse_attribute(element: Element):
    """
    Take an XML Element and pull out the tag (attribute name), context, value, and unit (if applicable)
    """
    if "contextRef" not in element.attrib or element.text is None:
        _LOG.warn(
            f"Ignoring attribute {_strip_ns(element.tag)}; has no context or value"
        )
        return None

    attribute_name = _strip_ns(element.tag)
    context_id = element.attrib["contextRef"]
    unit_id = element.attrib["unitRef"].upper() if "unitRef" in element.attrib else None
    value_str = element.text.strip()
    value = float(value_str) if value_str.isnumeric() else value_str
    return context_id, attribute_name, value, unit_id


def parse(file_name: str) -> pd.DataFrame:
    """
    Parse all attributes from a financial statement (10-K and 10-Q only)
    and return as a DataFrame

    Args:
        file_name (str): Local file name for XBLR financial statement
    """
    parser = etree.XMLParser(recover=True)
    doc = etree.parse(file_name, parser)

    units = []
    contexts = []
    attributes = []
    for child in doc.getroot():
        # some xblr docs have a tag that is interpretted as a cython comment function
        if isinstance(child.tag, str):
            tag = _strip_ns(child.tag).lower()
            if tag == "unit":
                unit = _parse_unit(child)
                if unit is not None:
                    units.append(unit)
            elif tag == "context":
                context = _parse_context(child)
                if context is not None:
                    contexts.append(context)
            else:
                # assume its some type of attribute
                attribute = _parse_attribute(child)
                if attribute is not None:
                    attributes.append(attribute)

    units_df = pd.DataFrame(units, columns=["unit_id", "unit"])
    contexts_df = pd.DataFrame(
        contexts, columns=["context_id", "period_start", "period_end"]
    )
    attributes_df = pd.DataFrame(
        attributes,
        columns=["context_id", "attribute_name", "attribute_value", "unit_id"],
    )

    statement_df = attributes_df.merge(contexts_df).merge(units_df, how="left")
    statement_df.loc[pd.isna(statement_df["unit"]), "unit"] = None

    output_columns = [
        "period_start",
        "period_end",
        "attribute_name",
        "attribute_value",
        "unit",
    ]
    return statement_df[output_columns]
