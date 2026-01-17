"""
Pytest configuration for spike 020: Paper Metadata Extraction

This conftest.py ensures these tests are NOT run as part of the regular test suite.
The regular test suite runs only tests in tests/unit/ via `make test`.

To run these spike tests explicitly:
    uv run pytest tests/spikes/020_parsing/ -v
"""

import pytest
from pathlib import Path


def pytest_configure(config):
    """Register custom markers for spike tests."""
    config.addinivalue_line("markers", "spike: marks tests as spike experiments (not run by default)")
    config.addinivalue_line("markers", "slow: marks tests as slow (API calls, ML inference)")
    config.addinivalue_line("markers", "requires_api: marks tests requiring ANTHROPIC_API_KEY")
    config.addinivalue_line("markers", "requires_gpu: marks tests requiring GPU for ML models")


@pytest.fixture(scope="session")
def spike_dir():
    """Return the spike directory path."""
    return Path(__file__).parent


@pytest.fixture(scope="session")
def corpus_dir():
    """Return the corpus directory path."""
    return Path(__file__).parent.parent.parent / "corpus"


@pytest.fixture(scope="session")
def outputs_dir(spike_dir):
    """Return the outputs directory path, creating it if needed."""
    outputs = spike_dir / "outputs"
    outputs.mkdir(exist_ok=True)
    return outputs


@pytest.fixture(scope="session")
def corpus_files(corpus_dir):
    """Get list of PDF files in the corpus."""
    if not corpus_dir.exists():
        pytest.skip(f"Corpus directory not found: {corpus_dir}")
    pdf_files = list(corpus_dir.glob("*.pdf"))
    if not pdf_files:
        pytest.skip("No PDF files found in corpus directory")
    return pdf_files


@pytest.fixture(scope="session")
def ground_truth(spike_dir):
    """Load ground truth from metamodel.yml."""
    import yaml

    metamodel_path = spike_dir / "metamodel.yml"
    if not metamodel_path.exists():
        pytest.skip("metamodel.yml not found")

    with open(metamodel_path) as f:
        data = yaml.safe_load(f)

    # Index by paper ID for easy lookup
    papers_by_id = {}
    for paper in data.get("papers", []):
        paper_id = paper.get("id")
        if paper_id:
            papers_by_id[paper_id] = paper.get("metadata", {})

    return papers_by_id


@pytest.fixture(scope="session")
def anthropic_api_key():
    """Get Anthropic API key from environment."""
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return api_key
