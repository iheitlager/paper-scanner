"""
Test 003: Ollama LLM Classification

This test uses Ollama with Phi3 model to classify papers by study type.
It sends prompts to the local LLM to extract and classify empirical characteristics.

Requirements:
  - Ollama installed and running (ollama serve)
  - Model pulled: ollama pull phi3:mini (or phi3.5)
"""

import json
import time
import re
from pathlib import Path
from typing import Dict, Tuple
import sys
import subprocess

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

try:
    from PyPDF2 import PdfReader
except ImportError:
    subprocess.check_call(["pip", "install", "PyPDF2"])
    from PyPDF2 import PdfReader

try:
    import requests
except ImportError:
    subprocess.check_call(["pip", "install", "requests"])
    import requests


# Ollama API endpoint
OLLAMA_API = "http://localhost:11434/api/generate"
OLLAMA_MODELS = ["phi3:mini", "phi3.5"]  # Try both models


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


def extract_abstract(text: str) -> str:
    """Extract abstract section from text."""
    # Look for abstract section
    abstract_match = re.search(
        r"abstract\s*[:–\-]?\s*(.{100,1500}?)(?:\n\s*(?:introduction|keywords|1\.|method))",
        text,
        re.IGNORECASE | re.DOTALL
    )
    
    if abstract_match:
        abstract = abstract_match.group(1)
        abstract = re.sub(r"\s+", " ", abstract).strip()
        return abstract[:500]
    
    # Use first 300 words
    words = text.split()[:50]
    return " ".join(words)


def check_ollama_running() -> bool:
    """Check if Ollama is running and accessible."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def query_ollama(prompt: str, model: str = None, timeout: int = 60) -> str:
    """Query Ollama model with prompt."""
    if model is None:
        model = OLLAMA_MODELS[0]  # Default to first model
    
    try:
        response = requests.post(
            OLLAMA_API,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
            },
            timeout=timeout,
        )
        
        if response.status_code == 200:
            return response.json().get("response", "")
        else:
            print(f"Ollama error: {response.status_code}")
            return ""
    except requests.exceptions.Timeout:
        print(f"Ollama request timed out for {model}")
        return ""
    except Exception as e:
        print(f"Error querying Ollama ({model}): {e}")
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
        r"abstract\s*[:–\-]?\s*(.{100,1500}?)(?:\n\s*(?:introduction|keywords|1\.|method))",
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


def classify_study_type_ollama(abstract: str, model: str) -> Tuple[str, str]:
    """
    Classify study type using Ollama LLM.
    
    Args:
        abstract: The abstract text
        model: Model name (phi3:mini or phi3.5)
    
    Returns:
        (study_type, reasoning): Study type and LLM reasoning
    """
    prompt = f"""Classify the following paper abstract by study type. 
Respond with ONLY the classification in this format: STUDY_TYPE: [type]

Study types:
- quantitative: numerical analysis, statistics, hypothesis testing
- qualitative: interviews, observation, thematic analysis
- mixed_methods: combination of quantitative and qualitative
- literature_review: systematic review, meta-analysis, literature synthesis
- conceptual: theoretical framework, model, conceptual analysis
- editorial: editor's perspective, commentary, opinion piece

Abstract:
{abstract}

Classification:"""
    
    response = query_ollama(prompt, model=model, timeout=120)  # Give LLM more time
    
    # Parse response
    if "STUDY_TYPE:" in response:
        type_str = response.split("STUDY_TYPE:")[-1].strip().split("\n")[0].lower()
        # Normalize
        if "quantitative" in type_str:
            study_type = "quantitative"
        elif "qualitative" in type_str:
            study_type = "qualitative"
        elif "mixed" in type_str:
            study_type = "mixed_methods"
        elif "literature" in type_str or "review" in type_str:
            study_type = "literature_review"
        elif "conceptual" in type_str or "theoretical" in type_str:
            study_type = "conceptual"
        elif "editorial" in type_str or "commentary" in type_str:
            study_type = "editorial"
        else:
            study_type = "unknown"
    else:
        study_type = "unknown"
    
    return study_type, response


def extract_metadata_ollama(abstract: str) -> Dict:
    """Extract metadata using Ollama."""
    prompt = f"""Analyze this paper abstract and extract metadata.
