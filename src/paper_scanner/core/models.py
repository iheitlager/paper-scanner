# src/paper_scanner/core/models.py

"""
Core Pydantic models for Paper Scanner
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from paper_scanner.core.enum import (
    CitationDirection,
    DiscoveryMethod,
    PaperType,
    QualityTier,
    ScreeningDecision,
    StudyType,
)

# ============================================================================
# PROCESSING METADATA
# ============================================================================

class ProcessingMetadata(BaseModel):
    """Metadata for any processing step"""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_seconds: Optional[float] = None
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

    @staticmethod
    def _apply_smart_titlecase(text: str, keep_first_word_caps: bool = True) -> str:
        """Apply title case while preserving lowercase particles (de, van, von, etc.)
        
        Also properly handles hyphenated words by titlecasing each part.
        
        Args:
            text: The text to titlecase
            keep_first_word_caps: If True, first word is always capitalized (for surnames)
        """
        if not text:
            return text
        
        # List of particles that should be lowercase when not at the start
        particles = {'de', 'van', 'von', 'der', 'den', 'el', 'la', 'le', 'di', 'da', 'du', 'the'}
        
        words = text.lower().split()
        result = []
        
        for i, word in enumerate(words):
            # Handle hyphenated words by titlecasing each part separately
            if '-' in word:
                hyphenated_parts = word.split('-')
                titlecased_parts = []
                for part in hyphenated_parts:
                    # Clean punctuation for particle checking
                    part_clean = part.rstrip('.,;:').lower()
                    # First part of hyphenated word: capitalize if first word overall, or always capitalize
                    if i == 0 or part_clean not in particles:
                        titlecased_parts.append(part.capitalize())
                    else:
                        titlecased_parts.append(part)
                result.append('-'.join(titlecased_parts))
            # First word: capitalize if requested, or if particle is first word, still capitalize it
            elif i == 0:
                result.append(word.capitalize())
            # Check if word (without punctuation) is a particle
            elif word.rstrip('.,;:').lower() in particles:
                result.append(word)
            # Regular words are title-cased
            else:
                result.append(word.capitalize())
        
        return ' '.join(result)

    @field_validator('given_name', mode='before')
    @classmethod
    def titlecase_given_name(cls, v):
        """Apply smart titlecase to given_name field"""
        if v is None:
            return None
        if isinstance(v, str):
            return cls._apply_smart_titlecase(v)
        return v

    @field_validator('family_name', mode='before')
    @classmethod
    def titlecase_family_name(cls, v):
        """Apply smart titlecase to family_name field
        
        For family names, we use a modified approach that preserves capitalization
        patterns more strictly - we capitalize each word (including particles)
        to ensure cite keys and other uses have consistent capitalization.
        """
        if v is None:
            return v
        if isinstance(v, str):
            # For family names, titlecase each word including particles
            # This is better for cite key generation and formal name use
            words = v.lower().split()
            result = []
            for word in words:
                # Handle hyphenated words
                if '-' in word:
                    parts = word.split('-')
                    result.append('-'.join(part.capitalize() for part in parts))
                else:
                    result.append(word.capitalize())
            return ' '.join(result)
        return v

    @field_validator('full_name', mode='before')
    @classmethod
    def titlecase_full_name(cls, v):
        """Apply smart titlecase to full_name field"""
        if v is None:
            return v
        if isinstance(v, str):
            return cls._apply_smart_titlecase(v)
        return v

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
    source_key: Optional[str] = None  # Original ID from source
    direction: CitationDirection

    # Identifiers
    doi: Optional[str] = None
    url: Optional[str] = None

    # Paper details
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
    raw_json: Optional[Dict[str, Any]] = None

    # Linking
    resolved: bool = False  # Whether citation was resolved to a known paper
    resolved_paper: Optional['Paper'] = None  # If citation matches known paper (computed)

    @field_validator('resolved_paper', mode='before')
    @classmethod
    def deserialize_resolved_paper(cls, v):
        """Handle deserialization of resolved_paper from ID string or dict"""
        if v is None:
            return None
        # If it's a string (ID from serialized form), skip it - will be None during checkpoint load
        if isinstance(v, str):
            return None
        # If it's a dict, it's already in the right format for Pydantic
        # If it's a Paper instance, use it directly
        return v

    @field_serializer('resolved_paper', when_used='always')
    def serialize_resolved_paper(self, value: Optional['Paper']) -> Optional[str]:
        """Convert Paper reference to ID string during serialization"""
        return value.id if value else None


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
    duplicate_of: Optional['Paper'] = None
    similarity_score: Optional[float] = Field(ge=0, le=1, default=None)
    method: str  # "doi_exact", "title_author", "fuzzy_title", etc.
    confidence: float = Field(ge=0, le=1)

    # Metadata
    metadata: Optional[ProcessingMetadata] = None

    @field_validator('duplicate_of', mode='before')
    @classmethod
    def deserialize_duplicate_of(cls, v):
        """Handle deserialization of duplicate_of from ID string or dict"""
        if v is None:
            return None
        # If it's a string (ID from serialized form), skip it - will be None during checkpoint load
        if isinstance(v, str):
            return None
        # If it's a dict or Paper instance, use it directly
        return v

    @field_serializer('duplicate_of', when_used='always')
    def serialize_duplicate_of(self, value: Optional['Paper']) -> Optional[str]:
        """Convert Paper reference to ID string during serialization"""
        return value.id if value else None


# ============================================================================
# METADATA SCREENING MODEL
# ============================================================================

class MetadataScreening(BaseModel):
    """Metadata screening results"""

    passed: bool

    paper_type: PaperType # Mandatory, importers should know
    language: Optional[str] = "en"  # ISO language code
    quality_tier: Optional[QualityTier] = QualityTier.UNKNOWN

    is_peer_reviewed: bool

    # Reasoning
    exclusion_reason: Optional[str] = None

    # Metadata
    metadata: Optional[ProcessingMetadata] = None

# ============================================================================
# KEYWORD SCREENING MODEL
# ============================================================================

class KeywordScreening(BaseModel):
    """Keyword-based screening results"""

    passed: bool

    study_type: Optional[StudyType] = StudyType.UNKNOWN

    # Matched keywords
    inclusion_keywords: List[str] = Field(default_factory=list)
    inclusion_threshold: Optional[int] = None  # Number of keywords that had to match
    exclusion_keywords: List[str] = Field(default_factory=list)

    # Classification details
    is_empirical: bool
    is_conceptual: bool
    is_literature_review: bool

    # Confidence scores
    keyword_screening_confidence: float = Field(ge=0, le=1)

    # Exclusion reason
    exclusion_reason: Optional[str] = None
    inclusion_reason: Optional[str] = None

    # Metadata
    metadata: Optional[ProcessingMetadata] = None

# ============================================================================
# SEMANTIC SCREENING MODEL
# ============================================================================

class SemanticScreening(BaseModel):
    """Semantic similarity screening results"""

    passed: bool

    similarity_score: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)

    # LLM decision (if applied)
    llm_decision: Optional[ScreeningDecision] = None
    llm_confidence: Optional[float] = Field(ge=0, le=1, default=None)

    exclusion_reason: Optional[str] = None

    # Metadata
    metadata: Optional[ProcessingMetadata] = None

# ============================================================================
# FULL PAPER  SCREENING MODEL
# ============================================================================

class FullPaperScreening(BaseModel):
    """Full paper screening results"""

    similarity_score: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)

    manual_decision: Optional[ScreeningDecision] = None
    # LLM decision
    llm_decision: Optional[ScreeningDecision] = None
    llm_confidence: Optional[float] = Field(ge=0, le=1, default=None)

    inclusion_reason: Optional[str] = None
    exclusion_reason: Optional[str] = None

    # Metadata
    metadata: Optional[ProcessingMetadata] = None

# ============================================================================
# SCREENING MODEL (aggregates all screening steps)
# ============================================================================

class Screening(BaseModel):
    """Complete screening results"""

    # Stage 0: Deduplication
    deduplication: Optional[DeduplicationResult] = None

    # Stage 1: Metadata screening
    metadata_screening: Optional[MetadataScreening] = None

    # Stage 2: Keyword screening
    keyword_screening: Optional[KeywordScreening] = None

    # Stage 3: Semantic screening
    semantic_screening: Optional[SemanticScreening] = None

    # Stage 4: Full paper screening (not excluded stages 0-3 means full paper review)
    full_paper_screening: Optional[FullPaperScreening] = None

    # Final decision (for further processing)
    final_decision: ScreeningDecision = ScreeningDecision.PENDING
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
    metadata: Optional[ProcessingMetadata] = None


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
    metadata: Optional[ProcessingMetadata] = None


# ============================================================================
# DISCOVERY MODEL
# ============================================================================

class Discovery(BaseModel):
    """How paper was discovered"""
    method: DiscoveryMethod = DiscoveryMethod.MANUAL
    iteration: int = 0  # 0 = initial, 1+ = snowballing iterations
    source_database: Optional[str] = None  # "scopus", "wos", "crossref"

# ============================================================================
# OPEN ACCESS STATUS MODEL
# ============================================================================

class OpenAccessStatus(BaseModel):
    """Open access availability details"""

    is_oa: bool  # Main flag: paper is openly accessible
    oa_status: Optional[str] = None  # "gold", "green", "bronze", "closed" (Unpaywall standard)
    oa_url: Optional[str] = None  # Direct link to free version
    version: Optional[str] = None  # "submittedVersion", "acceptedVersion", "publishedVersion"
    license: Optional[str] = None  # License type (CC-BY, etc.)
    host_type: Optional[str] = None  # "publisher", "repository"
    source: Optional[str] = None  # Which service found it (unpaywall, openalex, etc.)
    verified_at: Optional[datetime] = None


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

    # Open access
    oa_status: Optional[OpenAccessStatus] = None

    # ========================================
    # DEDUPLICATION
    # ========================================

    duplicate_of: Optional['Paper'] = None

    @field_validator('duplicate_of', mode='before')
    @classmethod
    def deserialize_duplicate_of_paper(cls, v):
        """Handle deserialization of duplicate_of from ID string or dict"""
        if v is None:
            return None
        # If it's a string (ID from serialized form), skip it - will be None during checkpoint load
        if isinstance(v, str):
            return None
        # If it's a dict or Paper instance, use it directly
        return v

    @field_serializer('duplicate_of', when_used='always')
    def serialize_duplicate_of_paper(self, value: Optional['Paper']) -> Optional[str]:
        """Convert Paper reference to ID string during serialization"""
        return value.id if value else None

    # ========================================
    # BIBLIOGRAPHIC DATA
    # ========================================

    # Core fields
    title: Optional[str] = None
    abstract: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    authors: List[Author] = Field(default_factory=list)
    year: Optional[int] = None

    # Publication venue
    journal: Optional[str] = None
    journal_acronym: Optional[str] = None
    journal_iso4: Optional[str] = None
    booktitle: Optional[str] = None  # For conference papers
    publisher: Optional[str] = None

    # Paper type from source (e.g., BibTeX entry type)
    paper_type: Optional[PaperType] = None  # "journal_article", "conference_paper", "book", etc.

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

    discovery: Discovery = Field(default_factory=Discovery)

    # ========================================
    # SCREENING
    # ========================================

    screening: Screening = Field(default_factory=Screening)

    # ========================================
    # REFERENCES & CITATIONS
    # ========================================

    citations: List[Citation] = Field(default_factory=list)
    cited_by: List[Citation] = Field(default_factory=list)
    cited_papers: List['Paper'] = Field(default_factory=list)
    cited_by_papers: List['Paper'] = Field(default_factory=list)

    @field_validator('cited_papers', mode='before')
    @classmethod
    def deserialize_cited_papers(cls, v):
        """Handle deserialization of cited_papers from ID strings or dicts"""
        if not v:
            return []
        # Convert any string IDs to None (can't resolve without DB context)
        result = []
        for item in v:
            if isinstance(item, str):
                # Skip ID strings - can't recreate Paper object
                continue
            # Keep dicts and Paper instances
            result.append(item)
        return result

    @field_serializer('cited_papers', when_used='always')
    def serialize_cited_papers(self, value: List['Paper']) -> List[str]:
        """Convert Paper references to ID strings during serialization"""
        return [paper.id for paper in value] if value else []

    @field_validator('cited_by_papers', mode='before')
    @classmethod
    def deserialize_cited_by_papers(cls, v):
        """Handle deserialization of cited_by_papers from ID strings or dicts"""
        if not v:
            return []
        # Convert any string IDs to None (can't resolve without DB context)
        result = []
        for item in v:
            if isinstance(item, str):
                # Skip ID strings - can't recreate Paper object
                continue
            # Keep dicts and Paper instances
            result.append(item)
        return result

    @field_serializer('cited_by_papers', when_used='always')
    def serialize_cited_by_papers(self, value: List['Paper']) -> List[str]:
        """Convert Paper references to ID strings during serialization"""
        return [paper.id for paper in value] if value else []

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
    def is_processed(self) -> bool:
        """Check if paper completed all processing"""
        return (
            self.screening.final_decision != ScreeningDecision.PENDING and
            (self.pdf_info is not None if self.is_included else True)
        )

    @property
    def is_included(self) -> bool:
        """Check if paper passed screening"""
        return self.screening.final_decision in (ScreeningDecision.INCLUDED, ScreeningDecision.INCLUDED_MANUAL)

    @property
    def is_excluded(self) -> bool:
        """Check if paper was excluded"""
        return self.screening.final_decision in (ScreeningDecision.EXCLUDED, ScreeningDecision.EXCLUDED_DUPLICATE, ScreeningDecision.EXCLUDED_MANUAL)

    @property
    def calculated_quality_score(self) -> float:
        """Calculated bibliographic quality"""
        base = 0.20
        if self.title:
            base += 0.20
        if self.keywords:
            base += 0.25
        if self.abstract:
            base += 0.25
        return min(base, 1.0)

    @property
    def apa(self) -> str:
        """Format paper as APA citation"""
        # Format authors
        if self.authors:
            author_names = [author.full_name for author in self.authors]
            if len(author_names) > 3:
                authors_str = f"{author_names[0]} et al."
            else:
                authors_str = " & ".join(author_names)
        else:
            authors_str = "Unknown Authors"

        # Build APA citation
        citation = f"{authors_str} ({self.year}). {self.title}."

        if self.journal:
            citation += f" {self.journal}"
            if self.volume:
                citation += f", {self.volume}"
                if self.number:
                    citation += f"({self.number})"
            if self.pages:
                citation += f", {self.pages}"

        citation += "."

        if self.doi:
            citation += f" https://doi.org/{self.doi}"

        return citation


    # =============
    # Magic Methods
    # =============

    def __str__(self) -> str:
        title_preview = self.title[:40] + "..." if self.title and len(self.title) > 40 else self.title or "N/A"
        return f"{self.cite_key}: {title_preview} ({self.year})"

    def __repr__(self) -> str:
        """Simplified repr to avoid infinite recursion with circular references"""
        title_preview = self.title[:40] + "..." if self.title and len(self.title) > 40 else self.title or "N/A"
        return f"Paper(id={self.id!r}, cite_key={self.cite_key!r}, title={title_preview!r}, year={self.year})"
