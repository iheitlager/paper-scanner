"""
Unit tests for patch step
"""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.models import Author, Paper
from paper_scanner.steps.patch import (PatchStep, _apply_patch_to_paper,
                                       _load_patches_from_file)

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_paper():
    """Create a sample paper for testing"""
    return Paper(
        cite_key="Smith2020",
        title="Original Title",
        abstract="Original abstract text",
        keywords=["original", "keywords"],
        authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
        doi="10.1080/10864415.2024.2332047",
        year=2020,
        journal="Test Journal"
    )


@pytest.fixture
def papers_db_with_sample(sample_paper):
    """Create a database with a sample paper"""
    db = PapersDatabase()
    db.add(sample_paper)
    return db


@pytest.fixture
def yaml_patch_file():
    """Create a temporary YAML patch file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        patches = {
            "patches": [
                {
                    "doi": "10.1080/10864415.2024.2332047",
                    "replace_fields": {
                        "abstract": "blabla"
                    }
                }
            ]
        }
        yaml.dump(patches, f)
        path = f.name
    
    yield path
    Path(path).unlink()


@pytest.fixture
def json_patch_file():
    """Create a temporary JSON patch file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        patches = {
            "patches": [
                {
                    "doi": "10.1080/10864415.2024.2332047",
                    "replace_fields": {
                        "title": "New Title"
                    }
                }
            ]
        }
        json.dump(patches, f)
        path = f.name
    
    yield path
    Path(path).unlink()


