#!/usr/bin/env python3
"""
Example 4: Batch Processing Multiple Research Reviews

This demonstrates:
- Creating multiple pipelines programmatically
- Processing multiple years of data
- Reusable pipeline generation patterns
- Scalable research review workflows
"""

from dataclasses import dataclass
from typing import Dict, List

from paper_scanner.definition import (BibtexSource, Definition,
                                      create_standard_pipeline)


@dataclass
class ResearchConfig:
    """Configuration for a research review"""
    year: int
    topic: str
    sources: List[str]  # File paths
    deduplicate: bool = True
    categorize: bool = True


def create_batch_pipelines(
    reviews: List[ResearchConfig],
    output_dir: str = "~/research_outputs"
) -> Dict[int, Definition]:
    """
    Create multiple research review pipelines from configurations.
    
    Args:
        reviews: List of research review configurations
        output_dir: Output directory for all exports
    
    Returns:
        Dictionary mapping year to Definition object
    """
    pipelines = {}
    
    for config in reviews:
        # Build sources from file paths
        sources = [
            BibtexSource.scopus(
                f"{config.topic} {config.year}",
                path,
                expected_count=100  # Placeholder
            )
            for path in config.sources
        ]
        
        # Create pipeline using factory function
        pipeline = create_standard_pipeline(
            project_name=f"{config.topic}_{config.year}",
            sources=sources,
            deduplicate=config.deduplicate,
            categorize=config.categorize,
            export_format="jsonl",
            output_path=f"{output_dir}/{config.topic}_{config.year}_review.jsonl"
        )
        
        pipelines[config.year] = pipeline
    
    return pipelines


def main():
    print("=" * 70)
    print("Example 4: Batch Processing Multiple Research Reviews")
    print("=" * 70)
    
    # Configuration for multiple research reviews
    reviews = [
        ResearchConfig(
            year=2020,
            topic="digital_innovation",
            sources=[
                "data/2020/scopus_innovation.bib",
                "data/2020/ieee_innovation.bib"
            ]
        ),
        ResearchConfig(
            year=2021,
            topic="digital_innovation",
            sources=[
                "data/2021/scopus_innovation.bib",
                "data/2021/ieee_innovation.bib"
            ]
        ),
        ResearchConfig(
            year=2022,
            topic="digital_innovation",
            sources=[
                "data/2022/scopus_innovation.bib",
                "data/2022/ieee_innovation.bib",
                "data/2022/wos_innovation.bib"
            ]
        ),
        ResearchConfig(
            year=2023,
            topic="digital_innovation",
            sources=[
                "data/2023/scopus_innovation.bib",
                "data/2023/ieee_innovation.bib",
                "data/2023/wos_innovation.bib"
            ]
        ),
        ResearchConfig(
            year=2024,
            topic="digital_innovation",
            sources=[
                "data/2024/scopus_innovation.bib",
                "data/2024/ieee_innovation.bib",
                "data/2024/wos_innovation.bib"
            ]
        ),
    ]
    
    # Generate all pipelines
    print("\nGenerating research review pipelines...")
    pipelines = create_batch_pipelines(reviews, output_dir="~/research_outputs")
    
    print(f"✓ Generated {len(pipelines)} pipelines")
    
    # Display summary
    print("\nPipelines:")
    for year, pipeline in sorted(pipelines.items()):
        print(f"  {year}: {pipeline.name} ({len(pipeline.get_steps())} steps)")
    
    # Example: Execute pipelines in sequence
    print("\n# Execute pipelines in sequence:")
    print("# for year, pipeline in sorted(pipelines.items()):")
    print("#     print(f'Processing {year}...')")
    print("#     results = pipeline.run(verbose=False)")
    print("#     print(f'  ✓ Complete: {results[\"steps_executed\"]} steps')")
    
    # Example: Execute pipelines in parallel (with concurrent.futures)
    print("\n# Or execute in parallel:")
    print("# from concurrent.futures import ThreadPoolExecutor")
    print("# with ThreadPoolExecutor(max_workers=3) as executor:")
    print("#     futures = {")
    print("#         executor.submit(pipeline.run): year")
    print("#         for year, pipeline in pipelines.items()")
    print("#     }")
    print("#     for future in concurrent.futures.as_completed(futures):")
    print("#         year = futures[future]")
    print("#         results = future.result()")
    print("#         print(f'{year}: Complete')")
    
    # Save one pipeline to YAML for reference
    print("\n# Save a pipeline to YAML for reference:")
    print("# pipelines[2024].to_yaml(Path('review_2024_definition.yml'))")
    
    return pipelines


if __name__ == "__main__":
    pipelines = main()
