#!/usr/bin/env python3
"""
Parse BibTeX file and print Paper objects

Usage:
    python parse_bibtex.py <path_to_file.bib> [--source-type TYPE] [--discovery METHOD] [--output-type {txt,jsonl}]
    
Example:
    python parse_bibtex.py tests/data/ieee_sample_20.bib --source-type ieee
    python parse_bibtex.py tests/data/scopus_sample_20.bib --source-type scopus --output-type jsonl
"""

import argparse
import signal
import sys
from datetime import datetime
from pathlib import Path
from pprint import pprint

from paper_scanner.core.enum import DiscoveryMethod
from paper_scanner.core.models import Discovery
from paper_scanner.io.bibtex import bibtex_file_to_papers
from paper_scanner.io.json import papers_to_jsonl

# Handle broken pipe gracefully (when piping to head, wc, etc.)
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
from paper_scanner.core.enum import DiscoveryMethod


def main():
    parser = argparse.ArgumentParser(
        description="Parse BibTeX file and display Paper objects"
    )
    parser.add_argument(
        "filepath",
        type=str,
        help="Path to BibTeX file (.bib)"
    )
    parser.add_argument(
        "--source-type",
        type=str,
        default="bibtex",
        help="Source database type (default: bibtex)"
    )
    parser.add_argument(
        "--discovery",
        type=str,
        default="keyword_search",
        help="Discovery method (default: keyword_search)"
    )
    parser.add_argument(
        "-t", "--output-type",
        type=str,
        choices=["txt", "jsonl"],
        default="txt",
        help="Output format: txt (default) or jsonl"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of papers to display (default: all)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full paper details"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print summary statistics only"
    )

    args = parser.parse_args()

    # Validate file exists
    filepath = Path(args.filepath)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    # Parse discovery method
    try:
        discovery_method = DiscoveryMethod(args.discovery)
    except ValueError:
        valid_methods = [m.value for m in DiscoveryMethod]
        print(f"Error: Invalid discovery method '{args.discovery}'", file=sys.stderr)
        print(f"Valid methods: {', '.join(valid_methods)}", file=sys.stderr)
        sys.exit(1)

    # Parse BibTeX file
    if args.output_type != "jsonl":
        print(f"Parsing: {filepath}")
        print(f"Source type: {args.source_type}")
        print(f"Discovery method: {args.discovery}")
        print()

    discovery = Discovery(
        method=discovery_method,
        source_database=args.source_type,
        import_batch_id=f"parse_bibtex_{filepath.stem}_{int(Path(filepath).stat().st_mtime)}_{int(datetime.now().timestamp())}"
    )

    try:
        papers = bibtex_file_to_papers(
            str(filepath),
            discovery=discovery
        )
    except Exception as e:
        print(f"Error parsing file: {e}", file=sys.stderr)
        sys.exit(1)

    # Apply limit
    if args.limit:
        papers = papers[:args.limit]

    # Output in requested format
    if args.output_type == "jsonl":
        output_jsonl(papers, args)
    else:
        print(f"Found {len(papers)} papers\n")
        print("=" * 80)
        output_txt(papers, args)
        print("\n" + "=" * 80)
        print(f"✓ Successfully parsed {len(papers)} papers")


def output_jsonl(papers, args):
    """Output papers as JSONL format"""
    jsonl_string = papers_to_jsonl(papers, exclude_none=True)
    print(jsonl_string, end="")


def output_txt(papers, args):
    """Output papers as text format"""
    if args.summary:
        # Print summary
        print("\nSUMMARY")
        print("-" * 80)

        total_authors = sum(len(p.authors) for p in papers)
        papers_with_doi = sum(1 for p in papers if p.doi)
        papers_with_abstract = sum(1 for p in papers if p.abstract)
        papers_with_keywords = sum(1 for p in papers if p.keywords)

        avg_year = sum(p.year for p in papers if p.year) / sum(1 for p in papers if p.year) if any(p.year for p in papers) else 0

        print(f"Total papers: {len(papers)}")
        print(f"Total authors: {total_authors}")
        print(f"Avg authors per paper: {total_authors / len(papers) if papers else 0:.1f}")
        print(f"Papers with DOI: {papers_with_doi} ({100*papers_with_doi/len(papers):.1f}%)")
        print(f"Papers with abstract: {papers_with_abstract} ({100*papers_with_abstract/len(papers):.1f}%)")
        print(f"Papers with keywords: {papers_with_keywords} ({100*papers_with_keywords/len(papers):.1f}%)")
        if avg_year:
            print(f"Average year: {avg_year:.0f}")

        return

    # Print detailed results
    for i, paper in enumerate(papers, 1):
        print(f"\n[{i}] {paper.cite_key}")
        print("-" * 80)
        print(f"Title: {paper.title}")

        if paper.authors:
            authors_str = paper.author_string
            print(f"Authors ({len(paper.authors)}): {authors_str}")

        if paper.year:
            print(f"Year: {paper.year}")

        if paper.doi:
            print(f"DOI: {paper.doi}")

        if paper.journal:
            journal_info = f"Journal: {paper.journal}"
            if paper.volume:
                journal_info += f", Vol. {paper.volume}"
            if paper.number:
                journal_info += f", No. {paper.number}"
            if paper.pages:
                journal_info += f", pp. {paper.pages}"
            print(journal_info)

        if paper.booktitle:
            print(f"Booktitle: {paper.booktitle}")

        if paper.publisher:
            print(f"Publisher: {paper.publisher}")

        if paper.keywords:
            print(f"Keywords ({len(paper.keywords)}): {'; '.join(paper.keywords[:5])}", end="")
            if len(paper.keywords) > 5:
                print(f" ... +{len(paper.keywords) - 5} more")
            else:
                print()

        if paper.abstract:
            abstract_preview = paper.abstract[:200]
            if len(paper.abstract) > 200:
                abstract_preview += "..."
            print(f"Abstract: {abstract_preview}")

        if args.verbose:
            print("\nFull Paper Details:")
            print("-" * 80)
            pprint(paper.model_dump(), width=80)


if __name__ == "__main__":
    main()
