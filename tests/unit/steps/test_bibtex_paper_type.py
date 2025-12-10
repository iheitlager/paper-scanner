"""
Tests for BibTeX paper type evaluation and mapping
"""

import pytest
from pathlib import Path

from paper_scanner.io.bibtex import (
    load_type_mapping_config,
    evaluate_paper_type,
    bibtex_file_to_papers,
    bibtex_to_papers
)


class TestTypeMapping:
    """Test type mapping configuration loading"""
    
    def test_load_default_type_mapping(self):
        """Test loading default type mapping configuration"""
        config = load_type_mapping_config()
        
        assert 'type_mappings' in config
        assert 'article' in config['type_mappings']
        assert 'inproceedings' in config['type_mappings']
        assert 'book' in config['type_mappings']
    
    def test_type_mapping_has_required_fields(self):
        """Test that type mappings have required fields"""
        config = load_type_mapping_config()
        
        for entry_type, mapping in config['type_mappings'].items():
            assert 'paper_type' in mapping, f"Missing paper_type for {entry_type}"
            assert 'confidence' in mapping, f"Missing confidence for {entry_type}"
            assert isinstance(mapping['confidence'], (int, float))
            assert 0 <= mapping['confidence'] <= 1
    
    def test_source_overrides_present(self):
        """Test that source-specific overrides are present"""
        config = load_type_mapping_config()
        
        assert 'source_overrides' in config
        assert isinstance(config['source_overrides'], dict)


class TestPaperTypeEvaluation:
    """Test paper type evaluation from BibTeX entries"""
    
    def test_evaluate_article_type(self):
        """Test evaluation of article entry type"""
        config = load_type_mapping_config()
        entry = {'ENTRYTYPE': 'article', 'ID': 'test123'}
        
        paper_type, confidence = evaluate_paper_type(entry, type_mapping_config=config)
        
        assert paper_type == 'article'
        assert confidence == 0.95
    
    def test_evaluate_inproceedings_type(self):
        """Test evaluation of inproceedings (conference) entry type"""
        config = load_type_mapping_config()
        entry = {'ENTRYTYPE': 'inproceedings', 'ID': 'test123'}
        
        paper_type, confidence = evaluate_paper_type(entry, type_mapping_config=config)
        
        assert paper_type == 'conference_paper'
        assert confidence == 0.95
    
    def test_evaluate_book_type(self):
        """Test evaluation of book entry type"""
        config = load_type_mapping_config()
        entry = {'ENTRYTYPE': 'book', 'ID': 'test123'}
        
        paper_type, confidence = evaluate_paper_type(entry, type_mapping_config=config)
        
        assert paper_type == 'book'
        assert confidence == 0.95
    
    def test_evaluate_book_chapter_type(self):
        """Test evaluation of book chapter entry types"""
        config = load_type_mapping_config()
        
        # Test incollection
        entry = {'ENTRYTYPE': 'incollection', 'ID': 'test123'}
        paper_type, confidence = evaluate_paper_type(entry, type_mapping_config=config)
        assert paper_type == 'book_chapter'
        
        # Test inbook
        entry = {'ENTRYTYPE': 'inbook', 'ID': 'test123'}
        paper_type, confidence = evaluate_paper_type(entry, type_mapping_config=config)
        assert paper_type == 'book_chapter'
    
    def test_evaluate_thesis_type(self):
        """Test evaluation of thesis entry types"""
        config = load_type_mapping_config()
        
        # Test phdthesis
        entry = {'ENTRYTYPE': 'phdthesis', 'ID': 'test123'}
        paper_type, confidence = evaluate_paper_type(entry, type_mapping_config=config)
        assert paper_type == 'thesis'
        
        # Test mastersthesis
        entry = {'ENTRYTYPE': 'mastersthesis', 'ID': 'test123'}
        paper_type, confidence = evaluate_paper_type(entry, type_mapping_config=config)
        assert paper_type == 'thesis'
    
    def test_evaluate_technical_report(self):
        """Test evaluation of technical report"""
        config = load_type_mapping_config()
        entry = {'ENTRYTYPE': 'techreport', 'ID': 'test123'}
        
        paper_type, confidence = evaluate_paper_type(entry, type_mapping_config=config)
        
        assert paper_type == 'technical_report'
        assert confidence == 0.90
    
    def test_evaluate_misc_type(self):
        """Test evaluation of misc (fallback) type"""
        config = load_type_mapping_config()
        entry = {'ENTRYTYPE': 'misc', 'ID': 'test123'}
        
        paper_type, confidence = evaluate_paper_type(entry, type_mapping_config=config)
        
        assert paper_type == 'other'
        assert confidence == 0.5
    
    def test_evaluate_unknown_type_fallback(self):
        """Test evaluation of unknown type returns None with low confidence"""
        config = load_type_mapping_config()
        entry = {'ENTRYTYPE': 'unknown_type', 'ID': 'test123'}
        
        paper_type, confidence = evaluate_paper_type(entry, type_mapping_config=config)
        
        assert paper_type is None
        assert confidence == 0.0
    
    def test_evaluate_case_insensitive(self):
        """Test that evaluation is case-insensitive"""
        config = load_type_mapping_config()
        
        # Mixed case
        entry = {'ENTRYTYPE': 'ArTiClE', 'ID': 'test123'}
        paper_type, confidence = evaluate_paper_type(entry, type_mapping_config=config)
        
        assert paper_type == 'article'


