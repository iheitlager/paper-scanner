# Browser Integration Spike

Exploratory work on integrating browser-based file browsing with paper-scanner processing.

## Experiment: PDF Browser Web Application

A complete web-based PDF viewer with PostgreSQL backend for managing and viewing PDF files. Supports both local development (port 8080) and Docker containerized deployment (port 8000).

## Features

- 📄 **File Browser**: Left sidebar with file selector showing file names and sizes
- 🔍 **PDF Viewer**: Full-featured PDF rendering in the main viewport
- 📊 **Database Backend**: PostgreSQL for storing file metadata
- 📥 **JSONL Import**: Load file metadata from JSONL files with one click
- 🐳 **Docker Support**: Complete Docker and docker-compose setup for easy deployment
- 🏠 **Mac Local Development**: Run directly on macOS port 8080

## Architecture

- **Backend**: Flask API for serving processor output
- **Frontend**: React-based file browser UI
- **Database**: PostgreSQL for storing file metadata and processor results
- **Deployment**: Docker containerization for easy deployment and reproducibility

## Components

### Backend (Flask)
- REST API to load processor output
- File metadata management
- Integration with paper-scanner processors

### Frontend (React)
- Interactive file browser
- Visualization of processor results
- Real-time updates

### Database (PostgreSQL)
- Store file metadata
- Cache processor results
- Query optimization

### Infrastructure (Docker)
- Containerized Flask backend
- Containerized PostgreSQL database
- Docker Compose for orchestration

## Purpose

Evaluate the feasibility of building a complete web-based interface for paper-scanner that allows users to:
1. Browse processed documents
2. View processor output in an organized hierarchy
3. Access file metadata and processing results
4. Manage and organize processed files

## Status

In progress on the `spike/browser` branch.
