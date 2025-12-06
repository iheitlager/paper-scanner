-- Crossref Reference Fetcher - SQL Query Reference
-- Useful queries for working with fetched references

-- ============================================================================
-- BASIC QUERIES
-- ============================================================================

-- View all papers from Crossref
SELECT 
  id,
  citekey,
  title,
  year,
  doi,
  source_type,
  processing_status,
  indexed_at
FROM papers
WHERE source_type = 'crossref'
ORDER BY indexed_at DESC
LIMIT 20;

-- Count papers by source type
SELECT 
  source_type,
  COUNT(*) as count
FROM papers
GROUP BY source_type
ORDER BY count DESC;

-- Count total references fetched
SELECT 
  p1.source_type as source,
  COUNT(ce.id) as reference_count
FROM papers p1
LEFT JOIN citation_edges ce ON p1.id = ce.citing_paper_id
GROUP BY p1.source_type
ORDER BY reference_count DESC;

-- ============================================================================
-- CITATION NETWORK QUERIES
-- ============================================================================

-- View citation network (citing paper → cited paper)
SELECT 
  p1.citekey as "Citing Paper",
  p1.year as "Citing Year",
  p2.citekey as "Cited Paper",
  p2.year as "Cited Year",
  p2.source_type as "Cited Source",
  p2.doi as "Cited DOI"
FROM citation_edges ce
JOIN papers p1 ON ce.citing_paper_id = p1.id
JOIN papers p2 ON ce.cited_paper_id = p2.id
WHERE p1.source_type = 'file'  -- Only original papers
ORDER BY p1.citekey, p2.year DESC
LIMIT 20;

-- Most cited papers in collection
SELECT 
  p.citekey,
  p.title,
  p.year,
  p.source_type,
  COUNT(ce.id) as times_cited
FROM papers p
LEFT JOIN citation_edges ce ON p.id = ce.cited_paper_id
WHERE p.source_type = 'file'
GROUP BY p.id
ORDER BY times_cited DESC
LIMIT 20;

-- Least cited papers (more than 0 citations)
SELECT 
  p.citekey,
  p.title,
  p.year,
  COUNT(ce.id) as times_cited
FROM papers p
LEFT JOIN citation_edges ce ON p.id = ce.cited_paper_id
WHERE p.source_type = 'file'
GROUP BY p.id
HAVING COUNT(ce.id) > 0
ORDER BY times_cited ASC
LIMIT 20;

-- ============================================================================
-- REFERENCE ANALYSIS
-- ============================================================================

-- References per original paper
SELECT 
  p.citekey,
  p.title,
  p.year,
  COUNT(ce.id) as reference_count
FROM papers p
LEFT JOIN citation_edges ce ON p.id = ce.citing_paper_id
WHERE p.source_type = 'file'
GROUP BY p.id, p.citekey, p.title, p.year
ORDER BY reference_count DESC;

-- Papers with NO references found in Crossref
SELECT 
  p.citekey,
  p.title,
  p.year,
  p.doi,
  COUNT(ce.id) as references_found
FROM papers p
LEFT JOIN citation_edges ce ON p.id = ce.citing_paper_id
WHERE p.source_type = 'file'
  AND p.doi IS NOT NULL
GROUP BY p.id, p.citekey
HAVING COUNT(ce.id) = 0
ORDER BY p.year DESC;

-- Papers with references fetched (from Crossref)
SELECT 
  p.citekey,
  p.title,
  p.year,
  p.doi,
  COUNT(ce.id) as references_count,
  COUNT(ce.id)::float / 
    NULLIF((SELECT COUNT(*) FROM papers WHERE source_type = 'file'), 0) * 100 
    as "% of collection"
FROM papers p
LEFT JOIN citation_edges ce ON p.id = ce.citing_paper_id
WHERE p.source_type = 'file'
  AND p.doi IS NOT NULL
GROUP BY p.id, p.citekey
HAVING COUNT(ce.id) > 0
ORDER BY COUNT(ce.id) DESC;

-- ============================================================================
-- TEMPORAL ANALYSIS
-- ============================================================================

-- Distribution of fetched references by year
SELECT 
  p2.year,
  COUNT(ce.id) as reference_count,
  COUNT(DISTINCT p2.id) as unique_papers
FROM citation_edges ce
JOIN papers p1 ON ce.citing_paper_id = p1.id
JOIN papers p2 ON ce.cited_paper_id = p2.id
WHERE p1.source_type = 'file'
  AND p2.year IS NOT NULL
