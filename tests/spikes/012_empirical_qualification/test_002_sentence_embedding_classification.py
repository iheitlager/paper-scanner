"""
Test 002: Sentence Embedding Classification

This test uses sentence embeddings (all-MiniLM-L6-v2) to classify papers by study type.
It extracts abstracts and classifies based on semantic similarity to known study type examples.

This approach is more robust than regex and captures semantic meaning.
"""

import json
import time
import re
from pathlib import Path
from typing import Dict, List, Tuple

from pypdf import PdfReader

from sentence_transformers import SentenceTransformer, util


# Study type exemplars for semantic classification
STUDY_TYPE_EXEMPLARS = {
    "quantitative": [
        "We conducted a quantitative study using statistical analysis.",
        "This research employs regression and hypothesis testing methods.",
        "We analyzed numerical data using ANOVA and t-tests.",
        "Quantitative methods were used to measure variables and test hypotheses.",
    ],
    "qualitative": [
        "This qualitative study used interviews and thematic analysis.",
        "We conducted ethnographic research and analyzed themes.",
        "Qualitative interviews were transcribed and coded.",
        "This research uses grounded theory and qualitative content analysis.",
    ],
    "mixed_methods": [
        "We used a mixed-methods approach combining quantitative and qualitative data.",
        "This study employed both statistical analysis and interviews.",
        "Triangulation of quantitative surveys and qualitative interviews was conducted.",
        "Sequential mixed-methods design was used in this research.",
    ],
    "literature_review": [
        "This is a systematic review of published literature.",
        "We conducted a literature review to synthesize existing research.",
        "A meta-analysis of published studies was performed.",
        "This paper reviews the current state of research on this topic.",
    ],
    "conceptual": [
        "We present a theoretical framework for understanding this phenomenon.",
        "This paper develops a conceptual model of the process.",
        "A theoretical analysis of existing concepts is provided.",
        "We propose a new theoretical perspective on this issue.",
    ],
    "editorial": [
        "This editorial presents our perspective on recent developments.",
        "As editors, we introduce this special issue.",
        "This commentary discusses emerging trends in the field.",
        "We provide our thoughts on the state of the discipline.",
    ],
}


def extract_text_from_pdf(pdf_path: str, max_pages: int = 3) -> str:
    """Extract text from PDF file."""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page_num in range(min(max_pages, len(reader.pages))):
            page = reader.pages[page_num]
            text += page.extract_text()
        return text
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return ""


def extract_title(text: str) -> str:
    """Extract title from PDF text."""
    lines = text.split("\n")[:10]
    for line in lines:
        line = line.strip()
        if len(line) > 20 and len(line) < 200 and not line.startswith("http"):
            if line[0].isupper():
                return line
    return ""


def extract_abstract(text: str) -> str:
    """Extract abstract section from text."""
    abstract_match = re.search(
        r"abstract\s*[:–\-]?\s*(.{100,1500}?)(?:\n\s*(?:introduction|keywords|1\.|method|background))",
        text,
        re.IGNORECASE | re.DOTALL
    )
    
    if abstract_match:
        abstract = abstract_match.group(1)
        abstract = re.sub(r"\s+", " ", abstract).strip()
        return abstract[:800]
    
    words = text.split()[:50]
    return " ".join(words)


def extract_keywords(text: str) -> list:
    """Extract keywords from PDF text."""
    keywords_match = re.search(
        r"keywords?:?\s*([^\n]+?)(?:\n|$)",
        text,
        re.IGNORECASE
    )
    
    if keywords_match:
        keywords_str = keywords_match.group(1)
        keywords = re.split(r"[,;]\s*|and\s+", keywords_str)
        keywords = [k.strip() for k in keywords if k.strip()]
        return keywords[:15]
    
    return []


