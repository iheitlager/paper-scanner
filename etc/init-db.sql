-- Initialize PostgreSQL database for PDF browser
-- This script runs automatically when the postgres container starts

-- Connect to the correct database
\connect pdfdb

-- Create table if it doesn't exist
CREATE TABLE IF NOT EXISTS pdf_files (
    id SERIAL PRIMARY KEY,
    file_path VARCHAR(500) UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    directory VARCHAR(500) NOT NULL,
    relative_path VARCHAR(500) NOT NULL,
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
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create tags lookup table
CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    tag_name VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_file_name ON pdf_files(file_name);
CREATE INDEX IF NOT EXISTS idx_directory ON pdf_files(directory);
CREATE INDEX IF NOT EXISTS idx_tags ON pdf_files(tags);
CREATE INDEX IF NOT EXISTS idx_title ON pdf_files(title);
CREATE INDEX IF NOT EXISTS idx_citekey ON pdf_files(citekey);
CREATE INDEX IF NOT EXISTS idx_year ON pdf_files(year);

-- Create references table for storing extracted citations
CREATE TABLE IF NOT EXISTS "references" (
    id SERIAL PRIMARY KEY,
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create citation edges table for linking papers to their references
CREATE TABLE IF NOT EXISTS citation_edges (
    id SERIAL PRIMARY KEY,
    citing_paper_id INTEGER NOT NULL REFERENCES pdf_files(id) ON DELETE CASCADE,
    cited_reference_id INTEGER NOT NULL REFERENCES "references"(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create citation metadata table for extraction status and notes
CREATE TABLE IF NOT EXISTS citation_metadata (
    id SERIAL PRIMARY KEY,
    reference_id INTEGER NOT NULL REFERENCES "references"(id) ON DELETE CASCADE,
    parsing_status VARCHAR(50) DEFAULT 'success',
    extraction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    parsing_issues TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for references tables
CREATE INDEX IF NOT EXISTS idx_references_source_paper ON "references"(source_paper_id);
CREATE INDEX IF NOT EXISTS idx_references_citekey ON "references"(citekey);
CREATE INDEX IF NOT EXISTS idx_citation_edges_citing ON citation_edges(citing_paper_id);
CREATE INDEX IF NOT EXISTS idx_citation_edges_cited ON citation_edges(cited_reference_id);
CREATE INDEX IF NOT EXISTS idx_citation_edges_pair ON citation_edges(citing_paper_id, cited_reference_id);

-- Grant permissions to the pdfuser
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO pdfuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO pdfuser;
GRANT USAGE ON SCHEMA public TO pdfuser;

-- Log initialization completion
SELECT 'PDF database initialized successfully' as status;