GROUP BY p2.year
ORDER BY p2.year DESC
LIMIT 50;

-- Recent references (last 5 years)
SELECT 
  p2.year,
  COUNT(ce.id) as reference_count
FROM citation_edges ce
JOIN papers p1 ON ce.citing_paper_id = p1.id
JOIN papers p2 ON ce.cited_paper_id = p2.id
WHERE p1.source_type = 'file'
  AND p2.year >= EXTRACT(YEAR FROM CURRENT_DATE) - 5
GROUP BY p2.year
ORDER BY p2.year DESC;

-- Age of references (how old are the cited papers)
SELECT 
  EXTRACT(YEAR FROM CURRENT_DATE) - p2.year as age_years,
  COUNT(ce.id) as reference_count
FROM citation_edges ce
JOIN papers p1 ON ce.citing_paper_id = p1.id
JOIN papers p2 ON ce.cited_paper_id = p2.id
WHERE p1.source_type = 'file'
  AND p2.year IS NOT NULL
GROUP BY EXTRACT(YEAR FROM CURRENT_DATE) - p2.year
ORDER BY age_years;

-- ============================================================================
-- AUTHOR & METADATA ANALYSIS
-- ============================================================================

-- Check for missing metadata in fetched papers
SELECT 
  COUNT(*) as total,
  COUNT(CASE WHEN title IS NULL THEN 1 END) as missing_title,
  COUNT(CASE WHEN year IS NULL THEN 1 END) as missing_year,
  COUNT(CASE WHEN authors IS NULL THEN 1 END) as missing_authors,
  COUNT(CASE WHEN doi IS NULL THEN 1 END) as missing_doi
FROM papers
WHERE source_type = 'crossref';

-- Authors in Crossref papers
SELECT 
  jsonb_array_length(authors) as author_count,
  COUNT(*) as paper_count
FROM papers
WHERE source_type = 'crossref'
  AND authors IS NOT NULL
GROUP BY author_count
ORDER BY author_count DESC;

-- ============================================================================
-- DATA QUALITY & VALIDATION
-- ============================================================================

-- Papers with complete metadata
SELECT 
  COUNT(*) as total_papers,
  COUNT(CASE WHEN title IS NOT NULL THEN 1 END) as with_title,
  COUNT(CASE WHEN year IS NOT NULL THEN 1 END) as with_year,
  COUNT(CASE WHEN authors IS NOT NULL THEN 1 END) as with_authors,
  COUNT(CASE WHEN doi IS NOT NULL THEN 1 END) as with_doi,
  COUNT(CASE WHEN 
    title IS NOT NULL AND 
    year IS NOT NULL AND 
    authors IS NOT NULL 
  THEN 1 END) as fully_complete
FROM papers
WHERE source_type = 'crossref';

-- Check for duplicates (same DOI)
SELECT 
  doi,
  COUNT(*) as count
FROM papers
WHERE source_type = 'crossref'
  AND doi IS NOT NULL
GROUP BY doi
HAVING COUNT(*) > 1;

-- Papers with incomplete author information
SELECT 
  citekey,
  title,
  authors,
  jsonb_array_length(authors) as author_count
FROM papers
WHERE source_type = 'crossref'
  AND (authors IS NULL OR jsonb_array_length(authors) = 0)
LIMIT 20;

-- ============================================================================
-- REPORTING & STATISTICS
-- ============================================================================

-- Comprehensive statistics report
SELECT 
  'Total Papers in Collection' as metric,
  COUNT(*)::text as value
FROM papers
WHERE source_type = 'file'

UNION ALL

SELECT 
  'Total References Fetched (from Crossref)',
  COUNT(*)::text
FROM papers
WHERE source_type = 'crossref'

UNION ALL

SELECT 
  'Total Citation Edges Created',
  COUNT(*)::text
FROM citation_edges

UNION ALL

SELECT 
  'Papers with References Fetched',
  COUNT(DISTINCT citing_paper_id)::text
FROM citation_edges

UNION ALL

SELECT 
  'Average References per Paper',
  ROUND(AVG(ref_count)::numeric, 2)::text
FROM (
  SELECT COUNT(*) as ref_count
  FROM citation_edges
  GROUP BY citing_paper_id
) t

UNION ALL