def classify_study_type_embedding(
    model: SentenceTransformer,
    text: str,
    exemplars: Dict[str, List[str]]
) -> Tuple[str, float]:
    """
    Classify study type using sentence embeddings.
    
    Returns:
        (study_type, confidence): Study type and confidence score (0-1)
    """
    # Extract abstract
    abstract = extract_abstract(text)
    
    # Encode abstract
    abstract_embedding = model.encode(abstract, convert_to_tensor=True)
    
    # Calculate similarity to each study type
    scores = {}
    for study_type, exemplar_list in exemplars.items():
        exemplar_embeddings = model.encode(exemplar_list, convert_to_tensor=True)
        similarities = util.pytorch_cos_sim(abstract_embedding, exemplar_embeddings)
        scores[study_type] = similarities.mean().item()
    
    # Find best match
    best_type = max(scores, key=scores.get)
    confidence = scores[best_type]
    
    return best_type, confidence


def extract_metadata_embedding(text: str) -> Dict:
    """Extract metadata from text."""
    import re
    
    metadata = {
        "has_abstract": "abstract" in text.lower(),
        "has_methods": bool(re.search(r"method|methodology", text, re.IGNORECASE)),
        "has_results": bool(re.search(r"result|finding|outcome", text, re.IGNORECASE)),
        "estimated_pages": len(text) // 3500,  # Rough estimate
    }
    
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
        ][:10]
    else:
        metadata["keywords"] = []
    
    return metadata


def process_pdfs_embedding() -> Dict:
    """Process all PDFs using sentence embedding classification."""
    test_data_dir = Path(__file__).parent.parent.parent / "data"
    pdf_files = sorted(test_data_dir.glob("*.pdf"))
    
    print("Loading sentence embedding model (all-MiniLM-L6-v2)...")
    model_start = time.time()
    model = SentenceTransformer("all-MiniLM-L6-v2")
    model_load_time = (time.time() - model_start) * 1000
    
    results = {
        "method": "sentence_embedding",
        "model": "all-MiniLM-L6-v2",
        "model_load_time_ms": model_load_time,
        "timestamp": time.time(),
        "papers_processed": 0,
        "papers": [],
        "total_latency_ms": 0,
    }
    
    print(f"Processing {len(pdf_files)} PDFs with embeddings...")
    print(f"Model load time: {model_load_time:.1f}ms\n")
    
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
        
        # Classify
        study_type, confidence = classify_study_type_embedding(model, text, STUDY_TYPE_EXEMPLARS)
        metadata = extract_metadata_embedding(text)
        
        latency_ms = (time.time() - start_time) * 1000
        
        paper_result = {
            "filename": pdf_path.name,
            "title": title,
            "abstract": abstract[:400],
            "keywords": keywords,
            "study_type": study_type,
            "confidence": confidence,
            "metadata": metadata,
            "latency_ms": latency_ms,
            "text_length": len(text),
        }
        
        results["papers"].append(paper_result)
        results["papers_processed"] += 1
        results["total_latency_ms"] += latency_ms
        
        confidence_pct = confidence * 100
        keywords_str = ", ".join(keywords[:2]) if keywords else "no keywords"
        print(f"✓ {pdf_path.name}: {study_type} ({confidence_pct:.1f}% | {keywords_str} | {latency_ms:.1f}ms)")
    
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
    """Run embedding classification test."""
    print("=" * 60)
    print("TEST 002: Sentence Embedding Classification")
    print("=" * 60)
    
    results = process_pdfs_embedding()
    
    # Print summary
    print(f"\n📈 Summary:")
    print(f"  Papers processed: {results['papers_processed']}")
    print(f"  Model load time: {results['model_load_time_ms']:.1f}ms")
    print(f"  Total classification latency: {results['total_latency_ms']:.1f}ms")
    print(f"  Avg latency/paper: {results['avg_latency_ms']:.1f}ms")
    
    # Save results
    output_dir = Path(__file__).parent / "outputs"
    output_dir.mkdir(exist_ok=True)
    save_results(results, str(output_dir / "results_002_embedding.json"))
    
    return results


if __name__ == "__main__":
    results = main()
