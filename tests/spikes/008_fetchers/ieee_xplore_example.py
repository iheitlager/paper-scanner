#!/usr/bin/env python3
"""
IEEE Xplore API Example - Extract paper details by DOI

Requires IEEE_XPLORE_API_KEY environment variable.
Get your API key at: https://developer.ieee.org/member/register

Usage:
    IEEE_XPLORE_API_KEY=<your_key> uv run tests/spikes/008_fetchers/ieee_xplore_example.py

IEEE Xplore provides access to:
- 6+ million documents (journals, conference papers, books, standards)
- Metadata with abstracts
- Open access and full-text articles (with subscription)
"""

import json
import os

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DOI = "10.1186/s13731-024-00404-5"
IEEE_XPLORE_API_URL = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
EMAIL = "i.heitlager@tue.nl"

def fetch_paper_details():
    """Fetch paper details from IEEE Xplore API."""
    api_key = os.getenv("IEEE_XPLORE_API_KEY")
    if not api_key:
        print(json.dumps({"error": "IEEE_XPLORE_API_KEY environment variable not set"}, indent=2))
        return
    
    headers = {
        "User-Agent": f"paper-scanner (https://github.com/iheitlager/paper-scanner; mailto:{EMAIL})",
        "Content-Type": "application/json"
    }
    
    # IEEE Xplore API parameters
    # Note: DOI API endpoint differs slightly from metadata search
    params = {
        "action": "search",
        "doi": DOI,
        "apikey": api_key,
        "format": "json",
        "max_records": 100
    }
    
    response = requests.get(IEEE_XPLORE_API_URL, headers=headers, params=params)
    response.raise_for_status()
    
    data = response.json()
    
    # IEEE Xplore returns results in an array
    if data.get("total_records", 0) > 0 and data.get("articles"):
        # Return the first matching article
        paper = data["articles"][0]
        print(json.dumps(paper, indent=2))
    else:
        print(json.dumps({"error": "Paper not found in IEEE Xplore"}, indent=2))

if __name__ == "__main__":
    fetch_paper_details()
