"""
Unit tests for ExportStep

Tests database export functionality to various formats (JSON, JSONL, BibTeX).

Run with:
    pytest tests/unit/steps/test_export.py -v
"""

import json
import tempfile
from pathlib import Path

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import ScreeningDecision, StepStatus
from paper_scanner.core.models import (
    Author,
    Discovery,
    DiscoveryMethod,
    Paper,
    Screening,
)
from paper_scanner.steps.export import VALID_FLAGS, ExportStep


def _make_step(papers=None):
    """Create an ExportStep with a mock database."""
    db = PapersDatabase()
    if papers:
        for p in papers:
            db.add(p)
    step = ExportStep(
        general_config={},
        db=db,
        cache_dir=Path("/tmp"),
    )
    return step


def _make_papers():
    """Create test papers with various attributes."""
    p1 = Paper(
        cite_key="Smith2023",
        title="Paper One",
        year=2023,
        doi="10.1234/test1",
        authors=[Author(family_name="Smith", given_name="J", full_name="J Smith")],
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH),
        screening=Screening(final_decision=ScreeningDecision.INCLUDED),
    )
    p2 = Paper(
        cite_key="Jones2023",
        title="Paper Two",
        year=2023,
        doi="10.1234/test2",
        authors=[Author(family_name="Jones", given_name="A", full_name="A Jones")],
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH),
        duplicate_of=p1,
        screening=Screening(final_decision=ScreeningDecision.EXCLUDED),
    )
    p3 = Paper(
        cite_key="Lee2024",
        title="Paper Three",
        year=2024,
        discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH),
        screening=Screening(final_decision=ScreeningDecision.INCLUDED),
    )
    return [p1, p2, p3]


class TestValidate:
    """Tests for export step configuration validation"""

    def test_validate_empty_config(self):
        """Should reject empty config (missing output)"""
        is_valid, errors = ExportStep.validate({})
        assert is_valid is False
        assert any("output" in e.lower() for e in errors)

    def test_validate_valid_format_jsonl(self):
        """Should accept valid jsonl format"""
        config = {"format": "jsonl", "output": "stdout"}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_valid_format_json(self):
        """Should accept valid json format"""
        config = {"format": "json", "output": "/tmp/export.json"}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_valid_format_bibtex(self):
        """Should accept valid bibtex format"""
        config = {"format": "bibtex", "output": "/tmp/export.bib"}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_invalid_format(self):
        """Should reject invalid format"""
        config = {"format": "xml", "output": "stdout"}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is False
        assert any("format" in e.lower() for e in errors)

    def test_validate_output_stdout(self):
        """Should accept stdout as output"""
        config = {"output": "stdout"}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_output_file_path(self):
        """Should accept file path as output"""
        config = {"output": "/tmp/export.jsonl"}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_legacy_output_path(self):
        """Should accept legacy output_path parameter"""
        config = {"output_path": "/tmp/export.jsonl"}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_output_not_string(self):
        """Should reject non-string output"""
        config = {"output": 123}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is False
        assert any("string" in e.lower() for e in errors)

    def test_validate_output_empty_string(self):
        """Should reject empty string output (except stdout)"""
        config = {"output": ""}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is False
        assert any("output" in e.lower() for e in errors)

    def test_validate_output_path_not_string(self):
        """Should reject non-string output_path"""
        config = {"output_path": 456}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is False
        assert any("string" in e.lower() for e in errors)

    def test_validate_exclude_none_boolean(self):
        """Should accept boolean exclude_none"""
        config = {"output": "stdout", "exclude_none": True}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_exclude_none_not_boolean(self):
        """Should reject non-boolean exclude_none"""
        config = {"output": "stdout", "exclude_none": "true"}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is False
        assert any("exclude_none" in e.lower() for e in errors)

    def test_validate_overwrite_boolean(self):
        """Should accept boolean overwrite"""
        config = {"output": "stdout", "overwrite": False}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_overwrite_not_boolean(self):
        """Should reject non-boolean overwrite"""
        config = {"output": "stdout", "overwrite": "false"}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is False
        assert any("overwrite" in e.lower() for e in errors)

    def test_validate_doi_flag_valid(self):
        """Should accept valid doi flag"""
        for flag in VALID_FLAGS:
            config = {"output": "stdout", "doi": flag}
            is_valid, errors = ExportStep.validate(config)
            assert is_valid is True, f"Failed for flag: {flag}"
            assert errors == []

    def test_validate_doi_flag_invalid(self):
        """Should reject invalid doi flag"""
        config = {"output": "stdout", "doi": "invalid"}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is False
        assert any("doi" in e.lower() for e in errors)

    def test_validate_duplicates_flag_valid(self):
        """Should accept valid duplicates flag"""
        for flag in VALID_FLAGS:
            config = {"output": "stdout", "duplicates": flag}
            is_valid, errors = ExportStep.validate(config)
            assert is_valid is True, f"Failed for flag: {flag}"
            assert errors == []

    def test_validate_duplicates_flag_invalid(self):
        """Should reject invalid duplicates flag"""
        config = {"output": "stdout", "duplicates": "maybe"}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is False
        assert any("duplicates" in e.lower() for e in errors)

    def test_validate_includes_flag_valid(self):
        """Should accept valid includes flag"""
        for flag in VALID_FLAGS:
            config = {"output": "stdout", "includes": flag}
            is_valid, errors = ExportStep.validate(config)
            assert is_valid is True, f"Failed for flag: {flag}"
            assert errors == []

    def test_validate_includes_flag_invalid(self):
        """Should reject invalid includes flag"""
        config = {"output": "stdout", "includes": "unknown"}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is False
        assert any("includes" in e.lower() for e in errors)

    def test_validate_multiple_errors(self):
        """Should collect multiple validation errors"""
        config = {
            "format": "xml",
            "doi": "bad_flag",
            "exclude_none": "not_bool"
        }
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is False
        assert len(errors) >= 2

    def test_validate_both_output_and_output_path(self):
        """Should accept both output and output_path (output takes precedence)"""
        config = {"output": "stdout", "output_path": "/tmp/export.jsonl"}
        is_valid, errors = ExportStep.validate(config)
        assert is_valid is True
        assert errors == []