class TestBibTeXFileImport:
    """Test importing BibTeX files with paper type evaluation"""
    
    @pytest.fixture
    def test_data_dir(self):
        """Return path to test data directory"""
        return Path(__file__).parent.parent.parent / "data"
    
    def test_import_scopus_file(self, test_data_dir):
        """Test importing Scopus BibTeX file"""
        scopus_file = test_data_dir / "scopus_sample_20.bib"
        
        if not scopus_file.exists():
            pytest.skip(f"Test file not found: {scopus_file}")
        
        papers = bibtex_file_to_papers(
            str(scopus_file),
            source_type="scopus"
        )
        
        assert len(papers) > 0
        # Check that papers have paper_type populated
        papers_with_type = [p for p in papers if p.paper_type]
        assert len(papers_with_type) > 0, "No papers have paper_type populated"
    
    def test_import_ieee_file(self, test_data_dir):
        """Test importing IEEE BibTeX file"""
        ieee_file = test_data_dir / "ieee_sample_20.bib"
        
        if not ieee_file.exists():
            pytest.skip(f"Test file not found: {ieee_file}")
        
        papers = bibtex_file_to_papers(
            str(ieee_file),
            source_type="ieee"
        )
        
        assert len(papers) > 0
        # Check that papers have paper_type populated
        papers_with_type = [p for p in papers if p.paper_type]
        assert len(papers_with_type) > 0, "No papers have paper_type populated"
    
    def test_import_wos_file(self, test_data_dir):
        """Test importing Web of Science BibTeX file"""
        wos_file = test_data_dir / "wos_sample_20.bib"
        
        if not wos_file.exists():
            pytest.skip(f"Test file not found: {wos_file}")
        
        papers = bibtex_file_to_papers(
            str(wos_file),
            source_type="wos"
        )
        
        assert len(papers) > 0
        # Check that papers have paper_type populated
        papers_with_type = [p for p in papers if p.paper_type]
        assert len(papers_with_type) > 0, "No papers have paper_type populated"
    
    def test_paper_type_distribution(self, test_data_dir):
        """Test that imported papers have diverse paper types"""
        scopus_file = test_data_dir / "scopus_sample_20.bib"
        ieee_file = test_data_dir / "ieee_sample_20.bib"
        
        if not scopus_file.exists() or not ieee_file.exists():
            pytest.skip("Test files not found")
        
        papers = bibtex_file_to_papers(str(scopus_file), source_type="scopus")
        papers.extend(bibtex_file_to_papers(str(ieee_file), source_type="ieee"))
        
        # Collect paper types
        paper_types = set()
        for paper in papers:
            if paper.paper_type:
                paper_types.add(paper.paper_type)
        
        assert len(paper_types) > 0, "No paper types found"
        print(f"Found paper types: {paper_types}")


class TestTypeEvaluationWithRealData:
    """Test type evaluation with actual BibTeX file data"""
    
    @pytest.fixture
    def test_data_dir(self):
        """Return path to test data directory"""
        return Path(__file__).parent.parent.parent / "data"
    
    def test_scopus_articles_identified(self, test_data_dir):
        """Test that Scopus articles are correctly identified as 'article' type"""
        scopus_file = test_data_dir / "scopus_sample_20.bib"
        
        if not scopus_file.exists():
            pytest.skip(f"Test file not found: {scopus_file}")
        
        papers = bibtex_file_to_papers(
            str(scopus_file),
            source_type="scopus"
        )
        
        # Scopus file should have articles (based on the sample data)
        articles = [p for p in papers if p.paper_type == 'article']
        assert len(articles) > 0, "No articles found in Scopus sample"
    
    def test_ieee_conferences_identified(self, test_data_dir):
        """Test that IEEE conference papers are correctly identified"""
        ieee_file = test_data_dir / "ieee_sample_20.bib"
        
        if not ieee_file.exists():
            pytest.skip(f"Test file not found: {ieee_file}")
        
        papers = bibtex_file_to_papers(
            str(ieee_file),
            source_type="ieee"
        )
        
        # IEEE file should have conference papers (based on the sample data)
        conferences = [p for p in papers if p.paper_type == 'conference_paper']
        assert len(conferences) > 0, "No conference papers found in IEEE sample"
