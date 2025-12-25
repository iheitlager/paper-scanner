-- Initialize PostgreSQL database for PDF browser
-- This script runs automatically when the postgres container starts

-- Connect to the correct database
\connect pdfdb

-- Enable pgvector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- MAIN PAPERS TABLE (Aligned with Pydantic Paper model)
-- ============================================================================
--
-- Key design decisions:
-- - id (UUID as VARCHAR): Unique identifier from Python/Pydantic
-- - db_id (SERIAL): PostgreSQL auto-increment primary key (for join efficiency)
-- - cite_key (VARCHAR UNIQUE): Global unique citation key (bibtex style)
-- - doi (VARCHAR): Optional, allows multiple papers with different DOIs or duplicates
-- - source_key (VARCHAR): Original ID from discovery source
-- - authors (JSONB): Full Author objects with given_name, family_name, affiliation, orcid
-- - keywords, topics (TEXT[]): List fields as PostgreSQL arrays
-- - abstract (TEXT): Long text field
-- - discovery (JSONB): Complete Discovery object (method, source_database)
-- - screening (JSONB): Complete Screening object (all stages)
-- - pdf_info (JSONB): PDFInfo object (file path, hash, download metadata)
-- - conceptual_analysis (JSONB): ConceptualAnalysis object
-- ============================================================================

CREATE TABLE IF NOT EXISTS papers (
    -- ========================================
    -- PRIMARY KEYS & IDENTIFIERS
    -- ========================================
    db_id SERIAL PRIMARY KEY,  -- PostgreSQL auto-increment PK for efficiency
    id VARCHAR(36) UNIQUE NOT NULL,  -- UUID from Paper model (Python unique identifier)
    cite_key VARCHAR(255) UNIQUE NOT NULL,  -- Bibtex-style cite key (globally unique)
    source_key VARCHAR(255),  -- Original ID from discovery source
    
    -- External identifiers
    doi VARCHAR(255),  -- DOI (can have duplicates if papers share DOI)
    arxiv_id VARCHAR(100),
    pmid VARCHAR(50),
    isbn VARCHAR(50),
    issn VARCHAR(50),
    url TEXT,
    
    -- ========================================
    -- BIBLIOGRAPHIC DATA (from Pydantic model)
    -- ========================================
    title VARCHAR(1000),
    abstract TEXT,  -- Long text
    authors JSONB,  -- [{given_name, family_name, full_name, affiliation, orcid, email}]
    keywords TEXT[],  -- Array of keywords
    topics TEXT[],  -- Array of topic tags
    year INTEGER,
    journal VARCHAR(500),
    journal _acronym VARCHAR(100),
    journal_iso4 VARCHAR(255),
    booktitle VARCHAR(500),  -- For conference papers
    publisher VARCHAR(255),
    volume VARCHAR(50),
    issue VARCHAR(100),
    pages VARCHAR(100),
    paper_type VARCHAR(50),  -- 'journal_article', 'conference_paper', 'book', etc.
    language VARCHAR(10) DEFAULT 'en',
    publication_date TIMESTAMP,
    
    -- ========================================
    -- DISCOVERY & IMPORT METADATA
    -- ========================================
    discovery JSONB,  -- {method, iteration, source_database discovered_at, record_update}
    
    -- ========================================
    -- SCREENING & DECISION DATA
    -- ========================================
    screening JSONB,  -- {current_stage, final_decision, final_decision_at, ...all stages...}
    processing_status VARCHAR(50) DEFAULT 'pending',

    -- ========================================
    -- PDF & FILE INFO
    -- ========================================
    pdf_info JSONB,  -- {file_path, file_name, file_size_bytes, file_hash, download_source, download_url, downloaded_at}
    
    file_path VARCHAR(500),
    file_name VARCHAR(255),
    size_bytes BIGINT,
    created_time TIMESTAMP,

    -- ========================================
    -- ANALYSIS DATA
    -- ========================================
    conceptual_analysis JSONB,  -- {camo_statements, theoretical_frameworks, key_constructs, ...}
    
    -- ========================================
    -- VALIDATION & AUDIT
    -- ========================================
    manually_validated BOOLEAN DEFAULT FALSE,
    validation_notes TEXT,
    validated_by VARCHAR(255),
    validated_at TIMESTAMP,
    raw_bibtex TEXT,
    raw_json JSONB,

    tags TEXT,

    -- ========================================
    -- TIMESTAMPS
    -- ========================================
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP    
);

-- ========================================
-- INDEXES (Optimized for common queries)
-- ========================================

