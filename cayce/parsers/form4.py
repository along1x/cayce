import datetime as dt
import logging
import re
from typing import Tuple

from lxml import etree
from lxml.etree import Element
import pandas as pd

from cayce.log import get_logger


_LOG = get_logger(__name__, console_level=logging.ERROR)


def _parse_owner(owner_element: Element):
    owner_name = None
    is_director = is_officer = istenpercentowner = isother = False
    for child in owner_element:
        tag = child.tag.lower()
        if tag == "reportingownerid":
            for detail in child:
                if detail.tag.lower() == "rptownername":
                    owner_name = detail.text
        elif tag == "reportingownerrelationship":
            for relationship in child:
                relationship_tag = relationship.tag.lower()
                flag = relationship.text == "1"
                if relationship_tag == "isdirector":
                    is_director = flag
                elif relationship_tag == "isofficer":
                    is_officer = flag
                elif relationship_tag == "istenpercentowner":
                    istenpercentowner = flag
                elif relationship_tag == "isother":
                    isother = flag
    return owner_name, is_director, is_officer, istenpercentowner, isother


def _parse_transaction(transaction_element: Element):
    def _get_string(element: Element) -> str:
        for child in element:
            tag = child.tag.lower()
            if tag == "value":
                return child.text
        _LOG.info(f"{element.tag} had no value")
        return None

    def _get_float(element: Element) -> float:
        value = _get_string(element)
        return float(value) if value is not None else None

    for child in transaction_element:
        tag = child.tag.lower()
        if tag == "transactiondate":
            transaction_date = _get_string(child)
            transaction_date = dt.datetime.strptime(transaction_date, "%Y-%m-%d").date()
        elif tag == "transactionamounts":
            for elem in child:
                attribute_tag = elem.tag.lower()
                if attribute_tag == "transactionshares":
                    transaction_shares = _get_float(elem)
                elif attribute_tag == "transactionpricepershare":
                    price = _get_float(elem)
                elif attribute_tag == "transactionacquireddisposedcode":
                    acquired_disposed = _get_string(elem)
        elif tag == "posttransactionamounts":
            for elem in child:
                if elem.tag.lower() == "sharesownedfollowingtransaction":
                    post_transaction_shares = _get_float(elem)

    trade_direction = 1 if acquired_disposed == "A" else -1
    return (
        transaction_date,
        transaction_shares * trade_direction,
        price,
        post_transaction_shares,
    )


def parse(file_name: str) -> pd.DataFrame:
    parser = etree.XMLParser(recover=True)
    doc = etree.parse(file_name, parser)

    transactions = []
    for child in doc.getroot():
        tag = child.tag.lower()
        if tag == "periodofreport":
            report_date = dt.datetime.strptime(child.text, "%Y-%m-%d").date()
        elif tag == "issuer":
            for elem in child:
                if elem.tag.lower() == "issuertradingsymbol":
                    ticker = elem.text
        elif tag == "reportingowner":
            owner_details = _parse_owner(child)
        elif tag == "nonderivativetable":
            for elem in child:
                if elem.tag.lower() == "nonderivativetransaction":
                    transactions.append(_parse_transaction(elem))

    form4_df = pd.DataFrame(
        transactions,
        columns=["transaction_date", "shares", "price", "post_transaction_shares"],
    )
    form4_df["report_date"] = report_date
    form4_df["ticker"] = ticker

    attribute_columns = ["owner", "director", "officer", "tenpercentowner", "other"]
    for attribute, value in zip(attribute_columns, owner_details,):
        form4_df[attribute] = value

    return form4_df
