#!/usr/bin/env python3
"""
Show top papers with screening status and APA formatting.

Displays papers grouped by screening stage with recommendations.

Usage:
    python show_top_papers.py [--db-url <url>] [--verbose]
"""

import argparse
import os
import sys
from typing import Dict, List, Optional

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

# Color codes for terminal output
class Color:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    DIM = '\033[2m'


def format_authors_apa(authors: List[Dict]) -> str:
    """Format authors in APA style."""
    if not authors:
        return "Unknown Author"
    
    author_names = []
    for author in authors[:3]:  # Show first 3 authors
        last = author.get('last_name', '')
        first = author.get('first_name', '')
        initials = author.get('initials', '')
        
        if initials:
            author_names.append(f"{last}, {initials}")
        elif first:
            # Use first initial if no initials extracted
            first_initial = first.split()[0][0] if first else ''
            author_names.append(f"{last}, {first_initial}.")
        else:
            author_names.append(last)
    
    if len(authors) > 3:
        return ', '.join(author_names[:-1]) + f", & {author_names[-1]}, et al."
    elif len(author_names) > 1:
        return ', '.join(author_names[:-1]) + f", & {author_names[-1]}"
    else:
        return author_names[0] if author_names else "Unknown Author"


def format_apa_citation(paper: Dict) -> str:
    """Format paper in APA style."""
    authors = paper.get('authors', [])
    author_str = format_authors_apa(authors)
    
    year = paper.get('year', 'n.d.')
    title = paper.get('title', 'Unknown Title')
    journal = paper.get('journal', '')
    volume = paper.get('volume', '')
    issue = paper.get('issue', '')
    pages = paper.get('pages', '')
    doi = paper.get('doi', '')
    
    # Basic APA format: Author(s). (Year). Title. Journal, Volume(Issue), pages. DOI
    citation = f"{author_str} ({year}). {title}."
    
    if journal:
        citation += f" {Color.CYAN}{journal}{Color.END}"
        if volume:
            citation += f", {volume}"
            if issue:
                citation += f"({issue})"
        if pages:
            citation += f", {pages}"
    
    if doi:
        citation += f" https://doi.org/{doi}"
    
    return citation


def get_papers_status(db_url: str) -> Dict:
    """Query papers and their screening status."""
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check screening status
        cursor.execute("""
        SELECT 
            COUNT(CASE WHEN screening_stage IS NOT NULL THEN 1 END) as screened,
            COUNT(*) as total
        FROM paper_screening
        """)
        status = cursor.fetchone()
        screened_count = status['screened'] or 0
        total_count = status['total'] or 0
        
        cursor.close()
        conn.close()
        
        return {'screened': screened_count, 'total': total_count}
    except Exception as e:
        return {'screened': 0, 'total': 0, 'error': str(e)}


def get_papers(db_url: str, verbose: bool = False) -> Dict[str, List[Dict]]:
    """Get papers grouped by screening stage."""
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if screening has been done
        cursor.execute("SELECT COUNT(CASE WHEN screening_stage IS NOT NULL THEN 1 END) as count FROM paper_screening")
        screened = cursor.fetchone()['count'] or 0
        
        papers = {'included': [], 'manual_review': [], 'top_10': []}
        
        if screened == 0:
            # No screening done - show top 10 by year
            if verbose:
                print(f"{Color.DIM}No screening data found. Showing top 10 papers by year.{Color.END}\n")
            
            cursor.execute("""
                SELECT 
                    p.id,
                    p.citekey,
                    p.title,
                    p.year,
                    p.authors,
                    p.abstract,
                    p.journal,
                    p.volume,
                    p.issue,
                    p.pages,
                    p.doi,
                    NULL as semantic_similarity,
                    NULL as screening_stage
                FROM papers p
                ORDER BY p.year DESC, p.id ASC
                LIMIT 10
            """)
            papers['top_10'] = cursor.fetchall()
        else:
            # Show papers that passed or need review (grouped)
            cursor.execute("""
                SELECT 
                    p.id,
                    p.citekey,
                    p.title,
                    p.year,
                    p.authors,
                    p.abstract,
                    p.journal,
                    p.volume,
                    p.issue,
                    p.pages,
                    p.doi,
                    ps.semantic_similarity,
                    ps.screening_stage,
                    ps.manual_review_reason
                FROM papers p
                LEFT JOIN paper_screening ps ON p.id = ps.paper_id
                WHERE ps.screening_stage IN ('stage2_pass', 'stage2_review')
                   OR (ps.screening_stage = 'stage1_pass' AND ps.stage2_processed_at IS NULL)
                ORDER BY 
                    CASE 
                        WHEN ps.screening_stage = 'stage2_pass' THEN 1
                        WHEN ps.screening_stage = 'stage2_review' THEN 2
                        ELSE 3
                    END,
                    ps.semantic_similarity DESC NULLS LAST,
                    p.year DESC
            """)
            
            all_papers = cursor.fetchall()
            for paper in all_papers:
                stage = paper.get('screening_stage', '')
                if stage == 'stage2_pass':
                    papers['included'].append(paper)
                elif stage == 'stage2_review':
                    papers['manual_review'].append(paper)
        
        cursor.close()
        conn.close()
        
        return papers
    
    except psycopg2.Error as e:
        print(f"{Color.RED}Error connecting to database: {e}{Color.END}")
        sys.exit(1)


