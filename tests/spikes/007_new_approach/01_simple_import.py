#!/usr/bin/env python3
"""
Example 1: Simple BibTeX Import and Export

This demonstrates the most basic use case:
- Import papers from a BibTeX file
- Export to JSONL format
"""

from paper_scanner.definition import BibtexSource, Definition


def main():
    # Create a simple import-export pipeline
    definition = (
        Definition(
            name="Quick Import",
            researcher="Alice",
            description="Simple paper import from Scopus"
        )
        .bibtex_import(
            batch_id="import_001",
            imports=[
                BibtexSource.scopus(
                    name="Scopus Sample",
                    file_path="data/scopus_sample_20.bib",
                    expected_count=20
                )
            ]
        )
        .export(
            format="jsonl",
            output_path="~/papers_imported.jsonl",
            overwrite=True
        )
    )

    # Execute the pipeline
    results = definition.run(verbose=True)

    print(f"\n✓ Pipeline complete: {results['steps_executed']} steps executed")
    return definition


if __name__ == "__main__":
    pipeline = main()
