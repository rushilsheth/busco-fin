import os
import json

from abc import ABC, abstractmethod
import dotenv
from datetime import datetime

from sec_api import QueryApi
from sec_api import RenderApi

import pandas as pd
from time import sleep

import sys
from retriever.util import get_logger

logger = get_logger()

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
        logger.info('Downloading filings...')
        companies_info = pd.DataFrame(columns=self.company_columns)
        documents_info = pd.DataFrame(columns=self.document_columns)
        for company in self.COMPANY_NAMES:
            # hack to avoid rate limits
            sleep(5)
            for doc_type in self.DOC_TYPES:
                logger.info(f'Downloading {doc_type} filings for {company}...')
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
            logger.info(f'{company} {doc_type} already exists')
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
            logger.error(f'Error downloading filings for {company} {doc_type}: {e}')
            if company_info is None or document_info is None:
                return None, None
            return company_info, document_info
        return company_info, document_info

import subprocess
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, explode, lit
from pyspark.sql.types import ArrayType, StructType, StructField, StringType
from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch

import subprocess
from subprocess import Popen
import time
import signal
import os

from langchain_community.document_loaders import UnstructuredHTMLLoader
from langchain_community.document_transformers import Html2TextTransformer

from pyspark.sql.functions import to_json, col, struct
from pyspark.sql.types import MapType, StringType


class ElasticsearchService(Elasticsearch):
    def __init__(self, es_nodes='localhost', es_port='9200', es_index='sec_filings'):
        self.es_nodes = es_nodes
        self.es_port = es_port
        self.es_index = es_index
        super().__init__([{"host": self.es_nodes, "port": int(self.es_port), "scheme": "http"}])

        self.es_home = "/Users/rushilsheth/Documents/elasticsearch"  # Path to your Elasticsearch 
        self.es_bin = self.es_home + "/bin/elasticsearch"  # Path to the Elasticsearch executable
    
    def start_elasticsearch(self):
            """
            Starts Elasticsearch using subprocess.
            """
            try:
                print("Starting Elasticsearch...")
                self.es_process = Popen([self.es_bin], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                print("Elasticsearch is starting. Please wait a few moments before it becomes available.")
                time.sleep(30)  # Wait for Elasticsearch to start
            except Exception as e:
                print(f"Failed to start Elasticsearch: {e}")

    def stop_elasticsearch(self):
        """
        Stops the Elasticsearch process.
        """
        if self.es_process:
            print("Stopping Elasticsearch...")
            self.es_process.terminate()  # Sends SIGTERM
            try:
                self.es_process.wait(timeout=10)  # Wait for the process to terminate
            except subprocess.TimeoutExpired:
                print("Elasticsearch did not terminate gracefully; forcing it to stop.")
                self.es_process.kill()  # Force terminate if not stopped after timeout
            print("Elasticsearch has been stopped.")
        else:
            print("Elasticsearch process is not running.")
    
    def searchwrapper(self, query):
        """
        Searches the Elasticsearch index for the given query.
        """
        results = self.search(index=self.es_index, body=query)
        return results

class ElasticsearchDataLoader(DataLoader):
    def __init__(self, index_name='sec_filings'):
        super().__init__()
        self.index_name = index_name
        self.es_client = ElasticsearchService(es_index=self.index_name)
        self.index_name = self.es_client.es_index
        self.mapping = {
            "mappings": {
                "properties": {
                    "ticker": {"type": "keyword"},
                    "formType": {"type": "keyword"},
                    "description": {"type": "text"},
                    "documentUrl": {"type": "keyword"},
                    "filedAt": {"type": "date"},
                    "periodOfReport": {"type": "date"},
                    "localFilePath": {"type": "keyword"},
                    "cik": {"type": "keyword"},
                    "companyName": {"type": "text"},
                    "stateOfIncorporation": {"type": "keyword"},
                    "fiscalYearEnd": {"type": "integer"},
                    "sic": {"type": "keyword"}
                }
            }
        }
        
        self.initialize_spark_session()
        self._start_and_prep_service()
    
    def initialize_spark_session(self):
        self.spark = SparkSession.builder \
                .appName("Document Processing") \
                .config("spark.master", "local[*]") \
                .config("spark.jars", "elasticsearch-hadoop-8.12.1.jar") \
                .config("spark.es.nodes", self.es_client.es_nodes) \
                .config("spark.jars", "elasticsearch-spark-30_2.12-8.12.1.jar") \
                .getOrCreate()

        time.sleep(10)  # Wait for the Elasticsearch container to start

    def _start_and_prep_service(self):
        self.es_client.start_elasticsearch()
    
    def extract_metadata(self, file_path, doc_df, company_df):
        doc_row = doc_df.loc[doc_df['localFilePath'] == file_path]
        metadata = doc_row.to_dict(orient='records')[0]
        metadata.update(company_df.loc[company_df['ticker'] == doc_row['ticker'].values[0]].to_dict(orient='records')[0])
        return metadata

    def load_documents_to_elasticsearch(self):
        # Load metadata CSVs
        doc_df = pd.read_csv(f'{self.base_dest}document_info.csv')
        company_df = pd.read_csv(f'{self.base_dest}companies_df.csv')

        # List to hold all document data
        documents_data = []

        # Crawl the directory for .htm files
        for root, dirs, files in os.walk(self.base_dest):
            for file in files:
                if file.endswith(".htm"):
                    file_path = os.path.join(root, file)
                    # Extract metadata
                    metadata = self.extract_metadata(file_path, doc_df, company_df)
                    # Convert HTML to text
                    html_text = self.html_to_text(file_path)
                    # Combine metadata and text content
                    documents_data.append((json.dumps(metadata), metadata['documentUrl'],html_text))
        
        # Convert list to RDD and then to DataFrame
        schema = StructType([
            StructField("metadata", StringType(), True),
            StructField("documentUrl", StringType(), True),
            StructField("text", StringType(), True)
        ])
        rdd = self.spark.sparkContext.parallelize(documents_data)
        documents_df = self.spark.createDataFrame(rdd, schema)
        # Load the DataFrame to Elasticsearch
        self.load_data(documents_df)

        # # adjust max_analyzed_offset to avoid Elasticsearch error
        # response = self.es_client.indices.put_settings(
        #     index=self.es_index,
        #     body={
        #         "index": {
        #             "highlight.max_analyzed_offset": 1000000
        #         }
        #     }
        # )
    
    def html_to_text(self, file_path):
        loader = UnstructuredHTMLLoader(file_path)
        doc = loader.load()
        html2text = Html2TextTransformer()
        docs_transformed = html2text.transform_documents(doc)
        return docs_transformed[0].page_content

    def load_data(self, documents_df):
        write_conf = {
            "es.nodes": self.es_client.es_nodes,
            "es.port": self.es_client.es_port,
            "es.resource": self.index_name,
            "es.mapping.id": "documentUrl",  # Use the document URL as the unique ID for Elasticsearch documents
        }

        # Write the DataFrame to Elasticsearch
        documents_df.write.format(
            "org.elasticsearch.spark.sql"
        ).options(
            **write_conf
        ).mode(
            "append" 
        ).save()

        logger.info("Data has been loaded into Elasticsearch.")