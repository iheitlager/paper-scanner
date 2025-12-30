"""
Test Spike 004: Adaptive Rocchio Classification - Prototype 1

Prototype 1: Zero-Seed Baseline

Tests the semantic_classification step with the Rocchio algorithm using:
- Research question: "How do incumbent firms involve suppliers in digital innovation processes?"
- Data source: scopus_sample_20.bib (20 papers from Scopus)
- Pipeline: bibtex_import → keyword_screening → semantic_classification
- Seeds: Zero papers pre-labeled initially

Expected behavior:
1. Load 20 papers from scopus_sample_20.bib
2. Run keyword_screening to label papers (keyword_screening will provide initial accept/reject)
3. Run semantic_classification with zero seeds to establish baseline
4. Observe centroid initialization from research question alone
5. Classify papers and track centroid evolution

This tests the core Rocchio functionality with minimal training signal.
"""

import pytest
from pathlib import Path
from paper_scanner.core.executor import StepExecutor
from paper_scanner.core.reporter import NOOP


@pytest.fixture
def test_data_dir():
    """Get the test data directory."""
    return Path(__file__).parent.parent.parent / "data"


@pytest.fixture
def executor(test_data_dir):
    """Create an executor with project configuration."""
    general_config = {
        "project_name": "Rocchio_Test_004",
        "description": "Test Rocchio semantic classification with zero seeds",
        "researcher": "Test",
        "research_question": "How do incumbent firms involve suppliers in digital innovation processes?",
        "email": "test@example.com",
    }
    
    return StepExecutor(
        general_config=general_config,
        step_reporter=NOOP,
        verbose=True,
        debug=True,
    )


@pytest.fixture
def bib_file(test_data_dir):
    """Locate the scopus_sample_20.bib file."""
    bib_path = test_data_dir / "scopus_sample_20.bib"
    if not bib_path.exists():
        # Try alternative location
        bib_path = Path(__file__).parent.parent.parent.parent / "scopus_sample_20.bib"
    return bib_path


def test_rocchio_prototype_1_zero_seed(executor, bib_file):
    """
    Test Rocchio classification with zero seeds (research question only).
    
    Flow:
    1. Load definition with bibtex_import → keyword_screening → semantic_classification
    2. Import papers from scopus_sample_20.bib
    3. Run keyword_screening to generate initial labels
    4. Run semantic_classification with zero seeds (only research question)
    5. Verify papers are classified and centroids are initialized
    """
    
    if not bib_file.exists():
        pytest.skip(f"Test data file not found: {bib_file}")
    
    # Load definition
    definition = {
        "steps": [
            {
                "name": "bibtex_import",
                "config": {
                    "input_file": str(bib_file),
                }
            },
            {
                "name": "keyword_screening",
                "config": {
                    "screening_mode": "inclusion_required",
                    "keywords": {
                        "inclusion": [
                            "digital innovation",
                            "digital transformation",
                            "supplier involvement",
                            "supply chain",
                            "incumbent firms",
                        ]
                    }
                }
            },
            {
                "name": "semantic_classification",
                "config": {
                    "model": "all-mpnet-base-v2",  # Lighter model for testing
                    "rocchio_weights": {
                        "alpha": 1.0,
                        "beta": 0.75,
                        "gamma": 0.15,
                    },
                    "thresholds": {
                        "accept": 0.7,
                        "reject": 0.3,
                    },
                    "initialize_from_keyword_screening": True,
                }
            }
        ]
    }
    
    executor.load_definition(definition)
    
    # Execute step by step
    results = []
    while executor.has_next_step:
        result = executor.execute_next_step()
        results.append(result)
        
        if result["status"] != "success":
            pytest.fail(f"Step failed: {result['message']}")
    
    # Verify results
    assert len(results) == 3, f"Expected 3 steps, got {len(results)}"
    
    # Check bibtex_import
    import_result = results[0]
    assert import_result["status"] == "success"
    assert import_result["stats"]["papers_count"] > 0, "No papers imported"
    initial_paper_count = import_result["stats"]["papers_count"]
    
    # Check keyword_screening
    keyword_result = results[1]
    assert keyword_result["status"] == "success"
    assert keyword_result["stats"]["screened"] > 0, "No papers screened"
    
    # Check semantic_classification
    rocchio_result = results[2]
    assert rocchio_result["status"] == "success"
    assert rocchio_result["stats"]["classified"] > 0, "No papers classified"
    
    # Verify step_state persistence
    assert "semantic_classification_rocchio_state" in executor.step_state, \
        "Rocchio state not stored in executor.step_state"
    
    state_dict = executor.step_state["semantic_classification_rocchio_state"]
    assert state_dict["query_centroid"] is not None, "Query centroid not initialized"
    assert state_dict["count_relevant"] > 0 or state_dict["count_irrelevant"] > 0, \
        "No centroids initialized from keyword_screening"
    
    # Print summary
    print("\n" + "="*60)
    print("PROTOTYPE 1: ZERO-SEED BASELINE")
    print("="*60)
    print(f"Papers imported: {initial_paper_count}")
    print(f"Papers screened (keyword): {keyword_result['stats']['screened']}")
    print(f"  - Passed: {keyword_result['stats']['passed']}")
    print(f"  - Failed: {keyword_result['stats']['failed']}")
    print(f"\nRocchio classification results:")
    print(f"  - Total classified: {rocchio_result['stats']['classified']}")
    print(f"  - Accepted: {rocchio_result['stats']['accepted']}")
    print(f"  - Rejected: {rocchio_result['stats']['rejected']}")
    print(f"  - Uncertain: {rocchio_result['stats']['uncertain']}")
    print(f"\nCentroid state:")
    print(f"  - Iteration: {state_dict['iteration']}")
    print(f"  - Relevant papers: {state_dict['count_relevant']}")
    print(f"  - Irrelevant papers: {state_dict['count_irrelevant']}")
    print(f"  - Query centroid dim: {len(state_dict['query_centroid']) if state_dict['query_centroid'] else 'None'}")
    print("="*60)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
