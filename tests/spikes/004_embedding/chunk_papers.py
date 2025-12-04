#!/usr/bin/env python3
"""
Paper Chunking & Embedding Pipeline

Reads JSONL file with paper metadata
For each record:
1. Reads PDF from file_path
2. Generates chunks using hybrid strategy
3. Generates embeddings for chunks and paper
4. Outputs enhanced JSONL with chunks and embeddings

Usage:
    python chunk_embed_pipeline.py input.jsonl output.jsonl
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import time
from datetime import datetime, UTC


from paper_scanner.tools.embedding.chunker import PDFChunker
from paper_scanner.tools.embedding.embedder import EmbeddingGenerator

class ChunkEmbedPipeline:
    """
    Main pipeline: JSONL → Chunk → Embed → Enhanced JSONL
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50, embedding_model: str = "all-mpnet-base-v2"):
        self.chunker = PDFChunker(chunk_size, chunk_overlap)
        self.embedder = EmbeddingGenerator(embedding_model)

    def process_record(self, record: Dict) -> Dict:
        """
        Process a single JSONL record

        Returns enhanced record with chunks and embeddings
        """

        file_path = record["file_path"]

        print(f"Processing: {Path(file_path).name}", file=sys.stderr)

        start_time = time.time()

        try:
            # Step 1: Chunk the PDF
            chunks = self.chunker.chunk_paper(file_path, strategy="hybrid")

            if not chunks:
                print(f"  Warning: No chunks generated", file=sys.stderr)
                return {
                    **record,
                    "chunks": [],
                    "paper_embedding": None,
                    "_chunk_embed_metadata": {
                        "status": "failed",
                        "error": "No chunks generated",
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                }

            print(f"  → Generated {len(chunks)} chunks", file=sys.stderr)

            # Step 2: Embed chunks
            enriched_chunks = self.embedder.embed_chunks(chunks)
            print(f"  → Generated {len(enriched_chunks)} chunk embeddings", file=sys.stderr)

            # Step 3: Generate paper-level embedding
            paper_embedding = self.embedder.embed_paper(enriched_chunks, method="aggregate_chunks")
            print(f"  → Generated paper embedding", file=sys.stderr)

            # Step 4: Create enhanced record
            elapsed = time.time() - start_time

            enhanced_record = {
                **record,
                "chunks": enriched_chunks,
                "paper_embedding": paper_embedding,
                "_chunk_embed_metadata": {
                    "status": "success",
                    "chunk_count": len(enriched_chunks),
                    "total_tokens": sum(c["token_count"] for c in enriched_chunks),
                    "chunking_strategy": "hybrid",
                    "chunk_size_target": self.chunker.chunk_size,
                    "overlap_size": self.chunker.overlap,
                    "embedding_model": self.embedder.model_name,
                    "embedding_dimension": self.embedder.dimension,
                    "elapsed_seconds": round(elapsed, 2),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            }

            print(f"  ✓ Complete ({elapsed:.1f}s)", file=sys.stderr)

            return enhanced_record

        except Exception as e:
            print(f"  ✗ Error: {e}", file=sys.stderr)

            return {
                **record,
                "chunks": [],
                "paper_embedding": None,
                "_chunk_embed_metadata": {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            }

    def process_jsonl(self, input_path: str, output_path: str):
        """
        Process entire JSONL file
        """

        print(f"Reading from: {input_path}", file=sys.stderr)
        print(f"Writing to: {output_path}", file=sys.stderr)
        print(f"Embedding model: {self.embedder.model_name}", file=sys.stderr)
        print(f"Chunk size: {self.chunker.chunk_size} tokens", file=sys.stderr)
        print(f"Overlap: {self.chunker.overlap} tokens", file=sys.stderr)
        print("", file=sys.stderr)

        records_processed = 0
        records_succeeded = 0
        records_failed = 0

        with open(input_path, "r") as infile, open(output_path, "w") as outfile:
            for line_num, line in enumerate(infile, 1):
                try:
                    record = json.loads(line)

                    # Process record
                    enhanced_record = self.process_record(record)

                    # Write to output
                    outfile.write(json.dumps(enhanced_record) + "\n")
                    outfile.flush()  # Flush after each record

                    records_processed += 1

                    if enhanced_record["_chunk_embed_metadata"]["status"] == "success":
                        records_succeeded += 1
                    else:
                        records_failed += 1

                except json.JSONDecodeError as e:
                    print(f"Error parsing line {line_num}: {e}", file=sys.stderr)
                    records_failed += 1
                except Exception as e:
                    print(f"Error processing line {line_num}: {e}", file=sys.stderr)
                    records_failed += 1

        # Summary
        print("", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("PROCESSING COMPLETE", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(f"Total records: {records_processed}", file=sys.stderr)
        print(f"Succeeded: {records_succeeded}", file=sys.stderr)
        print(f"Failed: {records_failed}", file=sys.stderr)
        print(f"Output: {output_path}", file=sys.stderr)


def main():
    """Main entry point"""

    if len(sys.argv) != 3:
        print("Usage: python chunk_embed_pipeline.py input.jsonl output.jsonl", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    # Validate input
    if not Path(input_path).exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Create pipeline
    pipeline = ChunkEmbedPipeline(
        chunk_size=512,
        chunk_overlap=50,
        embedding_model="all-mpnet-base-v2",  # 768 dimensions
    )

    # Process
    pipeline.process_jsonl(input_path, output_path)


if __name__ == "__main__":
    main()
