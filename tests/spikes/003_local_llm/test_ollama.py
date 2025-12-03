#!/usr/bin/env python3
"""
Test multiple models via Ollama
"""

import subprocess
import json
import time

MODELS = [
    'phi',
    'phi3',
    'llama3.2:1b',
    'llama3.2',
    'gemma:2b',
    'tinyllama',
    'qwen2.5:1.5b'
]

TEST_PROMPT = """Extract the following in JSON format:
- title
- authors (array)
- year

Text: "Digital technologies, innovation, and skills: Emerging trajectories and challenges" by Tommaso Ciarli, Martin Kenney, Silvia Massini, and Lucia Piscitello (2021)

JSON:"""

def test_model(model_name, prompt):
    """Test a model via Ollama CLI"""
    
    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    print('='*60)
    
    start = time.time()
    
    result = subprocess.run(
        ['ollama', 'run', model_name, prompt],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    elapsed = time.time() - start
    
    print(f"Response ({elapsed:.1f}s):")
    print(result.stdout)
    
    return {
        'model': model_name,
        'response': result.stdout,
        'time': elapsed
    }

# Test all models
results = []
for model in MODELS:
    try:
        result = test_model(model, TEST_PROMPT)
        results.append(result)
    except Exception as e:
        print(f"Error with {model}: {e}")

# Save results
with open('model_comparison.json', 'w') as f:
    json.dump(results, f, indent=2)

print("\n" + "="*60)
print("SUMMARY")
print("="*60)
for r in results:
    print(f"{r['model']:20s} - {r['time']:5.1f}s")