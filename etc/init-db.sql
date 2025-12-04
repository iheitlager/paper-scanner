-- Initialize PostgreSQL database for PDF browser
-- This script runs automatically when the postgres container starts

-- Connect to the correct database
\connect pdfdb

-- Enable pgvector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- MAIN TABLE: pdf_files (EXTENDED - keeping all original fields)
-- ============================================================================

CREATE TABLE IF NOT EXISTS pdf_files (
    id SERIAL PRIMARY KEY,
    
    -- ========================================
    -- ORIGINAL FIELDS (unchanged)
    -- ========================================
    file_path VARCHAR(500) UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    directory VARCHAR(500) NOT NULL,
    -- relative_path VARCHAR(500) NOT NULL,
    size_bytes BIGINT,
    created_time TIMESTAMP,
    modified_time TIMESTAMP,
    accessed_time TIMESTAMP,
    tags TEXT,
    title VARCHAR(500),
    citekey VARCHAR(100),
    year INTEGER,
    title_details JSONB,
    analysis JSONB,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- ========================================
    -- NEW FIELDS - Stage 1: Enhanced Metadata
    -- ========================================
    authors JSONB,  -- NEW: [{last_name, first_name, initials, order}]
    journal VARCHAR(500),  -- NEW
    volume VARCHAR(50),  -- NEW
    issue VARCHAR(50),  -- NEW
    pages VARCHAR(100),  -- NEW
    doi VARCHAR(255),  -- NEW
    publisher VARCHAR(255),  -- NEW
    abstract TEXT,  -- NEW
    keywords TEXT[],  -- NEW
    paper_type VARCHAR(50),  -- NEW: 'journal_article', 'conference_paper', etc.
    
    -- ========================================
    -- NEW FIELDS - Processing Status Tracking
    -- ========================================
    processing_status VARCHAR(50) DEFAULT 'pending',  -- NEW: 'pending', 'metadata_extracted', 'references_extracted', 'analyzed', 'embedded', 'complete', 'error'
    metadata_extracted_at TIMESTAMP,  -- NEW
    references_extracted_at TIMESTAMP,  -- NEW
    analysis_completed_at TIMESTAMP,  -- NEW
    embedding_completed_at TIMESTAMP,  -- NEW
    
    -- ========================================
    -- NEW FIELDS - Error Tracking
    -- ========================================
    last_error TEXT,  -- NEW
    error_count INTEGER DEFAULT 0,  -- NEW
    
    -- ========================================
    -- NEW FIELDS - Timestamps
    -- ========================================
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- NEW
);

-- Original indexes
CREATE INDEX IF NOT EXISTS idx_file_name ON pdf_files(file_name);
CREATE INDEX IF NOT EXISTS idx_directory ON pdf_files(directory);
CREATE INDEX IF NOT EXISTS idx_tags ON pdf_files(tags);
CREATE INDEX IF NOT EXISTS idx_title ON pdf_files(title);
CREATE INDEX IF NOT EXISTS idx_citekey ON pdf_files(citekey);
CREATE INDEX IF NOT EXISTS idx_year ON pdf_files(year);

-- NEW indexes
CREATE INDEX IF NOT EXISTS idx_pdf_files_journal ON pdf_files(journal);
CREATE INDEX IF NOT EXISTS idx_pdf_files_doi ON pdf_files(doi);
CREATE INDEX IF NOT EXISTS idx_pdf_files_status ON pdf_files(processing_status);
CREATE INDEX IF NOT EXISTS idx_pdf_files_paper_type ON pdf_files(paper_type);
CREATE INDEX IF NOT EXISTS idx_pdf_files_authors_gin ON pdf_files USING gin(authors);
CREATE INDEX IF NOT EXISTS idx_pdf_files_keywords ON pdf_files USING gin(keywords);

