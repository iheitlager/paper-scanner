#!/usr/bin/env python3
"""
ScienceOpen API Example - Extract paper details by DOI

ScienceOpen provides open access research discovery with API access to
paper metadata, citations, and open access status.

Usage:
    uv run tests/spikes/008_fetchers/scienceopen_example.py
"""

import json

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DOI = "10.1186/s13731-024-00404-5"
SCIENCEOPEN_API_URL = "https://www.scienceopen.com/api/openapi/search"
EMAIL = "i.heitlager@tue.nl"

def fetch_paper_details():
    """Fetch paper details from ScienceOpen API."""
    headers = {
        "User-Agent": f"paper-scanner (https://github.com/iheitlager/paper-scanner; mailto:{EMAIL})"
    }

    # Query parameters for ScienceOpen search by DOI
    params = {
        "q": f"doi:{DOI}",
        "limit": 1
    }

    response = requests.get(SCIENCEOPEN_API_URL, headers=headers, params=params)
    response.raise_for_status()

    data = response.json()

    # ScienceOpen returns results in an array
    if data.get("results") and len(data["results"]) > 0:
        paper = data["results"][0]
        print(json.dumps(paper, indent=2))
    else:
        print(json.dumps({"error": "Paper not found in ScienceOpen"}, indent=2))

if __name__ == "__main__":
    fetch_paper_details()

