# Web Interface Specification

**Domain:** Presentation Layer
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-10
**Owner:** Ilja Heitlager

## Overview

The Web Interface is a Flask-based REST API and HTML5 single-page application for browsing, filtering, tagging, and analyzing academic research papers. It provides a modern, paper-centric interface for exploring paper metadata, viewing PDFs, examining citation networks, and managing tags. The system supports both local (port 8080) and Docker (port 8000) deployments with PostgreSQL as the persistent data store.

### Philosophy

The web interface follows three core principles:

1. **Paper-Centric Browsing**: All UI interactions pivot around individual papers as the primary unit. Papers can be accessed by file name, cite key, or discovered through year/tag/network navigation.

2. **REST API Foundation**: All data operations flow through a RESTful API with JSON payloads. The frontend is a thin client consuming these endpoints. This enables stateless horizontal scaling and easy integration with other tools.

3. **Progressive Disclosure**: The interface reveals information progressively—start with a year histogram overview, navigate to papers in a year, then drill into detailed views with tabs for PDF, analysis, references, tags, and citation relationships.

### Key Capabilities

- **Paper Listing & Discovery**: Query papers by year, search by title/author, filter by tags, paginate with configurable items per page
- **Paper Detail Views**: Multi-tab interface showing PDF viewer, analysis data, bibliographic details, citing/cited papers, and tag management
- **PDF Serving**: Direct PDF downloads from configurable base directory with path resolution (absolute and relative support)
- **Tag Management**: Colon-separated tag format with centralized tag lookup, tag CRUD operations, and paper-tag associations
- **Citation Network Visualization**: Full graph visualization showing all papers (nodes) and citation relationships (edges) with interactive drill-down
- **Deeplinking**: Shareable URLs with `?paper=<CiteKey>` parameter to directly jump to specific papers
- **Bulk Import**: POST endpoint to load papers from JSONLines format with conflict handling (skip/update)
- **Health Monitoring**: GET /health endpoint for operational monitoring and environment reporting

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement: Flask Server Initialization
The system MUST initialize a Flask application with CORS support, configurable static folder, and database manager instance. The application lifecycle MUST support both direct execution (`python -m`) and WSGI server execution (gunicorn).

#### Scenario: Local Development Server Start
- GIVEN the application is started with `python -m paper_scanner.web.server`
- WHEN command-line arguments include `--port 8080 --env local`
- THEN the server MUST bind to `0.0.0.0:8080` and log "Starting PDF Browser on 0.0.0.0:8080 (ENV: local)"

#### Scenario: Database Initialization on Startup
- GIVEN the server is starting
- WHEN the database manager is created
- THEN it MUST call `init_database()` to verify the 'papers' table exists (or log a warning if not)

#### Scenario: Lazy WSGI Initialization
- GIVEN the application is deployed to a WSGI server (gunicorn)
- WHEN the first HTTP request arrives
- THEN the AppProxy MUST lazily initialize the Flask app on first call, not at import time

---

### Requirement: Configuration Management
The system MUST load configuration from multiple sources in priority order: command-line arguments > environment variables > .env file > defaults. All configuration MUST be validated and accessible via a cached Config instance.

#### Configuration Parameters

| Parameter | Environment Variable | Default | Type | Example |
|-----------|---------------------|---------|------|---------|
| Database URL | `DATABASE_URL` | `postgresql://pdfuser:pdfpass@localhost:5432/pdfdb` | str | `postgresql://user:pass@host:5432/db` |
| PDF Base Directory | `PDF_BASE_DIR` | `/Users/iheitlager/wc/papers` | str | `/mnt/pdfs` |
| Environment Mode | `ENV` | `local` | enum (local\|docker\|production) | `docker` |
| Host | `HOST` | `0.0.0.0` | str | `127.0.0.1` |
| Port | `PORT` | `8080` | int | `8000` |
| Debug Mode | `DEBUG` | `false` | bool | `true` (local only) |
| Log Level | `LOG_LEVEL` | `INFO` | enum (DEBUG\|INFO\|WARNING\|ERROR\|CRITICAL) | `DEBUG` |

