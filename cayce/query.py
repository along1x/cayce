"""
Query for available documents directly from EDGAR
"""

# TODO implement common logger for the library...

import datetime as dt
import json
import math
import requests
from os import path
import shutil
import tempfile
from urllib.parse import quote
from typing import Union, List
from zipfile import ZipFile

from bs4 import BeautifulSoup
import pandas as pd
import wget

from cayce.utils import ifna, split_fixed_length, add_months

# https://www.sec.gov/Archives/edgar/full-index/2020/QTR1/


class EdgarIndex:
    _index: pd.DataFrame = None

    def __init__(self, cache_dir: str = None):
        """
        Create a new Edgar filing index

        Args:
            cache_dir (str, optional): 
                Local path where Edgar cache files can be stored. 
                Defaults to None, which will equates to %TEMP%
        """
        if cache_dir:
            self._use_temp = False
            self._cache_dir = cache_dir
            self._index_cache_file = path.join(self._cache_dir, "edgar_filings.idx")
            if path.exists(self._index_cache_file):
                self._index = pd.read_csv(self._index_cache_file)
        else:
            self._use_temp = True
            self._cache_dir = tempfile.mkdtemp()

        if not self._index:
            self._index = pd.DataFrame(
                [], columns=["company", "form_type", "cik", "date_filed", "file_name"]
            )

    def __del__(self):
        if self._use_temp:
            # Clean up temp directory, if used
            try:
                shutil.rmtree(self._cache_dir)
            except Exception as e:
                print(f"Failed to remove temp directory {self._cache_dir}", e)
        else:
            # If we have a permenant cache, save the index we've built so far
            self._index.to_csv(self._index_cache_file)

    def _download_index(self, reference_date: dt.date) -> str:
        """
        Download an index file that would encapsulate the specified date

        Args:
            reference_date (dt.date): Reference date that needs to be in the index
        """
        year = str(reference_date.year)
        quarter = int(math.ceil(reference_date.month / 3))
        url = (
            f"http://sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/company.zip"
        )
        local_file_path = path.join(self._cache_dir, f"{year}-{quarter}-index.zip")

        if year == dt.date.today().year  and quarter == )

        if path.exists(local_file_path):
            print(f"Using cached file {local_file_path}")
        else:
            print(f"Downloading file {url}")
            wget.download(url, local_file_path)

        return local_file_path

    def _process_company_idx(self, file_name: str) -> pd.DataFrame:
        """
        Process a company.zip file, as retrieved from EDGAR

        Args:
            file_name (str): Local file name

        Returns:
            pd.DataFrame: Content of the index
        """
        # fmt: off
        assert file_name.endswith(".zip"), "Expecting a zipped file containing the company index"
        # fmt: on

        data = []

        with ZipFile(file_name) as zipped:
            assert len(zipped.namelist()) == 1, "Only expecting archive to have 1 file"

            archived_file = zipped.namelist()[0]
            with zipped.open(archived_file) as f:
                header = True
                for line_bytes in f:
                    # skip past all header rows
                    if header:
                        if line_bytes.startswith(b"-------"):
                            header = False
                        continue
                    line = line_bytes.decode("utf-8")
                    data.append(split_fixed_length(line, [62, 12, 12, 12]))

        return pd.DataFrame(
            data, columns=["company", "form_type", "cik", "date_filed", "file_name"]
        )

    def _refresh_index(
        self,
        start_date: dt.date = dt.date(1993, 1, 1),
        end_date: dt.date = dt.date.today(),
    ):
        # fmt: off
        assert start_date >= dt.date(1993, 1, 1), "Sadly, EDGAR's memory only stretches back to Q1 1993"
        assert end_date <= dt.date.today(), "Unfortunately, EDGAR can't see into the future"
        # fmt: on

        # if null, make these values such that we'll never see a sample date fall within the window
        min_filing_date = ifna(self._index["date_filed"].min(), dt.date(1992, 12, 31))
        max_filing_date = ifna(self._index["date_filed"].max(), dt.date(1992, 12, 31))

        date = start_date
        processed_files = []
        subindex_dfs = []
        while True:
            if date < min_filing_date or date > max_filing_date:
                file_name = self._download_index(date)

                # since we don't control if the end_date is the first day of a new quarter and the
                # length of the window we search, ensure we don't process the same index twice...
                if file_name not in processed_files:
                    subindex_dfs.append(self._process_company_idx(file_name))
                    processed_files.append(file_name)
            if date == end_date:
                break
            date = add_months(date, 3)
            if date > end_date:
                date = end_date

        # append all new index files to the master index
        self._index = pd.concat([self._index] + subindex_dfs, ignore_index=True)

    # TODO: add search parameters and implement query off of loaded index
    def search(
        self,
        start_date: dt.date = dt.date(1993, 1, 1),
        end_date: dt.date = dt.date.today(),
    ):
        """
        Search through the EDGAR company indices to find filings matching a provided criteria

        Args:
            start_date (dt.date, optional): Earliest date to accept. Defaults to 1993-01-01 (the earliest date on EDGAR).
            end_date (dt.date, optional): Latest date to accept. Defaults to today() (implicitly the latest possible date).
        """
        self._refresh_index(start_date, end_date)