-- Unique constraints
CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_id ON papers(id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_cite_key ON papers(cite_key);

-- Lookups by identifier
CREATE INDEX IF NOT EXISTS idx_papers_source_key ON papers(source_key);
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_arxiv_id ON papers(arxiv_id);

-- Bibliographic lookups
CREATE INDEX IF NOT EXISTS idx_papers_title ON papers(title);
CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year);
CREATE INDEX IF NOT EXISTS idx_papers_journal ON papers(journal);
CREATE INDEX IF NOT EXISTS idx_papers_paper_type ON papers(paper_type);

-- JSONB indexes
CREATE INDEX IF NOT EXISTS idx_papers_authors_gin ON papers USING gin(authors);
CREATE INDEX IF NOT EXISTS idx_papers_keywords_gin ON papers USING gin(keywords);
CREATE INDEX IF NOT EXISTS idx_papers_topics_gin ON papers USING gin(topics);
CREATE INDEX IF NOT EXISTS idx_papers_discovery_gin ON papers USING gin(discovery);
CREATE INDEX IF NOT EXISTS idx_papers_screening_gin ON papers USING gin(screening);

-- Full-text search
CREATE INDEX IF NOT EXISTS idx_papers_title_fts ON papers 
    USING gin(to_tsvector('english', COALESCE(title, '')));
CREATE INDEX IF NOT EXISTS idx_papers_abstract_fts ON papers 
    USING gin(to_tsvector('english', COALESCE(abstract, '')));

-- Timestamps
CREATE INDEX IF NOT EXISTS idx_papers_created_at ON papers(created_at);
CREATE INDEX IF NOT EXISTS idx_papers_updated_at ON papers(updated_at);

-- Legacy indexes
CREATE INDEX IF NOT EXISTS idx_file_name ON papers(file_name);
CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(processing_status);

-- ============================================================================
-- PAPER SCREENING TABLE (Multi-stage screening workflow)
-- ============================================================================

CREATE TABLE IF NOT EXISTS paper_screening (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(db_id) ON DELETE CASCADE,
    
    -- Current screening status
    screening_stage VARCHAR(50) NOT NULL DEFAULT 'unscreened',
    screening_stage_updated_at TIMESTAMP,

    -- ========================================
    -- STAGE 0: Article types
    -- ========================================
    stage0_processed_at TIMESTAMP,
    stage0_exclusion_reason VARCHAR(255),
    kept_paper_id VARCHAR(36),

    -- ========================================
    -- STAGE 1: Coarse Filter (Rule-based)
    -- ========================================
    stage1_processed_at TIMESTAMP,
    stage1_score INTEGER,
    stage1_exclusion_reason VARCHAR(255),
    stage1_matched_keywords TEXT[],
    stage1_excluded_keywords TEXT[],
    
    -- ========================================
    -- STAGE 2: Semantic Filter (Embedding-based)
    -- ========================================
    stage2_processed_at TIMESTAMP,
    semantic_similarity DECIMAL(5,4) CHECK (semantic_similarity BETWEEN 0 AND 1),
    stage2_exclusion_reason VARCHAR(255),
    semantic_embedding vector(768),
    
    -- ========================================
    -- STAGE 3: LLM Classification
    -- ========================================
    stage3_processed_at TIMESTAMP,
    llm_decision VARCHAR(50),
    llm_confidence DECIMAL(3,2) CHECK (llm_confidence BETWEEN 0 AND 1),
    llm_reasoning TEXT,
    llm_model_version VARCHAR(100),
    llm_tokens_used INTEGER,
    
    -- ========================================
    -- STAGE 4: Cluster Validation
    -- ========================================
    stage4_processed_at TIMESTAMP,
    cluster_id INTEGER,
    cluster_confidence DECIMAL(3,2),
    distance_to_centroid DECIMAL(5,4),
    is_outlier BOOLEAN DEFAULT FALSE,
    outlier_review_required BOOLEAN DEFAULT FALSE,
    
    -- ========================================
    -- FINAL DECISION
    -- ========================================
    final_decision VARCHAR(50),
    final_decision_method VARCHAR(50),
    final_decision_by VARCHAR(100),
    final_decision_at TIMESTAMP,
    
    exclusion_reason TEXT,
    inclusion_justification TEXT,
    reviewer_notes TEXT,
    
    needs_manual_review BOOLEAN DEFAULT FALSE,
    manual_review_reason TEXT,
    manual_review_priority INTEGER CHECK (manual_review_priority BETWEEN 1 AND 5),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(paper_id)
);