def get_reason(paper: Dict) -> str:
    """Get human-readable reason for inclusion."""
    stage = paper.get('screening_stage')
    similarity = paper.get('semantic_similarity')
    manual_review_reason = paper.get('manual_review_reason')
    
    reasons = []
    
    if similarity:
        if similarity >= 0.65:
            reasons.append(f"High semantic match ({similarity:.3f})")
        elif similarity >= 0.55:
            reasons.append(f"Moderate semantic match ({similarity:.3f})")
    
    if manual_review_reason:
        reasons.append(manual_review_reason)
    
    return " • ".join(reasons) if reasons else "Stage 1 passed (awaiting Stage 2)"


def display_paper(idx: int, paper: Dict, include_similarity: bool = True) -> None:
    """Display a single paper with formatting."""
    citekey = paper.get('citekey', 'N/A')
    year = paper.get('year', 'n.d.')
    
    # Print APA citation
    citation = format_apa_citation(paper)
    print(f"{Color.BOLD}{idx}. {citation}{Color.END}")
    
    # Print abstract if available
    abstract = paper.get('abstract', '')
    if abstract:
        abstract_short = abstract[:200] + "..." if len(abstract) > 200 else abstract
        print(f"   {Color.DIM}Abstract: {abstract_short}{Color.END}")
    
    # Print metadata
    metadata = []
    if paper.get('journal'):
        metadata.append(f"Journal: {paper['journal']}")
    if citekey:
        metadata.append(f"BibTeX: {Color.BLUE}{citekey}{Color.END}")
    
    if metadata:
        print(f"   {' | '.join(metadata)}")
    
    # Print reason/similarity
    if include_similarity:
        reason = get_reason(paper)
        stage = paper.get('screening_stage')
        
        if stage == 'stage2_pass':
            indicator = f"{Color.GREEN}✓ INCLUDE{Color.END}"
        elif stage == 'stage2_review':
            indicator = f"{Color.YELLOW}⚠ MANUAL REVIEW{Color.END}"
        else:
            indicator = f"{Color.BLUE}ℹ PENDING{Color.END}"
        
        print(f"   {indicator} | {reason}")
    
    print()


def display_papers(papers_dict: Dict) -> None:
    """Display papers grouped by stage."""
    print(f"\n{Color.BOLD}{Color.CYAN}{'='*130}{Color.END}")
    print(f"{Color.BOLD}📚 PAPER SCREENING RESULTS{Color.END}")
    print(f"{Color.BOLD}{Color.CYAN}{'='*130}{Color.END}\n")
    
    # Included papers
    if papers_dict['included']:
        print(f"{Color.BOLD}{Color.GREEN}✓ INCLUDED ({len(papers_dict['included'])} papers){Color.END}")
        print(f"{Color.GREEN}{'-'*130}{Color.END}")
        for idx, paper in enumerate(papers_dict['included'], 1):
            display_paper(idx, paper, include_similarity=True)
    
    # Manual review papers
    if papers_dict['manual_review']:
        print(f"\n{Color.BOLD}{Color.YELLOW}⚠ REQUIRES MANUAL REVIEW ({len(papers_dict['manual_review'])} papers){Color.END}")
        print(f"{Color.YELLOW}{'-'*130}{Color.END}")
        for idx, paper in enumerate(papers_dict['manual_review'], 1):
            display_paper(idx, paper, include_similarity=True)
    
    # Top 10 (no screening)
    if papers_dict['top_10']:
        print(f"\n{Color.BOLD}{Color.BLUE}📊 TOP 10 PAPERS BY YEAR (No Screening Yet){Color.END}")
        print(f"{Color.BLUE}{'-'*130}{Color.END}")
        print(f"{Color.DIM}Run Stage 1 and Stage 2 screening to filter these papers.{Color.END}\n")
        for idx, paper in enumerate(papers_dict['top_10'], 1):
            display_paper(idx, paper, include_similarity=False)
    
    if not papers_dict['included'] and not papers_dict['manual_review'] and not papers_dict['top_10']:
        print(f"{Color.YELLOW}ℹ No papers found in database{Color.END}")
    
    print(f"{Color.BOLD}{Color.CYAN}{'='*130}{Color.END}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Show papers from database with screening status")
    parser.add_argument("--db-url", default=os.getenv("DATABASE_URL", "postgresql://pdfuser:pdfpass@localhost:5432/pdfdb"),
                       help="Database URL")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    load_dotenv()
    
    # Get and display papers
    papers = get_papers(args.db_url, verbose=args.verbose)
    display_papers(papers)
    
    # Show action items
    if papers['included'] or papers['manual_review']:
        print(f"{Color.BOLD}📋 NEXT STEPS:{Color.END}")
        if papers['manual_review']:
            print(f"   {Color.YELLOW}→ Review {len(papers['manual_review'])} borderline paper(s) (0.55-0.65 similarity){Color.END}")
        if not papers['included']:
            print(f"   {Color.BLUE}→ Run Stage 3 for LLM classification of borderline papers{Color.END}")
        else:
            print(f"   {Color.GREEN}→ {len(papers['included'])} paper(s) ready for detailed analysis{Color.END}")
    elif papers['top_10']:
        print(f"{Color.BOLD}📋 NEXT STEPS:{Color.END}")
        print(f"   {Color.BLUE}→ Run: python stage1_keyword_screening.py{Color.END}")
        print(f"   {Color.BLUE}→ Then: python stage2_semantic_screening.py{Color.END}")
    
    print()


if __name__ == '__main__':
    main()
