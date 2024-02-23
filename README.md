## Project overview

`busco-fin` is a demonstration project aimed at showcasing the capabilities of searching and analyzing SEC documents. The project leverages a variety of technologies including Elasticsearch for efficient document retrieval, Spark for data processing, and unique usage of an LLM.

The core functionality includes:
- Indexing and searching SEC filings to quickly find relevant documents.
- Answering questions and generating summaries and insights from SEC filings
- Alternative to traditional RAG techniques

## Code Setup and Explanation

|Directory | Description|
|--- | ---|
|retriever | Contains the core search and retrieval logic using OpenAI's API.|
|examples | Provides example notebooks and scripts showing how to use retriever with various search tools.|
|dataloader| Contains code to populate datastores 

Example notebooks shows an outline of the setup and objects to create.

The alternative to RAG technique is utilizing the LLM to help create search queries based on a user's query. We then search our datastore for relevant info and ask the user's query again with the additional information gained from our retrieval.




## Todo

- populate vector search and create example notebook 
    - skeleton code in retriever/searcher/searchtools/vectorstores and latter half of retriever/searcher/embedding_and_search_tool.py
- containerize and locally host via streamlit
- improve elasticsearch and use metadata of documents. add related companies to document metadata via NER on document text
- include a rerank function (cohere, ColBERT, self fine-tuned)
- add visibility into retrieval scores via "Judge" model scoring, utilizing Arize Phoenix

## Attributions
- searchtool code iterated on from https://github.com/anthropics/anthropic-retrieval-demo