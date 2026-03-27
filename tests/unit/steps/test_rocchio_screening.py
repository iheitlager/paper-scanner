"""
Unit tests for rocchio_screening step

Tests for Rocchio-based semantic classification functionality.

Run with:
    pytest tests/unit/steps/test_rocchio_screening.py -v
"""


from paper_scanner.steps.keyword_screening import is_substantive_abstract
from paper_scanner.steps.rocchio_screening import RocchioScreeningStep


class TestIsSubstantiveAbstract:
    """Test abstract validation function"""

    def test_substantive_abstract_valid(self):
        """Verify valid abstract is recognized"""
        abstract = (
            "This paper presents a novel approach to digital transformation in manufacturing. "
            "We conducted interviews with 20 companies and identified key success factors."
        )
        assert is_substantive_abstract(abstract) is True

    def test_substantive_abstract_minimum_length(self):
        """Verify abstract must be at least 20 characters"""
        abstract_short = "Short abstract here"
        assert is_substantive_abstract(abstract_short) is False

    def test_substantive_abstract_just_above_minimum(self):
        """Verify abstract just above minimum length is accepted"""
        abstract = "This is an abstract about innovation"
        assert len(abstract) >= 20
        assert is_substantive_abstract(abstract) is True

    def test_boilerplate_conflict_of_interest(self):
        """Verify conflict of interest statement is rejected"""
        abstract = "The authors declare no conflicts of interest."
        assert is_substantive_abstract(abstract) is False

    def test_boilerplate_no_conflicts(self):
        """Verify 'no conflicts' statement is rejected"""
        abstract = "The authors declare no competing interests or conflicts of interest regarding this publication."
        assert is_substantive_abstract(abstract) is False

    def test_boilerplate_competing_interests(self):
        """Verify competing interests statement is rejected"""
        abstract = "The authors have no competing interests to declare."
        assert is_substantive_abstract(abstract) is False

    def test_boilerplate_acknowledgements(self):
        """Verify acknowledgements with funding/thanks is rejected"""
        abstract = "We acknowledge the funding support of our research institutions and sponsors."
        assert is_substantive_abstract(abstract) is False

    def test_boilerplate_acknowledgments_american(self):
        """Verify American spelling acknowledgments with thanks is rejected"""
        abstract = "The authors would like to thank the reviewers for their helpful comments and feedback."
        assert is_substantive_abstract(abstract) is False

    def test_acknowledgements_standalone_accepted(self):
        """Verify simple acknowledge word in normal context is accepted"""
        abstract = (
            "We acknowledge that digital transformation is important. This study examines how companies "
            "implement new technologies and processes for competitive advantage."
        )
        # This should be accepted because it's actually about research, not just a thanks statement
        assert is_substantive_abstract(abstract) is True

    def test_empty_abstract(self):
        """Verify empty abstract is rejected"""
        assert is_substantive_abstract("") is False

    def test_none_abstract(self):
        """Verify None abstract is rejected"""
        assert is_substantive_abstract(None) is False

    def test_whitespace_only_abstract(self):
        """Verify whitespace-only abstract is rejected"""
        assert is_substantive_abstract("   \n\t  ") is False

    def test_case_insensitive_matching(self):
        """Verify boilerplate detection is case-insensitive"""
        abstract = "THE AUTHORS DECLARE NO CONFLICTS OF INTEREST."
        assert is_substantive_abstract(abstract) is False

    def test_boilerplate_in_middle_of_text(self):
        """Verify boilerplate is rejected even if mixed with real content"""
        abstract = (
            "This paper studies digital innovation in manufacturing. "
            "The authors declare no conflicts of interest. "
            "We conducted extensive research."
        )
        # This should be rejected because it contains conflict of interest statement
        assert is_substantive_abstract(abstract) is False

    def test_valid_abstract_with_long_content(self):
        """Verify long valid abstract is accepted"""
        abstract = (
            "This comprehensive study examines the role of digital transformation in supply chain management. "
            "We conducted interviews with 50 companies across 10 industries and performed statistical analysis. "
            "Our findings show that firms incorporating digital technologies in supplier collaboration achieve 25% "
            "improvement in supply chain efficiency. We identified three critical success factors and developed a "
            "framework for digital innovation adoption."
        )
        assert is_substantive_abstract(abstract) is True

    def test_valid_abstract_exactly_50_characters(self):
        """Verify abstract exactly at 20 character minimum is accepted"""
        abstract = "A" * 20  # Exactly 20 characters
        assert is_substantive_abstract(abstract) is True

    def test_abstract_49_characters_rejected(self):
        """Verify abstract below 20 character minimum is rejected"""
        abstract = "A" * 19  # 19 characters
        assert is_substantive_abstract(abstract) is False


