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
import re

# PDF processing
from pypdf import PdfReader

# Embeddings
from sentence_transformers import SentenceTransformer
import numpy as np

# Tokenization
import tiktoken

from paper_scanner.tools.embedding.sections import detect_sections


class PDFChunker:
    """
    Intelligent PDF chunker with hybrid strategy
    """

    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def extract_text_from_pdf(self, pdf_path: str) -> List[Dict]:
        """Extract text from PDF with page information"""
        try:
            reader = PdfReader(pdf_path)
            pages = []

            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                pages.append({"page_number": page_num, "text": text, "char_count": len(text)})

            return pages
        except Exception as e:
            print(f"Error reading PDF {pdf_path}: {e}", file=sys.stderr)
            return []

    # def detect_sections(self, text: str) -> List[Dict]:
    #     """Detect sections in academic paper"""

    #     section_patterns = [
    #         r"^#+\s+(.+)$",  # Markdown headers
    #         r"^(\d+\.?\s+[A-Z][^.!?]+)$",  # Numbered sections
    #         r"^([A-Z][A-Z\s]{2,}:?)$",  # ALL CAPS headers
    #         r"^(Abstract|Introduction|Methods?|Results?|Discussion|Conclusion|References)",
    #     ]

    #     sections = []
    #     lines = text.split("\n")
    #     current_section = None
    #     current_content = []

    #     for line in lines:
    #         line = line.strip()
    #         if not line:
    #             continue

    #         # Check if this is a section header
    #         is_header = False
    #         for pattern in section_patterns:
    #             if re.match(pattern, line, re.IGNORECASE):
    #                 # Save previous section
    #                 if current_section:
    #                     sections.append({"title": current_section, "content": "\n".join(current_content)})

    #                 current_section = line
    #                 current_content = []
    #                 is_header = True
    #                 break

    #         if not is_header:
    #             current_content.append(line)

    #     # Add final section
    #     if current_section:
    #         sections.append({"title": current_section, "content": "\n".join(current_content)})

    #     return sections

    def chunk_by_sentences(self, text: str) -> List[str]:
        """Chunk text by sentences with overlap"""

        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)

        chunks = []
        current_chunk = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = len(self.tokenizer.encode(sentence))

            # If adding this sentence exceeds limit, start new chunk
            if current_tokens + sentence_tokens > self.chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))

                # Keep overlap
                overlap_sentences = []
                overlap_tokens = 0

                for s in reversed(current_chunk):
                    s_tokens = len(self.tokenizer.encode(s))
                    if overlap_tokens + s_tokens > self.overlap:
                        break
                    overlap_sentences.insert(0, s)
                    overlap_tokens += s_tokens

                current_chunk = overlap_sentences
                current_tokens = overlap_tokens

            current_chunk.append(sentence)
            current_tokens += sentence_tokens

        # Add final chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def chunk_paper(self, pdf_path: str, strategy: str = "hybrid") -> List[Dict]:
        """
        Main chunking function

        Returns list of chunks with metadata
        """

        # Extract pages
        pages = self.extract_text_from_pdf(pdf_path)
        if not pages:
            return []

        full_text = "\n\n".join(p["text"] for p in pages)
        chunks = []

        if strategy == "hybrid":
            # Hybrid: section-aware with size constraints
            sections = detect_sections(full_text)

            if sections:
                # Use sections
                for section in sections:
                    section_tokens = len(self.tokenizer.encode(section["content"]))

                    if section_tokens <= self.chunk_size:
                        # Section fits in one chunk
                        chunks.append(
                            {
                                "content": section["content"],
                                "chunk_type": "section",
                                "section_title": section["title"],
                                "token_count": section_tokens,
                            }
                        )
                    else:
                        # Section too large, split it
                        sub_chunks = self.chunk_by_sentences(section["content"])

                        for i, chunk_text in enumerate(sub_chunks):
                            chunks.append(
                                {
                                    "content": chunk_text,
                                    "chunk_type": "section_part",
                                    "section_title": f"{section['title']} (part {i + 1})",
                                    "token_count": len(self.tokenizer.encode(chunk_text)),
                                }
                            )
            else:
                # No sections detected, use fixed chunking
                text_chunks = self.chunk_by_sentences(full_text)

                for chunk_text in text_chunks:
                    chunks.append(
                        {
                            "content": chunk_text,
                            "chunk_type": "fixed",
                            "token_count": len(self.tokenizer.encode(chunk_text)),
                        }
                    )

        elif strategy == "fixed":
            # Fixed-size chunks
            text_chunks = self.chunk_by_sentences(full_text)

            for chunk_text in text_chunks:
                chunks.append(
                    {
                        "content": chunk_text,
                        "chunk_type": "fixed",
                        "token_count": len(self.tokenizer.encode(chunk_text)),
                    }
                )

        # Add chunk indices and metadata
        for i, chunk in enumerate(chunks):
            chunk["chunk_index"] = i
            chunk["content_length"] = len(chunk["content"])
            chunk["chunking_strategy"] = strategy
            chunk["chunk_size_target"] = self.chunk_size
            chunk["overlap_size"] = self.overlap

        return chunks


class EmbeddingGenerator:
    """
    Generate embeddings using sentence-transformers
    """

    def __init__(self, model_name: str = "all-mpnet-base-v2"):
        """
        Initialize embedding model

        Options:
        - 'all-mpnet-base-v2': 768 dims, best quality
        - 'all-MiniLM-L6-v2': 384 dims, faster
        """
        print(f"Loading embedding model: {model_name}...", file=sys.stderr)
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.dimension = self.model.get_sentence_embedding_dimension()
        print(f"Model loaded. Dimension: {self.dimension}", file=sys.stderr)

    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for single text"""
        return self.model.encode(text, convert_to_numpy=True)

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Generate embeddings for multiple texts efficiently"""
        return self.model.encode(texts, batch_size=batch_size, show_progress_bar=False, convert_to_numpy=True)

    def embed_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """
        Embed all chunks and return with embeddings attached
        """

        # Extract texts
        chunk_texts = [c["content"] for c in chunks]

        # Generate embeddings
        embeddings = self.embed_batch(chunk_texts)

        # Attach embeddings to chunks
        enriched_chunks = []
        for chunk, embedding in zip(chunks, embeddings):
            enriched_chunk = chunk.copy()
            enriched_chunk["embedding"] = {
                "vector": embedding.tolist(),
                "model_name": self.model_name,
                "dimension": self.dimension,
            }
            enriched_chunks.append(enriched_chunk)

        return enriched_chunks

    def embed_paper(self, chunks: List[Dict], method: str = "aggregate_chunks") -> Dict[str]:
        """
        Generate paper-level embedding

        Methods:
        - 'aggregate_chunks': Average all chunk embeddings
        - 'first_chunk': Use first chunk (usually abstract/intro)
        """

        if method == "aggregate_chunks":
            # Average all chunk embeddings
            chunk_vectors = [c["embedding"]["vector"] for c in chunks]
            paper_vector = np.mean(chunk_vectors, axis=0)

        elif method == "first_chunk":
            # Use first chunk
            paper_vector = np.array(chunks[0]["embedding"]["vector"])

        else:
            raise ValueError(f"Unknown method: {method}")

        return {
            "vector": paper_vector.tolist(),
            "model_name": self.model_name,
            "dimension": self.dimension,
            "method": method,
        }


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
