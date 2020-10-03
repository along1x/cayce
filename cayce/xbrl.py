from collections import namedtuple
import datetime as dt
import re
from typing import Any, Dict, Union, Tuple

from bs4 import BeautifulSoup
from bs4.element import Tag
import pandas as pd


class FinancialDocumentParser:
    ParsedTag = namedtuple(
        "ParsedTag", ["period_start", "period_end", "attribute", "value", "currency"]
    )

    def __init__(self, ticker: str, file_name: str):
        self._ticker = ticker

        with open(file_name, mode="r") as fin:
            contents = fin.read()
        self._soup = BeautifulSoup(contents, "lxml")

    def _parse_relevant_contexts(self):
        """
        Get a list of contexts that provide data on a date period
        (today, QTD, YTD, etc)
        Store contexts as a class variable
        """
        re_date_strip = re.compile("[^\d]+")

        def _parse_date(date_str: str) -> dt.date:
            stripped_date_str = re_date_strip.sub("", date_str)[:8]
            return dt.datetime.strptime(stripped_date_str, "%Y%m%d").date()

        # get relevant contexts
        context_elements = self._soup.find_all(
            name=re.compile("context", re.IGNORECASE | re.MULTILINE)
        )
        self._relevant_contexts = {}
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
                    self._relevant_contexts[context_id] = _parse_date(
                        instant_element.text
                    )
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

                    self._relevant_contexts[context_id] = (start_date, end_date)

    def _parse_tag(self, tag: Tag) -> ParsedTag:
        """
        Take a tag and pull out the context, value, and currency (if applicable)
        """
        if (
            "contextref" not in tag.attrs
            or tag["contextref"] not in self._relevant_contexts
        ):
            return None

        # get context period
        period = self._relevant_contexts[tag["contextref"]]
        start_date, end_date = (None, period) if type(period) == dt.date else period
        # get currency, if available
        currency = tag["unitref"].upper() if "unitref" in tag.attrs else None

        value = float(tag.text) if tag.text.isnumeric() else tag.text
        return self.ParsedTag(
            period_start=start_date,
            period_end=end_date,
            attribute=tag.name[len(self._ticker) + 1 :],
            value=value,
            currency=currency,
        )

    def _get_attribute_values_df(
        self, tag_labels: List[str], numeric_only: bool = True
    ):
        rows = []
        processed_elements = set()
        for tag_label in tag_labels:
            tags = self._soup.find_all(name=re.compile(tag_label, re.IGNORECASE))

            for tag in tags:
                if not numeric_only or tag.text.isnumeric():
                    # not bothering to track any attributes that are free-form text for now
                    if (
                        "contextref" in tag.attrs
                        and tag["contextref"] in self._relevant_contexts
                    ):
                        element_id = (tag_label, tag["contextref"])
                        if element_id in processed_elements:
                            continue
                        processed_elements.add(element_id)

                        # get context period
                        period = self._relevant_contexts[tag["contextref"]]
                        start_date, end_date = (
                            (None, period) if type(period) == dt.date else period
                        )
                        # get currency, if found
                        currency = (
                            tag["unitref"].upper() if "unitref" in tag.attrs else None
                        )

                        value = float(tag.text)
                        rows.append(
                            [
                                start_date,
                                end_date,
                                tag.name.split(":")[1],
                                value,
                                currency,
                            ]
                        )
        df = pd.DataFrame(
            rows,
            columns=[
                "PeriodStart",
                "PeriodEnd",
                "AttributeName",
                "AttributeValue",
                "Currency",
            ],
        )
        df["Ticker"] = self._ticker
        return df

    def get_bespoke_attributes_df(self) -> pd.DataFrame:
        """
        Find all bespoke tags for a company and extract numeric values
        into a denormalized name/value DataFrame
        """
        company_specific_tags = [f"{self._ticker}:.*"]
        return self._get_attribute_values_df(company_specific_tags)

    def get_dei_attributes_df(self) -> pd.DataFrame:
        header_tag_labels = [
            "dei:DocumentType",
            "dei:DocumentPeriodEndDate",
            "dei:EntityRegistrantName",
            "dei:TradingSymbol",
            "dei:SecurityExchangeName",
            "dei:EntityCommonStockSharesOutstanding",
        ]
        # These attributes will be text
        return self._get_attribute_values_df(header_tag_labels, False)

    def get_income_statement_df(self) -> pd.DataFrame:
        income_statement_attributes = [
            "us-gaap:Revenues",
            "us-gaap:CostOfGoodsAndServicesSoldAmortization",
            "us-gaap:CostOfGoodsAndServicesSold",
            "us-gaap:GrossProfit",
            "us-gaap:ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
            "us-gaap:SellingAndMarketingExpense",
            "us-gaap:GeneralAndAdministrativeExpense",
            "us-gaap:DepreciationAndAmortization",
            "us-gaap:BusinessCombinationAcquisitionRelatedCosts",
            "us-gaap:RestructuringAndRelatedCostIncurredCost",
            "us-gaap:OperatingExpenses",
            "us-gaap:OperatingIncomeLoss",
            "us-gaap:InvestmentIncomeInterest",
            "us-gaap:InterestExpense",
            "us-gaap:OtherNonoperatingIncomeExpense",
            "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
            "us-gaap:IncomeTaxExpenseBenefit",
            "us-gaap:IncomeLossFromContinuingOperations",
            "us-gaap:IncomeLossFromDiscontinuedOperationsNetOfTaxAttributableToReportingEntity",
            "us-gaap:NetIncomeLoss",
            "us-gaap:IncomeLossFromContinuingOperationsPerBasicShare",
            "us-gaap:DiscontinuedOperationIncomeLossFromDiscontinuedOperationNetOfTaxPerBasicShare",
            "us-gaap:EarningsPerShareBasic",
            "us-gaap:IncomeLossFromContinuingOperationsPerDilutedShare",
            "us-gaap:DiscontinuedOperationIncomeLossFromDiscontinuedOperationNetOfTaxPerDilutedShare",
            "us-gaap:EarningsPerShareDiluted",
            "us-gaap:WeightedAverageNumberOfSharesOutstandingBasic",
            "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding",
        ]
        income_statement_df = _get_attribute_values_df(income_statement_attributes)
        return income_statement_df
