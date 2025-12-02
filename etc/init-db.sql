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

-- Grant permissions to the pdfuser
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO pdfuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO pdfuser;
GRANT USAGE ON SCHEMA public TO pdfuser;

-- Log initialization completion
SELECT 'PDF database initialized successfully' as status;
