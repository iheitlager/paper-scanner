#!/usr/bin/env python3
"""
CORE API Example - Extract paper details by DOI

Requires CORE_API_KEY environment variable.

Usage:
    CORE_API_KEY=<your_key> uv run tests/spikes/008_fetchers/core_example.py
"""

import json
import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DOI = "10.1186/s13731-024-00404-5"
CORE_API_URL = "https://api.core.ac.uk/v3/search/works"
REQUEST_TIMEOUT = 10

def fetch_paper_details():
    """Fetch paper details from CORE API."""
    api_key = os.getenv("CORE_API_KEY")
    if not api_key:
        print(json.dumps({"error": "CORE_API_KEY environment variable not set"}, indent=2))
        return
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    params = {
        "q": f"doi:{DOI}",
        "limit": 1,
        "offset": 0
    }
    
    response = requests.get(CORE_API_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    
    data = response.json()
    
    if data.get("results"):
        paper = data["results"][0]
        print(json.dumps(paper, indent=2))
    else:
        print(json.dumps({"error": "Paper not found in CORE"}, indent=2))

if __name__ == "__main__":
    fetch_paper_details()