class TestExecute:
    """Tests for export step execution (covers bug fixes #65)."""

    def test_export_jsonl_to_file(self):
        """JSONL export to file should work (verifies method name fix)."""
        papers = _make_papers()
        step = _make_step(papers)

        with tempfile.TemporaryDirectory() as tmpdir:
            outfile = str(Path(tmpdir) / "out.jsonl")
            result = step.execute(
                config={
                    "format": "jsonl",
                    "output": outfile,
                    "overwrite": True,
                    "doi": "all",
                    "includes": "all",
                    "duplicates": "all",
                },
            )
            assert result.status == StepStatus.SUCCESS

            with open(outfile) as f:
                lines = [line for line in f.readlines() if line.strip()]
            assert len(lines) == 3

            for line in lines:
                data = json.loads(line)
                assert "cite_key" in data

    def test_export_jsonl_to_stdout(self, capsys):
        """JSONL export to stdout should not crash (verifies else clause fix)."""
        papers = _make_papers()
        step = _make_step(papers)

        result = step.execute(
            config={"format": "jsonl", "output": "stdout"},
        )
        assert result.status == StepStatus.SUCCESS

        captured = capsys.readouterr()
        assert "Smith2023" in captured.out

    def test_export_json_to_file(self):
        """JSON export to file should work."""
        papers = _make_papers()
        step = _make_step(papers)

        with tempfile.TemporaryDirectory() as tmpdir:
            outfile = str(Path(tmpdir) / "out.json")
            result = step.execute(
                config={
                    "format": "json",
                    "output": outfile,
                    "overwrite": True,
                    "doi": "all",
                    "includes": "all",
                    "duplicates": "all",
                },
            )
            assert result.status == StepStatus.SUCCESS

            with open(outfile) as f:
                data = json.load(f)
            assert len(data) == 3

    def test_export_json_to_stdout(self, capsys):
        """JSON export to stdout should not crash."""
        papers = _make_papers()
        step = _make_step(papers)

        result = step.execute(
            config={"format": "json", "output": "stdout"},
        )
        assert result.status == StepStatus.SUCCESS

    def test_filter_duplicates_no(self):
        """duplicates='no' should exclude duplicates (verifies == vs in fix)."""
        papers = _make_papers()
        step = _make_step(papers)

        with tempfile.TemporaryDirectory() as tmpdir:
            outfile = str(Path(tmpdir) / "out.jsonl")
            result = step.execute(
                config={
                    "format": "jsonl",
                    "output": outfile,
                    "duplicates": "no",
                    "includes": "all",
                    "doi": "all",
                    "overwrite": True,
                },
            )
            with open(outfile) as f:
                lines = [line for line in f.readlines() if line.strip()]

            cite_keys = [json.loads(line)["cite_key"] for line in lines]
            # Jones2023 is a duplicate, should be excluded
            assert "Jones2023" not in cite_keys
            assert "Smith2023" in cite_keys
            assert "Lee2024" in cite_keys

    def test_filter_includes_no(self):
        """includes='no' should export only excluded papers (verifies == vs in fix)."""
        papers = _make_papers()
        step = _make_step(papers)

        with tempfile.TemporaryDirectory() as tmpdir:
            outfile = str(Path(tmpdir) / "out.jsonl")
            result = step.execute(
                config={
                    "format": "jsonl",
                    "output": outfile,
                    "includes": "no",
                    "duplicates": "all",
                    "doi": "all",
                    "overwrite": True,
                },
            )
            with open(outfile) as f:
                lines = [line for line in f.readlines() if line.strip()]

            cite_keys = [json.loads(line)["cite_key"] for line in lines]
            # Only Jones2023 is excluded (not included)
            assert "Jones2023" in cite_keys
            assert "Smith2023" not in cite_keys
            assert "Lee2024" not in cite_keys
