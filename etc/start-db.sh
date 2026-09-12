#!/usr/bin/env bash
#
# PostgreSQL Database Startup Script
#
# Purpose: Start PostgreSQL database container anywhere on the filesystem
# Supports multiple versions in different projects with local data persistence
#
# Usage:
#   ./start-db.sh --help

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Show usage function
show_usage() {
    local HELP="cat"
    if command -v bat >/dev/null 2>&1; then
        HELP="bat --plain --language=help"
    fi
    
    $HELP << 'EOF'
Usage: start-db.sh [OPTIONS]

OPTIONS:
    -n, --refresh               Destroy and recreate the database
    -d, --data-folder PATH      Custom data folder (default: ./data/postgresql)
    -f, --compose-file PATH     Custom docker-compose.yml file
    -h, --help                  Show this help message
    -v, --verbose               Enable verbose output

EXAMPLES:
    start-db.sh                                     # Start existing database
    start-db.sh -n                                  # Fresh database (destroy existing)
    start-db.sh -d /tmp/pgdata                      # Custom data folder
    start-db.sh --refresh --data-folder /tmp/test   # Fresh with custom location
    start-db.sh -f /path/to/docker-compose.yml      # Use custom compose file
    start-db.sh -n -d /data/postgresql              # Multiple options
    start-db.sh -v                                  # Verbose output

ENVIRONMENT:
    Script automatically locates init-db.sql in its own directory
    Data folder structure: <data-folder>/postgresql/
    Docker network: pdf-browser-network (auto-created)

CONNECTION DETAILS:
    Host:     localhost
    Port:     5432
    Database: pdfdb
    User:     pdfuser
    Password: pdfpass

EOF
}

# Default values
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER="./data/postgresql"  # Default: relative to current working directory
DOCKER_COMPOSE_FILE="${SCRIPT_DIR%/*}/docker-compose.yml"  # One level up: project/docker-compose.yml
REFRESH_DB=false
CONTAINER_NAME="pdf-browser-db"
NETWORK_NAME="pdf-browser-network"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--refresh)
            REFRESH_DB=true
            shift
            ;;
        -d|--data-folder)
            if [[ -z "$2" ]]; then
                echo -e "${RED}Error: --data-folder requires a path argument${NC}" >&2
                exit 1
            fi
            DATA_FOLDER="$2"
            shift 2
            ;;
        -f|--compose-file)
            if [[ -z "$2" ]]; then
                echo -e "${RED}Error: --compose-file requires a file argument${NC}" >&2
                exit 1
            fi
            DOCKER_COMPOSE_FILE="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}" >&2
            show_usage
            exit 1
            ;;
    esac
done

# Show help function

# Validate docker-compose file exists
if [[ ! -f "$DOCKER_COMPOSE_FILE" ]]; then
    echo -e "${RED}Error: docker-compose file not found: $DOCKER_COMPOSE_FILE${NC}" >&2
    exit 1
fi

# Validate init-db.sql exists
INIT_SQL="${SCRIPT_DIR}/init-db.sql"
if [[ ! -f "$INIT_SQL" ]]; then
    echo -e "${RED}Error: init-db.sql not found in: $SCRIPT_DIR${NC}" >&2
    exit 1
fi

# Validate data folder path is absolute or make it absolute
if [[ "$DATA_FOLDER" != /* ]]; then
    DATA_FOLDER="$(cd "$(pwd)" && echo "$(pwd)/$DATA_FOLDER")"
fi

# Create temporary directory for docker-compose
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Copy docker-compose to temp directory
cp "$DOCKER_COMPOSE_FILE" "$TEMP_DIR/docker-compose.yml"

# Copy init-db.sql to temp directory
mkdir -p "$TEMP_DIR/etc"
cp "$INIT_SQL" "$TEMP_DIR/etc/init-db.sql"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE} PostgreSQL Database Startup${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Check if container is running
if docker ps --format "table {{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${YELLOW}Container ${CONTAINER_NAME} is already running${NC}"
    if [[ "$REFRESH_DB" == false ]]; then
        echo -e "${GREEN}✓ Database is ready${NC}"
        echo ""
        exit 0
    fi
fi

# Handle refresh mode
if [[ "$REFRESH_DB" == true ]]; then
    echo -e "${YELLOW}Refresh mode enabled - destroying existing data...${NC}"
    
    # Stop container if running
    if docker ps --format "table {{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        echo "Stopping container ${CONTAINER_NAME}..."
        docker stop "$CONTAINER_NAME" || true
    fi
    
    # Remove container
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
    
    # Remove data directory
    if [[ -d "$DATA_FOLDER" ]]; then
        echo "Removing data directory: $DATA_FOLDER"
        rm -rf "$DATA_FOLDER"
    fi
fi

# Create data directory
mkdir -p "$DATA_FOLDER"
echo -e "${GREEN}✓ Data directory: $DATA_FOLDER${NC}"

# Create network if it doesn't exist
if ! docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
    echo "Creating Docker network: $NETWORK_NAME"
    docker network create "$NETWORK_NAME" || true
fi

# Create temporary docker-compose.yml with correct paths
cat > "$TEMP_DIR/docker-compose.yml" << COMPOSE_EOF
version: '3.8'

services:
  pdf-browser-db:
    image: pgvector/pgvector:pg15
    container_name: pdf-browser-db
    environment:
      POSTGRES_USER: pdfuser
      POSTGRES_PASSWORD: pdfpass
      POSTGRES_DB: pdfdb
    volumes:
      - ${DATA_FOLDER}:/var/lib/postgresql/data
      - ${TEMP_DIR}/etc/init-db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    networks:
      - pdf-browser-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pdfuser -d pdfdb"]
      interval: 10s
      timeout: 5s
      retries: 5

networks:
  pdf-browser-network:
    external: true
COMPOSE_EOF

echo "Starting PostgreSQL container..."
cd "$TEMP_DIR"
docker-compose up -d pdf-browser-db

# Wait for database to be ready
echo ""
echo -e "${YELLOW}Waiting for PostgreSQL to be ready...${NC}"
MAX_ATTEMPTS=30
ATTEMPT=0

while [[ $ATTEMPT -lt $MAX_ATTEMPTS ]]; do
    if docker exec "$CONTAINER_NAME" pg_isready -U pdfuser -d pdfdb >/dev/null 2>&1; then
        echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    echo -n "."
    sleep 1
done

if [[ $ATTEMPT -eq $MAX_ATTEMPTS ]]; then
    echo -e "${RED}✗ PostgreSQL did not become ready in time${NC}" >&2
    exit 1
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Database started successfully${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Connection details:"
echo "  Host: localhost"
echo "  Port: 5432"
echo "  Database: pdfdb"
echo "  User: pdfuser"
echo "  Password: pdfpass"
echo ""
echo "Data location: $DATA_FOLDER"
echo ""
echo "To stop the database:"
echo "  docker stop $CONTAINER_NAME"
echo ""
echo "To remove the database:"
echo "  docker rm $CONTAINER_NAME"
echo "  rm -rf $DATA_FOLDER"
echo ""
