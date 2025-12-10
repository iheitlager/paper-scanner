# src/paper_scanner/core/models.py

"""
Core Pydantic models for Paper Scanner
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid

from paper_scanner.core.enum import (
    PaperType,
    StudyType,
    QualityTier,
    DiscoveryMethod,
    ScreeningDecision,
)

# ============================================================================
# PROCESSING METADATA
# ============================================================================

class ProcessingMetadata(BaseModel):
    """Metadata for any processing step"""
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_seconds: Optional[float] = None
    model_version: Optional[str] = None
    model_name: Optional[str] = None  # e.g., "claude-sonnet-4-20250514"
    api_cost: Optional[float] = None
    tokens_used: Optional[int] = None
    error: Optional[str] = None
    success: bool = True
    retry_count: int = 0
    
    model_config = ConfigDict(extra='allow')  # Allow extra fields


# ============================================================================
# AUTHOR MODEL
# ============================================================================

class Author(BaseModel):
    """Author information"""
    
    given_name: Optional[str] = None
    family_name: str
    full_name: str
    affiliation: Optional[str] = None
    orcid: Optional[str] = None
    email: Optional[str] = None
    
    @property
    def last_name(self) -> str:
        return self.family_name
    
    def __str__(self) -> str:
        return self.full_name


# ============================================================================
# EMBEDDING MODEL
# ============================================================================

class Embedding(BaseModel):
    """Vector embedding with metadata"""
    
    vector: List[float] = Field(description="Embedding vector (768 dimensions)")
    model: str = Field(default="all-mpnet-base-v2")
    text_source: str = Field(description="What was embedded: title, abstract, full_text, etc.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @field_validator('vector')
    @classmethod
    def validate_vector_length(cls, v):
        if len(v) != 768:
            raise ValueError(f"Embedding must be 768 dimensions, got {len(v)}")
        return v


# ============================================================================
# REFERENCE MODEL
# ============================================================================

class Citation(BaseModel):
    """Bibliographic reference"""

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))

    # Identifiers
    doi: Optional[str] = None
    title: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None

    # Publication details
    journal: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None

    # Extraction metadata
    extraction_method: str = Field(description="grobid, crossref, manual, etc.")
    confidence: Optional[float] = Field(ge=0, le=1, default=None)
    raw_text: Optional[str] = None

    # Linking
    resolved_paper: Optional[Paper] = None  # If citation matches known paper


# ============================================================================
# CHUNK MODEL (for full-text processing)
# ============================================================================

class TextChunk(BaseModel):
    """Chunk of paper text with embedding"""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chunk_index: int
    text: str
    section: Optional[str] = None  # "introduction", "methods", "results", etc.
    
    # Boundaries
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    
    # Embedding
    embedding: Optional[Embedding] = None
    
    # Metadata
    word_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# DEDUPLICATION MODEL
# ============================================================================

class DeduplicationResult(BaseModel):
    """Result of deduplication check"""
    
    is_duplicate: bool
    duplicate_of: Optional[Paper] = None
    similarity_score: Optional[float] = Field(ge=0, le=1, default=None)
    method: str  # "doi_exact", "title_author", "fuzzy_title", etc.
    confidence: float = Field(ge=0, le=1)
    metadata: ProcessingMetadata


# ============================================================================
# CATEGORIZATION MODEL
# ============================================================================

class Categorization(BaseModel):
    """Paper categorization results"""
    
    paper_type: PaperType
    study_type: StudyType
    quality_tier: QualityTier
    
    # Confidence scores
    paper_type_confidence: float = Field(ge=0, le=1)
    study_type_confidence: float = Field(ge=0, le=1)
    
    # Classification details
    is_empirical: bool
    is_peer_reviewed: bool
    is_open_access: bool = False
    
    # Reasoning (if LLM-based)
    reasoning: Optional[str] = None
    
    # Metadata
    metadata: ProcessingMetadata


# ============================================================================
# KEYWORD SCREENING MODEL
# ============================================================================

class KeywordScreening(BaseModel):
    """Keyword-based screening results"""
    
    passed: bool
    score: int
    
    # Matched keywords
    inclusion_keywords: List[str] = Field(default_factory=list)
    exclusion_keywords: List[str] = Field(default_factory=list)
    
    # Breakdown
    title_matches: int = 0
    abstract_matches: int = 0
    keywords_matches: int = 0
    
    # Exclusion reason
    exclusion_reason: Optional[str] = None
    
    # Metadata
    metadata: ProcessingMetadata


# ============================================================================
# SEMANTIC SCREENING MODEL
# ============================================================================

class SemanticScreening(BaseModel):
    """Semantic similarity screening results"""
    
    passed: bool
    similarity_score: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    
    # LLM decision (if borderline)
    llm_decision: Optional[ScreeningDecision] = None
    llm_confidence: Optional[float] = Field(ge=0, le=1, default=None)
    llm_reasoning: Optional[str] = None
    
    # Metadata
    metadata: ProcessingMetadata


# ============================================================================
# SCREENING MODEL (aggregates all screening steps)
# ============================================================================

class Screening(BaseModel):
    """Complete screening results"""
    
    # Stage 0: Deduplication
    deduplication: Optional[DeduplicationResult] = None
    
    # Stage 1: Categorization
    categorization: Optional[Categorization] = None
    
    # Stage 2: Keyword screening
    keyword_screening: Optional[KeywordScreening] = None
    
    # Stage 3: Semantic screening
    semantic_screening: Optional[SemanticScreening] = None
    
    # Final decision
    final_decision: ScreeningDecision = ScreeningDecision.PENDING
    final_decision_at: Optional[datetime] = None
    final_decision_by: Optional[str] = None  # "automated", "manual:user_name"
    
    # Overall metadata
    current_stage: str = "import"
    notes: Optional[str] = None


# ============================================================================
# CAMO MODEL
# ============================================================================

class CAMOStatement(BaseModel):
    """Context-Agency-Mechanism-Outcome statement"""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # CAMO components
    context: str
    agency: str
    mechanism: str
    outcome: str
    full_statement: str
    
    # Embeddings
    mechanism_embedding: Optional[Embedding] = None
    context_embedding: Optional[Embedding] = None
    
    # Clustering
    cluster_id: Optional[int] = None
    cluster_label: Optional[str] = None
    distance_to_centroid: Optional[float] = None
    is_outlier: bool = False
    
    # Additional extracted info
    innovation_type: Optional[str] = None
    it_suppliers: List[str] = Field(default_factory=list)
    regular_suppliers: List[str] = Field(default_factory=list)
    success_indicator: Optional[str] = None
    
    # Extraction metadata
    confidence: float = Field(ge=0, le=1)
    metadata: ProcessingMetadata


# ============================================================================
# CONCEPTUAL ANALYSIS MODEL
# ============================================================================

class ConceptualAnalysis(BaseModel):
    """Conceptual analysis results"""
    
    # CAMO statements
    camo_statements: List[CAMOStatement] = Field(default_factory=list)
    
    # Extracted concepts
    theoretical_frameworks: List[str] = Field(default_factory=list)
    key_constructs: List[str] = Field(default_factory=list)
    
    # Context
    industry_context: Optional[str] = None
    country_context: Optional[str] = None
    organization_type: Optional[str] = None
    
    # Innovation details
    innovation_types: List[str] = Field(default_factory=list)
    digital_technologies: List[str] = Field(default_factory=list)
    
    # Findings
    main_findings: Optional[str] = None
    contribution_type: Optional[str] = None
    
    # Metadata
    metadata: ProcessingMetadata


# ============================================================================
# DISCOVERY MODEL
# ============================================================================

class Discovery(BaseModel):
    """How paper was discovered"""
    
    method: DiscoveryMethod
    iteration: int = 0  # 0 = initial, 1+ = snowballing iterations
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    discovered_by: Optional[str] = None  # Script/user name
    
    # Source details
    source_database: Optional[str] = None  # "scopus", "wos", "crossref"
    source_query: Optional[str] = None
    
    # Import details
    import_batch_id: Optional[str] = None


# ============================================================================
# PDF INFO MODEL
# ============================================================================

class PDFInfo(BaseModel):
    """PDF file information"""
    
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_size_bytes: Optional[int] = None
    file_hash: Optional[str] = None  # SHA256
    
    # Download info
    download_source: Optional[str] = None  # "unpaywall", "openalex", etc.
    download_url: Optional[str] = None
    downloaded_at: Optional[datetime] = None
    
    # PDF metadata
    pdf_pages: Optional[int] = None
    pdf_is_scanned: Optional[bool] = None
    pdf_extraction_success: bool = False
    
    # Text extraction
    full_text: Optional[str] = None
    full_text_word_count: Optional[int] = None
    chunks: List[TextChunk] = Field(default_factory=list)
    
    # Metadata
    metadata: Optional[ProcessingMetadata] = None


# ============================================================================
# MAIN PAPER MODEL
# ============================================================================

class Paper(BaseModel):
    """
    Complete paper model - central data structure
    """

    # ========================================
    # IDENTIFIERS
    # ========================================

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    db_id: Optional[int] = None  # Database primary key

    cite_key: str  # Unique (bibtex) citation key
    source_key: Optional[str] = None  # Original ID from source

    # External identifiers
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    pmid: Optional[str] = None
    isbn: Optional[str] = None
    issn: Optional[str] = None
    url: Optional[str] = None


    # ========================================
    # DEDUPLICATION
    # ========================================

    duplicate_of: Optional[Paper] = None

    # ========================================
    # BIBLIOGRAPHIC DATA
    # ========================================

    # Core fields
    title: str
    abstract: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    authors: List[Author] = Field(default_factory=list)
    year: Optional[int] = None

    # Publication venue
    journal: Optional[str] = None
    journal_abbreviation: Optional[str] = None
    booktitle: Optional[str] = None  # For conference papers
    publisher: Optional[str] = None
    
    # Paper type from source (e.g., BibTeX entry type)
    paper_type: Optional[str] = None  # "journal_article", "conference_paper", "book", etc.

    # Volume/issue
    volume: Optional[str] = None
    number: Optional[str] = None
    pages: Optional[str] = None

    # Dates
    publication_date: Optional[datetime] = None

    # Language
    language: Optional[str] = "en"

    # ========================================
    # EMBEDDINGS
    # ========================================

    title_abstract_embedding: Optional[Embedding] = None  # Combined

    # ========================================
    # DISCOVERY
    # ========================================

    discovery: Optional[Discovery] = None

    # ========================================
    # SCREENING
    # ========================================

    screening: Screening = Field(default_factory=Screening)

    # ========================================
    # REFERENCES & CITATIONS
    # ========================================

    citations: List[Citation] = Field(default_factory=list)
    cited_by: List[str] = Field(default_factory=list)  # Paper IDs

    reference_count: int = 0
    citation_count: int = 0

    # ========================================
    # PDF & FULL TEXT
    # ========================================

    pdf_info: Optional[PDFInfo] = None

    # ========================================
    # CONCEPTUAL ANALYSIS
    # ========================================

    conceptual_analysis: Optional[ConceptualAnalysis] = None

    # ========================================
    # METADATA & TIMESTAMPS
    # ========================================

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ========================================
    # VALIDATION
    # ========================================

    manually_validated: bool = False
    validation_notes: Optional[str] = None
    validated_by: Optional[str] = None
    validated_at: Optional[datetime] = None

    # ========================================
    # RAW DATA (for audit)
    # ========================================

    raw_bibtex: Optional[str] = None
    raw_json: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        extra='forbid',  # Don't allow extra fields
        validate_assignment=True,  # Validate on attribute assignment
        str_strip_whitespace=True
    )

    # ========================================
    # COMPUTED PROPERTIES
    # ========================================

    @property
    def author_string(self) -> str:
        """Format authors as string"""
        if not self.authors:
            return "Unknown"
        if len(self.authors) == 1:
            return self.authors[0].family_name
        elif len(self.authors) == 2:
            return f"{self.authors[0].family_name} & {self.authors[1].family_name}"
        else:
            return f"{self.authors[0].family_name} et al."

    @property
    def citation_key_apa(self) -> str:
        """Generate APA-style citation key"""
        author_part = self.authors[0].family_name if self.authors else "Unknown"
        year_part = self.year or "n.d."
        return f"{author_part}, {year_part}"

    @property
    def is_processed(self) -> bool:
        """Check if paper completed all processing"""
        return (
            self.screening.final_decision != ScreeningDecision.PENDING and
            (self.pdf_info is not None if self.screening.final_decision == ScreeningDecision.INCLUDED else True)
        )

    @property
    def is_included(self) -> bool:
        """Check if paper passed screening"""
        return self.screening.final_decision == ScreeningDecision.INCLUDED

    def __str__(self) -> str:
        return f"{self.cite_key}: {self.title[:60]}... ({self.year})"


# ============================================================================
# COLLECTION/BATCH MODEL
# ============================================================================

class PaperCollection(BaseModel):
    """Collection of papers (for batch processing)"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None

    papers: List[Paper] = Field(default_factory=list)

    # Statistics
    total_count: int = 0
    included_count: int = 0
    excluded_count: int = 0
    pending_count: int = 0
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def update_statistics(self):
        """Recalculate statistics"""
        self.total_count = len(self.papers)
        self.included_count = sum(1 for p in self.papers if p.is_included)
        self.excluded_count = sum(
            1 for p in self.papers 
            if p.screening.final_decision == ScreeningDecision.EXCLUDED
        )
        self.pending_count = sum(
            1 for p in self.papers 
            if p.screening.final_decision == ScreeningDecision.PENDING
        )