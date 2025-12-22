#!/usr/bin/env python3
"""
Example 2: Full Pipeline with Deduplication and Categorization

This demonstrates:
- Importing from multiple sources (Scopus, IEEE, Web of Science)
- Deduplication with multiple methods (DOI, fuzzy title/author matching)
- Categorization
- Checkpoints for resuming interrupted runs
- Summary and export to multiple formats
"""

from paper_scanner.definition import (BibtexSource, DeduplicationMethod,
                                      Definition)


def main():
    definition = (
        Definition(
            name="Comprehensive Research Review",
            description="Multi-source systematic literature review",
            researcher="Bob Smith",
            institution="MIT"
        )
        # Import from multiple sources
        .bibtex_import(
            batch_id="review_2024",
            imports=[
                BibtexSource.scopus(
                    "Scopus - Digital Innovation",
                    "data/scopus_digital_innovation.bib",
                    expected_count=500
                ),
                BibtexSource.ieee(
                    "IEEE - Transformation",
                    "data/ieee_transformation.bib",
                    expected_count=300
                ),
                BibtexSource.wos(
                    "Web of Science - Digitalization",
                    "data/wos_digitalization.bib",
                    expected_count=250
                )
            ]
        )
        .echo(message="Imported 1,050 papers from 3 sources")
        .checkpoint(label="post_import")
        
        # Deduplicate using multiple methods
        .deduplication(
            enabled=True,
            methods=[
                DeduplicationMethod(
                    method="doi_exact",
                    priority=1
                ),
                DeduplicationMethod(
                    method="title_author_fuzzy",
                    priority=2,
                    threshold=0.90
                ),
                DeduplicationMethod(
                    method="title_fuzzy",
                    priority=3,
                    threshold=0.95
                )
            ]
        )
        .echo(message="Deduplication complete")
        .checkpoint(label="post_dedup")
        
        # Categorize papers
        .categorization(enabled=True)
        .checkpoint(label="post_categorization")
        
        # Display summary statistics
        .summarize(
            summary=True,
            tabulate=[
                {"field": "paper_type", "duplicates": False},
                {"field": "journal", "duplicates": False},
                {"field": "publication_year", "duplicates": False}
            ]
        )
        
        # Export deduplicated papers to JSONL
        .export(
            format="jsonl",
            output_path="~/review_deduped.jsonl",
            exclude_none=True,
            duplicates=False,
            overwrite=True
        )
        
        # Export only duplicate papers to BibTeX
        .export(
            format="bibtex",
            output_path="~/review_duplicates.bib",
            duplicates="only",
            overwrite=True
        )
    )
    
    # Run with detailed output and timing
    results = definition.run(verbose=True)
    
    print(f"\n✓ Review complete: {results['steps_executed']} steps executed")
    return definition


if __name__ == "__main__":
    pipeline = main()