-- NEW full-text search indexes
CREATE INDEX IF NOT EXISTS idx_pdf_files_title_fts ON pdf_files USING gin(to_tsvector('english', COALESCE(title, '')));
CREATE INDEX IF NOT EXISTS idx_pdf_files_abstract_fts ON pdf_files USING gin(to_tsvector('english', COALESCE(abstract, '')));

-- ============================================================================
-- STAGE 2: REFERENCES (Enhanced from original)
-- ============================================================================

CREATE TABLE IF NOT EXISTS "references" (
    id SERIAL PRIMARY KEY,
    
    -- ========================================
    -- ORIGINAL FIELDS (unchanged)
    -- ========================================
    source_paper_id INTEGER NOT NULL REFERENCES pdf_files(id) ON DELETE CASCADE,
    citekey VARCHAR(255) NOT NULL,
    reference_type VARCHAR(100),
    authors JSONB,
    year VARCHAR(50),
    title TEXT,
    source_type VARCHAR(100),
    source_name TEXT,
    volume VARCHAR(50),
    issue VARCHAR(50),
    pages_start VARCHAR(50),
    pages_end VARCHAR(50),
    pages_range VARCHAR(100),
    publisher TEXT,
    location VARCHAR(255),
    doi VARCHAR(255),
    url TEXT,
    arxiv_id VARCHAR(100),
    ssrn_id VARCHAR(100),
    isbn VARCHAR(50),
    raw_citation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- ========================================
    -- NEW FIELDS
    -- ========================================
    reference_order INTEGER,  -- NEW: Order in original paper's reference list
    editors JSONB,  -- NEW: For book chapters
    edition VARCHAR(50),  -- NEW
    links_to_paper_id INTEGER REFERENCES pdf_files(id),  -- NEW: Links to papers in our DB
    parsing_quality VARCHAR(50) DEFAULT 'success',  -- NEW: 'success', 'partial', 'failed'
    parsing_issues TEXT,  -- NEW
    confidence_score DECIMAL(3,2),  -- NEW: 0.00 to 1.00
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- NEW
);

-- Original indexes
CREATE INDEX IF NOT EXISTS idx_references_source_paper ON "references"(source_paper_id);
CREATE INDEX IF NOT EXISTS idx_references_citekey ON "references"(citekey);

-- NEW indexes
CREATE INDEX IF NOT EXISTS idx_references_doi ON "references"(doi);
CREATE INDEX IF NOT EXISTS idx_references_year ON "references"(year);
CREATE INDEX IF NOT EXISTS idx_references_type ON "references"(reference_type);
CREATE INDEX IF NOT EXISTS idx_references_links_to ON "references"(links_to_paper_id);
CREATE INDEX IF NOT EXISTS idx_references_authors_gin ON "references" USING gin(authors);
CREATE INDEX IF NOT EXISTS idx_references_title_fts ON "references" USING gin(to_tsvector('english', COALESCE(title, '')));

-- ============================================================================
-- CITATION NETWORK (Enhanced from original)
-- ============================================================================

