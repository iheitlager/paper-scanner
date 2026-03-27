#!/usr/bin/env python3
"""
Comprehensive model comparison for paper extraction
"""

import json
import subprocess
import time
from typing import Dict, List


class ModelTester:
    def __init__(self):
        self.results = []

    def test_extraction_quality(self, model: str, prompt: str) -> Dict:
        """
        Test a model's extraction quality
        """

        print(f"\nTesting {model}...")

        start = time.time()

        # Use Ollama for simplicity
        result = subprocess.run(["ollama", "run", model, prompt], capture_output=True, text=True, timeout=60)

        elapsed = time.time() - start
        response = result.stdout

        # Evaluate response
        quality_score = self.evaluate_quality(response)

        return {"model": model, "response": response, "time": elapsed, "quality_score": quality_score}

    def evaluate_quality(self, response: str) -> Dict:
        """
        Score the extraction quality
        """

        score = {
            "has_title": 1 if "title" in response.lower() else 0,
            "has_authors": 1 if "author" in response.lower() else 0,
            "has_year": 1 if "2021" in response else 0,
            "is_json": 1 if "{" in response and "}" in response else 0,
            "has_correct_title": 1 if "digital tech" in response.lower() else 0,
        }

        score["total"] = sum(score.values()) / len(score) * 100

        return score

    def run_comparison(self, models: List[str], test_cases: List[str]):
        """
        Run comprehensive comparison
        """

        for model in models:
            for i, test in enumerate(test_cases):
                result = self.test_extraction_quality(model, test)
                result["test_case"] = i
                self.results.append(result)

        self.generate_report()

    def generate_report(self):
        """
        Generate comparison report
        """

        print("\n" + "=" * 80)
        print("MODEL COMPARISON REPORT")
        print("=" * 80)

        # Group by model
        by_model = {}
        for r in self.results:
            model = r["model"]
            if model not in by_model:
                by_model[model] = []
            by_model[model].append(r)

        # Print summary
        print(f"\n{'Model':<20} {'Avg Time':<12} {'Avg Quality':<15} {'JSON %'}")
        print("-" * 80)

        for model, results in by_model.items():
            avg_time = sum(r["time"] for r in results) / len(results)
            avg_quality = sum(r["quality_score"]["total"] for r in results) / len(results)
            json_pct = sum(r["quality_score"]["is_json"] for r in results) / len(results) * 100

            print(f"{model:<20} {avg_time:>6.1f}s       {avg_quality:>6.1f}%          {json_pct:>5.0f}%")

        # Save detailed results
        with open("detailed_comparison.json", "w") as f:
            json.dump(self.results, f, indent=2)

        print("\nDetailed results saved to: detailed_comparison.json")


# Usage
if __name__ == "__main__":
    tester = ModelTester()

    models = ["phi", "llama3.2:1b", "gemma:2b", "tinyllama"]

    test_cases = [
        """Extract in JSON format - title, authors (array), year:

"Digital technologies, innovation, and skills: Emerging trajectories and challenges" by Tommaso Ciarli, Martin Kenney, Silvia Massini, and Lucia Piscitello (2021)

JSON:""",
        """Extract paper metadata as JSON:

Correani, A., De Massis, A., Frattini, F., Messeni Petruzzelli, A., & Natalicchio, A. (2020). Implementing a Digital Strategy. California Management Review, 62(4), 37-56.

JSON:""",
    ]

    tester.run_comparison(models, test_cases)
