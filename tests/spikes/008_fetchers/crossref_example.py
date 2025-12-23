#!/usr/bin/env python3
"""
Crossref API Example - Extract paper details by DOI

Usage:
    uv run tests/spikes/008_fetchers/crossref_example.py
"""

import json

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DOI = "10.1186/s13731-024-00404-5"
CROSSREF_API_URL = "https://api.crossref.org/works"
EMAIL = "i.heitlager@tue.nl"

def fetch_paper_details():
    """Fetch paper details from Crossref API."""
    url = f"{CROSSREF_API_URL}/{DOI}"

    headers = {
        "User-Agent": f"paper-scanner (https://github.com/iheitlager/paper-scanner; mailto:{EMAIL})"
    }

    # Add mailto parameter for polite pool access with better performance
    params = {"mailto": EMAIL}

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    data = response.json()

    if data.get("status") == "ok":
        paper = data.get("message", {})
        print(json.dumps(paper, indent=2))
    else:
        print(json.dumps({"error": "Paper not found in Crossref"}, indent=2))

if __name__ == "__main__":
    fetch_paper_details()
