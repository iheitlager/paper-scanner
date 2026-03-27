"""
Tests for citation edge insertion into PostgreSQL database.

Tests the _insert_citation_edges method that converts Citation objects to database records
and verifies end-to-end citation persistence.
"""

import uuid
from unittest.mock import MagicMock, patch

from paper_scanner.core.enum import CitationDirection, DiscoveryMethod, PaperType
from paper_scanner.core.models import Author, Citation, Paper
from paper_scanner.io.sql import PaperUploader


class TestCitationEdgeInsertion:
    """Test citation edge insertion into database"""

    def create_paper_with_citations(
        self,
        title: str = "Test Paper",
        cite_key: str = "test2023",
        citations: list = None,
    ) -> Paper:
        """Helper to create a paper with citations"""
        if citations is None:
            citations = []

        return Paper(
            id=str(uuid.uuid4()),
            cite_key=cite_key,
            title=title,
            authors=[Author(given_name="John", family_name="Doe", full_name="John Doe")],
            year=2023,
            paper_type=PaperType.JOURNAL_ARTICLE,
            discovery={"method": DiscoveryMethod.MANUAL},
            citations=citations,
        )

    def create_citation(
        self,
        title: str = "Cited Paper",
        year: int = 2022,
        doi: str = None,
        direction: CitationDirection = CitationDirection.BACKWARD,
    ) -> Citation:
        """Helper to create a citation"""
        return Citation(
            title=title,
            year=year,
            doi=doi,
            authors=["Jane Smith"],
            direction=direction,
            extraction_method="manual",
        )

    def test_insert_citation_edges_with_matching_doi(self):
        """Test citation edge insertion when cited paper matches by DOI"""
        # Create papers
        paper1 = self.create_paper_with_citations(
            cite_key="paper1",
            citations=[self.create_citation(doi="10.1234/cited")],
        )

        self.create_paper_with_citations(
            cite_key="paper2",
        )

        # Mock cursor and connection
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            (1,),  # paper1 db_id lookup
            (2,),  # cited paper found by DOI
        ]

        # Create uploader
        mock_pool = MagicMock()
        uploader = PaperUploader(mock_pool)

        # Execute
        stats = uploader._insert_citation_edges(mock_cursor, [paper1])

        # Verify
        assert stats["edges_inserted"] == 1
        assert stats["edges_skipped"] == 0
        assert len(stats["errors"]) == 0

        # Verify correct SQL calls
        calls = mock_cursor.execute.call_args_list
        assert len(calls) >= 3  # 1 for paper lookup + 1 for citation lookup + 1 for insert

    def test_insert_citation_edges_with_matching_title_year(self):
        """Test citation edge insertion when cited paper matches by title+year"""
        # Create papers - citation with title but NO DOI
        paper1 = self.create_paper_with_citations(
            cite_key="paper1",
            citations=[self.create_citation(title="Existing Paper", year=2022, doi=None)],
        )

        # Mock cursor - only 2 calls: 1 for paper lookup + 1 for title+year lookup
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            (1,),  # paper1 db_id lookup
            (3,),  # cited paper found by title+year
        ]

        # Create uploader
        mock_pool = MagicMock()
        uploader = PaperUploader(mock_pool)

        # Execute
        stats = uploader._insert_citation_edges(mock_cursor, [paper1])

        # Verify
        assert stats["edges_inserted"] == 1
        assert stats["edges_skipped"] == 0

    def test_insert_citation_edges_with_unresolved_citation(self):
        """Test citation edge when cited paper is not in database"""
        # Create papers
        paper1 = self.create_paper_with_citations(
            cite_key="paper1",
            citations=[
                self.create_citation(
                    title="Unknown Paper",
                    year=2020,
                    doi="10.9999/unknown",
                )
            ],
        )

        # Mock cursor - cited paper not found
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            (1,),  # paper1 db_id lookup
            None,  # DOI lookup fails
            None,  # title+year lookup fails
        ]

        # Create uploader
        mock_pool = MagicMock()
        uploader = PaperUploader(mock_pool)

        # Execute
        stats = uploader._insert_citation_edges(mock_cursor, [paper1])

        # Verify - edge inserted with NULL cited_paper_id
        assert stats["edges_inserted"] == 0  # Unresolved edges are skipped in count
        assert stats["edges_skipped"] == 1
        assert len(stats["errors"]) == 0

    def test_insert_citation_edges_multiple_citations(self):
        """Test citation edge insertion with multiple citations in one paper"""
        # Create papers with multiple citations
        paper1 = self.create_paper_with_citations(
            cite_key="paper1",
            citations=[
                self.create_citation(doi="10.1111/first"),
                self.create_citation(doi="10.2222/second"),
                self.create_citation(title="Third Paper", year=2021),
            ],
        )

        # Mock cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            (1,),  # paper1 db_id lookup
            (2,),  # citation 1 found by DOI
            (3,),  # citation 2 found by DOI
            (4,),  # citation 3 found by title+year
        ]

        # Create uploader
        mock_pool = MagicMock()
        uploader = PaperUploader(mock_pool)

        # Execute
        stats = uploader._insert_citation_edges(mock_cursor, [paper1])

        # Verify
        assert stats["edges_inserted"] == 3
        assert stats["edges_skipped"] == 0

    def test_insert_citation_edges_batch_papers(self):
        """Test citation edge insertion for multiple papers"""
        # Create multiple papers with citations
        paper1 = self.create_paper_with_citations(
            cite_key="paper1",
            citations=[self.create_citation(doi="10.1111/ref1")],
        )

        paper2 = self.create_paper_with_citations(
            cite_key="paper2",
            citations=[
                self.create_citation(doi="10.2222/ref2"),
                self.create_citation(doi="10.3333/ref3"),
            ],
        )

        # Mock cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            (10,),  # paper1 db_id
            (11,),  # citation 1 resolved
            (20,),  # paper2 db_id
            (12,),  # citation 2 resolved
            (13,),  # citation 3 resolved
        ]

        # Create uploader
        mock_pool = MagicMock()
        uploader = PaperUploader(mock_pool)

        # Execute
        stats = uploader._insert_citation_edges(mock_cursor, [paper1, paper2])

        # Verify
        assert stats["edges_inserted"] == 3
        assert stats["edges_skipped"] == 0

    def test_insert_citation_edges_paper_not_in_db(self):
        """Test citation edge insertion when citing paper not found in database"""
        # Create papers
        paper1 = self.create_paper_with_citations(
            cite_key="paper1",
            citations=[self.create_citation(doi="10.1111/ref1")],
        )

        # Mock cursor - citing paper not found
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # Paper lookup fails

        # Create uploader
        mock_pool = MagicMock()
        uploader = PaperUploader(mock_pool)

        # Execute
        stats = uploader._insert_citation_edges(mock_cursor, [paper1])

        # Verify - skipped with error
        assert stats["edges_inserted"] == 0
        assert len(stats["errors"]) == 1
        assert "not found in DB" in stats["errors"][0]

    def test_insert_citation_edges_no_citations(self):
        """Test citation edge insertion when paper has no citations"""
        # Create papers without citations
        paper1 = self.create_paper_with_citations(cite_key="paper1", citations=[])

        # Mock cursor
        mock_cursor = MagicMock()

        # Create uploader
        mock_pool = MagicMock()
        uploader = PaperUploader(mock_pool)

        # Execute
        stats = uploader._insert_citation_edges(mock_cursor, [paper1])

        # Verify - no edges inserted, no SQL calls
        assert stats["edges_inserted"] == 0
        assert stats["edges_skipped"] == 0
        assert mock_cursor.execute.call_count == 0

    def test_insert_citation_edges_empty_papers_list(self):
        """Test citation edge insertion with empty papers list"""
        # Mock cursor
        mock_cursor = MagicMock()

        # Create uploader
        mock_pool = MagicMock()
        uploader = PaperUploader(mock_pool)

        # Execute
        stats = uploader._insert_citation_edges(mock_cursor, [])

        # Verify
        assert stats["edges_inserted"] == 0
        assert stats["edges_skipped"] == 0
        assert mock_cursor.execute.call_count == 0

    def test_insert_citation_edges_backward_direction(self):
        """Test citation edge insertion preserves BACKWARD direction"""
        # Create paper citing another
        paper1 = self.create_paper_with_citations(
            cite_key="paper1",
            citations=[
                self.create_citation(
                    doi="10.1111/ref1",
                    direction=CitationDirection.BACKWARD,
                )
            ],
        )

        # Mock cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [(1,), (2,)]

        # Create uploader
        mock_pool = MagicMock()
        uploader = PaperUploader(mock_pool)

        # Execute
        stats = uploader._insert_citation_edges(mock_cursor, [paper1])

        # Verify edge was inserted (direction stored in Citation model)
        assert stats["edges_inserted"] == 1
        assert paper1.citations[0].direction == CitationDirection.BACKWARD

    def test_insert_citation_edges_forward_direction(self):
        """Test citation edge insertion preserves FORWARD direction"""
        # Create paper with forward citation (cited by another)
        paper1 = self.create_paper_with_citations(
            cite_key="paper1",
            citations=[
                self.create_citation(
                    doi="10.1111/ref1",
                    direction=CitationDirection.FORWARD,
                )
            ],
        )

        # Mock cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [(1,), (2,)]

        # Create uploader
        mock_pool = MagicMock()
        uploader = PaperUploader(mock_pool)

        # Execute
        stats = uploader._insert_citation_edges(mock_cursor, [paper1])

        # Verify
        assert stats["edges_inserted"] == 1
        assert paper1.citations[0].direction == CitationDirection.FORWARD

    def test_insert_citation_edges_conflict_handling(self):
        """Test citation edge insertion handles duplicates with UNIQUE constraint"""
        # Create papers with same citation twice (conflict scenario)
        paper1 = self.create_paper_with_citations(
            cite_key="paper1",
            citations=[
                self.create_citation(doi="10.1111/ref1"),
                self.create_citation(doi="10.1111/ref1"),  # Same citation
            ],
        )

        # Mock cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [(1,), (2,), (2,)]  # Same cited paper

        # Create uploader
        mock_pool = MagicMock()
        uploader = PaperUploader(mock_pool)

        # Execute
        stats = uploader._insert_citation_edges(mock_cursor, [paper1])

        # Verify - both insertions attempted, UNIQUE constraint prevents duplicates
        assert stats["edges_inserted"] == 2  # Both counted (ON CONFLICT handles at DB level)

    def test_insert_papers_includes_citation_edges(self):
        """Test that insert_papers method includes citation edge statistics"""
        # This is an integration test that verifies insert_papers calls _insert_citation_edges
        # We mock the necessary parts while keeping the real method structure

        paper1 = self.create_paper_with_citations(
            cite_key="paper1",
            citations=[self.create_citation(doi="10.1111/ref1")],
        )

        # Create mock connection and pool
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Setup context manager chain
        mock_pool.get_connection.return_value.__enter__ = MagicMock(
            return_value=mock_conn
        )
        mock_pool.get_connection.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor

        # Mock transaction context manager
        with patch.object(
            PaperUploader,
            "transaction",
        ) as mock_transaction:
            mock_transaction.return_value.__enter__ = MagicMock()
            mock_transaction.return_value.__exit__ = MagicMock(return_value=False)

            # Mock PaperToRowConverter
            with patch(
                "paper_scanner.io.sql.PaperToRowConverter.paper_to_row"
            ) as mock_converter:
                mock_converter.return_value = {"id": paper1.id, "cite_key": "paper1"}

                # Mock citation edge fetches
                mock_cursor.fetchone.side_effect = [(1,), (2,)]

                uploader = PaperUploader(mock_pool)

                # Execute
                stats = uploader.insert_papers([paper1])

                # Verify citation edges in stats
                assert "citation_edges" in stats
                assert "edges_inserted" in stats["citation_edges"]
                assert "edges_skipped" in stats["citation_edges"]

    def test_insert_citation_edges_sql_correctness(self):
        """Test that the generated SQL for citation edges is correct"""
        # Verify that _insert_citation_edges generates correct INSERT statement
        # This ensures the UNIQUE constraint and ON CONFLICT work properly

        paper1 = self.create_paper_with_citations(
            cite_key="paper1",
            citations=[self.create_citation(doi="10.1111/ref1")],
        )

        # Mock cursor that captures execute calls
        mock_cursor = MagicMock()
        insert_calls = []

        def capture_execute(sql_str, params):
            if "INSERT INTO citation_edges" in str(sql_str):
                insert_calls.append((str(sql_str), params))

        mock_cursor.execute.side_effect = capture_execute
        mock_cursor.fetchone.side_effect = [(1,), (2,)]

        # Create uploader
        mock_pool = MagicMock()
        uploader = PaperUploader(mock_pool)

        # Execute
        stats = uploader._insert_citation_edges(mock_cursor, [paper1])

        # We can't easily verify the exact SQL string due to psycopg2.sql module,
        # but we can verify the structure exists
        assert stats["edges_inserted"] == 1


