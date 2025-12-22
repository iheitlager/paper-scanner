#!/usr/bin/env python3
"""
Example 3: Conditional Pipeline with Python Logic

This demonstrates:
- Building pipelines conditionally based on runtime parameters
- Reusing pipeline configurations
- Environment-aware step inclusion
- Programmatic pipeline generation
"""

from typing import List, Optional

from paper_scanner.definition import (BibtexSource, DeduplicationMethod,
                                      Definition)


def build_custom_pipeline(
    project_name: str,
    sources: List[BibtexSource],
    *,
    deduplicate: bool = True,
    categorize: bool = True,
    screen_by_keywords: bool = False,
    keywords: Optional[List[str]] = None,
    dry_run: bool = False
) -> Definition:
    """
    Factory function to build pipelines with conditional steps.
    
    Args:
        project_name: Name of the research project
        sources: List of BibTeX sources to import
        deduplicate: Whether to run deduplication
        categorize: Whether to run categorization
        screen_by_keywords: Whether to screen by keywords
        keywords: List of keywords for screening
        dry_run: Dry run mode
    
    Returns:
        Configured Definition object
    """
    definition = Definition(
        name=project_name,
        description="Custom research review pipeline",
        researcher="Carol Johnson"
    )
    
    # Always start with import
    definition.bibtex_import(
        batch_id=f"batch_{project_name}",
        imports=sources
    )
    definition.echo(message="Sources imported")
    definition.checkpoint(label="post_import")
    
    # Conditionally deduplicate
    if deduplicate:
        definition.deduplication(
            enabled=True,
            methods=[
                DeduplicationMethod(method="doi_exact", priority=1),
                DeduplicationMethod(
                    method="title_author_fuzzy",
                    priority=2,
                    threshold=0.90
                ),
            ]
        )
        definition.checkpoint(label="post_dedup")
    
    # Conditionally categorize
    if categorize:
        definition.categorization(enabled=True)
        definition.checkpoint(label="post_categorization")
    
    # Conditionally screen by keywords
    if screen_by_keywords and keywords:
        definition.keyword_screening(
            enabled=True,
            keywords=keywords
        )
        definition.checkpoint(label="post_keyword_screening")
    
    # Always end with summary and export
    definition.summarize(summary=True)
    definition.export(
        format="jsonl",
        output_path=f"~/review_{project_name}.jsonl",
        overwrite=True
    )
    
    return definition


def main():
    print("=" * 70)
    print("Example 3: Conditional Pipeline with Python Logic")
    print("=" * 70)
    
    # Scenario 1: Basic pipeline without deduplication
    print("\n[1] Building basic pipeline (import only)...")
    basic = build_custom_pipeline(
        "basic_review",
        sources=[
            BibtexSource.scopus("Scopus", "data/scopus.bib", 100)
        ],
        deduplicate=False,
        categorize=False
    )
    print(f"    Steps: {len(basic.get_steps())}")
    
    # Scenario 2: Full pipeline with all features
    print("\n[2] Building comprehensive pipeline (with dedup & categorization)...")
    comprehensive = build_custom_pipeline(
        "comprehensive_review",
        sources=[
            BibtexSource.scopus("Scopus", "data/scopus.bib", 300),
            BibtexSource.ieee("IEEE", "data/ieee.bib", 200),
        ],
        deduplicate=True,
        categorize=True,
        screen_by_keywords=False
    )
    print(f"    Steps: {len(comprehensive.get_steps())}")
    
    # Scenario 3: Specialized pipeline with keyword screening
    print("\n[3] Building specialized pipeline (with keyword screening)...")
    specialized = build_custom_pipeline(
        "specialized_review",
        sources=[
            BibtexSource.scopus("Scopus", "data/scopus.bib", 150)
        ],
        deduplicate=True,
        categorize=True,
        screen_by_keywords=True,
        keywords=["digital innovation", "transformation", "supplier involvement"]
    )
    print(f"    Steps: {len(specialized.get_steps())}")
    
    # Print pipeline summaries
    print("\n" + "=" * 70)
    print("Pipeline Summaries:")
    print("=" * 70)
    
    for pipeline in (basic, comprehensive, specialized):
        print(f"\n{pipeline.name}:")
        for i, step in enumerate(pipeline.get_steps(), 1):
            print(f"  {i}. {step.get_description()}")
    
    # Example: Run one pipeline (commented out to avoid actual execution)
    print("\n# To execute a pipeline, uncomment the line below:")
    print("# results = comprehensive.run(verbose=True)")
    
    return comprehensive


if __name__ == "__main__":
    pipeline = main()
