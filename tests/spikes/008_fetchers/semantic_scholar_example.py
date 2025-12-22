#!/usr/bin/env python3
"""
Semantic Scholar API Example - Extract paper details by DOI

Usage:
    uv run tests/spikes/008_fetchers/semantic_scholar_example.py
"""

import json

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DOI = "10.1186/s13731-024-00404-5"
SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/DOI"

def fetch_paper_details():
    """Fetch paper details from Semantic Scholar API."""
    url = f"{SEMANTIC_SCHOLAR_API_URL}:{DOI}"
    
    params = {
        "fields": "paperId,externalIds,title,year,authors,abstract,publicationTypes,publicationDate,citationCount,isOpenAccess,openAccessPdf,fieldsOfStudy"
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2))
    elif response.status_code == 404:
        print(json.dumps({"error": "Paper not found in Semantic Scholar"}, indent=2))
    else:
        response.raise_for_status()

if __name__ == "__main__":
    fetch_paper_details()