class TestValidate:
    """Tests for rocchio_screening step configuration validation"""

    def test_validate_empty_config(self):
        """Should accept empty config (all parameters are optional)"""
        is_valid, errors = RocchioScreeningStep.validate({})
        assert is_valid is True
        assert errors == []

    def test_validate_model_string(self):
        """Should accept string model parameter"""
        config = {"model": "specter2"}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_model_not_string(self):
        """Should reject non-string model"""
        config = {"model": 123}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is False
        assert any("model" in e.lower() and "string" in e.lower() for e in errors)

    def test_validate_rocchio_weights_dict(self):
        """Should accept rocchio_weights as dict"""
        config = {
            "rocchio_weights": {
                "alpha": 1.0,
                "beta": 0.75,
                "gamma": 0.15
            }
        }
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_rocchio_weights_not_dict(self):
        """Should reject rocchio_weights not dict"""
        config = {"rocchio_weights": [1.0, 0.75, 0.15]}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is False
        assert any("rocchio_weights" in e.lower() and "dictionary" in e.lower() for e in errors)

    def test_validate_rocchio_weight_alpha_valid(self):
        """Should accept numeric alpha weight"""
        config = {"rocchio_weights": {"alpha": 1.0}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_rocchio_weight_alpha_not_number(self):
        """Should reject non-numeric alpha weight"""
        config = {"rocchio_weights": {"alpha": "1.0"}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is False
        assert any("alpha" in e.lower() and "number" in e.lower() for e in errors)

    def test_validate_rocchio_weight_alpha_negative(self):
        """Should reject negative alpha weight"""
        config = {"rocchio_weights": {"alpha": -0.5}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is False
        assert any("alpha" in e.lower() and "non-negative" in e.lower() for e in errors)

    def test_validate_rocchio_weight_beta_valid(self):
        """Should accept numeric beta weight"""
        config = {"rocchio_weights": {"beta": 0.75}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_rocchio_weight_beta_not_number(self):
        """Should reject non-numeric beta weight"""
        config = {"rocchio_weights": {"beta": "0.75"}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is False
        assert any("beta" in e.lower() and "number" in e.lower() for e in errors)

    def test_validate_rocchio_weight_beta_negative(self):
        """Should reject negative beta weight"""
        config = {"rocchio_weights": {"beta": -0.1}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is False
        assert any("beta" in e.lower() and "non-negative" in e.lower() for e in errors)

    def test_validate_rocchio_weight_gamma_valid(self):
        """Should accept numeric gamma weight"""
        config = {"rocchio_weights": {"gamma": 0.15}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_rocchio_weight_gamma_not_number(self):
        """Should reject non-numeric gamma weight"""
        config = {"rocchio_weights": {"gamma": "0.15"}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is False
        assert any("gamma" in e.lower() and "number" in e.lower() for e in errors)

    def test_validate_rocchio_weight_gamma_negative(self):
        """Should reject negative gamma weight"""
        config = {"rocchio_weights": {"gamma": -0.05}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is False
        assert any("gamma" in e.lower() and "non-negative" in e.lower() for e in errors)

    def test_validate_rocchio_weight_zero_allowed(self):
        """Should accept zero weight values"""
        config = {"rocchio_weights": {"alpha": 0, "beta": 0, "gamma": 0}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_rocchio_weight_large_positive(self):
        """Should accept large positive weight values"""
        config = {"rocchio_weights": {"alpha": 100.5}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_thresholds_dict(self):
        """Should accept thresholds as dict"""
        config = {
            "thresholds": {
                "accept": 0.7,
                "reject": 0.3
            }
        }
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_thresholds_not_dict(self):
        """Should reject thresholds not dict"""
        config = {"thresholds": 0.7}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is False
        assert any("thresholds" in e.lower() and "dictionary" in e.lower() for e in errors)

    def test_validate_threshold_accept_valid(self):
        """Should accept numeric accept threshold between 0 and 1"""
        config = {"thresholds": {"accept": 0.7}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_threshold_accept_not_number(self):
        """Should reject non-numeric accept threshold"""
        config = {"thresholds": {"accept": "0.7"}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is False
        assert any("accept" in e.lower() and "number" in e.lower() for e in errors)

    def test_validate_threshold_accept_below_zero(self):
        """Should reject accept threshold below 0"""
        config = {"thresholds": {"accept": -0.1}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is False
        assert any("accept" in e.lower() for e in errors)

    def test_validate_threshold_accept_above_one(self):
        """Should reject accept threshold above 1"""
        config = {"thresholds": {"accept": 1.5}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is False
        assert any("accept" in e.lower() for e in errors)

    def test_validate_threshold_reject_valid(self):
        """Should accept numeric reject threshold between 0 and 1"""
        config = {"thresholds": {"reject": 0.3}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_threshold_reject_not_number(self):
        """Should reject non-numeric reject threshold"""
        config = {"thresholds": {"reject": "0.3"}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is False
        assert any("reject" in e.lower() and "number" in e.lower() for e in errors)

    def test_validate_threshold_reject_invalid_range(self):
        """Should reject reject threshold outside [0, 1]"""
        config = {"thresholds": {"reject": 2.0}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is False
        assert any("reject" in e.lower() for e in errors)

    def test_validate_threshold_boundary_zero(self):
        """Should accept threshold value of exactly 0"""
        config = {"thresholds": {"accept": 0}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_threshold_boundary_one(self):
        """Should accept threshold value of exactly 1"""
        config = {"thresholds": {"accept": 1}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_initialize_from_keyword_screening_boolean(self):
        """Should accept boolean initialize_from_keyword_screening"""
        config = {"initialize_from_keyword_screening": True}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_initialize_from_keyword_screening_false(self):
        """Should accept False for initialize_from_keyword_screening"""
        config = {"initialize_from_keyword_screening": False}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_initialize_from_keyword_screening_not_boolean(self):
        """Should reject non-boolean initialize_from_keyword_screening"""
        config = {"initialize_from_keyword_screening": "true"}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is False
        assert any("initialize_from_keyword_screening" in e.lower() and "boolean" in e.lower() for e in errors)

    def test_validate_all_parameters_together(self):
        """Should accept all parameters specified together"""
        config = {
            "model": "all-mpnet-base-v2",
            "rocchio_weights": {"alpha": 1.0, "beta": 0.75, "gamma": 0.15},
            "thresholds": {"accept": 0.7, "reject": 0.3},
            "initialize_from_keyword_screening": True
        }
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_multiple_errors(self):
        """Should collect multiple validation errors"""
        config = {
            "model": 123,
            "rocchio_weights": {
                "alpha": "invalid",
                "beta": -0.5
            },
            "thresholds": {"accept": 2.0},
            "initialize_from_keyword_screening": "yes"
        }
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is False
        assert len(errors) >= 3

    def test_validate_partial_rocchio_weights(self):
        """Should accept partial rocchio_weights specification"""
        config = {"rocchio_weights": {"alpha": 1.5}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_partial_thresholds(self):
        """Should accept partial thresholds specification"""
        config = {"thresholds": {"accept": 0.8}}
        is_valid, errors = RocchioScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

