"""
Unit tests for ExportStep

Tests database export functionality to various formats (JSON, JSONL, BibTeX).

Run with:
    pytest tests/unit/steps/test_export.py -v
"""


from paper_scanner.steps.export import VALID_FLAGS, ExportStep


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
