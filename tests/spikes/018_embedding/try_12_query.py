#!/usr/bin/env python
"""
Interactive Query Tool: "Who Says What?"

Uses Claude API to help interrogate the paper database about research findings,
methodologies, and claims. Combines LLM reasoning with vector similarity search
to find relevant papers and sections.

Usage:
    python try_12_query.py

Examples of questions:
    - "What do papers say about digital transformation?"
    - "Who discusses platform ecosystems?"
    - "What methodologies are used in digital business research?"
    - "Who found that digitalization creates new business models?"
    - "Compare how different papers view digital platforms"
"""

import os
import sys
from dotenv import load_dotenv

import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector
import anthropic

# Load environment
load_dotenv()


def get_db_url():
    """Build database URL from env"""
    db_user = os.getenv("DB_USER", "pdfuser")
    db_password = os.getenv("DB_PASSWORD", "pdfpass")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "paper_scanner")
    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


class PaperQueryEngine:
    """Interactive query engine for "who says what" questions"""

    def __init__(self):
        self.conn = psycopg2.connect(get_db_url())
        register_vector(self.conn)
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-3-5-sonnet-20241022"
        self.load_papers()

    def load_papers(self):
        """Load papers and their info into memory"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT db_id, cite_key, title, year, journal, authors
            FROM papers
            ORDER BY year DESC, cite_key
        """
        )
        self.papers = {}
        for row in cursor.fetchall():
            db_id, cite_key, title, year, journal, authors = row
            self.papers[db_id] = {
                "cite_key": cite_key,
                "title": title,
                "year": year,
                "journal": journal,
                "authors": authors,
            }
        cursor.close()
        print(f"\n✓ Loaded {len(self.papers)} papers from database")

    def search_similar_chunks(self, query_text: str, limit: int = 5) -> list:
        """Find similar chunks using vector search"""
        from sentence_transformers import SentenceTransformer

        # Generate embedding for query
        model = SentenceTransformer("all-mpnet-base-v2")
        query_embedding = model.encode(query_text)

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT 
                ce.id,
                ce.paper_db_id,
                p.cite_key,
                p.title,
                p.year,
                pc.section,
                pc.text,
                ce.embedding <=> %s::vector as distance
            FROM chunk_embeddings ce
            JOIN paper_chunks pc ON ce.chunk_db_id = pc.db_id
            JOIN papers p ON ce.paper_db_id = p.db_id
            ORDER BY ce.embedding <=> %s::vector
            LIMIT %s
        """,
            (query_embedding, query_embedding, limit),
        )

        results = cursor.fetchall()
        cursor.close()

        return [
            {
                "chunk_id": r[0],
                "paper_db_id": r[1],
                "cite_key": r[2],
                "paper_title": r[3],
                "year": r[4],
                "section": r[5],
                "text": r[6][:500] + ("..." if len(r[6]) > 500 else ""),
                "distance": r[7],
            }
            for r in results
        ]

    def format_search_results(self, results: list) -> str:
        """Format search results for display"""
        if not results:
            return "No relevant papers found."

        formatted = "\n📄 RELEVANT PAPERS & SECTIONS:\n"
        formatted += "=" * 80 + "\n"

        for i, result in enumerate(results, 1):
            formatted += f"\n{i}. {result['cite_key']} ({result['year']})\n"
            formatted += f"   Title: {result['paper_title']}\n"
            formatted += f"   Section: {result['section']}\n"
            formatted += f"   Similarity: {(1 - result['distance']) * 100:.1f}%\n"
            formatted += f"   Content: {result['text']}\n"
            formatted += "-" * 80

        return formatted

    def ask_claude_about_results(
        self, user_question: str, search_results: list, search_text: str
    ) -> str:
        """Ask Claude to synthesize findings from search results"""

        # Format papers info for context
        papers_context = "\n\n".join(
            [
                f"- {p['cite_key']} ({p['year']}): {p['title']}"
                for p in self.papers.values()
            ]
        )

        # Format search results for Claude
        results_context = "\n\n".join(
            [
                f"From {r['cite_key']} ({r['year']}):\n"
                f"Section: {r['section']}\n"
                f"Quote: {r['text']}"
                for r in search_results
            ]
        )

        prompt = f"""You are an academic research assistant helping with a literature review.
