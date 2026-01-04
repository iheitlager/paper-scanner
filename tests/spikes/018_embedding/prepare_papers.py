#!/usr/bin/env python3
"""
Prepare papers from BibTeX file into JSONL format with PDF attachments.

This script:
1. Parses eight_cases.bib using bibtexparser
2. Creates Paper models with PDFInfo attached
3. Exports to papers_with_pdfs.jsonl for use in test_02
"""

import json
import logging
from pathlib import Path

import bibtexparser

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Import from paper_scanner
from paper_scanner.core.models import Paper, PDFInfo
from paper_scanner.io.bibtex import bibtex_file_to_papers


def prepare_papers_jsonl():
    """Parse BibTeX and create JSONL with PDF attachments."""
    
    # Paths
    tests_dir = Path(__file__).parent.parent.parent  # tests/
    bib_path = tests_dir / "data" / "eight_cases.bib"
    data_dir = tests_dir / "data"
    output_path = Path(__file__).parent / "papers_with_pdfs.jsonl"
    
    logger.info(f"Reading BibTeX: {bib_path}")
    if not bib_path.exists():
        raise FileNotFoundError(f"BibTeX file not found: {bib_path}")
    
    # Load papers using the standard handler
    papers = bibtex_file_to_papers(str(bib_path))
    logger.info(f"✓ Loaded {len(papers)} papers from BibTeX")
    
    # Parse BibTeX again to get PDF field
    with open(bib_path, 'r') as f:
        bib_str = f.read()
    
    parser = bibtexparser.bparser.BibTexParser(common_strings=False)
    bibtex_db = bibtexparser.loads(bib_str, parser=parser)
    
    # Create map: cite_key → entry dict
    bibtex_map = {entry['ID']: entry for entry in bibtex_db.entries}
    logger.info(f"  Parsed {len(bibtex_map)} BibTeX entries")
    
    # Attach PDFs to papers
    papers_with_pdfs = 0
    for paper in papers:
        if paper.cite_key in bibtex_map:
            entry = bibtex_map[paper.cite_key]
            pdf_filename = entry.get('pdf')
            
            if pdf_filename:
                pdf_path = data_dir / pdf_filename
                if pdf_path.exists():
                    paper.pdf_info = PDFInfo(
                        file_path=str(pdf_path),
                        file_name=pdf_filename,
                        file_size_bytes=pdf_path.stat().st_size,
                        download_source="bibtex_embedded"
                    )
                    papers_with_pdfs += 1
                    logger.info(f"  ✓ {paper.cite_key}: {pdf_filename}")
                else:
                    logger.warning(f"  ✗ PDF not found: {pdf_path}")
            else:
                logger.warning(f"  ✗ No PDF field in BibTeX for {paper.cite_key}")
    
    logger.info(f"✓ Attached PDFs to {papers_with_pdfs}/{len(papers)} papers")
    
    # Export to JSONL
    logger.info(f"Writing JSONL: {output_path}")
    with open(output_path, 'w') as f:
        for paper in papers:
            # Serialize using Pydantic's model_dump
            json_line = json.dumps(paper.model_dump(mode='json'))
            f.write(json_line + '\n')
    
    logger.info(f"✓ Exported {len(papers)} papers to {output_path}")
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info(f"SUMMARY:")
    logger.info(f"  Input: {bib_path}")
    logger.info(f"  Output: {output_path}")
    logger.info(f"  Papers: {len(papers)}")
    logger.info(f"  With PDFs: {papers_with_pdfs}")
    logger.info("="*60)
    
    return output_path


if __name__ == "__main__":
    output_path = prepare_papers_jsonl()
    print(f"\n✓ Ready to use: {output_path}")
