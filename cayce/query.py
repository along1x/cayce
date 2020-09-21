"""
Query for available documents directly from EDGAR
"""

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

from cayce.utils import split_fixed_length

# https://www.sec.gov/Archives/edgar/full-index/2020/QTR1/


class EdgarIndex:
    def __init__(self, cache_dir: str = None):
        """
        Create a new Edgar filing index

        Args:
            cache_dir (str, optional): 
                Local path where Edgar cache files can be stored. 
                Defaults to None, which will equates to %TEMP%
        """
        if cache_dir:
            self.use_temp = False
            self.cache_dir = cache_dir
        else:
            self.use_temp = True
            self.cache_dir = tempfile.mkdtemp()

    def __del__(self):
        # Clean up temp directory, if used
        if self.use_temp:
            try:
                shutil.rmtree(self.cache_dir)
            except Exception as e:
                print(f"Failed to remove temp directory {self.cache_dir}", e)

    def _download_index(self, reference_date: dt.date):
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
        local_file_name = f"{year}-{quarter}-index.zip"
        wget.download(url, path.join(self.cache_dir, local_file))

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


# Some test code for now
idx = EdgarIndex()
df = idx._process_company_idx("e:/Google Drive Backup/company.zip")
print(df.head())
