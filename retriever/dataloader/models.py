# so we will have childs for elasticsearch and vectorstore

from langchain_community.document_loaders import UnstructuredHTMLLoader
from langchain_community.document_transformers import Html2TextTransformer

import os
import logging
logging.getLogger().setLevel(logging.INFO)
logging.getLogger().setLevel(logging.ERROR)

from abc import ABC, abstractmethod
import dotenv
from datetime import datetime

from sec_api import QueryApi
from sec_api import RenderApi

import pandas as pd
from time import sleep

class DataLoader():
    dotenv.load_dotenv()
    COMPANY_NAMES = ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'GOOG', 'META', 'TSLA', 'BRK.B', 'JPM', 'JNJ']
    DOC_TYPES = ['10-K']

    def __init__(self, min_date = '2020-01-01', max_date = '2023-12-31'):    
        self.base_dest = 'edgar_docs/'
        self.min_date = min_date
        self.max_date = max_date
        self.company_columns = ['cik', 'ticker', 'companyName','stateOfIncorporation', 'fiscalYearEnd', 'sic']
        self.document_columns = ['ticker','formType', 'description', 'documentUrl', 'filedAt', 'periodOfReport', 'localFilePath']
        self.queryApi = QueryApi(api_key=os.environ.get('SEC_API_KEY'))
        self.renderApi = RenderApi(api_key=os.environ.get("SEC_API_KEY"))
    
    def company_dir_path(self, company_name):
        return os.path.join(self.base_dest, company_name)
    
    def doc_type_dir_path(self, company_name, doc_type):
        return os.path.join(self.company_dir_path(company_name), doc_type)

    def download_filings(self):
        '''This method downloads filings for a given company and document type from the SEC API. The downloaded files are saved locally in the following directory structure: edgar_docs/{company_name}/{doc_type}/{filing_date}.htm. 

        The method ensures that it only downloads files that do not already exist for a certain company and document type. It also saves company information and document information to CSV files locally.

        Parameters:
        - company_name (str): The name of the company for which filings are to be downloaded.
        - doc_type (str): The type of document to be downloaded (e.g., '10-K', '10-Q', etc.).
        - min_date (str): The minimum date for which filings are to be downloaded (format: 'YYYY-MM-DD').
        - max_date (str): The maximum date for which filings are to be downloaded (format: 'YYYY-MM-DD').

        Returns:
        - None
        '''
        logging.info('Downloading filings...')
        companies_info = pd.DataFrame(columns=self.company_columns)
        documents_info = pd.DataFrame(columns=self.document_columns)
        for company in self.COMPANY_NAMES:
            # hack to avoid rate limits
            sleep(5)
            for doc_type in self.DOC_TYPES:
                logging.info(f'Downloading {doc_type} filings for {company}...')
                company_info, documents = self._download_filings_for_company_and_doc_type(company, doc_type)
                # if None for either, remove directory
                if company_info is None or documents is None:
                    continue
                companies_info = pd.concat([companies_info, company_info], ignore_index=True)
                documents_info = pd.concat([documents_info, documents], ignore_index=True)
        
        companies_info.to_csv(os.path.join(self.base_dest, 'companies_df.csv'), index=False)
        documents_info.to_csv(os.path.join(self.base_dest, 'document_info.csv'), index=False)

    def _download_filings_for_company_and_doc_type(self, company, doc_type):
        company_info = pd.DataFrame(columns=self.company_columns)
        document_info = pd.DataFrame(columns=self.document_columns)
        # check if company_dir_path with doc_type exists
        if not os.path.exists(os.path.join(self.company_dir_path(company), doc_type)):
            os.makedirs(os.path.join(self.company_dir_path(company), doc_type))
        else:
            logging.info(f'{company} {doc_type} already exists')
            return None, None
        
        query = {
           "query": { "query_string": {
                         "query": f"ticker:{company} AND filedAt:{{{self.min_date} TO {self.max_date}}} AND formType:\"{doc_type}\""
            } },
            "from": "0",
            "size": "10",
            "sort": [{ "filedAt": { "order": "desc" } }]
        }
        try:
            filings = self.queryApi.get_filings(query)
            first_filing = filings['filings'][0]
            company_info = pd.concat([company_info, pd.DataFrame({'cik': first_filing['cik'], 'ticker': company, 'companyName': first_filing['companyName'], 'stateOfIncorporation': first_filing['entities'][0]['stateOfIncorporation'], 'fiscalYearEnd': first_filing['entities'][0]['fiscalYearEnd'], 'sic': first_filing['entities'][0]['sic']}, index=[0])], ignore_index=True)
            for filing in filings['filings']:
                datetime_obj = datetime.fromisoformat(filing['filedAt'])
                localFilePath = os.path.join(self.doc_type_dir_path(company, doc_type), f"{str(datetime_obj.date())}.htm")
                
                document_info = pd.concat([document_info, pd.DataFrame({'ticker': company, 'formType': filing['formType'], 'description': filing['description'], 'documentUrl': filing['linkToFilingDetails'], 'filedAt': filing['filedAt'], 'periodOfReport': filing['periodOfReport'], 'localFilePath': localFilePath}, index=[0])], ignore_index=True)
                filing_html = self.renderApi.get_filing(filing['linkToFilingDetails'])
                with open(localFilePath, 'w', encoding='utf-8') as file:
                    file.write(filing_html)
        except Exception as e:
            logging.error(f'Error downloading filings for {company} {doc_type}: {e}')
            if company_info is None or document_info is None:
                return None, None
            return company_info, document_info
        return company_info, document_info
    
    def load_single_form(self, file_path):
        '''load a single form'''
        loader = UnstructuredHTMLLoader(file_path)
        doc = loader.load()
        

    def load_forms(self):
        pass
    
    @abstractmethod
    def populate_datastore(self):
        raise NotImplementedError()


