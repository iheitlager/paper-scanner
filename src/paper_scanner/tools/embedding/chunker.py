import re
import sys
from typing import List, Dict
from pypdf import PdfReader
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
