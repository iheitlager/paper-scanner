"""
Test 001: Regex Pattern-Based Classification

This test uses regex patterns to classify papers by study type and extract metadata
from PDF text. It measures accuracy, latency, and pattern coverage.

Expected patterns:
- Quantitative: "quantitative", "statistical", "regression", "ANOVA", "t-test"
- Qualitative: "qualitative", "interview", "ethnograph", "thematic"
- Mixed Methods: "mixed method", "sequential", "concurrent"
- Literature Review: "literature review", "systematic review", "meta-analysis"
- Conceptual: "conceptual", "theoretical framework", "model"
"""

import json
import time
import re
from pathlib import Path
from typing import Dict, List, Tuple

from pypdf import PdfReader


# Define regex patterns for study type classification
STUDY_TYPE_PATTERNS = {
    "quantitative": [
        r"\bquantitative\b",
        r"\bstatistical(ly)?\b",
        r"\bregression\b",
        r"\bANOVA\b",
        r"\bt[- ]?test\b",
        r"\bchi[- ]?square\b",
        r"\bcorrelation\b",
        r"\bhypothesis testing\b",
        r"\bnumerical analysis\b",
    ],
    "qualitative": [
        r"\bqualitative\b",
        r"\binterview(s)?\b",
        r"\bethnograph(ic|y)?\b",
        r"\bthematic analysis\b",
        r"\bcontent analysis\b",
        r"\bgrounded theory\b",
        r"\bnarrative\b",
        r"\bfocus group(s)?\b",
    ],
    "mixed_methods": [
        r"\bmixed[- ]?methods?\b",
        r"\bsequential mixed\b",
        r"\bconcurrent mixed\b",
        r"\btriangulation\b",
        r"\bmulti[- ]?method\b",
    ],
    "literature_review": [
        r"\bliterature review\b",
        r"\bsystematic review\b",
        r"\bmeta[- ]?analysis\b",
        r"\bscoping review\b",
        r"\bnarrativereview\b",
    ],
    "conceptual": [
        r"\bconceptual\b",
        r"\btheoretical framework\b",
        r"\btheory building\b",
        r"\btheoretical model\b",
    ],
    "editorial": [
        r"\beditorial\b",
        r"\beditor'?s?\s+note\b",
        r"\bletter to (the )?editor\b",
        r"\bguest editorial\b",
        r"\bcommentary\b",
        r"\bperspective\b",
    ],
}


def extract_text_from_pdf(pdf_path: str, max_pages: int = 3) -> str:
    """Extract text from PDF file."""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        # Scan at least 3 pages to handle extra front pages
        for page_num in range(min(max_pages, len(reader.pages))):
            page = reader.pages[page_num]
            text += page.extract_text()
        return text.lower()
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return ""


def extract_title(text: str) -> str:
    """Extract title from PDF text."""
    # Look for title patterns
    # Often at the beginning or marked with uppercase
    lines = text.split("\n")[:10]  # Check first 10 lines
    
    for line in lines:
        line = line.strip()
        # Skip short lines and common headers
        if len(line) > 20 and len(line) < 200 and not line.startswith("http"):
            # Likely title if it's uppercase or title case
            if line[0].isupper():
                return line
    
    return ""


def extract_abstract(text: str) -> str:
    """Extract abstract section from text."""
    # Look for abstract section
    abstract_match = re.search(
        r"abstract\s*[:–\-]?\s*(.{100,1500}?)(?:\n\s*(?:introduction|keywords|1\.|method|background))",
        text,
        re.IGNORECASE | re.DOTALL
    )
    
    if abstract_match:
        abstract = abstract_match.group(1)
        abstract = re.sub(r"\s+", " ", abstract).strip()
        return abstract[:800]
    
    # Return empty string if not found (some papers don't have abstracts)
    return ""


def extract_keywords(text: str) -> List[str]:
    """Extract keywords from PDF text."""
    keywords_match = re.search(
        r"keywords?:?\s*([^\n]+?)(?:\n|$)",
        text,
        re.IGNORECASE
    )
    
    if keywords_match:
        keywords_str = keywords_match.group(1)
        # Split by comma, semicolon, or "and"
        keywords = re.split(r"[,;]\s*|and\s+", keywords_str)
        keywords = [k.strip() for k in keywords if k.strip()]
        return keywords[:15]  # Limit to 15 keywords
    
    return []


