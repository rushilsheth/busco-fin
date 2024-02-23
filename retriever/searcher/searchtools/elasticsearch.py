from typing import Optional
from retriever.searcher.embedding_and_search_tool import SearchResult, SearchTool
from dataloader.models import ElasticsearchService

from retriever.util import get_logger

logger = get_logger()

class ElasticsearchSearchTool(SearchTool):

    def __init__(self,
                tool_description: str,
                truncate_to_n_tokens: Optional[int] = 5000):
        
        self.es_client = ElasticsearchService(es_index='sec_filings')

        self.tool_description = tool_description
        self.truncate_to_n_tokens = truncate_to_n_tokens

        self.es_client.start_elasticsearch()

    def raw_search(self, query: str, n_search_results_to_use: int=10) -> list[SearchResult]:
        """
        Runs a query using the searcher, then returns the raw search results without formatting.
        Uses fuzzy match in es query and uses fragment_size to get more context around the match.
        TODO: metadata usage for better search results.
        
        :param query: The query to run.
        """

        query_arg = {
            "query": {
                "match": {
                    "text": query,
                }
            },
            "highlight": {
                "max_analyzed_offset": 999999,
                "fields": {
                    "text": {
                        "fragment_size": 400,
                    }
                }
            },
        }
        results = self.es_client.searchwrapper(query=query_arg)
        search_results: list[SearchResult] = []
        for result in results["hits"]["hits"]:
            if len(search_results) >= n_search_results_to_use:
                break
            if 'highlight' in result:
                search_results.append(SearchResult(content=result['highlight']['text']))

        return search_results
    
    def process_raw_search_results(self, results: list[SearchResult]) -> list[str]:
        processed_search_results = [(result.content) for result in results]
        return processed_search_results
    @staticmethod
    def format_results(extracted: list[str]) -> str:
        """
        Joins and formats the extracted search results as a string.

        :param extracted: The extracted search results to format.
        """
        result = "\n".join(
            [
                f'<item index="{i+1}">\n<page_content>\n' + '\n\n'.join(r) + '\n</page_content>\n</item>'
                for i, r in enumerate(extracted)
            ]
        )
        return result
    
    def format_results_full(self, extracted: list[str]) -> str:
        """
        Formats the extracted search results as a string, including the <search_results> tags.

        :param extracted: The extracted search results to format.
        """
        return f"\n<search_results>\n{self.format_results(extracted)}\n</search_results>"