CREATE TABLE IF NOT EXISTS citation_edges (
    id SERIAL PRIMARY KEY,
    
    -- ========================================
    -- ORIGINAL FIELDS (unchanged)
    -- ========================================
    citing_paper_id INTEGER NOT NULL REFERENCES pdf_files(id) ON DELETE CASCADE,
    cited_reference_id INTEGER NOT NULL REFERENCES "references"(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- ========================================
    -- NEW FIELDS
    -- ========================================
    cited_paper_id INTEGER REFERENCES pdf_files(id) ON DELETE SET NULL,  -- NEW: If we have both papers in DB
    citation_context TEXT,  -- NEW: The sentence/paragraph where citation appears
    
    UNIQUE(citing_paper_id, cited_reference_id)
);

-- Original indexes
CREATE INDEX IF NOT EXISTS idx_citation_edges_citing ON citation_edges(citing_paper_id);
CREATE INDEX IF NOT EXISTS idx_citation_edges_cited ON citation_edges(cited_reference_id);
CREATE INDEX IF NOT EXISTS idx_citation_edges_pair ON citation_edges(citing_paper_id, cited_reference_id);

-- NEW indexes
CREATE INDEX IF NOT EXISTS idx_citation_edges_cited_paper ON citation_edges(cited_paper_id);

-- Drop the old citation_metadata table if it exists (replaced by fields in references)
DROP TABLE IF EXISTS citation_metadata;

-- ============================================================================
-- STAGE 3: DEEP ANALYSIS (NEW TABLE)
-- ============================================================================

CREATE TABLE IF NOT EXISTS paper_analysis (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES pdf_files(id) ON DELETE CASCADE,
    
    -- Analysis version (in case you reprocess with better LLM)
    analysis_version INTEGER DEFAULT 1,
    model_used VARCHAR(100), -- e.g., 'claude-sonnet-4.5', 'gpt-4'
    
    -- Deep analysis fields (JSONB for flexibility)
    summary TEXT,
    summary_structured JSONB, -- {paragraph_1, paragraph_2}
    
    research_question TEXT,
    research_questions JSONB, -- Array if multiple
    
    methodology JSONB, -- {description, empirical_base, methodology_class, data_collection, analytical_approach}
    
    key_findings JSONB, -- Array of main findings
    
    results JSONB, -- {key_findings, conclusion, limitations}
    
    theoretical_frameworks JSONB, -- Array of frameworks used
    
    key_concepts JSONB, -- [{term, definition}]
    
    implications JSONB, -- {theoretical, practical, policy}
    
    contributions TEXT,
    
    limitations JSONB, -- Array of limitations
    
    future_research JSONB, -- Array of future research directions
    
    -- Full analysis blob (keep everything)
    full_analysis JSONB,
    
    -- Quality indicators
    analysis_confidence DECIMAL(3,2),
    extraction_notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(paper_id, analysis_version)
);

CREATE INDEX IF NOT EXISTS idx_analysis_paper ON paper_analysis(paper_id);
CREATE INDEX IF NOT EXISTS idx_analysis_version ON paper_analysis(paper_id, analysis_version);
CREATE INDEX IF NOT EXISTS idx_analysis_model ON paper_analysis(model_used);

-- Full-text search on analysis fields
CREATE INDEX IF NOT EXISTS idx_analysis_summary_fts ON paper_analysis USING gin(to_tsvector('english', COALESCE(summary, '')));
CREATE INDEX IF NOT EXISTS idx_analysis_findings_fts ON paper_analysis USING gin(to_tsvector('english', COALESCE(key_findings::text, '')));

-- ============================================================================
-- STAGE 4: CHUNKS (NEW TABLE)
-- ============================================================================

CREATE TABLE IF NOT EXISTS paper_chunks (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES pdf_files(id) ON DELETE CASCADE,
    
    -- Chunk identification
    chunk_index INTEGER NOT NULL,
    chunk_type VARCHAR(50), -- 'abstract', 'introduction', 'section', 'paragraph', 'conclusion', 'full_text'
    
    -- Content
    content TEXT NOT NULL,
    content_length INTEGER,
    token_count INTEGER,
    
    -- Location in paper
    section_title TEXT,
    page_numbers INTEGER[],
    line_start INTEGER,
    line_end INTEGER,
    
    -- Chunking strategy metadata
    chunking_strategy VARCHAR(50), -- 'hybrid', 'section', 'fixed', 'semantic'
    chunk_size_target INTEGER, -- Target size used
    overlap_size INTEGER, -- Overlap with previous chunk
    
    -- Additional context
    metadata JSONB, -- Additional chunk-specific metadata
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(paper_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_paper ON paper_chunks(paper_id);
CREATE INDEX IF NOT EXISTS idx_chunks_type ON paper_chunks(chunk_type);
CREATE INDEX IF NOT EXISTS idx_chunks_section ON paper_chunks(section_title);

-- Full-text search on chunk content
CREATE INDEX IF NOT EXISTS idx_chunks_content_fts ON paper_chunks USING gin(to_tsvector('english', content));

-- ============================================================================
-- STAGE 5: EMBEDDINGS (NEW TABLES)
-- ============================================================================

-- Chunk-level embeddings (for precise section search)
CREATE TABLE IF NOT EXISTS chunk_embeddings (
    id SERIAL PRIMARY KEY,
    chunk_id INTEGER NOT NULL REFERENCES paper_chunks(id) ON DELETE CASCADE,
    
    -- Vector embedding (adjust dimension based on model)
    embedding vector(768), -- For sentence-transformers all-mpnet-base-v2
    -- embedding vector(1536), -- For OpenAI ada-002 (uncomment if using)
    -- embedding vector(384), -- For all-MiniLM-L6-v2 (uncomment if using)
    
    -- Embedding metadata
    model_name VARCHAR(100) NOT NULL,
    model_dimension INTEGER NOT NULL,
    embedding_version INTEGER DEFAULT 1,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(chunk_id, model_name, embedding_version)
);

-- Vector similarity search index
CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_vector 
ON chunk_embeddings USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_chunk ON chunk_embeddings(chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_model ON chunk_embeddings(model_name);

-- Paper-level embeddings (for paper similarity)
CREATE TABLE IF NOT EXISTS paper_embeddings (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES pdf_files(id) ON DELETE CASCADE,
    
    -- Vector embedding
    embedding vector(768), -- Adjust dimension based on model
    
    -- How was paper-level embedding created?
    embedding_method VARCHAR(50), -- 'abstract', 'summary', 'aggregate_chunks', 'full_text'
    
    -- Embedding metadata
    model_name VARCHAR(100) NOT NULL,
    model_dimension INTEGER NOT NULL,
    embedding_version INTEGER DEFAULT 1,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(paper_id, model_name, embedding_method, embedding_version)
);

-- Vector similarity search index
CREATE INDEX IF NOT EXISTS idx_paper_embeddings_vector 
ON paper_embeddings USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_paper_embeddings_paper ON paper_embeddings(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_embeddings_model ON paper_embeddings(model_name);

-- ============================================================================
-- ADDITIONAL TABLES
-- ============================================================================

-- Tags table (from your original schema)
CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    tag_name VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Paper-Tag junction table (NEW)
CREATE TABLE IF NOT EXISTS paper_tags (
    paper_id INTEGER NOT NULL REFERENCES pdf_files(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (paper_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_tags_paper ON paper_tags(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_tags_tag ON paper_tags(tag_id);

-- Processing logs (track what happened during processing) - NEW
CREATE TABLE IF NOT EXISTS processing_logs (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER REFERENCES pdf_files(id) ON DELETE CASCADE,
    
    stage VARCHAR(50) NOT NULL, -- 'metadata', 'references', 'analysis', 'chunking', 'embedding'
    status VARCHAR(50) NOT NULL, -- 'started', 'completed', 'failed', 'skipped'
    
    -- Details
    message TEXT,
    error_details TEXT,
    
    -- Performance metrics
    duration_seconds DECIMAL(10,2),
    tokens_used INTEGER,
    cost_usd DECIMAL(10,4),
    
    -- Model info
    model_used VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_processing_logs_paper ON processing_logs(paper_id);
CREATE INDEX IF NOT EXISTS idx_processing_logs_stage ON processing_logs(stage);
CREATE INDEX IF NOT EXISTS idx_processing_logs_status ON processing_logs(status);
CREATE INDEX IF NOT EXISTS idx_processing_logs_created ON processing_logs(created_at);

-- Clusters table (for topic modeling results) - NEW
CREATE TABLE IF NOT EXISTS paper_clusters (
    id SERIAL PRIMARY KEY,
    cluster_name VARCHAR(255),
    cluster_description TEXT,
    
    -- Clustering metadata
    clustering_method VARCHAR(50), -- 'kmeans', 'hdbscan', 'hierarchical'
    clustering_parameters JSONB,
    
    -- Cluster statistics
    paper_count INTEGER,
    avg_year DECIMAL(6,2),
    top_keywords TEXT[],
    
    -- Cluster centroid (average embedding)
    centroid_embedding vector(768),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Paper-Cluster junction - NEW
CREATE TABLE IF NOT EXISTS paper_cluster_assignments (
    paper_id INTEGER NOT NULL REFERENCES pdf_files(id) ON DELETE CASCADE,
    cluster_id INTEGER NOT NULL REFERENCES paper_clusters(id) ON DELETE CASCADE,
    
    distance_to_centroid DECIMAL(10,6),
    assignment_confidence DECIMAL(3,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (paper_id, cluster_id)
);

CREATE INDEX IF NOT EXISTS idx_cluster_assignments_paper ON paper_cluster_assignments(paper_id);
CREATE INDEX IF NOT EXISTS idx_cluster_assignments_cluster ON paper_cluster_assignments(cluster_id);

-- ============================================================================
-- VIEWS (Useful queries as views) - NEW
-- ============================================================================

-- Papers with full citation counts
CREATE OR REPLACE VIEW papers_with_citations AS
SELECT 
    p.*,
    COUNT(DISTINCT ce.id) as citation_count,
    COUNT(DISTINCT ref.id) as reference_count
FROM pdf_files p
LEFT JOIN citation_edges ce ON p.id = ce.cited_paper_id
LEFT JOIN "references" ref ON p.id = ref.source_paper_id
GROUP BY p.id;

-- Paper processing status overview
CREATE OR REPLACE VIEW processing_status_overview AS
SELECT 
    processing_status,
    COUNT(*) as paper_count,
    AVG(EXTRACT(EPOCH FROM (COALESCE(updated_at, indexed_at) - indexed_at))) as avg_processing_time_seconds
FROM pdf_files
GROUP BY processing_status;

-- Most cited papers in collection
CREATE OR REPLACE VIEW most_cited_papers AS
SELECT 
    p.id,
    p.citekey,
    p.title,
    p.year,
    p.authors,
    COUNT(ce.id) as times_cited
FROM pdf_files p
JOIN citation_edges ce ON p.id = ce.cited_paper_id
GROUP BY p.id, p.citekey, p.title, p.year, p.authors
ORDER BY times_cited DESC;

-- Papers by year
CREATE OR REPLACE VIEW papers_by_year AS
SELECT 
    year,
    COUNT(*) as paper_count,
    COUNT(CASE WHEN processing_status = 'complete' THEN 1 END) as complete_count
FROM pdf_files
WHERE year IS NOT NULL
GROUP BY year
ORDER BY year DESC;

-- ============================================================================
-- FUNCTIONS - NEW
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at on pdf_files
DROP TRIGGER IF EXISTS trigger_pdf_files_updated_at ON pdf_files;
CREATE TRIGGER trigger_pdf_files_updated_at
    BEFORE UPDATE ON pdf_files
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for references
DROP TRIGGER IF EXISTS trigger_references_updated_at ON "references";
CREATE TRIGGER trigger_references_updated_at
    BEFORE UPDATE ON "references"
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for paper_analysis
DROP TRIGGER IF EXISTS trigger_analysis_updated_at ON paper_analysis;
CREATE TRIGGER trigger_analysis_updated_at
    BEFORE UPDATE ON paper_analysis
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
-- STATISTICS
-- ============================================================================

-- Analyze tables for query optimization
ANALYZE pdf_files;
ANALYZE "references";
ANALYZE paper_analysis;
ANALYZE paper_chunks;
ANALYZE chunk_embeddings;
ANALYZE paper_embeddings;

-- ============================================================================
-- INITIALIZATION COMPLETE
-- ============================================================================

SELECT 'PDF database initialized successfully' as status;
SELECT 'Extended pdf_files table with new fields for multi-stage processing' as summary;
SELECT 'New tables: paper_analysis, paper_chunks, chunk_embeddings, paper_embeddings, processing_logs, paper_clusters' as new_tables;