#!/usr/bin/env python3

"""Unit tests for paper_processor CLI."""

import os
import tempfile
from io import StringIO
from unittest.mock import Mock, patch

import pytest

from paper_scanner.cli.paper_processor_old import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    PaperProcessor,
    ProcessorConfig,
    create_parser,
    generate_yaml_definition,
    load_yaml_config,
    merge_configs,
)


class TestProcessorConfig:
    """Tests for ProcessorConfig dataclass."""

    def test_processor_config_defaults(self):
        """Test that ProcessorConfig has correct defaults."""
        config = ProcessorConfig()

        assert config.model == DEFAULT_MODEL
        assert config.max_tokens == DEFAULT_MAX_TOKENS
        assert config.text_source == "pdf"
        assert config.output_key == "processed"
        assert config.mode == "add"
        assert config.add_metadata is False
        assert config.workers == 1
        assert config.skip_existing is False
        assert config.verbose is False
        assert config.quiet is False

    def test_processor_config_custom_values(self):
        """Test ProcessorConfig with custom values."""
        config = ProcessorConfig(
            model="phi",
            max_tokens=4096,
            text_source="content",
            output_key="llm_result",
            mode="replace",
            add_metadata=True,
            verbose=True,
        )

        assert config.model == "phi"
        assert config.max_tokens == 4096
        assert config.text_source == "content"
        assert config.output_key == "llm_result"
        assert config.mode == "replace"
        assert config.add_metadata is True
        assert config.verbose is True

    def test_processor_config_with_files(self):
        """Test ProcessorConfig with file paths."""
        config = ProcessorConfig(
            input_file="/path/to/input.jsonl",
            output_file="/path/to/output.jsonl",
            prompt_file="/path/to/prompt.md",
            yaml_config="/path/to/config.yaml",
        )

        assert config.input_file == "/path/to/input.jsonl"
        assert config.output_file == "/path/to/output.jsonl"
        assert config.prompt_file == "/path/to/prompt.md"
        assert config.yaml_config == "/path/to/config.yaml"


class TestMergeConfigs:
    """Tests for configuration merging."""

    def test_merge_configs_yaml_only(self):
        """Test merging with YAML config only."""
        yaml_config = {
            "model": "phi",
            "max_tokens": 2048,
            "output_key": "custom_output",
        }
        cli_args = Mock()
        cli_args.__dict__ = {
            "model": None,
            "max_tokens": None,
            "output_key": None,
            "input_file": None,
            "output_file": None,
        }

        with patch("sys.argv", ["prog"]):
            config = merge_configs(yaml_config, cli_args)

        assert config.model == "phi"
        assert config.max_tokens == 2048
        assert config.output_key == "custom_output"

    def test_merge_configs_cli_overrides_yaml(self):
        """Test that CLI args override YAML config."""
        yaml_config = {
            "model": "phi",
            "max_tokens": 2048,
        }
        cli_args = Mock()
        cli_args.__dict__ = {
            "model": "claude-3-opus-20240229",
            "max_tokens": 4096,
            "output_key": None,
        }

        with patch("sys.argv", ["prog"]):
            config = merge_configs(yaml_config, cli_args)

        assert config.model == "claude-3-opus-20240229"
        assert config.max_tokens == 4096

    def test_merge_configs_defaults_applied(self):
        """Test that defaults are applied for missing values."""
        yaml_config = {}
        cli_args = Mock()
        cli_args.__dict__ = {
            "model": None,
            "max_tokens": None,
            "output_key": None,
        }

        with patch("sys.argv", ["prog"]):
            config = merge_configs(yaml_config, cli_args)

        assert config.model == DEFAULT_MODEL
        assert config.max_tokens == DEFAULT_MAX_TOKENS
        assert config.output_key == "processed"


class TestCreateParser:
    """Tests for argument parser creation."""

    def test_create_parser_returns_parser(self):
        """Test that create_parser returns an ArgumentParser."""
        parser = create_parser()

        assert parser is not None
        assert hasattr(parser, "parse_args")

    def test_create_parser_has_required_arguments(self):
        """Test that parser has all required arguments."""
        parser = create_parser()

        # Parse empty args to get defaults
        args = parser.parse_args([])

        # Check for key arguments
        assert hasattr(args, "input_file")
        assert hasattr(args, "output_file")
        assert hasattr(args, "model")
        assert hasattr(args, "max_tokens")
        assert hasattr(args, "verbose")
        assert hasattr(args, "quiet")
        assert hasattr(args, "list_models")

    def test_create_parser_list_models_flag(self):
        """Test that parser accepts --list-models flag."""
        parser = create_parser()
        args = parser.parse_args(["--list-models"])

        assert args.list_models is True

    def test_create_parser_model_choices(self):
        """Test that parser has model choices."""
        parser = create_parser()

        # Should not raise error when parsing valid model
        args = parser.parse_args(["--model", "phi"])
        assert args.model == "phi"


