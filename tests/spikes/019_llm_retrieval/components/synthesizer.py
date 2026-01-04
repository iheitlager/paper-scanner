"""Synthesizer: LLM-based answer generation from retrieved context."""
import time
from typing import Any, Dict, List
from anthropic import Anthropic

from .common import SynthesisResult, RetrievalResult


class Synthesizer:
    """Generates final answer from retrieved context."""

    def __init__(self, llm_client: Anthropic):
        """
        Initialize Synthesizer with LLM client.
        
        Args:
            llm_client: Anthropic client for API calls
        """
        self.llm_client = llm_client

    def synthesize(self,
                   question: str,
                   retrieval_result: RetrievalResult,
                   verbose: bool = False) -> SynthesisResult:
        """
        Generate final answer from question and retrieved chunks.
        
        Args:
            question: Original user question
            retrieval_result: Retrieved chunks from Tool
            verbose: Print verbose output
            
        Returns:
            SynthesisResult with answer and metadata
        """
        start_time = time.time()
        
        # Format chunks into context
        context = self._format_context(retrieval_result)
        
        # Create synthesis prompt
        messages = [{
            "role": "user",
            "content": f"""You are a research analyst synthesizing findings from academic papers.

QUESTION: {question}

RETRIEVED CONTEXT:
{context}

Based on the retrieved excerpts above, provide a comprehensive answer to the question. 
Include specific findings, methodologies, and insights from the papers.
Cite which papers you're drawing from.

ANSWER:"""
        }]
        
        # Call LLM
        message = self.llm_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=messages
        )
        
        answer_text = message.content[0].text.strip()
        tokens_used = message.usage.input_tokens + message.usage.output_tokens
        latency_ms = (time.time() - start_time) * 1000
        
        # Extract citations from answer
        citations = self._extract_citations(answer_text, retrieval_result)
        
        if verbose:
            print(f"\n[Synthesizer] Generated answer with {tokens_used} tokens in {latency_ms:.0f}ms")
        
        return SynthesisResult(
            answer_text=answer_text,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            citations=citations
        )

    def _format_context(self, retrieval_result: RetrievalResult) -> str:
        """Format retrieved chunks into readable context."""
        if not retrieval_result.chunks:
            return "[No chunks retrieved]"
        
        lines = []
        for i, chunk in enumerate(retrieval_result.chunks, 1):
            title = chunk.get('title', 'Unknown')
            cite_key = chunk.get('cite_key', 'N/A')
            year = chunk.get('year', 'N/A')
            section = chunk.get('section', 'N/A')
            similarity = chunk.get('similarity', 0)
            content = chunk.get('content', '')
            
            lines.append(f"""
[{i}] {title} ({cite_key}, {year})
    Section: {section}
    Relevance: {similarity:.2f}
    Content: {content[:200]}...""")
        
        return '\n'.join(lines)

    def _extract_citations(self, answer_text: str, retrieval_result: RetrievalResult) -> List[str]:
        """Extract paper citations from answer."""
        citations = []
        
        # Look for cite_key references in answer
        for chunk in retrieval_result.chunks:
            cite_key = chunk.get('cite_key', '')
            if cite_key and cite_key in answer_text:
                title = chunk.get('title', '')
                year = chunk.get('year', '')
                citations.append(f"{cite_key} - {title} ({year})")
        
        return list(set(citations))  # Deduplicate
