#!/usr/bin/env python3
"""
Unpaywall API Example - Extract paper details by DOI

Usage:
    uv run tests/spikes/008_fetchers/unpaywall_example.py
"""

import json

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DOI = "10.1186/s13731-024-00404-5"
UNPAYWALL_API_URL = "https://api.unpaywall.org/v2"
EMAIL = "i.heitlager@tue.nl"

def fetch_paper_details():
    """Fetch paper details from Unpaywall API (polite pool)."""
    url = f"{UNPAYWALL_API_URL}/{DOI}"

    headers = {
        "User-Agent": f"paper-scanner (https://github.com/iheitlager/paper-scanner; mailto:{EMAIL})"
    }

    # Add email parameter for polite API access - provides better service and support
    params = {"email": EMAIL}

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    data = response.json()

    # Unpaywall returns the data directly, not in a results array
    if data.get("doi"):
        print(json.dumps(data, indent=2))
    else:
        print(json.dumps({"error": "Paper not found in Unpaywall"}, indent=2))

if __name__ == "__main__":
    fetch_paper_details()
