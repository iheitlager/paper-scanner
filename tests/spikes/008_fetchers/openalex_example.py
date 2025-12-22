#!/usr/bin/env python3
"""
OpenAlex API Example - Extract paper details by DOI

Usage:
    uv run tests/spikes/008_fetchers/openalex_example.py
"""

import json

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DOI = "10.1186/s13731-024-00404-5"
OPENALEX_API_URL = "https://api.openalex.org/works"
EMAIL = "i.heitlager@tue.nl"

def fetch_paper_details():
    """Fetch paper details from OpenAlex API."""
    headers = {
        "User-Agent": f"paper-scanner (https://github.com/iheitlager/paper-scanner; mailto:{EMAIL})"
    }
    params = {
        "filter": f"doi:{DOI}",
        "mailto": EMAIL  # Add email for polite download - improves rate limits
    }
    
    response = requests.get(OPENALEX_API_URL, params=params, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    
    if data["results"]:
        paper = data["results"][0]
        print(json.dumps(paper, indent=2))
    else:
        print(json.dumps({"error": "Paper not found in OpenAlex"}, indent=2))

if __name__ == "__main__":
    fetch_paper_details()
