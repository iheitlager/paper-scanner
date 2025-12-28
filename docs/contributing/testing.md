# Testing

Complete guide to testing in paper-scanner.

## Test Structure

```
tests/
├── unit/              # Fast, isolated unit tests
│   ├── core/
│   ├── steps/
│   ├── cli/
│   └── tools/
├── integration/       # Tests requiring multiple components
├── spikes/           # Experimental test code
└── data/             # Test data files
```

## Running Tests

### All Tests
```bash
make test
# or
uv run pytest
```

### Specific Test File
```bash
uv run pytest tests/unit/steps/test_citations.py -v
```

### Specific Test Class
```bash
uv run pytest tests/unit/steps/test_citations.py::TestCitations -v
```

### Specific Test Function
```bash
uv run pytest tests/unit/steps/test_citations.py::TestCitations::test_validate -v
```

### With Coverage
```bash
uv run pytest --cov=src/paper_scanner tests/
```

### Watch Mode
```bash
make test-watch
# Runs tests on file changes
```

## Writing Unit Tests

### Basic Test Structure
```python
import pytest
from paper_scanner.core.models import Paper, Author

class TestPaper:
    """Tests for Paper model"""
    
    def test_paper_creation(self):
        """Test creating a paper"""
        paper = Paper(
            cite_key="Smith2023",
            title="Example Paper",
            year=2023
        )
        
        assert paper.cite_key == "Smith2023"
        assert paper.title == "Example Paper"
```

### Using Fixtures
```python
@pytest.fixture
def sample_paper():
    """Create a sample paper for testing"""
    return Paper(
        cite_key="Smith2023",
        title="Example",
        year=2023
    )

def test_paper_with_authors(sample_paper):
    """Test paper with authors"""
    sample_paper.authors.append(
        Author(first_name="John", last_name="Smith")
    )
    
    assert len(sample_paper.authors) == 1
```

### Mocking External Calls
```python
from unittest.mock import MagicMock, patch

@patch('paper_scanner.tools.fetchers.fetcher.Fetcher')
def test_fetch_with_mock(mock_fetcher):
    """Test with mocked fetcher"""
    mock_fetcher.return_value.fetch_paper.return_value = (
        Paper(title="Fetched"),
        True,  # cache_hit
        "crossref"
    )
    
    # Test code
    fetcher = Fetcher()
    paper, cache_hit, handler = fetcher.fetch_paper("10.1234/test")
    
    assert paper.title == "Fetched"
    assert cache_hit is True
```

### Testing Database Operations
```python
@pytest.fixture
def temp_db(tmp_path):
    """Create temporary test database"""
    db_path = tmp_path / "test.db"
    db = PapersDatabase(str(db_path))
    yield db
    # Cleanup happens automatically

def test_add_paper(temp_db):
    """Test adding paper to database"""
    paper = Paper(cite_key="Test", title="Test", year=2023)
    temp_db.add(paper)
    
    papers = temp_db.all()
    assert len(papers) == 1
    assert papers[0].cite_key == "Test"
```

## Testing Steps

### Basic Step Test
```python
from paper_scanner.steps.export import ExportStep
from paper_scanner.core.database import PapersDatabase

class TestExportStep:
    
    @pytest.fixture
    def step(self, tmp_path):
        db = PapersDatabase(str(tmp_path / "test.db"))
        return ExportStep(
            general_config={},
            db=db,
            cache_dir=tmp_path
        )
    
    def test_validate_requires_format(self):
        """Test that format is required"""
        config = {}
        is_valid, errors = ExportStep.validate(config)
        
        assert not is_valid
        assert any("format" in err for err in errors)
    
    def test_execute_exports_papers(self, step):
        """Test exporting papers"""
        # Setup
        paper = Paper(cite_key="Test", title="Test")
        step.db.add(paper)
        
        # Execute
        config = {"format": "bibtex"}
        result = step.execute(config)
        
        # Assert
        assert result.status == StepStatus.SUCCESS
```

## Testing Best Practices

### 1. Isolation
Each test should be independent:
```python
# ✅ Good
def test_paper_title(self):
    paper = Paper(title="Test")
    assert paper.title == "Test"

# ❌ Bad
def test_paper_operations(self):
    paper = Paper(title="Test")
    # Tests multiple things in one
```

### 2. Clear Naming
Test names should describe what they test:
```python
# ✅ Good
def test_validate_requires_input_file(self):
    pass

# ❌ Bad
def test_validate(self):
    pass
```

### 3. Arrange-Act-Assert
```python
def test_example(self):
    # Arrange (setup)
    paper = Paper(title="Test")
    
    # Act (execute)
    paper.title = "Updated"
    
    # Assert (verify)
    assert paper.title == "Updated"
```

### 4. Specific Assertions
```python
# ✅ Good
assert len(papers) == 3
assert papers[0].doi is not None

# ❌ Bad
assert papers  # Too vague
```

### 5. Test Edge Cases
```python
def test_empty_list(self):
    result = process_papers([])
    assert result == {}

def test_none_value(self):
    result = process_paper(None)
    assert result is None

def test_very_long_string(self):
    long_title = "x" * 10000
    paper = Paper(title=long_title)
    assert len(paper.title) == 10000
```

## Test Markers

Mark tests with metadata:

```python
@pytest.mark.slow
def test_large_dataset(self):
    """This test takes time"""
    pass

@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature(self):
    pass

@pytest.mark.parametrize("input,expected", [
    ("test1", 1),
    ("test2", 2),
])
def test_multiple_inputs(self, input, expected):
    assert len(input) == expected
```

## Coverage Requirements

Aim for:
- **80%+** overall coverage
- **90%+** for critical paths (core, database)
- **70%+** for UI/CLI code

Check coverage:
```bash
uv run pytest --cov=src/paper_scanner --cov-report=html tests/
```

## Continuous Integration

Tests run automatically on:
- Pull requests
- Commits to main branch
- On schedule (daily)

See `.github/workflows/` for CI configuration.

## Debugging Tests

### Add Print Statements
```python
def test_example(self):
    result = some_function()
    print(f"Result: {result}")  # Shows in test output with -s
    assert result == expected
```

Run with output:
```bash
uv run pytest -s tests/unit/test_example.py
```

### Use Debugger
```python
def test_example(self):
    breakpoint()  # Drops into pdb debugger
    result = some_function()
    assert result == expected
```

### Verbose Output
```bash
uv run pytest -vv tests/unit/test_example.py::test_function
```

## Performance Testing

### Timing Tests
```python
import time

def test_large_import_performance(self):
    """Ensure import completes quickly"""
    start = time.time()
    result = import_large_file()
    duration = time.time() - start
    
    assert duration < 5.0  # Should complete in under 5 seconds
```

## Next Steps

- [Code Standards](standards.md)
- [Development Setup](setup.md)
- [Architecture Overview](../architecture/overview.md)