def classify_study_type_regex(text: str, keywords: List[str] = None) -> Tuple[str, int]:
    """
    Classify study type based on regex patterns and keywords.
    
    Keywords are given higher weight in classification.
    
    Returns:
        (study_type, pattern_count): Study type and number of matched patterns
    """
    scores = {}
    
    for study_type, patterns in STUDY_TYPE_PATTERNS.items():
        matches = 0
        for pattern in patterns:
            matches += len(re.findall(pattern, text, re.IGNORECASE))
        scores[study_type] = matches
    
    # Boost score if keywords match study type
    if keywords:
        keywords_lower = [k.lower() for k in keywords]
        keywords_text = " ".join(keywords_lower)
        
        for study_type, patterns in STUDY_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, keywords_text, re.IGNORECASE):
                    # Keywords are strong signal, boost by 5
                    scores[study_type] += 5
    
    # Find the study type with highest score
    if max(scores.values()) == 0:
        return "unknown", 0
    
    best_type = max(scores, key=scores.get)
    return best_type, scores[best_type]


def extract_metadata_regex(text: str) -> Dict:
    """Extract basic metadata using regex patterns."""
    metadata = {
        "keywords": [],
        "has_abstract": False,
        "has_methods": False,
        "has_results": False,
    }
    
    # Check for common sections
    if re.search(r"abstract", text):
        metadata["has_abstract"] = True
    
    if re.search(r"(method|methodology|procedure)", text):
        metadata["has_methods"] = True
    
    if re.search(r"(result|findings|outcome)", text):
        metadata["has_results"] = True
    
    # Extract keywords if present
    keywords_match = re.search(
        r"keywords?:?\s*([^\n]+)",
        text,
        re.IGNORECASE
    )
    if keywords_match:
        keywords_str = keywords_match.group(1)
        metadata["keywords"] = [
            k.strip() for k in keywords_str.split(",")
        ][:10]  # First 10 keywords
    
    return metadata


def process_pdfs_regex() -> Dict:
    """Process all PDFs in tests/data using regex classification."""
    test_data_dir = Path(__file__).parent.parent.parent / "data"
    pdf_files = sorted(test_data_dir.glob("*.pdf"))
    
    results = {
        "method": "regex_patterns",
        "timestamp": time.time(),
        "papers_processed": 0,
        "papers": [],
        "total_latency_ms": 0,
        "accuracy_estimate": None,
    }
    
    print(f"Processing {len(pdf_files)} PDFs with regex patterns...")
    
    for pdf_path in pdf_files:
        start_time = time.time()
        
        # Extract text
        text = extract_text_from_pdf(str(pdf_path))
        if not text:
            print(f"⚠️  Skipped {pdf_path.name} (no text extracted)")
            continue
        
        # Extract metadata
        title = extract_title(text)
        abstract = extract_abstract(text)
        keywords = extract_keywords(text)
        
        # Classify using text and keywords
        study_type, pattern_count = classify_study_type_regex(text, keywords)
        metadata = extract_metadata_regex(text)
        
        latency_ms = (time.time() - start_time) * 1000
        
        paper_result = {
            "filename": pdf_path.name,
            "title": title,
            "abstract": abstract if abstract else "(no abstract found)",
            "keywords": keywords,
            "study_type": study_type,
            "pattern_count": pattern_count,
            "metadata": metadata,
            "latency_ms": latency_ms,
            "text_length": len(text),
            "has_abstract": bool(abstract),
        }
        
        results["papers"].append(paper_result)
        results["papers_processed"] += 1
        results["total_latency_ms"] += latency_ms
        
        keywords_str = ", ".join(keywords[:3]) if keywords else "no keywords"
        print(f"✓ {pdf_path.name}: {study_type} | Keywords: {keywords_str} ({latency_ms:.1f}ms)")
    
    results["avg_latency_ms"] = (
        results["total_latency_ms"] / results["papers_processed"]
        if results["papers_processed"] > 0
        else 0
    )
    
    return results


def save_results(results: Dict, output_path: str):
    """Save results to JSON file."""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📊 Results saved to {output_file}")


def main():
    """Run regex classification test."""
    print("=" * 60)
    print("TEST 001: Regex Pattern-Based Classification")
    print("=" * 60)
    
    results = process_pdfs_regex()
    
    # Print summary
    print(f"\n📈 Summary:")
    print(f"  Papers processed: {results['papers_processed']}")
    print(f"  Total latency: {results['total_latency_ms']:.1f}ms")
    print(f"  Avg latency/paper: {results['avg_latency_ms']:.1f}ms")
    
    # Save results
    output_dir = Path(__file__).parent / "outputs"
    output_dir.mkdir(exist_ok=True)
    save_results(results, str(output_dir / "results_001_regex.json"))
    
    return results


if __name__ == "__main__":
    results = main()
