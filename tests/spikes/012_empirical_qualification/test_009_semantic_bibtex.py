#!/usr/bin/env python3
"""
Test 009: Semantic Screening on BibTeX Data

Tests semantic embedding models on abstracts from BibTeX, specialized for scientific papers.

Models tested:
1. allenai/specter - Specialized for scientific papers (768 dim)
2. sentence-transformers/all-mpnet-base-v2 - Best general model (768 dim)
3. sentence-transformers/all-MiniLM-L6-v2 - Fast baseline (384 dim)

This test uses abstract text from BibTeX instead of PDF extraction,
separating fact extraction from classification.
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import bibtexparser
from bibtexparser.bparser import BibTexParser
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))


def load_bibtex_data(bibtex_path: Path) -> Dict[str, Dict[str, str]]:
    """Load abstract and keywords from BibTeX file."""
    with open(bibtex_path, "r", encoding="utf-8") as f:
        parser = BibTexParser(common_strings=True)
        bib_database = bibtexparser.load(f, parser=parser)
    
    papers = {}
    for entry in bib_database.entries:
        paper_id = entry.get("pdf", "unknown").replace(".pdf", "")
        papers[paper_id] = {
            "title": entry.get("title", ""),
            "abstract": entry.get("abstract", ""),
            "keywords": entry.get("keywords", ""),
            "ground_truth": entry.get("papertype", "unknown"),
        }
    return papers


def get_category_descriptors() -> Dict[str, List[str]]:
    """
    Enhanced category descriptors based on academic paper characteristics.
    Each category has multiple descriptive phrases for better semantic matching.
    """
    return {
        "qualitative": [
            "qualitative research methodology interviews observations",
            "ethnographic study fieldwork qualitative analysis",
            "thematic analysis coding grounded theory",
            "interpretive research phenomenological approach",
            "qualitative data collection participant observation"
        ],
        "case_study": [
            "case study empirical investigation real-world",
            "single case multiple cases longitudinal study",
            "in-depth case analysis organizational case",
            "exploratory case research case study methodology",
            "empirical case evidence practical implications"
        ],
        "quantitative": [
            "quantitative analysis statistical methods survey",
            "regression analysis hypothesis testing empirical data",
            "large-scale survey questionnaire statistical significance",
            "experimental design control group treatment",
            "quantitative measurement statistical model correlation"
        ],
        "mixed_methods": [
            "mixed methods combining qualitative quantitative",
            "triangulation multi-method research design",
            "sequential explanatory mixed approach",
            "convergent parallel mixed methodology",
            "integrating qualitative and quantitative data"
        ],
        "literature_review": [
            "systematic literature review meta-analysis synthesis",
            "review of existing literature prior research",
            "comprehensive review academic publications",
            "bibliometric analysis citation analysis",
            "systematic review research trends state of the art"
        ],
        "conceptual": [
            "conceptual framework theoretical model",
            "theoretical development propositions concepts",
            "conceptual analysis philosophical foundations",
            "theoretical contribution conceptual lens",
            "framework development theoretical perspective"
        ],
        "editorial": [
            "editorial commentary perspective opinion",
            "research agenda future directions call",
            "reflections insights discussion implications",
            "editorial introduction special issue",
            "perspective piece viewpoint commentary"
        ]
    }


def classify_with_embeddings(
    abstract: str,
    model: SentenceTransformer,
    category_embeddings: Dict[str, np.ndarray],
    model_name: str
) -> Tuple[str, float, int]:
    """
    Classify paper based on semantic similarity with category descriptors.
    
    Returns:
        (category, confidence, latency_ms)
    """
    if not abstract or abstract == "No abstract available":
        return "unknown", 0.0, 0
    
    start = time.time()
    
    # Encode abstract
    abstract_embedding = model.encode([abstract], show_progress_bar=False)[0]
    
    # Calculate similarity with each category
    similarities = {}
    for category, category_emb in category_embeddings.items():
        # Average similarity across all descriptors for this category
        sim = cosine_similarity(
            abstract_embedding.reshape(1, -1),
            category_emb
        )[0]
        similarities[category] = np.mean(sim)
    
    # Get best match
    best_category = max(similarities.items(), key=lambda x: x[1])
    latency_ms = int((time.time() - start) * 1000)
    
    return best_category[0], float(best_category[1]), latency_ms


def normalize_category(category: str) -> str:
    """Normalize category names."""
    category = category.lower().strip().replace(" ", "_")
    
    mappings = {
        "case study": "case_study",
        "case-study": "case_study",
        "mixed methods": "mixed_methods",
        "mixed-methods": "mixed_methods",
        "literature review": "literature_review",
        "literature-review": "literature_review",
        "qualitative study": "qualitative",
        "quantitative study": "quantitative",
        "commentary": "editorial",
        "commentory": "editorial",
    }
    
    return mappings.get(category, category)


def test_model(
    model_name: str,
    papers: Dict[str, Dict[str, str]],
    output_dir: Path
) -> Dict:
    """Test a specific model on all papers."""
    
    print(f"\n{'=' * 80}")
    print(f"Testing Model: {model_name}")
    print(f"{'=' * 80}")
    print(f"Loading model...")
    
    # Load model
    model = SentenceTransformer(model_name)
    
    # Encode category descriptors
    print(f"Encoding category descriptors...")
    category_descriptors = get_category_descriptors()
    category_embeddings = {}
    
    for category, descriptors in category_descriptors.items():
        embeddings = model.encode(descriptors, show_progress_bar=False)
        category_embeddings[category] = embeddings
    
    # Test on papers
    results = {}
    correct = 0
    total_latency = 0
    
    print(f"\nClassifying {len(papers)} papers...")
    
    for i, (paper_id, paper_data) in enumerate(papers.items(), 1):
        title_short = paper_data["title"][:50] + "..." if len(paper_data["title"]) > 50 else paper_data["title"]
        print(f"\n[{i}/{len(papers)}] {title_short}")
        print(f"   Ground truth: {paper_data['ground_truth']}")
        
        # Classify
        predicted, confidence, latency = classify_with_embeddings(
            paper_data["abstract"],
            model,
            category_embeddings,
            model_name
        )
        
        # Check correctness
        expected = normalize_category(paper_data["ground_truth"])
        is_correct = predicted == expected
        
        if is_correct:
            correct += 1
            print(f"   ✓ Predicted: {predicted} (confidence: {confidence:.3f})")
        else:
            print(f"   ✗ Predicted: {predicted} (expected: {expected})")
            print(f"     Confidence: {confidence:.3f}")
        
        print(f"   Latency: {latency}ms")
        total_latency += latency
        
        results[paper_id] = {
            "predicted": predicted,
            "confidence": confidence,
            "latency_ms": latency,
            "ground_truth": expected,
            "correct": is_correct
        }
    
    # Calculate metrics
    accuracy = (correct / len(papers)) * 100 if papers else 0
    avg_latency = total_latency / len(papers) if papers else 0
    
    print(f"\n{'=' * 80}")
    print(f"Results for {model_name}:")
    print(f"{'=' * 80}")
    print(f"Accuracy:      {correct}/{len(papers)} ({accuracy:.1f}%)")
    print(f"Avg Latency:   {avg_latency:.1f}ms")
    print(f"Total Time:    {total_latency/1000:.1f}s")
    
    # Save results
    model_safe = model_name.replace("/", "_").replace("-", "_")
    output_file = output_dir / f"test_009_semantic_{model_safe}_results.json"
    
    ground_truth = {
        paper_id: normalize_category(data["ground_truth"])
        for paper_id, data in papers.items()
    }
    
    output_data = {
        "model": model_name,
        "accuracy": accuracy,
        "correct": correct,
        "total": len(papers),
        "avg_latency_ms": avg_latency,
        "total_latency_ms": total_latency,
        "ground_truth": ground_truth,
        "results": results
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Results saved to {output_file.name}")
    
    return output_data


def main():
    """Run semantic classification on BibTeX data."""
    print("=" * 80)
    print("Test 009: Semantic Screening on BibTeX Data")
    print("=" * 80)
    
    # Configuration
    bibtex_path = Path(__file__).parent.parent.parent / "data" / "eight_cases.bib"
    output_dir = Path(__file__).parent
    
    # Models to test (best for scientific papers)
    models = [
        "allenai/specter",                              # Specialized for scientific papers
        "BAAI/bge-base-en-v1.5",                       # BGE - state of the art
        "intfloat/e5-base-v2",                         # E5 - strong semantic
        "sentence-transformers/all-mpnet-base-v2",     # Best general purpose
        "sentence-transformers/all-MiniLM-L6-v2",      # Fast baseline
    ]
    
    # Load BibTeX data
    print(f"\n📚 Loading papers from {bibtex_path.name}...")
    papers = load_bibtex_data(bibtex_path)
    print(f"   Loaded {len(papers)} papers with abstracts")
    
    # Check abstracts
    abstracts_available = sum(1 for p in papers.values() if p["abstract"])
    print(f"   Abstracts available: {abstracts_available}/{len(papers)}")
    
    # Test each model
    all_results = []
    for model_name in models:
        try:
            result = test_model(model_name, papers, output_dir)
            all_results.append(result)
        except Exception as e:
            print(f"\n⚠️  Error testing {model_name}: {e}")
            continue
    
    # Summary comparison
    if all_results:
        print(f"\n{'=' * 80}")
        print("Model Comparison Summary")
        print(f"{'=' * 80}")
        print(f"{'Model':<50} {'Accuracy':<12} {'Avg Latency':<12}")
        print("-" * 80)
        
        for result in all_results:
            model_short = result["model"].split("/")[-1][:48]
            print(f"{model_short:<50} {result['accuracy']:>6.1f}%     {result['avg_latency_ms']:>8.1f}ms")
        
        # Best model
        best = max(all_results, key=lambda x: x["accuracy"])
        print(f"\n🏆 Best Model: {best['model']} ({best['accuracy']:.1f}% accuracy)")
    
    print(f"\n{'=' * 80}")
    print("All models tested!")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