#### Scenario: Configuration from Environment Variables
- GIVEN environment variables `DATABASE_URL=postgresql://prod:pass@db.example.com/papers`, `PORT=8000`, `ENV=production`
- WHEN the server starts without command-line overrides
- THEN the Config MUST use the environment variable values and NOT log database credentials

#### Scenario: Configuration Validation
- GIVEN a Config is created with `port=99999` or `env=invalid`
- WHEN the Config is instantiated
- THEN it MUST raise a ValueError with clear message about valid values

#### Scenario: PDF Base Directory Expansion
- GIVEN `PDF_BASE_DIR=~/papers` in environment
- WHEN Config is loaded
- THEN it MUST expand `~` to user home directory and store absolute resolved path

---

### Requirement: Health Check Endpoint
The system MUST provide a GET /health endpoint that verifies database connectivity and reports the environment mode. The endpoint MUST be the first thing queried for operational monitoring.

#### Scenario: Health Check Success
- GIVEN the database is operational
- WHEN a client sends `GET /health`
- THEN the response MUST be HTTP 200 with JSON body: `{"status": "ok", "environment": "local"}`

#### Scenario: Health Check Failure
- GIVEN the database connection fails with OperationalError
- WHEN a client sends `GET /health`
- THEN the response MUST be HTTP 500 with JSON body: `{"status": "error", "message": "..."}`

---

### Requirement: Paper Listing API
The system MUST provide a GET /api/files endpoint that returns all papers in the database with essential metadata. The response MUST exclude large JSONB fields (raw_json, discovery, screening) for performance. Citation counts (inbound and outbound) MUST be included in the response.

#### Scenario: List All Papers
- GIVEN the database contains 5 papers
- WHEN a client sends `GET /api/files`
- THEN the response MUST be HTTP 200 with JSON body:
  ```json
  {
    "success": true,
    "files": [
      {
        "db_id": 1,
        "id": "uuid-1",
        "cite_key": "Author2020",
        "title": "A Great Paper",
        "authors": "Author, A.",
        "year": 2020,
        "doi": "10.1234/example",
        "file_name": "paper.pdf",
        "tags": "tag1:tag2",
        "inbound_count": 3,
        "outbound_count": 2
      },
      ...
    ]
  }
  ```
- AND papers MUST be ordered by title alphabetically

#### Scenario: Missing Metadata Handling
- GIVEN a paper record in the database without title, authors, or year
- WHEN `/api/files` is called
- THEN the paper MUST still be included with null values for missing fields

---

### Requirement: Paper Detail Retrieval
The system MUST provide a GET /api/file_details/<identifier> endpoint that retrieves a single paper by file name or cite key. The identifier lookup MUST try file_name first, then cite_key.

#### Scenario: Retrieve by File Name
- GIVEN a paper with file_name "paper.pdf"
- WHEN a client sends `GET /api/file_details/paper.pdf`
- THEN the response MUST be HTTP 200 with the complete paper object

#### Scenario: Retrieve by Cite Key
- GIVEN a paper with cite_key "Smith2021"
- WHEN a client sends `GET /api/file_details/Smith2021`
- THEN the response MUST be HTTP 200 with the complete paper object

#### Scenario: Not Found Response
- GIVEN no paper matches the identifier
- WHEN a client sends `GET /api/file_details/nonexistent`
- THEN the response MUST be HTTP 404 with JSON body: `{"success": false, "error": "PDF not found: nonexistent"}`

---

### Requirement: Bulk Paper Import via JSONLines
The system MUST provide a POST /api/load-jsonlines endpoint that accepts a JSON payload with a "records" array. Each record MAY contain file_path, file_name, directory, size_bytes, timestamps, title-details (with title/cite_key/year), analysis, and references.

#### Scenario: Valid Bulk Load
- GIVEN a POST payload:
  ```json
  {
    "records": [
      {
        "file_path": "papers/paper1.pdf",
        "file_name": "paper1.pdf",
        "directory": "papers",
        "size_bytes": 1000000,
        "created_time": "2024-01-01T00:00:00",
        "modified_time": "2024-01-01T00:00:00",
        "accessed_time": "2024-01-01T00:00:00",
        "title-details": {
          "title": "My Paper",
          "cite_key": "Author2024",
          "year": 2024
        },
        "analysis": {...}
      }
    ]
  }
  ```