A user asked: "{user_question}"

We searched the database with: "{search_text}"

Available papers in database:
{papers_context}

Most relevant findings:
{results_context}

Based on these findings, provide a synthesis answer to the user's question about "who says what".
Format your response as:
1. Direct answer to the question (what the papers say)
2. Key findings from each paper (who says what)
3. Any patterns or contradictions you notice
4. Suggested follow-up questions for deeper exploration

Be specific about which papers make which claims."""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        return message.content[0].text

    def interactive_session(self):
        """Run interactive query session"""
        print("\n" + "=" * 80)
        print("📚 PAPER QUERY ENGINE: 'Who Says What?'")
        print("=" * 80)
        print(
            """
Use natural language to ask questions about what papers say.
Examples:
  - "What do papers say about digital transformation?"
  - "Who discusses platform ecosystems?"
  - "What methodologies are used?"
  - "Compare how papers view digitalization"

Commands:
  'exit' or 'quit' - Exit the program
  'papers' - List all loaded papers
  'help' - Show this help message
        """
        )
        print("=" * 80 + "\n")

        while True:
            try:
                try:
                    user_input = input("\n🔍 Your question: ").strip()
                except EOFError:
                    print("\n👋 End of input. Goodbye!")
                    break

                if not user_input:
                    continue

                # Handle commands
                if user_input.lower() in ["exit", "quit"]:
                    print("\n👋 Goodbye!")
                    break

                if user_input.lower() == "papers":
                    print("\n📖 PAPERS IN DATABASE:")
                    for db_id, info in sorted(
                        self.papers.items(), key=lambda x: x[1]["year"], reverse=True
                    ):
                        print(
                            f"  • {info['cite_key']} ({info['year']}): {info['title'][:60]}..."
                        )
                    continue

                if user_input.lower() == "help":
                    print(
                        """
COMMANDS:
  'papers'    - List all loaded papers
  'exit'      - Exit the program
  'help'      - Show this help message

QUESTION TYPES:
  • What do papers say about X? → Finds papers discussing X
  • Who discusses X?            → Finds papers by topic
  • Compare X and Y             → Finds papers on both topics
  • What methodologies...       → Finds methodology sections
                    """
                    )
                    continue

                # Process question
                print("\n⏳ Searching papers and analyzing...")

                # Step 1: Search for relevant chunks
                search_results = self.search_similar_chunks(user_input, limit=5)

                if not search_results:
                    print("❌ No relevant papers found. Try a different question.")
                    continue

                # Display search results
                print(self.format_search_results(search_results))

                # Step 2: Ask Claude to synthesize
                print("\n💭 Claude is synthesizing findings...\n")
                synthesis = self.ask_claude_about_results(
                    user_input, search_results, user_input
                )

                print("\n" + "=" * 80)
                print("📝 SYNTHESIS:")
                print("=" * 80)
                print(synthesis)
                print("=" * 80)

                # Suggested follow-up
                print("\n💡 Tip: You can ask follow-up questions for deeper exploration!")

            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                print("Please try another question.")

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    """Main entry point"""
    print("\n" + "=" * 80)
    print("🚀 INITIALIZING PAPER QUERY ENGINE")
    print("=" * 80)

    try:
        engine = PaperQueryEngine()

        print("\n✅ Engine ready! Starting interactive session...")
        engine.interactive_session()

    except Exception as e:
        print(f"\n❌ Error initializing engine: {e}")
        sys.exit(1)
    finally:
        try:
            engine.close()
        except:
            pass


if __name__ == "__main__":
    main()