class TestLoadYamlConfig:
    """Tests for YAML config loading."""

    def test_load_yaml_config_valid_file(self):
        """Test loading valid YAML config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml_content = """
model: phi
max_tokens: 2048
output_key: result
"""
            f.write(yaml_content)
            f.flush()

            try:
                config = load_yaml_config(f.name)

                assert config["model"] == "phi"
                assert config["max_tokens"] == 2048
                assert config["output_key"] == "result"
            finally:
                os.unlink(f.name)

    def test_load_yaml_config_nonexistent_file(self):
        """Test loading nonexistent YAML file returns empty dict."""
        config = load_yaml_config("/nonexistent/path/config.yaml")

        assert config == {}

    def test_load_yaml_config_invalid_yaml(self):
        """Test loading invalid YAML returns empty dict."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content:")
            f.flush()

            try:
                config = load_yaml_config(f.name)
                # Should return dict (even if parsing issues)
                assert isinstance(config, dict)
            finally:
                os.unlink(f.name)


class TestGenerateYamlDefinition:
    """Tests for YAML definition generation."""

    def test_generate_yaml_definition(self):
        """Test generating YAML definition file."""
        config = ProcessorConfig(
            model="phi",
            max_tokens=2048,
            output_key="result",
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            # Capture stderr
            with patch("sys.stderr", new_callable=StringIO):
                generate_yaml_definition(config, temp_path)

            # Check file was created
            assert os.path.exists(temp_path)

            # Check content
            with open(temp_path, "r") as f:
                content = f.read()
                assert "model:" in content
                assert "phi" in content
                assert "max_tokens:" in content
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_generate_yaml_definition_invalid_path(self):
        """Test generating YAML to invalid path."""
        config = ProcessorConfig()

        # Should handle error gracefully and exit
        with patch("sys.stderr", new_callable=StringIO):
            with patch("builtins.open", side_effect=IOError):
                with pytest.raises(SystemExit):
                    generate_yaml_definition(config, "/invalid/path/file.yaml")


class TestPaperProcessor:
    """Tests for PaperProcessor class."""

    @patch("paper_scanner.cli.paper_processor.initialize_handlers")
    @patch("paper_scanner.cli.paper_processor.get_handler")
    def test_processor_initialization(self, mock_get_handler, mock_init):
        """Test PaperProcessor initialization."""
        mock_handler = Mock()
        mock_handler.GROUP = "Claude"
        mock_get_handler.return_value = mock_handler

        config = ProcessorConfig(model="claude-3-opus-20240229")
        processor = PaperProcessor(config)

        assert processor.config == config
        assert processor.handler == mock_handler
        assert processor.stats["processed"] == 0
        assert processor.stats["success"] == 0

    @patch("paper_scanner.cli.paper_processor.initialize_handlers")
    @patch("paper_scanner.cli.paper_processor.get_handler")
    def test_processor_initialization_invalid_model(self, mock_get_handler, mock_init):
        """Test PaperProcessor with invalid model."""
        mock_get_handler.return_value = None

        config = ProcessorConfig(model="nonexistent-model")

        with pytest.raises(ValueError, match="No handler registered"):
            PaperProcessor(config)

    @patch("paper_scanner.cli.paper_processor.initialize_handlers")
    @patch("paper_scanner.cli.paper_processor.get_handler")
    def test_processor_logging(self, mock_get_handler, mock_init):
        """Test processor logging."""
        mock_handler = Mock()
        mock_get_handler.return_value = mock_handler

        config = ProcessorConfig(verbose=True)
        processor = PaperProcessor(config)

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            processor.log("test message")
            output = mock_stderr.getvalue()
            assert "test message" in output

    @patch("paper_scanner.cli.paper_processor.initialize_handlers")
    @patch("paper_scanner.cli.paper_processor.get_handler")
    def test_processor_logging_quiet_mode(self, mock_get_handler, mock_init):
        """Test processor logging in quiet mode."""
        mock_handler = Mock()
        mock_get_handler.return_value = mock_handler

        config = ProcessorConfig(verbose=True, quiet=True)
        processor = PaperProcessor(config)

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            processor.log("test message")
            output = mock_stderr.getvalue()
            assert output == ""

    @patch("paper_scanner.cli.paper_processor.initialize_handlers")
    @patch("paper_scanner.cli.paper_processor.get_handler")
    def test_processor_load_prompt(self, mock_get_handler, mock_init):
        """Test loading prompt file."""
        mock_handler = Mock()
        mock_get_handler.return_value = mock_handler

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Extract metadata from this PDF")
            f.flush()

            try:
                config = ProcessorConfig(prompt_file=f.name)
                processor = PaperProcessor(config)

                assert processor.custom_prompt == "Extract metadata from this PDF"
            finally:
                os.unlink(f.name)

    @patch("paper_scanner.cli.paper_processor.initialize_handlers")
    @patch("paper_scanner.cli.paper_processor.get_handler")
    def test_processor_load_nonexistent_prompt(self, mock_get_handler, mock_init):
        """Test loading nonexistent prompt file."""
        mock_handler = Mock()
        mock_get_handler.return_value = mock_handler

        config = ProcessorConfig(prompt_file="/nonexistent/prompt.md")
        processor = PaperProcessor(config)

        # Should have empty prompt
        assert processor.custom_prompt == ""

    @patch("paper_scanner.cli.paper_processor.initialize_handlers")
    @patch("paper_scanner.cli.paper_processor.get_handler")
    def test_processor_stats_initialization(self, mock_get_handler, mock_init):
        """Test processor statistics initialization."""
        mock_handler = Mock()
        mock_get_handler.return_value = mock_handler

        config = ProcessorConfig()
        processor = PaperProcessor(config)

        stats = processor.stats
        assert stats["processed"] == 0
        assert stats["success"] == 0
        assert stats["error"] == 0
        assert stats["skipped"] == 0
        assert stats["total_tokens"] == 0


class TestProcessorConfigValidation:
    """Tests for processor configuration validation."""

    def test_config_mode_valid_values(self):
        """Test that config accepts valid mode values."""
        config_add = ProcessorConfig(mode="add")
        config_replace = ProcessorConfig(mode="replace")

        assert config_add.mode == "add"
        assert config_replace.mode == "replace"

    def test_config_text_source_valid_values(self):
        """Test that config accepts valid text_source values."""
        config_pdf = ProcessorConfig(text_source="pdf")
        config_content = ProcessorConfig(text_source="content")
        config_custom = ProcessorConfig(text_source="summary")

        assert config_pdf.text_source == "pdf"
        assert config_content.text_source == "content"
        assert config_custom.text_source == "summary"

    def test_config_token_limits(self):
        """Test token limit configurations."""
        config_min = ProcessorConfig(max_tokens=256)
        config_max = ProcessorConfig(max_tokens=16384)

        assert config_min.max_tokens == 256
        assert config_max.max_tokens == 16384

    def test_config_with_all_options(self):
        """Test configuration with all options set."""
        config = ProcessorConfig(
            model="phi",
            max_tokens=4096,
            text_source="content",
            max_chars=10000,
            prompt_file="/path/to/prompt.md",
            output_key="custom",
            mode="replace",
            add_metadata=True,
            workers=4,
            input_file="/input.jsonl",
            output_file="/output.jsonl",
            skip_existing=True,
            verbose=True,
            quiet=False,
            api_key="test_key",
            yaml_config="/config.yaml",
        )

        assert config.model == "phi"
        assert config.max_tokens == 4096
        assert config.text_source == "content"
        assert config.max_chars == 10000
        assert config.prompt_file == "/path/to/prompt.md"
        assert config.output_key == "custom"
        assert config.mode == "replace"
        assert config.add_metadata is True
        assert config.workers == 4
        assert config.input_file == "/input.jsonl"
        assert config.output_file == "/output.jsonl"
        assert config.skip_existing is True
        assert config.verbose is True
        assert config.quiet is False
        assert config.api_key == "test_key"
        assert config.yaml_config == "/config.yaml"


class TestProcessorIntegration:
    """Integration tests for processor."""

    @patch("paper_scanner.cli.paper_processor.initialize_handlers")
    @patch("paper_scanner.cli.paper_processor.get_handler")
    def test_processor_creates_statistics(self, mock_get_handler, mock_init):
        """Test that processor creates statistics correctly."""
        mock_handler = Mock()
        mock_get_handler.return_value = mock_handler

        config = ProcessorConfig()
        processor = PaperProcessor(config)

        required_stats = [
            "processed",
            "success",
            "error",
            "skipped",
            "not_updated",
            "total_input_tokens",
            "total_output_tokens",
            "total_tokens",
        ]

        for stat in required_stats:
            assert stat in processor.stats

    @patch("paper_scanner.cli.paper_processor.initialize_handlers")
    @patch("paper_scanner.cli.paper_processor.get_handler")
    def test_processor_tracks_processed_records(self, mock_get_handler, mock_init):
        """Test that processor can track processed records."""
        mock_handler = Mock()
        mock_get_handler.return_value = mock_handler

        config = ProcessorConfig()
        processor = PaperProcessor(config)

        assert isinstance(processor.processed_records, set)
        assert len(processor.processed_records) == 0