- WHEN a client sends `POST /api/load-jsonlines` with this body
- THEN the response MUST be HTTP 200 with JSON body:
  ```json
  {
    "success": true,
    "loaded": 1,
    "failed": 0,
    "total": 1
  }
  ```
- AND the paper MUST be inserted into the papers table with tags synced to the tags table

#### Scenario: Partial Load with Errors
- GIVEN a POST payload with 3 records, where record 2 is invalid (missing required fields)
- WHEN `/api/load-jsonlines` is called
- THEN the response MUST be HTTP 200 with `"loaded": 2, "failed": 1, "total": 3`
- AND a warning MUST be logged for each failed record

#### Scenario: Empty Request
- GIVEN a POST payload with `"records": []`
- WHEN `/api/load-jsonlines` is called
- THEN the response MUST be HTTP 400 with error `"No records provided in request"`

#### Scenario: Duplicate Paper Handling
- GIVEN a paper with the same file_path already exists in the database
- WHEN the same record is posted to `/api/load-jsonlines`
- THEN the existing paper MUST be updated (ON CONFLICT file_path DO UPDATE)

---

### Requirement: Year Overview Statistics
The system MUST provide a GET /api/year-overview endpoint that groups papers by publication year and returns aggregated statistics. For each year, MUST return count and array of papers with essential fields.

#### Scenario: Year Overview Response
- GIVEN the database contains papers from years 2020, 2021, 2022
- WHEN a client sends `GET /api/year-overview`
- THEN the response MUST be HTTP 200 with JSON body:
  ```json
  {
    "success": true,
    "years": [
      {
        "year": 2022,
        "count": 5,
        "papers": [
          {
            "id": "uuid-1",
            "file_name": "paper1.pdf",
            "title": "Title",
            "cite_key": "Author2022",
            "authors": "Author, A."
          },
          ...
        ]
      },
      {
        "year": 2021,
        "count": 3,
        ...
      }
    ]
  }
  ```
- AND years MUST be ordered descending (newest first)
- AND papers within each year MUST be ordered by title

#### Scenario: No Papers with Year
- GIVEN the database has papers but none with a year field
- WHEN `/api/year-overview` is called
- THEN the response MUST be HTTP 200 with `"years": []`

---

### Requirement: Tag Management
The system MUST implement a centralized tag system where tags are colon-separated (e.g., "machine-learning:nlp:attention"). Tags MUST be synced to a dedicated tags table and MUST be retrievable via the API.

#### Scenario: Get All Tags
- GIVEN the database has papers with tags "ML:AI" and "NLP:TEXT", and a tags table entry for each
- WHEN a client sends `GET /api/tags`
- THEN the response MUST be HTTP 200 with JSON body:
  ```json
  {
    "success": true,
    "tags": ["AI", "ML", "NLP", "TEXT"]
  }
  ```
- AND tags MUST be unique and alphabetically sorted

#### Scenario: Update Paper Tags
- GIVEN a paper with file_name "paper.pdf"
- WHEN a client sends `PUT /api/file_tags/paper.pdf` with body `{"tags": "deep-learning:transformer:2024"}`
- THEN the response MUST be HTTP 200 with JSON body: `{"success": true, "message": "Tags updated successfully"}`
- AND the paper.tags MUST be updated to "deep-learning:transformer:2024"
- AND the tags table MUST have entries for "deep-learning", "transformer", "2024" (with ON CONFLICT DO NOTHING)

#### Scenario: Update by Cite Key
- GIVEN a paper with cite_key "Smith2021"
- WHEN a client sends `PUT /api/file_tags/Smith2021` with tags JSON
- THEN the system MUST find the paper by cite_key and update tags

#### Scenario: Invalid Tag Update
- GIVEN a paper identifier that doesn't exist
- WHEN a client sends `PUT /api/file_tags/nonexistent` with tags
- THEN the response MUST be HTTP 404 with error `"PDF not found: nonexistent"`

---

