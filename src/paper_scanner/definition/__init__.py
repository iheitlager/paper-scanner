"""
Pythonic Definition API - Type-safe step definition without YAML

This module provides a fluent builder API for constructing paper-scanner
processing pipelines entirely in Python with full type safety and IDE support.

Example:
    >>> definition = (
    ...     Definition("My Research Review")
    ...     .bibtex_import(
    ...         batch_id="batch_1",
    ...         imports=[BibtexSource.scopus("Scopus", "data.bib", 100)]
    ...     )
    ...     .deduplication(enabled=True)
    ...     .export(format="jsonl", output_path="~/output.jsonl")
    ... )
    >>> results = definition.run(verbose=True)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
import yaml

from paper_scanner.core.database import PapersDatabase
from paper_scanner.cli.paper_processor import StepExecutor


# ============================================================================
# Base Step Class
# ============================================================================

class Step(ABC):
    """Abstract base class for all processing steps"""
    
    @abstractmethod
    def get_name(self) -> str:
        """Get step identifier (e.g., 'bibtex_import')"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Get human-readable step description"""
        pass
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert to YAML-compatible dictionary format"""
        pass


# ============================================================================
# Configuration Dataclasses
# ============================================================================

@dataclass
class DatabaseConfig:
    """Database connection configuration"""
    host: str = "localhost"
    port: int = 5432
    name: str = "paper_scanner"
    user: str = "pdfuser"
    password: str = "pdfpass"


@dataclass
class BibtexSource:
    """Single BibTeX import source"""
    name: str
    file_path: str
    source_type: str
    expected_count: Optional[int] = None
    
    @staticmethod
    def scopus(name: str, file_path: str, expected_count: Optional[int] = None) -> "BibtexSource":
        """Create Scopus import source"""
        return BibtexSource(name, file_path, "scopus", expected_count)
    
    @staticmethod
    def ieee(name: str, file_path: str, expected_count: Optional[int] = None) -> "BibtexSource":
        """Create IEEE Xplore import source"""
        return BibtexSource(name, file_path, "ieee_xplore", expected_count)
    
    @staticmethod
    def wos(name: str, file_path: str, expected_count: Optional[int] = None) -> "BibtexSource":
        """Create Web of Science import source"""
        return BibtexSource(name, file_path, "web_of_science", expected_count)


@dataclass
class BibtexImportConfig:
    """BibTeX import step configuration"""
    batch_id: str
    imports: List[BibtexSource]


@dataclass
class DeduplicationMethod:
    """Single deduplication method configuration"""
    method: str
    priority: int
    threshold: Optional[float] = None


@dataclass
class DeduplicationConfig:
    """Deduplication step configuration"""
    enabled: bool = True
    methods: Optional[List[DeduplicationMethod]] = None


@dataclass
class CategorizationConfig:
    """Categorization step configuration"""
    enabled: bool = True


@dataclass
class KeywordScreeningConfig:
    """Keyword screening step configuration"""
    enabled: bool = True
    keywords: Optional[List[str]] = None


@dataclass
class SemanticScreeningConfig:
    """Semantic screening step configuration"""
    enabled: bool = True


@dataclass
class CheckpointConfig:
    """Checkpoint step configuration"""
    label: Optional[str] = None


@dataclass
class EchoConfig:
    """Echo step configuration"""
    message: Optional[str] = None


@dataclass
class SummarizeConfig:
    """Summarize step configuration"""
    summary: bool = True
    tabulate: Optional[List[Dict[str, Any]]] = None


@dataclass
class ExportConfig:
    """Export step configuration"""
    format: str
    output_path: str
    exclude_none: bool = True
    duplicates: bool = False  # False, True, or "only"
    overwrite: bool = False


@dataclass
class HaltConfig:
    """Halt step configuration"""
    message: str = ""


# ============================================================================
# Step Implementations
# ============================================================================

class BibtexImportStep(Step):
    """BibTeX import step"""
    
    def __init__(self, config: BibtexImportConfig):
        self.config = config
    
    def get_name(self) -> str:
        return "bibtex_import"
    
    def get_description(self) -> str:
        return f"Import {len(self.config.imports)} BibTeX source(s)"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.get_description(),
            "builtin.bibtex_import": asdict(self.config)
        }


class DeduplicationStep(Step):
    """Deduplication step"""
    
    def __init__(self, config: DeduplicationConfig):
        self.config = config
    
    def get_name(self) -> str:
        return "deduplication"
    
    def get_description(self) -> str:
        num_methods = len(self.config.methods) if self.config.methods else 0
        return f"Deduplicate papers using {num_methods} method(s)"
    
    def to_dict(self) -> Dict[str, Any]:
        config_dict = asdict(self.config)
        return {
            "step": self.get_description(),
            "builtin.deduplication": config_dict
        }


class CategorizationStep(Step):
    """Categorization step"""
    
    def __init__(self, config: CategorizationConfig):
        self.config = config
    
    def get_name(self) -> str:
        return "categorization"
    
    def get_description(self) -> str:
        return "Categorize and screen papers for quality"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.get_description(),
            "builtin.categorization": asdict(self.config)
        }


class KeywordScreeningStep(Step):
    """Keyword screening step"""
    
    def __init__(self, config: KeywordScreeningConfig):
        self.config = config
    
    def get_name(self) -> str:
        return "keyword_screening"
    
    def get_description(self) -> str:
        return "Screen papers by keywords"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.get_description(),
            "builtin.keyword_screening": asdict(self.config)
        }


class SemanticScreeningStep(Step):
    """Semantic screening step"""
    
    def __init__(self, config: SemanticScreeningConfig):
        self.config = config
    
    def get_name(self) -> str:
        return "semantic_screening"
    
    def get_description(self) -> str:
        return "Perform semantic screening"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.get_description(),
            "builtin.semantic_screening": asdict(self.config)
        }


class CheckpointStep(Step):
    """Checkpoint step"""
    
    def __init__(self, config: CheckpointConfig):
        self.config = config
    
    def get_name(self) -> str:
        return "checkpoint"
    
    def get_description(self) -> str:
        label = f" ({self.config.label})" if self.config.label else ""
        return f"Save checkpoint{label}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.get_description(),
            "builtin.checkpoint": asdict(self.config)
        }


class EchoStep(Step):
    """Echo step"""
    
    def __init__(self, config: EchoConfig):
        self.config = config
    
    def get_name(self) -> str:
        return "echo"
    
    def get_description(self) -> str:
        return self.config.message or "Echo message"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.get_description(),
            "builtin.echo": asdict(self.config)
        }


class SummarizeStep(Step):
    """Summarize step"""
    
    def __init__(self, config: SummarizeConfig):
        self.config = config
    
    def get_name(self) -> str:
        return "summarize"
    
    def get_description(self) -> str:
        return "Display database statistics and summary"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.get_description(),
            "builtin.summarize": asdict(self.config)
        }


class ExportStep(Step):
    """Export step"""
    
    def __init__(self, config: ExportConfig):
        self.config = config
    
    def get_name(self) -> str:
        return "export"
    
    def get_description(self) -> str:
        return f"Export database to {self.config.format.upper()} format"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.get_description(),
            "builtin.export": asdict(self.config)
        }


class HaltStep(Step):
    """Halt step"""
    
    def __init__(self, config: HaltConfig):
        self.config = config
    
    def get_name(self) -> str:
        return "halt"
    
    def get_description(self) -> str:
        return self.config.message or "Halt pipeline"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.get_description(),
            "builtin.halt": asdict(self.config)
        }


# ============================================================================
# Definition Class (Fluent Builder)
# ============================================================================

class Definition:
    """
    Fluent builder for paper-scanner processing pipelines.
    
    Allows construction of processing pipelines entirely in Python with
    full type safety and IDE support.
    
    Example:
        >>> pipeline = (
        ...     Definition("My Project")
        ...     .bibtex_import(
        ...         batch_id="batch_1",
        ...         imports=[BibtexSource.scopus("Scopus", "data.bib", 100)]
        ...     )
        ...     .export(format="jsonl", output_path="~/output.jsonl")
        ... )
        >>> results = pipeline.run()
    """
    
    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        researcher: Optional[str] = None,
        institution: Optional[str] = None,
        database: Optional[DatabaseConfig] = None
    ):
        """
        Initialize a new Definition.
        
        Args:
            name: Project name
            description: Project description
            researcher: Researcher name
            institution: Institution name
            database: Database configuration
        """
        self.name = name
        self.description = description
        self.researcher = researcher
        self.institution = institution
        self.database = database or DatabaseConfig()
        self.steps: List[Step] = []
        self.project_metadata: Dict[str, Any] = {}
    
    # ========== Step Methods ==========
    
    def bibtex_import(
        self,
        batch_id: str,
        imports: List[BibtexSource]
    ) -> "Definition":
        """Add BibTeX import step"""
        self.steps.append(BibtexImportStep(BibtexImportConfig(batch_id, imports)))
        return self
    
    def deduplication(
        self,
        enabled: bool = True,
        methods: Optional[List[DeduplicationMethod]] = None
    ) -> "Definition":
        """Add deduplication step"""
        self.steps.append(DeduplicationStep(DeduplicationConfig(enabled, methods)))
        return self
    
    def categorization(self, enabled: bool = True) -> "Definition":
        """Add categorization step"""
        self.steps.append(CategorizationStep(CategorizationConfig(enabled)))
        return self
    
    def keyword_screening(
        self,
        enabled: bool = True,
        keywords: Optional[List[str]] = None
    ) -> "Definition":
        """Add keyword screening step"""
        self.steps.append(KeywordScreeningStep(KeywordScreeningConfig(enabled, keywords)))
        return self
    
    def semantic_screening(self, enabled: bool = True) -> "Definition":
        """Add semantic screening step"""
        self.steps.append(SemanticScreeningStep(SemanticScreeningConfig(enabled)))
        return self
    
    def checkpoint(self, label: Optional[str] = None) -> "Definition":
        """Add checkpoint step"""
        self.steps.append(CheckpointStep(CheckpointConfig(label)))
        return self
    
    def echo(self, message: Optional[str] = None) -> "Definition":
        """Add echo step"""
        self.steps.append(EchoStep(EchoConfig(message)))
        return self
    
    def summarize(
        self,
        summary: bool = True,
        tabulate: Optional[List[Dict[str, Any]]] = None
    ) -> "Definition":
        """Add summarize step"""
        self.steps.append(SummarizeStep(SummarizeConfig(summary, tabulate)))
        return self
    
    def export(
        self,
        format: str,
        output_path: str,
        exclude_none: bool = True,
        duplicates: bool = False,
        overwrite: bool = False
    ) -> "Definition":
        """Add export step"""
        self.steps.append(ExportStep(ExportConfig(
            format, output_path, exclude_none, duplicates, overwrite
        )))
        return self
    
    def halt(self, message: str = "") -> "Definition":
        """Add halt step"""
        self.steps.append(HaltStep(HaltConfig(message)))
        return self
    
    def add_step(self, step: Step) -> "Definition":
        """Add custom step"""
        self.steps.append(step)
        return self
    
    # ========== Conversion Methods ==========
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert definition to YAML-compatible dictionary"""
        result = {
            "project": {
                "name": self.name,
            }
        }
        
        if self.description:
            result["project"]["description"] = self.description
        if self.researcher:
            result["project"]["researcher"] = self.researcher
        if self.institution:
            result["project"]["institution"] = self.institution
        
        # Add database config
        result["database"] = asdict(self.database)
        
        # Add steps
        result["steps"] = [step.to_dict() for step in self.steps]
        
        return result
    
    def to_yaml(self, filepath: Path) -> None:
        """Save definition to YAML file"""
        with open(filepath, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)
    
    def get_steps(self) -> List[Step]:
        """Get list of steps in definition"""
        return self.steps.copy()
    
    # ========== Execution Methods ==========
    
    def run(self, verbose: bool = False, dry_run: bool = False):
        """
        Execute the pipeline.
        
        Args:
            verbose: Enable verbose output
            dry_run: Don't actually execute
        
        Returns:
            Execution results
        """
        papers_db = PapersDatabase()
        results = []
        
        for i, step in enumerate(self.steps, 1):
            step_dict = step.to_dict()
            
            try:
                result = StepExecutor.execute_step(
                    step_dict,
                    papers_db,
                    verbose=verbose,
                    dry_run=dry_run,
                    step_index=i - 1,
                    project_name=self.name,
                    project_config={"name": self.name}
                )
                results.append(result)
            except Exception as e:
                if verbose:
                    print(f"Error in step {i}: {e}")
                raise
        
        return {
            "project": self.name,
            "steps_executed": len(results),
            "results": results
        }