CREATE INDEX IF NOT EXISTS idx_screening_paper ON paper_screening(paper_id);
CREATE INDEX IF NOT EXISTS idx_screening_stage ON paper_screening(screening_stage);
CREATE INDEX IF NOT EXISTS idx_screening_final_decision ON paper_screening(final_decision);

-- ============================================================================
-- CITATION EDGES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS citation_edges (
    id SERIAL PRIMARY KEY,
    citing_paper_id INTEGER NOT NULL REFERENCES papers(db_id) ON DELETE CASCADE,
    cited_paper_id INTEGER REFERENCES papers(db_id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(citing_paper_id, cited_paper_id)
);

CREATE INDEX IF NOT EXISTS idx_citation_edges_citing ON citation_edges(citing_paper_id);
CREATE INDEX IF NOT EXISTS idx_citation_edges_cited ON citation_edges(cited_paper_id);
CREATE INDEX IF NOT EXISTS idx_citation_edges_pair ON citation_edges(citing_paper_id, cited_paper_id);

-- ============================================================================
-- PAPER ANALYSIS TABLE (Deep analysis results)
-- ============================================================================

CREATE TABLE IF NOT EXISTS paper_analysis (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(db_id) ON DELETE CASCADE,
    
    analysis_version INTEGER DEFAULT 1,
    model_used VARCHAR(100),
    
    summary TEXT,
    summary_structured JSONB,
    
    research_question TEXT,
    research_questions JSONB,
    
    methodology JSONB,
    key_findings JSONB,
    results JSONB,
    
    theoretical_frameworks JSONB,
    key_concepts JSONB,
    
    implications JSONB,
    contributions TEXT,
    limitations JSONB,
    future_research JSONB,
    
    full_analysis JSONB,
    
    analysis_confidence DECIMAL(3,2),
    extraction_notes TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(paper_id, analysis_version)
);

CREATE INDEX IF NOT EXISTS idx_analysis_paper ON paper_analysis(paper_id);
CREATE INDEX IF NOT EXISTS idx_analysis_version ON paper_analysis(paper_id, analysis_version);
CREATE INDEX IF NOT EXISTS idx_analysis_model ON paper_analysis(model_used);
CREATE INDEX IF NOT EXISTS idx_analysis_summary_fts ON paper_analysis 
    USING gin(to_tsvector('english', COALESCE(summary, '')));

-- ============================================================================
-- PAPER CHUNKS TABLE (For chunking strategy)
-- ============================================================================

CREATE TABLE IF NOT EXISTS paper_chunks (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(db_id) ON DELETE CASCADE,
    
    chunk_index INTEGER NOT NULL,
    chunk_type VARCHAR(50),
    
    content TEXT NOT NULL,
    content_length INTEGER,
    token_count INTEGER,
    
    section_title TEXT,
    page_numbers INTEGER[],
    line_start INTEGER,
    line_end INTEGER,
    
    chunking_strategy VARCHAR(50),
    chunk_size_target INTEGER,
    overlap_size INTEGER,
    
    metadata JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(paper_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_paper ON paper_chunks(paper_id);
CREATE INDEX IF NOT EXISTS idx_chunks_type ON paper_chunks(chunk_type);
CREATE INDEX IF NOT EXISTS idx_chunks_section ON paper_chunks(section_title);
CREATE INDEX IF NOT EXISTS idx_chunks_content_fts ON paper_chunks 
    USING gin(to_tsvector('english', content));

-- ============================================================================
-- EMBEDDINGS TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS chunk_embeddings (
    id SERIAL PRIMARY KEY,
    chunk_id INTEGER NOT NULL REFERENCES paper_chunks(id) ON DELETE CASCADE,
    
    embedding vector(768),
    
    model_name VARCHAR(100) NOT NULL,
    model_dimension INTEGER NOT NULL,
    embedding_version INTEGER DEFAULT 1,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(chunk_id, model_name, embedding_version)
);

CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_vector 
    ON chunk_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_chunk ON chunk_embeddings(chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_model ON chunk_embeddings(model_name);

CREATE TABLE IF NOT EXISTS paper_embeddings (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(db_id) ON DELETE CASCADE,
    
    embedding vector(768),
    
    embedding_method VARCHAR(50),
    model_name VARCHAR(100) NOT NULL,
    model_dimension INTEGER NOT NULL,
    embedding_version INTEGER DEFAULT 1,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(paper_id, model_name, embedding_method, embedding_version)
);

CREATE INDEX IF NOT EXISTS idx_paper_embeddings_vector 
    ON paper_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_paper_embeddings_paper ON paper_embeddings(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_embeddings_model ON paper_embeddings(model_name);

-- ============================================================================
-- UTILITY TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    tag_name VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS paper_tags (
    paper_id INTEGER NOT NULL REFERENCES papers(db_id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (paper_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_tags_paper ON paper_tags(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_tags_tag ON paper_tags(tag_id);

CREATE TABLE IF NOT EXISTS processing_logs (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER REFERENCES papers(db_id) ON DELETE CASCADE,
    
    stage VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    
    message TEXT,
    error_details TEXT,
    
    duration_seconds DECIMAL(10,2),
    tokens_used INTEGER,
    cost_usd DECIMAL(10,4),
    
    model_used VARCHAR(100),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_processing_logs_paper ON processing_logs(paper_id);
CREATE INDEX IF NOT EXISTS idx_processing_logs_stage ON processing_logs(stage);
CREATE INDEX IF NOT EXISTS idx_processing_logs_status ON processing_logs(status);
CREATE INDEX IF NOT EXISTS idx_processing_logs_created ON processing_logs(created_at);

CREATE TABLE IF NOT EXISTS paper_clusters (
    id SERIAL PRIMARY KEY,
    cluster_name VARCHAR(255),
    cluster_description TEXT,
    
    clustering_method VARCHAR(50),
    clustering_parameters JSONB,
    
    paper_count INTEGER,
    avg_year DECIMAL(6,2),
    top_keywords TEXT[],
    
    centroid_embedding vector(768),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS paper_cluster_assignments (
    paper_id INTEGER NOT NULL REFERENCES papers(db_id) ON DELETE CASCADE,
    cluster_id INTEGER NOT NULL REFERENCES paper_clusters(id) ON DELETE CASCADE,
    
    distance_to_centroid DECIMAL(10,6),
    assignment_confidence DECIMAL(3,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (paper_id, cluster_id)
);

CREATE INDEX IF NOT EXISTS idx_cluster_assignments_paper ON paper_cluster_assignments(paper_id);
CREATE INDEX IF NOT EXISTS idx_cluster_assignments_cluster ON paper_cluster_assignments(cluster_id);

-- ============================================================================
-- VIEWS
-- ============================================================================

CREATE OR REPLACE VIEW papers_with_citations AS
SELECT 
    p.*,
    COUNT(DISTINCT ce.id) as citation_count
FROM papers p
LEFT JOIN citation_edges ce ON p.db_id = ce.cited_paper_id
GROUP BY p.db_id;

CREATE OR REPLACE VIEW processing_status_overview AS
SELECT 
    processing_status,
    COUNT(*) as paper_count
FROM papers
GROUP BY processing_status;

CREATE OR REPLACE VIEW most_cited_papers AS
SELECT 
    p.db_id,
    p.id,
    p.cite_key,
    p.title,
    p.year,
    p.authors,
    COUNT(ce.id) as times_cited
FROM papers p
JOIN citation_edges ce ON p.db_id = ce.cited_paper_id
GROUP BY p.db_id, p.id, p.cite_key, p.title, p.year, p.authors
ORDER BY times_cited DESC;

CREATE OR REPLACE VIEW papers_by_year AS
SELECT 
    year,
    COUNT(*) as paper_count,
    COUNT(CASE WHEN processing_status = 'complete' THEN 1 END) as complete_count
FROM papers
WHERE year IS NOT NULL
GROUP BY year
ORDER BY year DESC;

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_papers_updated_at ON papers;
CREATE TRIGGER trigger_papers_updated_at
    BEFORE UPDATE ON papers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_analysis_updated_at ON paper_analysis;
CREATE TRIGGER trigger_analysis_updated_at
    BEFORE UPDATE ON paper_analysis
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_screening_updated_at ON paper_screening;
CREATE TRIGGER trigger_screening_updated_at
    BEFORE UPDATE ON paper_screening
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- PERMISSIONS
-- ============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO pdfuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO pdfuser;
GRANT USAGE ON SCHEMA public TO pdfuser;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO pdfuser;

-- ============================================================================
-- INITIALIZATION COMPLETE
-- ============================================================================

SELECT 'PostgreSQL database initialized successfully (v3.1.0+)' as status;
SELECT 'Main papers table aligned with Pydantic Paper model' as summary;
SELECT 'Multi-stage screening, analysis, chunks, embeddings, and clustering support enabled' as features;