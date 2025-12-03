from transformers import pipeline

print("Loading Phi-2...")
generator = pipeline("text-generation", model="microsoft/phi-2", trust_remote_code=True)

print("Testing...")
result = generator("Hello, I am", max_length=30)
print(result[0]['generated_text'])
print("\nSuccess! Phi-2 is working.")