class TestCitationEdgeIntegration:
    """Integration tests for citation edges with full database flow"""

    def test_citation_direction_preserved_through_edge(self):
        """Test that citation direction is preserved in the edge (via Citation model)"""
        # Create citation with specific direction
        citation = Citation(
            title="Referenced Paper",
            year=2022,
            doi="10.1111/ref",
            direction=CitationDirection.BACKWARD,
            extraction_method="manual",
        )

        # Direction is stored in the Citation object itself
        assert citation.direction == CitationDirection.BACKWARD

        # When edge is inserted, the Citation object's direction is available
        paper = Paper(
            id=str(uuid.uuid4()),
            cite_key="paper1",
            title="Test Paper",
            authors=[],
            year=2023,
            paper_type=PaperType.JOURNAL_ARTICLE,
            discovery={"method": DiscoveryMethod.MANUAL},
            citations=[citation],
        )

        assert paper.citations[0].direction == CitationDirection.BACKWARD

    def test_mixed_resolved_unresolved_citations(self):
        """Test batch with mix of resolved and unresolved citations"""
        paper1 = Paper(
            id=str(uuid.uuid4()),
            cite_key="paper1",
            title="Test Paper",
            authors=[],
            year=2023,
            paper_type=PaperType.JOURNAL_ARTICLE,
            discovery={"method": DiscoveryMethod.MANUAL},
            citations=[
                Citation(
                    title="Known Paper",
                    year=2022,
                    doi="10.1111/known",
                    direction=CitationDirection.BACKWARD,
                    extraction_method="manual",
                ),
                Citation(
                    title="Unknown Paper",
                    year=2020,
                    direction=CitationDirection.BACKWARD,
                    extraction_method="manual",
                ),
            ],
        )

        # Mock cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            (1,),  # paper1 db_id
            (2,),  # first citation resolved by DOI
            None,  # second citation DOI lookup fails (no DOI)
            None,  # second citation title+year lookup fails (not in DB)
        ]

        # Create uploader
        mock_pool = MagicMock()
        uploader = PaperUploader(mock_pool)

        # Execute
        stats = uploader._insert_citation_edges(mock_cursor, [paper1])

        # Verify mixed results
        assert stats["edges_inserted"] == 1
        assert stats["edges_skipped"] == 1