### Requirement: Citation Network Retrieval
The system MUST provide GET /api/references/<identifier> for single-paper references and GET /api/citation-network for the full network. Both MUST return citation edges, with the full network providing all papers as nodes.

#### Scenario: Get References for a Paper
- GIVEN a paper with db_id=5 that cites 3 other papers
- WHEN a client sends `GET /api/references/Smith2021`
- THEN the response MUST be HTTP 200 with JSON body:
  ```json
  {
    "success": true,
    "references": [
      {
        "db_id": 2,
        "id": "uuid-2",
        "cite_key": "Jones2019",
        "title": "Cited Paper",
        "authors": "Jones, B.",
        "year": 2019,
        "doi": "10.5678/example"
      },
      ...
    ]
  }
  ```
- AND cited papers MUST be ordered by title
- AND papers MUST be retrieved via citation_edges.cited_paper_id lookup

#### Scenario: Get Full Citation Network
- GIVEN the database has 10 papers and 20 citation edges
- WHEN a client sends `GET /api/citation-network`
- THEN the response MUST be HTTP 200 with JSON body:
  ```json
  {
    "success": true,
    "nodes": [
      {
        "db_id": 1,
        "id": "uuid-1",
        "cite_key": "Author2024",
        "title": "Paper Title",
        "authors": "Author, A.",
        "year": 2024,
        "journal": "Journal Name",
        "doi": "10.1234/example",
        "url": "https://example.com",
        "inbound_count": 5,
        "outbound_count": 3
      },
      ...
    ],
    "links": [
      {
        "source": "uuid-1",
        "target": "uuid-2"
      },
      ...
    ]
  }
  ```
- AND nodes MUST be all papers in the database
- AND links MUST represent citation_edges (source=citing_paper.id, target=cited_paper.id)
- AND links MUST only include edges where cited_paper_id IS NOT NULL

#### Scenario: Paper with No References
- GIVEN a paper that doesn't cite any other papers
- WHEN `/api/references/<identifier>` is called
- THEN the response MUST be HTTP 200 with `"references": []`

#### Scenario: Paper Not Found
- GIVEN a paper identifier that doesn't exist
- WHEN `/api/references/nonexistent` or `/api/citation-network` is called (for single-paper endpoint)
- THEN the response MUST be HTTP 404 with appropriate error message

---

### Requirement: PDF Serving
The system MUST provide a GET /api/pdf/<identifier> endpoint that serves PDFs from disk. The system MUST resolve file paths with support for both absolute and relative paths. If the file does not exist on disk, MUST return a 404 error.

#### Scenario: Serve PDF by File Name
- GIVEN a paper with file_name "paper.pdf" and file_path "papers/paper.pdf"
- WHEN a client sends `GET /api/pdf/paper.pdf`
- THEN the response MUST be HTTP 200 with MIME type "application/pdf"
- AND the PDF file MUST be served from disk

#### Scenario: Serve PDF by Cite Key
- GIVEN a paper with cite_key "Author2024" and file_path "papers/author_2024.pdf"
- WHEN a client sends `GET /api/pdf/Author2024`
- THEN the response MUST be HTTP 200 with the PDF file

#### Scenario: Path Resolution Behavior
- GIVEN file_path is a relative path "papers/paper.pdf"
- WHEN the server resolves the path
- THEN it MUST join with current working directory: `os.path.join(os.getcwd(), "papers/paper.pdf")`
- AND if the file exists, MUST serve it

#### Scenario: Absolute Path Handling
- GIVEN file_path is absolute "/mnt/pdfs/paper.pdf"
- WHEN the server tries to serve the PDF
- THEN it MUST first try relative resolution from cwd for basename, then use absolute path if relative doesn't exist

#### Scenario: File Not Found on Disk
- GIVEN a paper record exists but file_path doesn't exist on disk
- WHEN a client sends `GET /api/pdf/<identifier>`
- THEN the response MUST be HTTP 404 with error `"File not found on disk: <path>"`
- AND the error MUST be logged with the resolved path for debugging

#### Scenario: PDF Not Found
- GIVEN an identifier that doesn't match any paper
- WHEN a client sends `GET /api/pdf/nonexistent`
- THEN the response MUST be HTTP 404 with error `"PDF not found: nonexistent"`

