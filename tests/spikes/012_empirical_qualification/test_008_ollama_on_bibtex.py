#!/usr/bin/env python3
"""
Test 008: Ollama Classification on BibTeX Data

Tests Ollama models using abstract + keywords from BibTeX entries
instead of PDF extraction. This separates fact extraction from categorization.

Uses the OllamaHandler from paper_scanner.models.ollama

Setup:
1. Ensure Ollama is running: ollama serve
2. Pull models if needed:
   ollama pull llama3.2:3b
   ollama pull mistral:7b
   ollama pull qwen2.5:3b
   ollama pull phi3:mini
3. Check GPU usage: Activity Monitor -> Window -> GPU History
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any
import bibtexparser
from bibtexparser.bparser import BibTexParser

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from paper_scanner.models.ollama import OllamaHandler


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
            "year": entry.get("year", ""),
            "authors": entry.get("author", ""),
            "ground_truth": entry.get("papertype", "unknown"),
        }
    return papers


def classify_with_ollama(
    paper_data: Dict[str, str], 
    handler: OllamaHandler,
    timeout: int = 180
) -> Dict[str, Any]:
    """Classify a paper using Ollama with BibTeX data."""
    
    system_prompt = """You are an expert academic paper classifier. Based on the title, abstract, and keywords provided, classify this paper into ONE of these categories:

Categories:
- qualitative: Empirical qualitative research (interviews, observations, ethnography)
- case_study: Empirical case study research (single or multiple cases)
- quantitative: Empirical quantitative research (surveys, experiments, statistical analysis)
- mixed_methods: Combines qualitative and quantitative methods
- literature_review: Systematic review, meta-analysis, literature survey
- conceptual: Theoretical framework, conceptual model, opinion piece
- editorial: Editorial, commentary, perspective piece

IMPORTANT RULE: If the paper conducts NEW empirical research (case studies, interviews, experiments), classify as the empirical type (qualitative, case_study, quantitative), NOT as literature_review, even if it starts with a literature review section.

Respond ONLY with a valid JSON object in this exact format:
{"category": "one_of_the_categories_above", "confidence": 0.0-1.0, "reasoning": "brief explanation"}"""

    text = f"""Paper Information:
Title: {paper_data['title']}

Abstract: {paper_data['abstract']}

Keywords: {paper_data['keywords']}"""

    try:
        start = time.time()
        result, token_usage = handler.call(
            text=text,
            system_prompt=system_prompt,
            max_tokens=500
        )
        latency = time.time() - start
        
        if result is None:
            return {
                "category": "error",
                "confidence": 0.0,
                "reasoning": "Failed to get response from Ollama",
                "latency_ms": int(latency * 1000),
                "status": "error"
            }
        
        return {
            "category": result.get("category", "unknown"),
            "confidence": result.get("confidence", 0.0),
            "reasoning": result.get("reasoning", ""),
            "latency_ms": int(latency * 1000),
            "tokens_in": token_usage["input_tokens"],
            "tokens_out": token_usage["output_tokens"],
            "status": "success"
        }
            
    except Exception as e:
        return {
            "category": "error",
            "confidence": 0.0,
            "reasoning": f"Error: {str(e)}",
            "latency_ms": 0,
            "status": "error"
        }


def normalize_category(category: str) -> str:
    """Normalize category names."""
    category = category.lower().strip().replace(" ", "_")
    
    # Handle variations
    mappings = {
        "case study": "case_study",
        "case-study": "case_study",
        "casestudy": "case_study",
        "mixed methods": "mixed_methods",
        "mixed-methods": "mixed_methods",
        "literature review": "literature_review",
        "literature-review": "literature_review",
        "qualitative study": "qualitative",
        "quantitative study": "quantitative",
        "commentary": "editorial",
        "commentory": "editorial",
        "conceptual": "conceptual",
    }
    
    return mappings.get(category, category)


def main():
    """Run Ollama classification on BibTeX data."""
    print("=" * 80)
    print("Test 008: Ollama Classification on BibTeX Data")
    print("=" * 80)
    
    # Configuration
    bibtex_path = Path(__file__).parent.parent.parent / "data" / "eight_cases.bib"
    output_dir = Path(__file__).parent
    
    # Get all available Ollama models
    all_models = list(OllamaHandler.MODELS.keys())
    
    # Test only these models (available on user's system)
    models_to_test = ["llama3.2:3b", "phi3:mini"]  # Add more as you pull them
    
    print(f"\n📋 Available models in OllamaHandler: {', '.join(all_models)}")
    print(f"🧪 Testing models: {', '.join(models_to_test)}")
    
    # Load BibTeX data
    print(f"\n📚 Loading papers from {bibtex_path.name}...")
    papers = load_bibtex_data(bibtex_path)
    print(f"   Loaded {len(papers)} papers with abstracts and keywords")
    
    # Ground truth
    ground_truth = {
        paper_id: normalize_category(data["ground_truth"])
        for paper_id, data in papers.items()
    }
    
    # Test each model
    for model in models_to_test:
        print(f"\n{'=' * 80}")
        print(f"Testing Model: {model}")
        print(f"{'=' * 80}")
        
        # Initialize handler for this model
        handler = OllamaHandler(model=model)
        
        results = {}
        total_latency = 0
        correct = 0
        errors = 0
        
        for i, (paper_id, paper_data) in enumerate(papers.items(), 1):
            title_short = paper_data["title"][:50] + "..." if len(paper_data["title"]) > 50 else paper_data["title"]
            print(f"\n[{i}/{len(papers)}] {title_short}")
            print(f"   Ground truth: {paper_data['ground_truth']}")
            
            # Classify
            result = classify_with_ollama(paper_data, handler, timeout=180)
            
            if result["status"] == "success":
                category = normalize_category(result["category"])
                result["category"] = category
                
                # Check correctness
                expected = ground_truth[paper_id]
                is_correct = category == expected
                
                if is_correct:
                    correct += 1
                    print(f"   ✓ Predicted: {category} (confidence: {result['confidence']:.2f})")
                else:
                    print(f"   ✗ Predicted: {category} (expected: {expected})")
                    print(f"     Reasoning: {result['reasoning'][:100]}...")
                
                print(f"   Latency: {result['latency_ms']}ms | Tokens: {result['tokens_in']}→{result['tokens_out']}")
                total_latency += result["latency_ms"]
            else:
                errors += 1
                print(f"   ⚠️  ERROR: {result['reasoning']}")
            
            results[paper_id] = result
        
        # Calculate metrics
        accuracy = (correct / len(papers)) * 100 if papers else 0
        avg_latency = total_latency / (len(papers) - errors) if (len(papers) - errors) > 0 else 0
        
        print(f"\n{'=' * 80}")
        print(f"Results for {model}:")
        print(f"{'=' * 80}")
        print(f"Accuracy:      {correct}/{len(papers)} ({accuracy:.1f}%)")
        print(f"Errors:        {errors}/{len(papers)}")
        print(f"Avg Latency:   {avg_latency:.0f}ms")
        print(f"Total Time:    {total_latency/1000:.1f}s")
        
        # Save results
        model_safe = model.replace(":", "_").replace(".", "_")
        output_file = output_dir / f"test_008_ollama_{model_safe}_results.json"
        
        output_data = {
            "model": model,
            "accuracy": accuracy,
            "correct": correct,
            "total": len(papers),
            "errors": errors,
            "avg_latency_ms": avg_latency,
            "total_latency_ms": total_latency,
            "ground_truth": ground_truth,
            "results": results
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Results saved to {output_file.name}")
    
    print(f"\n{'=' * 80}")
    print("All models tested!")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
