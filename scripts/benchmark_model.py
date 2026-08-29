#!/usr/bin/env python3
"""Benchmark local LLM latency and availability via Ollama."""

import sys
import time
from pydantic import BaseModel
from app.llm.client import LLMClient

class SimpleResponse(BaseModel):
    status: str
    message: str

def benchmark(model_name: str = "qwen3:4b"):
    print(f"Benchmarking model: {model_name}...")
    client = LLMClient(model=model_name)
    
    if not client.is_available():
        print(f"Error: Model '{model_name}' is not available on Ollama server.")
        print("Please ensure Ollama is running (`ollama serve`) and the model is pulled (`ollama pull qwen3:4b`).")
        sys.exit(1)

    print("Sending test structured JSON prompt...")
    start = time.time()
    try:
        result = client.generate_json(
            messages=[{"role": "user", "content": "Respond with status ok and message hello."}],
            schema_model=SimpleResponse,
        )
        elapsed = time.time() - start
        print(f"Success! Time elapsed: {elapsed:.2f}s")
        print(f"Result: {result.model_dump_json(indent=2)}")
    except Exception as e:
        print(f"Benchmark failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3:4b"
    benchmark(model)