---

### Requirement: HTML Interface
The system MUST serve a single-page HTML application at GET / that provides a browser interface for paper discovery, PDF viewing, and data management.

#### Scenario: Load HTML Interface
- GIVEN a running Flask server with templates configured
- WHEN a client sends `GET /`
- THEN the response MUST be HTTP 200 with HTML content
- AND the response MUST include `<title>PDF Browser</title>`
- AND the response MUST reference static assets: `style.css` and `script.js`
- AND the response MUST include external libraries: Chart.js and D3.js
- AND the response MUST pass `pdf_base_dir` to the template for frontend use

#### Scenario: Multi-Tab Interface
- GIVEN the HTML interface is loaded in a browser
- WHEN the user selects a paper from the list
- THEN the interface MUST display tabs for: PDF (native viewer), Analysis (analysis data), Details (bibliographic details), References (cited papers), and Tags (tag management)

#### Scenario: Overview Navigation
- GIVEN the HTML interface is loaded in a browser
- WHEN the user navigates from the year overview
- THEN the interface MUST initially show a year overview (histogram or network graph)
- AND clicking on a year MUST show papers from that year
- AND clicking on a paper MUST show its detail view
- AND a breadcrumb MUST show: "Year Overview > Year 2024 > Smith2021"

---

### Requirement: Error Handling
The system MUST register HTTP error handlers for custom exceptions and standard HTTP errors. All error responses MUST return JSON with "success": false and an "error" message. Custom exceptions MUST have HTTP status codes.

#### Exception Hierarchy

```
PDFBrowserException (base, status 500)
  ├── DatabaseException (status 500)
  ├── PDFNotFoundException (status 404, identifier)
  ├── FileNotFoundException (status 404, path)
  └── InvalidDataException (status 400, message)
```

#### Scenario: Database Exception
- GIVEN a database query fails with DatabaseException
- WHEN the error handler is invoked
- THEN the response MUST be HTTP 500 with JSON: `{"success": false, "error": "..."}`
- AND the error MUST be logged at ERROR level

#### Scenario: Invalid Data Exception
- GIVEN a POST request with invalid JSON or missing required fields
- WHEN InvalidDataException is raised
- THEN the response MUST be HTTP 400 with JSON: `{"success": false, "error": "..."}`

#### Scenario: Generic HTTP Errors
- GIVEN a request to a non-existent endpoint
- WHEN the 404 handler is invoked
- THEN the response MUST be HTTP 404 with JSON: `{"success": false, "error": "Resource not found"}`

#### Scenario: Unhandled 500 Error
- GIVEN an unhandled exception occurs
- WHEN the 500 handler is invoked
- THEN the response MUST be HTTP 500 with JSON: `{"success": false, "error": "Internal server error"}`
- AND the exception MUST be logged for debugging

---

### Requirement: Database Connection Management
The system MUST maintain a PostgreSQL connection with retry logic, connection pooling, and graceful error handling. The database manager MUST support context managers and handle serialization of complex types.

#### Scenario: Connection with Retry
- GIVEN the database is initially unavailable
- WHEN `get_connection(retries=3, delay=2)` is called
- THEN it MUST attempt 3 connection retries with 2-second delays between attempts
- AND if successful on retry 2, MUST return the connection
- AND if all retries fail, MUST raise DatabaseException

#### Scenario: Serialize DateTime Objects
- GIVEN a database query returns rows with datetime columns
- WHEN rows are serialized for JSON response
- THEN datetime objects MUST be converted to ISO format strings (e.g., "2024-01-15T10:30:00")

#### Scenario: Serialize JSONB Columns
- GIVEN a database query returns rows with JSONB columns (authors, discovery, etc.)
- WHEN rows are serialized for JSON response
- THEN JSONB columns MUST remain as dictionaries and be JSON-serializable

#### Scenario: Handle NULL Values
- GIVEN a database row has NULL values in various columns
- WHEN serialized for JSON response
- THEN NULL values MUST be represented as JSON null

---

