from collections import namedtuple
import datetime as dt
import re
from typing import Any, Dict, Iterable, Set, Tuple, Union

from bs4 import BeautifulSoup
from bs4.element import Tag
import pandas as pd

from cayce.log import get_logger

# TODO: Add proper logging
_LOG = get_logger(__name__)


class FinancialStatementsParser:
    """
    Parser for 10-Q and 10-K filings
    """

    ParsedTag = namedtuple(
        "ParsedTag", ["period_start", "period_end", "attribute", "value", "unit"]
    )

    def __init__(self, ticker: str, file_name: str):
        self._ticker = ticker

        with open(file_name, mode="r") as fin:
            contents = fin.read()
        self._xbrl_soup = BeautifulSoup(contents, "lxml")

        self._parse_relevant_contexts()
        self._parse_units()

    def _get_re(self, pattern: str) -> re.Pattern:
        return re.compile(pattern, re.IGNORECASE | re.MULTILINE)

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
        context_elements = self._xbrl_soup.find_all(self._get_re("context"))
        self._relevant_contexts = {}
        for context_element in context_elements:
            context_id = context_element.attrs["id"]

            entity_element = context_element.find(self._get_re("entity"))
            if entity_element is not None:
                # fmt: off
                if entity_element.find(self._get_re("segment")) is not None:
                    # don't care about contexts that apply to a given segment
                    continue
                # fmt: on

            period_element = context_element.find(self._get_re("period"))
            if period_element is not None:
                instant_element = period_element.find(self._get_re("instant"))
                if instant_element is not None:
                    self._relevant_contexts[context_id] = _parse_date(
                        instant_element.text
                    )
                else:
                    start_date_element = period_element.find(self._get_re("startdate"))
                    start_date = (
                        _parse_date(start_date_element.text)
                        if start_date_element is not None
                        else None
                    )

                    end_date_element = period_element.find(self._get_re("enddate"))
                    end_date = (
                        _parse_date(end_date_element.text)
                        if end_date_element is not None
                        else None
                    )

                    self._relevant_contexts[context_id] = (start_date, end_date)

    def _parse_units(self):
        """
        Get a list of unit definitions, store in a class variable
        """

        def clean_measure(x: str) -> str:
            x = x.upper()
            if ":" in x:
                return x.split(":")[-1]
            return x

        unit_elements = self._xbrl_soup.find_all(self._get_re("^(xbrli:)?unit$"))

        self._units = {}
        for unit_element in unit_elements:
            unit_id = unit_element.attrs["id"].upper()

            measure_element = unit_element.find(self._get_re("measure"))
            if measure_element is not None:
                self._units[unit_id] = clean_measure(measure_element.text)
            else:
                divide_element = unit_element.find("divide")
                if divide_element is not None:
                    numerator_element = divide_element.find(
                        self._get_re("unitnumerator")
                    )
                    denominator_element = divide_element.find(
                        self._get_re("unitdenominator")
                    )
                    if (
                        numerator_element is not None
                        and denominator_element is not None
                    ):
                        numerator = clean_measure(numerator_element.text)
                        denominator = clean_measure(denominator_element.text)
                        self._units[unit_id] = f"{numerator}/{denominator}"

    def _parse_tag(self, tag: Tag) -> ParsedTag:
        """
        Take a tag and pull out the context, value, and unit (if applicable)
        """
        if (
            "contextref" not in tag.attrs
            or tag["contextref"] not in self._relevant_contexts
        ):
            return None

        # get context period
        period = self._relevant_contexts[tag["contextref"]]
        start_date, end_date = (None, period) if type(period) == dt.date else period
        # get unit, if available
        unit = tag["unitref"].upper() if "unitref" in tag.attrs else None
        if unit is not None:
            if unit in self._units:
                unit = self._units[unit]

        value = float(tag.text) if tag.text.isnumeric() else tag.text
        return self.ParsedTag(
            period_start=start_date,
            period_end=end_date,
            attribute=tag.name.split(":")[1],
            value=value,
            unit=unit,
        )

    def _get_attribute_values_df(
        self, attributes: Iterable[str], numeric_only: bool = True
    ):
        """
        Get a normalized DataFrame of all attributes provided from the pre-loaded
        BeautifulSoup object.  If numeric_only, skip any non-numeric attributes and
        parse the values captured as floats
        """
        rows = []
        processed_elements = set()
        for tag_label in attributes:
            tags = self._xbrl_soup.find_all(self._get_re(tag_label))

            for tag in tags:
                if not numeric_only or tag.text.isnumeric():
                    parsed_tag = self._parse_tag(tag)
                    if parsed_tag is not None:
                        rows.append(
                            [
                                parsed_tag.period_start,
                                parsed_tag.period_end,
                                parsed_tag.attribute,
                                parsed_tag.value,
                                parsed_tag.unit,
                            ]
                        )
        df = pd.DataFrame(
            rows,
            columns=[
                "period_start",
                "period_end",
                "attribute_name",
                "attribute_value",
                "unit",
            ],
        )
        df["Ticker"] = self._ticker
        return df

    def parse_bespoke_attributes(self) -> pd.DataFrame:
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

    def get_other_gaap_attributes(self, exclude_tag_names: Set[str]) -> pd.DataFrame:
        """
        Provide a dictionary of tags you're parsing elsewhere, then grab
        every other tag of the pattern us-gaap:.* and parse it.

        This is intended to be a catch-all, which will highlight attributes
        that perhaps should be classified as part of the income statement,
        balance sheet or cash flow statement.

        Args:
            exclude_tag_names (Set[str]): 
                A set of every tag name that will be parsed elsewhere
        """
        # find all us-gaap tags
        tags = self._xbrl_soup.find_all(self._get_re("us-gaap:.*"))

        # identify which tags haven't already been parsed elsewhere
        tag_names_to_extract = set()
        for tag in tags:
            if (
                "contextref" in tag.attrs
                and tag["contextref"] in self._relevant_contexts
            ):
                trimmed_tag_name = tag.name.split(":")[1]
                if trimmed_tag_name not in exclude_tag_names:
                    tag_names_to_extract.add(tag.name)

        # parse all of these extraneous tags
        other_gaap_attributes_df = self._get_attribute_values_df(tag_names_to_extract)
        return other_gaap_attributes_df

    def parse_all(self) -> pd.DataFrame:
        """
        Parse as much data out of this document as possible, and return all of it
        in one huge normalized DataFrame
        """

        def append_category(df: pd.DataFrame, category: str) -> pd.DataFrame:
            df["Category"] = category
            return df

        dfs = [
            append_category(self.parse_dei_attributes(), "DEI"),
            append_category(self.parse_income_statement(), "Income"),
            append_category(self.parse_comprehensive_income(), "Comprehensive Income"),
            append_category(self.parse_balance_sheet(), "Balance Sheet"),
            append_category(self.parse_cash_flows(), "Cash Flow"),
            append_category(self.parse_bespoke_attributes(), "Bespoke Attributes"),
        ]
        merged_df = pd.concat(dfs, ignore_index=True)

        # capture every field with a 'us-gaap' tag that hasn't otherwise been picked up
        processed_fields = set(merged_df["attribute_name"].values)
        df_others = append_category(
            self.get_other_gaap_attributes(processed_fields), "Unclassified"
        )
        merged_df = pd.concat([merged_df, df_others], ignore_index=True)

        return merged_df