@pytest.fixture
def complex_patch_file():
    """Create a patch file with multiple operations"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        patches = {
            "patches": [
                {
                    "doi": "10.1080/10864415.2024.2332047",
                    "replace_fields": {
                        "abstract": "New abstract",
                        "title": "New Title",
                        "journal": "New Journal"
                    },
                    "append_fields": {
                        "keywords": ["new-keyword"]
                    }
                }
            ]
        }
        yaml.dump(patches, f)
        path = f.name
    
    yield path
    Path(path).unlink()


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


# ============================================================================
# VALIDATION TESTS
# ============================================================================

class TestValidate:
    """Tests for patch step validation"""
    
    def test_validate_with_file_parameter(self):
        """Should validate when file parameter is provided"""
        config = {"file": "patches.yaml"}
        is_valid, errors = PatchStep.validate(config)
        assert is_valid
        assert errors == []
    
    def test_validate_with_patches_parameter(self):
        """Should validate when patches parameter is provided"""
        config = {
            "patches": [
                {
                    "doi": "10.1234/test",
                    "replace_fields": {"title": "New"}
                }
            ]
        }
        is_valid, errors = PatchStep.validate(config)
        assert is_valid
        assert errors == []
    
    def test_validate_missing_both_parameters(self):
        """Should fail when neither file nor patches provided"""
        config = {}
        is_valid, errors = PatchStep.validate(config)
        assert not is_valid
        assert len(errors) == 1
        assert "Either 'file' or 'patches'" in errors[0]
    
    def test_validate_file_not_string(self):
        """Should fail when file is not a string"""
        config = {"file": 123}
        is_valid, errors = PatchStep.validate(config)
        assert not is_valid
        assert any("must be a string" in e for e in errors)
    
    def test_validate_patches_not_list(self):
        """Should fail when patches is not a list"""
        config = {"patches": {"doi": "10.1234/test"}}
        is_valid, errors = PatchStep.validate(config)
        assert not is_valid
        assert any("must be a list" in e for e in errors)
    
    def test_validate_patch_missing_doi(self):
        """Should fail when patch is missing doi field"""
        config = {
            "patches": [
                {
                    "replace_fields": {"title": "New"}
                }
            ]
        }
        is_valid, errors = PatchStep.validate(config)
        assert not is_valid
        assert any("missing required 'doi'" in e for e in errors)
    
    def test_validate_patch_invalid_replace_fields(self):
        """Should fail when replace_fields is not a dict"""
        config = {
            "patches": [
                {
                    "doi": "10.1234/test",
                    "replace_fields": "invalid"
                }
            ]
        }
        is_valid, errors = PatchStep.validate(config)
        assert not is_valid
        assert any("must be a dictionary" in e for e in errors)
    
    def test_validate_multiple_patches(self):
        """Should validate multiple patches"""
        config = {
            "patches": [
                {
                    "doi": "10.1234/test1",
                    "replace_fields": {"title": "New1"}
                },
                {
                    "doi": "10.1234/test2",
                    "replace_fields": {"abstract": "New2"}
                }
            ]
        }
        is_valid, errors = PatchStep.validate(config)
        assert is_valid
        assert errors == []


# ============================================================================
# EXECUTION TESTS
# ============================================================================

class TestExecute:
    """Tests for patch step execution"""
    
    def test_execute_with_inline_patches_replace(self, papers_db_with_sample, temp_cache_dir):
        """Should apply inline patches with replace operation"""
        config = {
            "patches": [
                {
                    "doi": "10.1080/10864415.2024.2332047",
                    "replace_fields": {
                        "abstract": "blabla"
                    }
                }
            ]
        }
        
        step = PatchStep(general_config={}, db=papers_db_with_sample, cache_dir=temp_cache_dir)
        result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["status"] == "ok"
        assert result["patches_found"] == 1
        assert result["patches_applied"] == 1
        assert result["patches_failed"] == 0
        
        # Verify the paper was actually updated
        papers = papers_db_with_sample.get_by_doi("10.1080/10864415.2024.2332047")
        assert len(papers) == 1
        assert papers[0].abstract == "blabla"
    
    def test_execute_with_inline_patches_append_keywords(self, papers_db_with_sample, temp_cache_dir):
        """Should append to keywords list"""
        config = {
            "patches": [
                {
                    "doi": "10.1080/10864415.2024.2332047",
                    "append_fields": {
                        "keywords": ["new-keyword"]
                    }
                }
            ]
        }
        
        step = PatchStep(general_config={}, db=papers_db_with_sample, cache_dir=temp_cache_dir)
        result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["status"] == "ok"
        assert result["patches_applied"] == 1
        
        papers = papers_db_with_sample.get_by_doi("10.1080/10864415.2024.2332047")
        assert "new-keyword" in papers[0].keywords
        assert "original" in papers[0].keywords
    
    def test_execute_with_inline_patches_append_string(self, papers_db_with_sample, temp_cache_dir):
        """Should append to string fields"""
        config = {
            "patches": [
                {
                    "doi": "10.1080/10864415.2024.2332047",
                    "append_fields": {
                        "abstract": " more text"
                    }
                }
            ]
        }
        
        step = PatchStep(general_config={}, db=papers_db_with_sample, cache_dir=temp_cache_dir)
        result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["status"] == "ok"
        
        papers = papers_db_with_sample.get_by_doi("10.1080/10864415.2024.2332047")
        assert papers[0].abstract == "Original abstract text more text"
    
    def test_execute_multiple_field_replacements(self, papers_db_with_sample, temp_cache_dir):
        """Should replace multiple fields in one patch"""
        config = {
            "patches": [
                {
                    "doi": "10.1080/10864415.2024.2332047",
                    "replace_fields": {
                        "abstract": "new abstract",
                        "title": "new title",
                        "journal": "new journal"
                    }
                }
            ]
        }
        
        step = PatchStep(general_config={}, db=papers_db_with_sample, cache_dir=temp_cache_dir)
        result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["status"] == "ok"
        assert result["patches_applied"] == 1
        
        papers = papers_db_with_sample.get_by_doi("10.1080/10864415.2024.2332047")
        assert papers[0].abstract == "new abstract"
        assert papers[0].title == "new title"
        assert papers[0].journal == "new journal"
    
    def test_execute_mixed_replace_and_append(self, papers_db_with_sample, temp_cache_dir):
        """Should handle both replace and append in same patch"""
        config = {
            "patches": [
                {
                    "doi": "10.1080/10864415.2024.2332047",
                    "replace_fields": {
                        "abstract": "completely new"
                    },
                    "append_fields": {
                        "keywords": ["added"]
                    }
                }
            ]
        }
        
        step = PatchStep(general_config={}, db=papers_db_with_sample, cache_dir=temp_cache_dir)
        result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["status"] == "ok"
        
        papers = papers_db_with_sample.get_by_doi("10.1080/10864415.2024.2332047")
        assert papers[0].abstract == "completely new"
        assert "added" in papers[0].keywords
    
    def test_execute_doi_not_found(self, papers_db_with_sample, temp_cache_dir):
        """Should fail when DOI doesn't exist"""
        config = {
            "patches": [
                {
                    "doi": "10.9999/nonexistent.doi",
                    "replace_fields": {
                        "abstract": "blabla"
                    }
                }
            ]
        }
        
        step = PatchStep(general_config={}, db=papers_db_with_sample, cache_dir=temp_cache_dir)
        result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["status"] == "partial"
        assert result["patches_found"] == 1
        assert result["patches_applied"] == 0
        assert result["patches_failed"] == 1
        assert result["failed_details"] is not None
    
    def test_execute_multiple_patches_mixed_results(self, papers_db_with_sample, temp_cache_dir):
        """Should track multiple patches with mixed success/failure"""
        # Add a second paper
        paper2 = Paper(
            cite_key="Doe2021",
            title="Another Paper",
            abstract="Another abstract",
            authors=[],
            doi="10.1234/another.doi",
            year=2021
        )
        papers_db_with_sample.add(paper2)
        
        config = {
            "patches": [
                {
                    "doi": "10.1080/10864415.2024.2332047",
                    "replace_fields": {"abstract": "patched1"}
                },
                {
                    "doi": "10.9999/nonexistent.doi",
                    "replace_fields": {"abstract": "patched2"}
                },
                {
                    "doi": "10.1234/another.doi",
                    "replace_fields": {"abstract": "patched3"}
                }
            ]
        }
        
        step = PatchStep(general_config={}, db=papers_db_with_sample, cache_dir=temp_cache_dir)
        result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["patches_found"] == 3
        assert result["patches_applied"] == 2
        assert result["patches_failed"] == 1
    
    def test_execute_dry_run(self, papers_db_with_sample, temp_cache_dir):
        """Should not modify database in dry_run mode"""
        original_abstract = papers_db_with_sample.get_by_doi("10.1080/10864415.2024.2332047")[0].abstract
        
        config = {
            "patches": [
                {
                    "doi": "10.1080/10864415.2024.2332047",
                    "replace_fields": {"abstract": "modified"}
                }
            ]
        }
        
        step = PatchStep(general_config={}, db=papers_db_with_sample, cache_dir=temp_cache_dir)
        result = step.execute(config, verbose=False, dry_run=True)
        
        assert result["patches_applied"] == 1
        # Verify paper was not actually updated
        papers = papers_db_with_sample.get_by_doi("10.1080/10864415.2024.2332047")
        assert papers[0].abstract == original_abstract
    
    def test_execute_with_yaml_file(self, papers_db_with_sample, yaml_patch_file, temp_cache_dir):
        """Should load and apply patches from YAML file"""
        config = {"file": yaml_patch_file}
        
        step = PatchStep(general_config={}, db=papers_db_with_sample, cache_dir=temp_cache_dir)
        result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["status"] == "ok"
        assert result["patches_found"] == 1
        assert result["patches_applied"] == 1
        
        papers = papers_db_with_sample.get_by_doi("10.1080/10864415.2024.2332047")
        assert papers[0].abstract == "blabla"
    
    def test_execute_with_json_file(self, papers_db_with_sample, json_patch_file, temp_cache_dir):
        """Should load and apply patches from JSON file"""
        config = {"file": json_patch_file}
        
        step = PatchStep(general_config={}, db=papers_db_with_sample, cache_dir=temp_cache_dir)
        result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["status"] == "ok"
        assert result["patches_found"] == 1
        assert result["patches_applied"] == 1
        
        papers = papers_db_with_sample.get_by_doi("10.1080/10864415.2024.2332047")
        assert papers[0].title == "New Title"
    
    def test_execute_with_nonexistent_file(self, papers_db_with_sample, temp_cache_dir):
        """Should fail when file doesn't exist"""
        config = {"file": "/nonexistent/path/patches.yaml"}
        
        step = PatchStep(general_config={}, db=papers_db_with_sample, cache_dir=temp_cache_dir)
        result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()
    
    def test_execute_with_invalid_yaml_file(self, papers_db_with_sample, temp_cache_dir):
        """Should fail when YAML file is invalid"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            path = f.name
        
        try:
            config = {"file": path}
            step = PatchStep(general_config={}, db=papers_db_with_sample, cache_dir=temp_cache_dir)
            result = step.execute(config, verbose=False, dry_run=False)
            assert result["status"] == "error"
            assert "invalid" in result["error"].lower()
        finally:
            Path(path).unlink()
    
    def test_execute_with_complex_patch_file(self, papers_db_with_sample, complex_patch_file, temp_cache_dir):
        """Should handle complex patches with multiple operations"""
        config = {"file": complex_patch_file}
        
        step = PatchStep(general_config={}, db=papers_db_with_sample, cache_dir=temp_cache_dir)
        result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["status"] == "ok"
        
        papers = papers_db_with_sample.get_by_doi("10.1080/10864415.2024.2332047")
        assert papers[0].abstract == "New abstract"
        assert papers[0].title == "New Title"
        assert papers[0].journal == "New Journal"
        assert "new-keyword" in papers[0].keywords
    
    def test_execute_empty_patches_list(self, papers_db_with_sample, temp_cache_dir):
        """Should handle empty patches gracefully"""
        config = {"patches": []}
        
        step = PatchStep(general_config={}, db=papers_db_with_sample, cache_dir=temp_cache_dir)
        result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["status"] == "ok"
        assert result["patches_found"] == 0
        assert result["patches_applied"] == 0
    
    def test_execute_no_patches_no_append_fields(self, papers_db_with_sample, temp_cache_dir):
        """Should handle patch with only replace_fields (no append_fields)"""
        config = {
            "patches": [
                {
                    "doi": "10.1080/10864415.2024.2332047",
                    "replace_fields": {"abstract": "new"}
                }
            ]
        }
        
        step = PatchStep(general_config={}, db=papers_db_with_sample, cache_dir=temp_cache_dir)
        result = step.execute(config, verbose=False, dry_run=False)
        
        assert result["status"] == "ok"
        assert result["patches_applied"] == 1


# ============================================================================
# HELPER FUNCTION TESTS
# ============================================================================

class TestLoadPatchesFromFile:
    """Tests for _load_patches_from_file function"""
    
    def test_load_yaml_file(self, yaml_patch_file):
        """Should load patches from YAML file"""
        patches = _load_patches_from_file(Path(yaml_patch_file))
        assert len(patches) == 1
        assert patches[0]["doi"] == "10.1080/10864415.2024.2332047"
    
    def test_load_json_file(self, json_patch_file):
        """Should load patches from JSON file"""
        patches = _load_patches_from_file(Path(json_patch_file))
        assert len(patches) == 1
        assert patches[0]["doi"] == "10.1080/10864415.2024.2332047"
    
    def test_load_nonexistent_file(self):
        """Should raise IOError for nonexistent file"""
        with pytest.raises(IOError):
            _load_patches_from_file(Path("/nonexistent/file.yaml"))
    
    def test_load_invalid_yaml(self):
        """Should raise ValueError for invalid YAML"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: [")
            path = f.name
        
        try:
            with pytest.raises(ValueError):
                _load_patches_from_file(Path(path))
        finally:
            Path(path).unlink()
    
    def test_load_unsupported_format(self):
        """Should raise ValueError for unsupported file format"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("patches: []")
            path = f.name
        
        try:
            with pytest.raises(ValueError, match="Unsupported file format"):
                _load_patches_from_file(Path(path))
        finally:
            Path(path).unlink()


class TestApplyPatchToPaper:
    """Tests for _apply_patch_to_paper function"""
    
    def test_apply_simple_replace(self, sample_paper):
        """Should apply simple field replacement"""
        patch = {
            "replace_fields": {"abstract": "new abstract"}
        }
        success, error = _apply_patch_to_paper(sample_paper, patch)
        assert success
        assert error is None
        assert sample_paper.abstract == "new abstract"
    
    def test_apply_invalid_field_name(self, sample_paper):
        """Should fail for invalid field name"""
        patch = {
            "replace_fields": {"nonexistent_field": "value"}
        }
        success, error = _apply_patch_to_paper(sample_paper, patch)
        assert not success
        assert "nonexistent_field" in error
    
    def test_apply_append_to_list(self, sample_paper):
        """Should append to list fields"""
        patch = {
            "append_fields": {"keywords": ["new"]}
        }
        success, error = _apply_patch_to_paper(sample_paper, patch)
        assert success
        assert "new" in sample_paper.keywords
    
    def test_apply_append_to_string(self, sample_paper):
        """Should append to string fields"""
        patch = {
            "append_fields": {"abstract": " more"}
        }
        success, error = _apply_patch_to_paper(sample_paper, patch)
        assert success
        assert sample_paper.abstract == "Original abstract text more"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])