### Requirement: Deeplinking Support
The system MUST support deeplinking with URL parameters of the form `?paper=<CiteKey>` to navigate directly to a paper's detail view.

#### Scenario: Deeplink Navigation
- GIVEN a user visits `/?paper=Smith2021`
- WHEN the client-side JavaScript initializes
- THEN it MUST fetch `/api/file_details/Smith2021`
- AND it MUST populate the detail view with the paper's information
- AND tabs MUST be accessible immediately without clicking through the year view

#### Scenario: Share Button
- GIVEN a paper detail view is displayed
- WHEN the user clicks the "Share" button
- THEN the system MUST copy to clipboard a URL like `http://localhost:8080/?paper=Smith2021`
- AND the URL MUST enable other users to directly access the same paper

---

### Requirement: Static Assets and Templates
The system MUST serve static CSS and JavaScript files from the `/static` directory. The HTML template MUST be served from Flask's templates directory.

#### Scenario: Static CSS
- GIVEN a running Flask server with static folder configured
- WHEN a client requests `GET /static/style.css`
- THEN the response MUST be HTTP 200 with MIME type "text/css"
- AND the file MUST be served from `src/paper_scanner/web/static/style.css`

#### Scenario: Static JavaScript
- GIVEN a running Flask server with static folder configured
- WHEN a client requests `GET /static/script.js`
- THEN the response MUST be HTTP 200 with MIME type "application/javascript"
- AND the file MUST be served from `src/paper_scanner/web/static/script.js`

#### Scenario: Template Rendering
- GIVEN Flask renders the index.html template
- WHEN variables like `pdf_base_dir` are passed to render_template()
- THEN the template MUST have access to these variables via Jinja2 syntax

---

### Requirement: CORS Support
The system MUST enable CORS (Cross-Origin Resource Sharing) to allow cross-origin requests for API endpoints.

#### Scenario: CORS Headers
- GIVEN a client from a different origin sends a request to an API endpoint
- WHEN the request is processed
- THEN the response MUST include CORS headers (Access-Control-Allow-Origin, etc.)
- AND cross-origin requests MUST be allowed by default

---

### Requirement: PostgreSQL Database Schema
The web interface MUST interact with the following PostgreSQL schema (managed elsewhere but defined here for reference).

#### Schema Overview

```sql
-- Core paper metadata
CREATE TABLE papers (
  db_id SERIAL PRIMARY KEY,
  id VARCHAR(36) UNIQUE,
  cite_key VARCHAR(255) UNIQUE,
  title TEXT,
  abstract TEXT,
  authors JSONB,  -- Array of Author objects
  keywords TEXT[],
  topics TEXT[],
  year INTEGER,
  journal VARCHAR(255),
  doi VARCHAR(255),
  url TEXT,
  file_path TEXT UNIQUE,
  file_name VARCHAR(255),
  size_bytes INTEGER,
  tags VARCHAR(1024),  -- Colon-separated: "tag1:tag2:tag3"
  title_details JSONB,
  analysis JSONB,
  conceptual_analysis JSONB,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- Centralized tag lookup
CREATE TABLE tags (
  id SERIAL PRIMARY KEY,
  tag_name VARCHAR(255) UNIQUE
);

-- Citation relationships
CREATE TABLE citation_edges (
  id SERIAL PRIMARY KEY,
  citing_paper_id INTEGER REFERENCES papers(db_id),
  cited_paper_id INTEGER REFERENCES papers(db_id),
  UNIQUE(citing_paper_id, cited_paper_id)
);

-- Embedding vectors (from spec 005)
CREATE TABLE paper_embeddings (
  id SERIAL PRIMARY KEY,
  paper_id INTEGER REFERENCES papers(db_id),
  embedding vector(768),
  model_name VARCHAR(255),
  embedding_method VARCHAR(255),
  created_at TIMESTAMP
);
```

#### Scenario: Query Paper with Citation Counts
- GIVEN a paper with db_id=5 that is cited by 10 papers and cites 3 papers
- WHEN querying `GET /api/files`
- THEN the response for that paper MUST include `"inbound_count": 10, "outbound_count": 3`