class Form4Parser:
    """
    Document parser for Form 4 submissions (changes in beneficial ownership)
    """

    def __init__(self, ticker: str, file_name: str):
        self._ticker = ticker

        with open(file_name, mode="r") as fin:
            contents = fin.read()
        self._form4_soup = BeautifulSoup(contents, "lxml")

    def _get_text(self, root, *xml_path):
        """
        Navigate through the xml structure to find the text of a specific element
        """
        tag = root
        for tag_label in xml_path:
            tag = tag.find(tag_label)
        return tag.text

    def _parse_owner_details(self, element):
        """
        Parse details of how the filer of this report is related to the company
        """
        owner_details = {}
        if element is not None:
            for relationship_type in [
                "director",
                "officer",
                "tenpercentowner",
                "other",
            ]:
                flag = element.find(f"is{relationship_type}").text
                owner_details[relationship_type] = flag == "1"

            officer_title_element = element.find("officertitle")
            if officer_title_element is not None:
                officer_title = officer_title_element.text.strip()
                if officer_title.lower() == "see remarks":
                    officer_title = self._get_text(self._form4_soup, "remarks")
                if officer_title:
                    owner_details["officer_title"] = officer_title

            other_text_element = element.find("othertext")
            if other_text_element is not None:
                other_text = other_text_element.text.strip()
                if other_text:
                    owner_details["other_text"] = other_text
        return owner_details

    def _parse_transaction_details(
        self, transaction_tag: Tag
    ) -> Tuple[int, float, int]:
        """
        Parse out the number of shares traded, the trade price, and the position after this trade
        """
        transaction_detail_tag = transaction_tag.find("transactionamounts")

        # if acquiring shares, use a positive number of shares; sells have negative share count
        aquired_disposed = self._get_text(
            transaction_detail_tag, "transactionacquireddisposedcode", "value"
        )
        trade_direction = 1 if aquired_disposed == "A" else -1
        shares = int(
            self._get_text(transaction_detail_tag, "transactionshares", "value")
        )
        price = float(
            self._get_text(transaction_detail_tag, "transactionpricepershare", "value")
        )

        post_transaction_shares = int(
            self._get_text(
                transaction_tag,
                "posttransactionamounts",
                "sharesownedfollowingtransaction",
                "value",
            )
        )
        return (
            trade_direction * shares,
            price,
            post_transaction_shares,
        )

    def parse(self) -> pd.DataFrame:
        report_date = dt.datetime.strptime(
            self._get_text(self._form4_soup, "periodofreport"), "%Y-%m-%d"
        ).date()

        # Get info on the party that this filing pertains to
        owner_element = self._form4_soup.find("reportingowner")
        owner_name = self._get_text(owner_element, "reportingownerid", "rptownername")

        owner_details = self._parse_owner_details(
            owner_element.find("reportingownerrelationship")
        )

        # Get the detail of all transactions
        transaction_tags = self._form4_soup.find_all("nonderivativetransaction")
        records = []
        for transaction_tag in transaction_tags:
            transaction_date = self._get_text(
                transaction_tag, "transactiondate", "value"
            )

            shares, price, post_transaction_shares = self._parse_transaction_details(
                transaction_tag
            )
            records.append([transaction_date, shares, price, post_transaction_shares])

        df = pd.DataFrame(
            records,
            columns=["transaction_date", "shares", "price", "post_transaction_shares"],
        )
        df["owner"] = owner_name
        for attribute, value in owner_details.items():
            df[attribute] = value

        return df