SELECT 
  'Coverage Rate (%)',
  ROUND(
    COUNT(DISTINCT ce.citing_paper_id)::float / 
    COUNT(DISTINCT p.id) * 100,
    2
  )::text
FROM papers p
LEFT JOIN citation_edges ce ON p.id = ce.citing_paper_id
WHERE p.source_type = 'file'
  AND p.doi IS NOT NULL;

-- Summary by screening stage
SELECT 
  ps.screening_stage,
  COUNT(DISTINCT p.id) as papers,
  COUNT(DISTINCT CASE WHEN p.doi IS NOT NULL THEN p.id END) as with_doi,
  COUNT(DISTINCT ce.id) as references_fetched
FROM papers p
LEFT JOIN paper_screening ps ON p.id = ps.paper_id
LEFT JOIN citation_edges ce ON p.id = ce.citing_paper_id
WHERE p.source_type = 'file'
GROUP BY ps.screening_stage
ORDER BY ps.screening_stage;

-- ============================================================================
-- EXPORT & BACKUP QUERIES
-- ============================================================================

-- Export Crossref papers as CSV
-- \COPY (SELECT * FROM papers WHERE source_type = 'crossref') 
-- TO 'crossref_papers.csv' WITH (FORMAT CSV, HEADER);

-- Export citation network
-- \COPY (
--   SELECT 
--     p1.citekey as citing_paper,
--     p2.citekey as cited_paper,
--     p2.year,
--     p2.title
--   FROM citation_edges ce
--   JOIN papers p1 ON ce.citing_paper_id = p1.id
--   JOIN papers p2 ON ce.cited_paper_id = p2.id
-- ) TO 'citation_network.csv' WITH (FORMAT CSV, HEADER);

-- Export as BibTeX format (partial - needs additional processing)
SELECT 
  'crossref_' || id as bibkey,
  'article' as bibtype,
  citekey as author_field,
  title,
  year,
  journal,
  doi
FROM papers
WHERE source_type = 'crossref'
  AND doi IS NOT NULL
LIMIT 20;

-- ============================================================================
-- MAINTENANCE & CLEANUP
-- ============================================================================

-- Find and list duplicate DOIs
SELECT 
  doi,
  COUNT(*) as count,
  array_agg(id) as paper_ids,
  array_agg(citekey) as citekeys
FROM papers
WHERE doi IS NOT NULL
GROUP BY doi
HAVING COUNT(*) > 1
ORDER BY count DESC;

-- Papers with NULL year (problematic for analysis)
SELECT 
  id,
  citekey,
  title,
  source_type
FROM papers
WHERE year IS NULL
ORDER BY source_type, id;

-- Check processing status of Crossref papers
SELECT 
  processing_status,
  COUNT(*) as count
FROM papers
WHERE source_type = 'crossref'
GROUP BY processing_status
ORDER BY processing_status;

-- ============================================================================
-- ADVANCED ANALYTICS
-- ============================================================================

-- Citation flow analysis (which years cite which years)
SELECT 
  p1.year as "Citing Year",
  p2.year as "Cited Year",
  COUNT(*) as reference_count
FROM citation_edges ce
JOIN papers p1 ON ce.citing_paper_id = p1.id
JOIN papers p2 ON ce.cited_paper_id = p2.id
WHERE p1.source_type = 'file'
  AND p1.year IS NOT NULL
  AND p2.year IS NOT NULL
GROUP BY p1.year, p2.year
ORDER BY p1.year DESC, p2.year DESC;

-- Co-citation analysis (papers cited together)
SELECT 
  ce1.cited_paper_id,
  ce2.cited_paper_id,
  COUNT(*) as co_citation_count
FROM citation_edges ce1
JOIN citation_edges ce2 ON ce1.citing_paper_id = ce2.citing_paper_id
WHERE ce1.cited_paper_id < ce2.cited_paper_id
GROUP BY ce1.cited_paper_id, ce2.cited_paper_id
ORDER BY co_citation_count DESC
LIMIT 20;

-- ============================================================================
-- NOTES
-- ============================================================================
-- These queries assume:
-- - Database schema from init-db.sql with source_type field
-- - Papers fetched from Crossref have source_type = 'crossref'
-- - Original collection papers have source_type = 'file'
-- - Citation edges link citing_paper_id to cited_paper_id
--
-- Modify WHERE clauses as needed for your specific analysis
-- Use EXPLAIN ANALYZE for performance optimization