#### Scenario: Tag Sync on Insert
- GIVEN a POST to `/api/load-jsonlines` with tags "ML:AI:vision"
- WHEN the paper is inserted
- THEN the papers table MUST have tags="ML:AI:vision"
- AND the tags table MUST have three rows: (tag_name="ML"), (tag_name="AI"), (tag_name="vision")

---

## Metadata

### Implementation Files

- [src/paper_scanner/web/server.py](../../../src/paper_scanner/web/server.py) - HTTP server and routing
- [src/paper_scanner/web/database.py](../../../src/paper_scanner/web/database.py) - Database manager for web interface
- [src/paper_scanner/web/config.py](../../../src/paper_scanner/web/config.py) - Web configuration management
- [src/paper_scanner/web/http_handlers.py](../../../src/paper_scanner/web/http_handlers.py) - HTTP request handlers
- [src/paper_scanner/web/exceptions.py](../../../src/paper_scanner/web/exceptions.py) - Web-specific exceptions
- [src/paper_scanner/io/sql.py](../../../src/paper_scanner/io/sql.py) - SQL database operations
- [src/paper_scanner/web/templates/index.html](../../../src/paper_scanner/web/templates/index.html) - Main HTML template

### Test Coverage

The following test files verify the requirements in this specification:

**Web Application:**
- [tests/unit/web/test_config.py](../../../tests/unit/web/test_config.py) - Web configuration management
- [tests/unit/web/test_exceptions.py](../../../tests/unit/web/test_exceptions.py) - Exception handling
- [tests/unit/web/test_http_handlers.py](../../../tests/unit/web/test_http_handlers.py) - HTTP request handlers

**Viewers and Controllers:**
- [tests/unit/viewer/test_console_controller.py](../../../tests/unit/viewer/test_console_controller.py) - Console controller logic
- [tests/unit/viewer/test_console_viewer.py](../../../tests/unit/viewer/test_console_viewer.py) - Console viewer output
- [tests/unit/viewer/test_json_controller.py](../../../tests/unit/viewer/test_json_controller.py) - JSON controller
- [tests/unit/viewer/test_json_viewer.py](../../../tests/unit/viewer/test_json_viewer.py) - JSON viewer serialization

**CLI Interface:**
- [tests/unit/cli/test_repl.py](../../../tests/unit/cli/test_repl.py) - REPL interface
- [tests/unit/cli/test_paper_processor.py](../../../tests/unit/cli/test_paper_processor.py) - Paper processing CLI
- [tests/unit/cli/test_validate.py](../../../tests/unit/cli/test_validate.py) - Validation commands
- [tests/unit/cli/test_cache_task.py](../../../tests/unit/cli/test_cache_task.py) - Cache management CLI
- [tests/unit/cli/test_db_task.py](../../../tests/unit/cli/test_db_task.py) - Database CLI operations
- [tests/unit/cli/test_info_task.py](../../../tests/unit/cli/test_info_task.py) - Information display CLI
- [tests/unit/cli/test_run_task.py](../../../tests/unit/cli/test_run_task.py) - Pipeline execution CLI

**Export and Reporting:**
- [tests/unit/steps/test_export.py](../../../tests/unit/steps/test_export.py) - Export functionality
- [tests/unit/steps/test_export_integration.py](../../../tests/unit/steps/test_export_integration.py) - Export integration tests
- [tests/unit/steps/test_report.py](../../../tests/unit/steps/test_report.py) - Report generation
- [tests/unit/steps/test_patch.py](../../../tests/unit/steps/test_patch.py) - Data patching
- [tests/unit/steps/test_paper.py](../../../tests/unit/steps/test_paper.py) - Paper operations
- [tests/unit/steps/test_fix_cite_keys.py](../../../tests/unit/steps/test_fix_cite_keys.py) - Citation key fixes

**Tools and Utilities:**
- [tests/unit/tools/test_abstract_parser.py](../../../tests/unit/tools/test_abstract_parser.py) - Abstract parsing
- [tests/unit/tools/test_filereader.py](../../../tests/unit/tools/test_filereader.py) - File reading utilities
- [tests/unit/tools/test_core_handler.py](../../../tests/unit/tools/test_core_handler.py) - Core handler logic
- [tests/unit/tools/test_journals.py](../../../tests/unit/tools/test_journals.py) - Journal data handling
- [tests/unit/core/test_iso4_comprehensive.py](../../../tests/unit/core/test_iso4_comprehensive.py) - ISO4 abbreviations

