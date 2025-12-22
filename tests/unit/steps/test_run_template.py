"""
Unit tests for RunTemplateStep

Tests cover:
- Configuration validation
- Step execution
- Error handling
"""

from unittest.mock import Mock

import pytest

from paper_scanner.steps.run_template import RunTemplateStep
from paper_scanner.core.database import PapersDatabase


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def general_config():
    """Basic project configuration"""
    return {
        "project_name": "Test Project",
    }


@pytest.fixture
def mock_db():
    """Mock PapersDatabase"""
    return PapersDatabase()


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Temporary cache directory"""
    return tmp_path


@pytest.fixture
def run_template_step(general_config, mock_db, temp_cache_dir):
    """Create a RunTemplateStep instance"""
    return RunTemplateStep(
        general_config=general_config,
        db=mock_db,
        cache_dir=temp_cache_dir,
    )


# ============================================================================
# TestValidation
# ============================================================================

class TestValidation:
    """Tests for RunTemplateStep.validate method"""

    def test_validate_valid_config(self):
        """Test validation of valid config with template name"""
        config = {"template": "screen_basics"}
        
        is_valid, errors = RunTemplateStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_missing_template(self):
        """Test validation fails without template key"""
        config = {}
        
        is_valid, errors = RunTemplateStep.validate(config)
        
        assert is_valid is False
        assert len(errors) > 0
        assert any("template" in err for err in errors)

    def test_validate_missing_template_value(self):
        """Test validation fails when template is None"""
        config = {"template": None}
        
        is_valid, errors = RunTemplateStep.validate(config)
        
        # Should fail because template is None or empty
        assert is_valid is False

    def test_validate_empty_string_template(self):
        """Test validation fails when template is empty string"""
        config = {"template": ""}
        
        is_valid, errors = RunTemplateStep.validate(config)
        
        assert is_valid is False

    def test_validate_extra_parameters(self):
        """Test validation succeeds with extra parameters (ignored in v1)"""
        config = {
            "template": "screen_basics",
            "extra_param": "value"
        }
        
        is_valid, errors = RunTemplateStep.validate(config)
        
        # v1 static templates ignore extra parameters
        assert is_valid is True

    def test_validate_various_template_names(self):
        """Test validation with various valid template names"""
        template_names = [
            "screening",
            "screen_basics",
            "advanced_screening_v1",
            "SCREENING",
            "screening_2024",
        ]
        
        for name in template_names:
            config = {"template": name}
            is_valid, errors = RunTemplateStep.validate(config)
            assert is_valid is True, f"Should validate template name: {name}"


# ============================================================================
# TestExecution
# ============================================================================

class TestExecution:
    """Tests for RunTemplateStep.execute method"""

    def test_execute_valid_config(self, run_template_step):
        """Test successful execution with valid config"""
        config = {"template": "screen_basics"}
        
        result = run_template_step.execute(
            step_config=config,
            verbose=False,
            dry_run=False,
            debug=False,
        )
        
        assert result["status"] == "ok"
        assert "message" in result
        assert result["count"] == 0

    def test_execute_invalid_config(self, run_template_step):
        """Test execution with invalid config"""
        config = {}
        
        result = run_template_step.execute(
            step_config=config,
            verbose=False,
            dry_run=False,
            debug=False,
        )
        
        assert result["status"] == "error"
        assert "Invalid template config" in result["error"]

    def test_execute_dry_run(self, run_template_step):
        """Test execution in dry_run mode"""
        config = {"template": "screen_basics"}
        
        result = run_template_step.execute(
            step_config=config,
            verbose=False,
            dry_run=True,
            debug=False,
        )
        
        assert result["status"] == "ok"
        assert "Would execute" in result["message"]

    def test_execute_verbose(self, run_template_step, capsys):
        """Test execution with verbose flag"""
        config = {"template": "screen_basics"}
        
        result = run_template_step.execute(
            step_config=config,
            verbose=True,
            dry_run=False,
            debug=False,
        )
        
        assert result["status"] == "ok"

    def test_execute_missing_template_key(self, run_template_step):
        """Test execution fails when template key is missing"""
        config = {}
        
        result = run_template_step.execute(
            step_config=config,
            verbose=False,
            dry_run=False,
            debug=False,
        )
        
        assert result["status"] == "error"

    def test_execute_with_extra_params(self, run_template_step):
        """Test execution with extra parameters (v1 ignores them)"""
        config = {
            "template": "screen_basics",
            "threshold": 0.8,
            "method": "fuzzy"
        }
        
        result = run_template_step.execute(
            step_config=config,
            verbose=False,
            dry_run=False,
            debug=False,
        )
        
        # v1 should ignore extra parameters and succeed
        assert result["status"] == "ok"

    def test_execute_result_structure(self, run_template_step):
        """Test that execution returns proper result structure"""
        config = {"template": "screen_basics"}
        
        result = run_template_step.execute(
            step_config=config,
            verbose=False,
            dry_run=False,
            debug=False,
        )
        
        assert "status" in result
        assert "message" in result
        assert "count" in result

    def test_execute_template_expanded_message(self, run_template_step):
        """Test execution message indicates template expansion"""
        config = {"template": "screen_basics"}
        
        result = run_template_step.execute(
            step_config=config,
            verbose=False,
            dry_run=False,
            debug=False,
        )
        
        assert "screen_basics" in result["message"]
        assert "expanded" in result["message"].lower()

    def test_execute_count_zero(self, run_template_step):
        """Test that step returns count=0 (handled by StepExecutor)"""
        config = {"template": "screen_basics"}
        
        result = run_template_step.execute(
            step_config=config,
            verbose=False,
            dry_run=False,
            debug=False,
        )
        
        # RunTemplateStep itself doesn't process papers
        # Actual expansion is handled by StepExecutor
        assert result["count"] == 0


# ============================================================================
# TestIntegration
# ============================================================================

class TestIntegration:
    """Integration tests with StepExecutor"""

    def test_step_validates_before_execution(self):
        """Test that step can be validated before execution"""
        config = {"template": "screen_basics"}
        
        # Validate
        is_valid, errors = RunTemplateStep.validate(config)
        assert is_valid is True
        
        # Execute
        step = RunTemplateStep(
            general_config={"project_name": "Test"},
            db=PapersDatabase(),
            cache_dir=None,
        )
        result = step.execute(config)
        assert result["status"] == "ok"

    def test_step_in_builtin_steps_registry(self):
        """Test that step can be imported from registry"""
        from paper_scanner.cli import STEP_REGISTRY_PATHS
        
        assert "run-template" in STEP_REGISTRY_PATHS
        assert "run_template:RunTemplateStep" in STEP_REGISTRY_PATHS["run-template"]

    def test_validate_called_before_execute(self):
        """Test typical workflow: validate then execute"""
        config = {"template": "screen_basics"}
        
        # This is how it would be used in practice
        is_valid, errors = RunTemplateStep.validate(config)
        if is_valid:
            step = RunTemplateStep(
                general_config={"project_name": "Test"},
                db=PapersDatabase(),
                cache_dir=None,
            )
            result = step.execute(config)
            assert result["status"] == "ok"
        else:
            pytest.fail(f"Validation failed: {errors}")


# ============================================================================
# TestEdgeCases
# ============================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions"""

    def test_execute_unicode_template_name(self, run_template_step):
        """Test with unicode characters in template name"""
        config = {"template": "screening_αβγ"}
        
        result = run_template_step.execute(
            step_config=config,
            verbose=False,
            dry_run=False,
            debug=False,
        )
        
        # Should succeed (template existence checked by StepExecutor)
        assert result["status"] == "ok"

    def test_execute_long_template_name(self, run_template_step):
        """Test with very long template name"""
        long_name = "a" * 500
        config = {"template": long_name}
        
        result = run_template_step.execute(
            step_config=config,
            verbose=False,
            dry_run=False,
            debug=False,
        )
        
        assert result["status"] == "ok"

    def test_execute_special_chars_template_name(self, run_template_step):
        """Test with special characters in template name"""
        config = {"template": "screen-basics_v1.2"}
        
        result = run_template_step.execute(
            step_config=config,
            verbose=False,
            dry_run=False,
            debug=False,
        )
        
        assert result["status"] == "ok"

    def test_validate_config_none(self):
        """Test validate with None config"""
        # This might raise or return False - test defensive programming
        try:
            is_valid, errors = RunTemplateStep.validate(None)
            assert is_valid is False
        except (TypeError, AttributeError):
            # Either behavior is acceptable
            pass

    def test_execute_multiple_times(self, run_template_step):
        """Test executing the same step multiple times"""
        config = {"template": "screen_basics"}
        
        for _ in range(3):
            result = run_template_step.execute(
                step_config=config,
                verbose=False,
                dry_run=False,
                debug=False,
            )
            assert result["status"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
