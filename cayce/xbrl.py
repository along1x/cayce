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

        self._parse_relevant_contexts()

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
        self, attributes: List[str], numeric_only: bool = True
    ):
        """
        Get a normalized DataFrame of all attributes provided from the pre-loaded
        BeautifulSoup object.  If numeric_only, skip any non-numeric attributes and
        parse the values captured as floats
        """
        rows = []
        processed_elements = set()
        for tag_label in attributes:
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

    def parse_dei_attributes(self) -> pd.DataFrame:
        attributes = [
            "dei:DocumentType",
            "dei:DocumentPeriodEndDate",
            "dei:EntityRegistrantName",
            "dei:TradingSymbol",
            "dei:SecurityExchangeName",
            "dei:EntityCommonStockSharesOutstanding",
        ]
        # These attributes will be text
        return self._get_attribute_values_df(attributes, False)

    def parse_income_statement(self) -> pd.DataFrame:
        attributes = [
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
        income_statement_df = self._get_attribute_values_df(attributes)
        return income_statement_df

    def parse_comprehensive_income(self) -> pd.DataFrame:
        attributes = [
            "us-gaap:OtherComprehensiveIncomeForeignCurrencyTransactionAndTranslationAdjustmentNetOfTaxPortionAttributableToParent",
            "us-gaap:OtherComprehensiveIncomeLossForeignCurrencyTransactionAndTranslationReclassificationAdjustmentFromAOCIRealizedUponSaleOrLiquidationBeforeTax"
            "us-gaap:OtherComprehensiveIncomeLossPensionAndOtherPostretirementBenefitPlansAdjustmentNetOfTax",
            "us-gaap:OtherComprehensiveIncomeUnrealizedHoldingGainLossOnSecuritiesArisingDuringPeriodNetOfTax",
            "us-gaap:OtherComprehensiveIncomeLossNetOfTax",
            "us-gaap:ComprehensiveIncomeNetOfTax",
        ]
        comprehensive_income_df = self._get_attribute_values_df(attributes)
        return comprehensive_income_df

    def parse_balance_sheet(self) -> pd.DataFrame:
        attributes = [
            "us-gaap:AllowanceForDoubtfulAccountsReceivableCurrent",
            "us-gaap:AvailableForSaleSecuritiesAmortizedCost",
            "us-gaap:CashAndCashEquivalentsAtCarryingValue",
            "us-gaap:AvailableForSaleSecuritiesCurrent",
            "us-gaap:AccountsReceivableNetCurrent",
            "us-gaap:PrepaidExpenseAndOtherAssetsCurrent",
            "us-gaap:AssetsOfDisposalGroupIncludingDiscontinuedOperationCurrent",
            "us-gaap:AssetsCurrent",
            "us-gaap:MarketableSecuritiesNoncurrent",
            "us-gaap:PropertyPlantAndEquipmentNet",
            "us-gaap:Goodwill",
            "us-gaap:IntangibleAssetsNetExcludingGoodwill",
            "us-gaap:OperatingLeaseRightOfUseAsset",
            "us-gaap:OtherAssetsNoncurrent",
            "us-gaap:DisposalGroupIncludingDiscontinuedOperationOtherNoncurrentAssets",
            "us-gaap:Assets",
            "us-gaap:LongTermDebtAndCapitalLeaseObligationsCurrent",
            "us-gaap:AccountsPayableCurrent",
            "us-gaap:AccruedLiabilitiesCurrent",
            "us-gaap:DeferredRevenueCurrent",
            "us-gaap:LiabilitiesOfDisposalGroupIncludingDiscontinuedOperationCurrent",
            "us-gaap:LiabilitiesCurrent",
            "us-gaap:LongTermDebtAndCapitalLeaseObligations",
            "us-gaap:DeferredRevenueNoncurrent",
            "us-gaap:DeferredIncomeTaxLiabilities",
            "us-gaap:OperatingLeaseLiabilityNoncurrent",
            "us-gaap:OtherLiabilitiesNoncurrent",
            "us-gaap:LiabilitiesOfDisposalGroupIncludingDiscontinuedOperationNoncurrent",
            "us-gaap:Liabilities",
            "us-gaap:CommitmentsAndContingencies",
            "us-gaap:CommonStockParOrStatedValuePerShare",
            "us-gaap:CommonStockSharesAuthorized",
            "us-gaap:CommonStockSharesIssued",
            "us-gaap:CommonStockSharesOutstanding",
            "us-gaap:TreasuryStockShares",
            "us-gaap:CommonStockValue",
            "us-gaap:AdditionalPaidInCapital",
            "us-gaap:TreasuryStockValue",
            "us-gaap:AccumulatedOtherComprehensiveIncomeLossNetOfTax",
            "us-gaap:RetainedEarningsAccumulatedDeficit",
            "us-gaap:StockholdersEquity",
            "us-gaap:MinorityInterest",
            "us-gaap:MembersEquity",
            "us-gaap:LiabilitiesAndStockholdersEquity",
        ]
        balance_sheet_df = self._get_attribute_values_df(attributes)
        return balance_sheet_df

    def parse_cash_flows(self):
        attributes = [
            "us-gaap:IncomeLossFromContinuingOperations",
            "us-gaap:Depreciation",
            "us-gaap:AmortizationOfIntangibleAssets",
            "us-gaap:ShareBasedCompensation",
            "us-gaap:AmortizationOfFinancingCosts",
            "us-gaap:DeferredIncomeTaxExpenseBenefit",
            "us-gaap:GainsLossesOnExtinguishmentOfDebt",
            "us-gaap:OtherNoncashIncomeExpense",
            "us-gaap:IncreaseDecreaseInAccountsReceivable",
            "us-gaap:IncreaseDecreaseInPrepaidDeferredExpenseAndOtherAssets",
            "us-gaap:IncreaseDecreaseInAccountsPayableTrade",
            "us-gaap:IncreaseDecreaseInAccruedLiabilities",
            "us-gaap:IncreaseDecreaseInDeferredRevenue",
            "us-gaap:NetCashProvidedByUsedInContinuingOperations",
            "us-gaap:CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations",
            "us-gaap:NetCashProvidedByUsedInOperatingActivities",
            "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
            "us-gaap:ProceedsFromDivestitureOfBusinesses",
            "us-gaap:PaymentsToAcquireInvestments",
            "us-gaap:ProceedsFromSaleMaturityAndCollectionsOfInvestments",
            "us-gaap:PaymentsForProceedsFromOtherInvestingActivities",
            "us-gaap:NetCashProvidedByUsedInInvestingActivities",
            "us-gaap:RepaymentsOfLongTermDebtAndCapitalSecurities",
            "us-gaap:ProceedsFromEquityMethodInvestmentDividendsOrDistributionsReturnOfCapital",
            "us-gaap:PaymentsForRepurchaseOfCommonStock",
            "us-gaap:ProceedsFromIssuanceOfSharesUnderIncentiveAndShareBasedCompensationPlansIncludingStockOptions",
            "us-gaap:ProceedsFromLinesOfCredit",
            "us-gaap:RepaymentsOfUnsecuredDebt",
            "us-gaap:PaymentsRelatedToTaxWithholdingForShareBasedCompensation",
            "us-gaap:ProceedsFromPaymentsForOtherFinancingActivities",
            "us-gaap:NetCashProvidedByUsedInFinancingActivities",
            "us-gaap:EffectOfExchangeRateOnCashAndCashEquivalents",
            "us-gaap:CashAndCashEquivalentsPeriodIncreaseDecrease",
            "us-gaap:CashAndCashEquivalentsAtCarryingValue",
        ]
        cash_flow_statement_df = self._get_attribute_values_df(attributes)
        return cash_flow_statement_df

    def parse_all(self) -> pd.DataFrame:
        """
        Parse as much data out of this document as possible, and return all of it
        in one huge normalized DataFrame
        """
        dfs = [
            self.parse_dei_attributes(),
            self.parse_income_statement(),
            self.parse_comprehensive_income(),
            self.parse_balance_sheet(),
            self.parse_cash_flows(),
        ]
        return pd.concat(dfs, ignore_index=True)