**Model Handlers:**
- [tests/unit/models/test_claude_handler.py](../../../tests/unit/models/test_claude_handler.py) - Claude API integration
- [tests/unit/models/test_ollama_handler.py](../../../tests/unit/models/test_ollama_handler.py) - Ollama integration
- [tests/unit/core/test_base_handler.py](../../../tests/unit/core/test_base_handler.py) - Base handler class

**Database Operations:**
- [tests/unit/steps/test_upload_database.py](../../../tests/unit/steps/test_upload_database.py) - Database upload
- [tests/unit/steps/test_bibtex_paper_type.py](../../../tests/unit/steps/test_bibtex_paper_type.py) - BibTeX paper type handling

### Related Specifications

- [001-data-models](../001-data-models/spec.md) — Paper, Author, Citation models
- [002-pipeline-engine](../002-pipeline-engine/spec.md) — Data processing pipeline
- [005-embedding-system](../005-embedding-system/spec.md) — Vector embeddings storage
- **REST API Standard**: [RFC 7231 HTTP Semantics](https://datatracker.ietf.org/doc/html/rfc7231)
- **JSON Web Standards**: [RFC 8259 JSON Data Interchange Format](https://datatracker.ietf.org/doc/html/rfc8259)

### Architectural Decision Records

- [ADR-0004: Source Structure & Test Organization](../../../docs/adr/0004-source-setup.md) — Module layout and three-tier test strategy

---

## API Endpoint Summary

| Method | Endpoint | Purpose | Status Code |
|--------|----------|---------|-------------|
| GET | `/health` | Server health check | 200, 500 |
| GET | `/api/files` | List all papers | 200 |
| GET | `/api/file_details/<id>` | Get single paper details | 200, 404 |
| GET | `/api/tags` | Get all tags | 200 |
| GET | `/api/year-overview` | Papers grouped by year | 200 |
| GET | `/api/references/<id>` | Get cited papers | 200, 404 |
| GET | `/api/citation-network` | Full citation graph | 200 |
| GET | `/api/pdf/<id>` | Serve PDF file | 200, 404 |
| PUT | `/api/file_tags/<id>` | Update paper tags | 200, 400, 404 |
| POST | `/api/load-jsonlines` | Bulk import papers | 200, 400 |
| GET | `/` | Main HTML interface | 200 |
| GET | `/static/*` | Static CSS/JS assets | 200, 404 |

---

## Configuration Environment Variables

All configuration is environment-driven. Deploy with these environment variables:

```bash
# PostgreSQL Connection (REQUIRED)
export DATABASE_URL="postgresql://user:password@localhost:5432/papers_db"

# PDF Storage Directory (REQUIRED)
export PDF_BASE_DIR="/mnt/pdfs"

# Server Configuration
export ENV="production"           # local, docker, or production
export HOST="0.0.0.0"            # Bind address
export PORT="8000"               # Bind port
export DEBUG="false"             # Debug mode (local only)
export LOG_LEVEL="INFO"          # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

For development with .env file:

```bash
# .env
DATABASE_URL=postgresql://dev:devpass@localhost:5432/papers_dev
PDF_BASE_DIR=./papers
ENV=local
PORT=8080
DEBUG=true
LOG_LEVEL=DEBUG
```

---

## References

- **RFC 2119 - Key Words**: https://datatracker.ietf.org/doc/html/rfc2119
- **RFC 7231 - HTTP Semantics**: https://datatracker.ietf.org/doc/html/rfc7231
- **RFC 8259 - JSON Format**: https://datatracker.ietf.org/doc/html/rfc8259
- **Flask Documentation**: https://flask.palletsprojects.com/
- **PostgreSQL Documentation**: https://www.postgresql.org/docs/
- **psycopg2 Documentation**: https://www.psycopg.org/

---

**License:** Apache-2.0
**Copyright:** 2026 Ilja Heitlager