Respond in JSON format with: {{"keywords": [...], "methodology": "...", "has_empirical_data": true/false}}

Abstract:
{abstract}

Metadata:"""
    
    response = query_ollama(prompt)
    
    # Try to parse JSON
    try:
        # Find JSON in response
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            metadata = json.loads(json_match.group())
            return metadata
    except Exception:
        pass
    
    # Fallback
    return {
        "keywords": [],
        "methodology": "unknown",
        "has_empirical_data": "data" in abstract.lower(),
    }


def process_pdfs_ollama() -> Dict:
    """Process all PDFs using Ollama classification with both models."""
    test_data_dir = Path(__file__).parent.parent.parent / "data"
    pdf_files = sorted(test_data_dir.glob("*.pdf"))
    
    # Check Ollama
    print("Checking Ollama connection...")
    if not check_ollama_running():
        print("❌ ERROR: Ollama is not running!")
        print("Please start Ollama with: ollama serve")
        print("And pull the models with:")
        print("  ollama pull phi3:mini")
        print("  ollama pull phi3.5")
        return {
            "method": "ollama_lm",
            "models": OLLAMA_MODELS,
            "status": "error",
            "error": "Ollama not running",
            "papers": [],
        }
    
    print("✓ Ollama is running\n")
    
    results = {
        "method": "ollama_lm",
        "models": OLLAMA_MODELS,
        "timestamp": time.time(),
        "papers_processed": 0,
        "papers": [],
        "total_latency_ms": 0,
        "status": "success",
    }
    
    print(f"Processing {len(pdf_files)} PDFs with Ollama models: {', '.join(OLLAMA_MODELS)}...\n")
    
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
        
        # Classify with both models
        classifications = {}
        for model in OLLAMA_MODELS:
            study_type, reasoning = classify_study_type_ollama(abstract, model)
            classifications[model] = {
                "study_type": study_type,
                "reasoning": reasoning[:150],
            }
        
        latency_ms = (time.time() - start_time) * 1000
        
        paper_result = {
            "filename": pdf_path.name,
            "title": title,
            "abstract": abstract[:400],
            "keywords": keywords,
            "classifications": classifications,
            "metadata": extract_metadata_ollama(abstract),
            "latency_ms": latency_ms,
            "text_length": len(text),
        }
        
        results["papers"].append(paper_result)
        results["papers_processed"] += 1
        results["total_latency_ms"] += latency_ms
        
        # Display results from both models
        phi3_mini_type = classifications.get("phi3:mini", {}).get("study_type", "?")
        phi3_5_type = classifications.get("phi3.5", {}).get("study_type", "?")
        keywords_str = ", ".join(keywords[:2]) if keywords else "no keywords"
        print(f"✓ {pdf_path.name}")
        print(f"  phi3:mini → {phi3_mini_type} | phi3.5 → {phi3_5_type}")
        print(f"  Keywords: {keywords_str} | {latency_ms:.1f}ms")
    
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
    """Run Ollama classification test."""
    print("=" * 60)
    print("TEST 003: Ollama LLM Classification")
    print("=" * 60)
    
    results = process_pdfs_ollama()
    
    if results.get("status") == "error":
        print(f"\n❌ Error: {results.get('error')}")
        return results
    
    # Print summary
    print(f"\n📈 Summary:")
    print(f"  Papers processed: {results['papers_processed']}")
    print(f"  Models: {', '.join(results.get('models', []))}")
    print(f"  Total latency: {results['total_latency_ms']:.1f}ms")
    print(f"  Avg latency/paper: {results['avg_latency_ms']:.1f}ms")
    
    # Save results
    output_dir = Path(__file__).parent / "outputs"
    output_dir.mkdir(exist_ok=True)
    save_results(results, str(output_dir / "results_003_ollama.json"))
    
    return results


if __name__ == "__main__":
    results = main()