# ============================================================================
# Factory Functions
# ============================================================================

def from_yaml(filepath: Path) -> Definition:
    """Load definition from YAML file"""
    with open(filepath) as f:
        data = yaml.safe_load(f)
    
    # Parse project section
    project = data.get("project", {})
    database = data.get("database", {})
    
    definition = Definition(
        name=project.get("name", "Untitled"),
        description=project.get("description"),
        researcher=project.get("researcher"),
        institution=project.get("institution"),
        database=DatabaseConfig(**database) if database else None
    )
    
    # TODO: Parse and add steps from YAML
    # This would require reverse-mapping YAML to Step objects
    
    return definition


# ============================================================================
# Helper Functions
# ============================================================================

def create_standard_pipeline(
    project_name: str,
    sources: List[BibtexSource],
    deduplicate: bool = True,
    categorize: bool = True,
    export_format: str = "jsonl",
    output_path: str = "~/output.jsonl"
) -> Definition:
    """
    Create a standard processing pipeline.
    
    Args:
        project_name: Name of the project
        sources: List of BibTeX sources to import
        deduplicate: Whether to deduplicate papers
        categorize: Whether to categorize papers
        export_format: Export format (jsonl, bibtex, csv)
        output_path: Path for export file
    
    Returns:
        Configured Definition object
    """
    definition = Definition(project_name)
    
    definition.bibtex_import(
        batch_id=f"batch_{project_name}",
        imports=sources
    )
    
    definition.echo(message="Import complete")
    definition.checkpoint(label="post_import")
    
    if deduplicate:
        definition.deduplication(
            enabled=True,
            methods=[
                DeduplicationMethod(method="doi_exact", priority=1),
                DeduplicationMethod(method="title_author_fuzzy", priority=2, threshold=0.90),
                DeduplicationMethod(method="title_fuzzy", priority=3, threshold=0.95),
            ]
        )
        definition.checkpoint(label="post_dedup")
    
    if categorize:
        definition.categorization(enabled=True)
        definition.checkpoint(label="post_categorization")
    
    definition.summarize(summary=True)
    definition.export(format=export_format, output_path=output_path, overwrite=True)
    
    return definition


__all__ = [
    "Definition",
    "Step",
    "BibtexSource",
    "BibtexImportConfig",
    "DeduplicationConfig",
    "DeduplicationMethod",
    "CategorizationConfig",
    "KeywordScreeningConfig",
    "SemanticScreeningConfig",
    "CheckpointConfig",
    "EchoConfig",
    "SummarizeConfig",
    "ExportConfig",
    "HaltConfig",
    "DatabaseConfig",
    "from_yaml",
    "create_standard_pipeline",
]
