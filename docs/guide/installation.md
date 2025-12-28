# Installation

## System Requirements

- Python 3.11 or higher
- PostgreSQL 12+ (or SQLite for development)
- 2GB RAM minimum (4GB+ recommended)
- macOS, Linux, or Windows (WSL2)

## Install from Source

### 1. Clone the Repository
```bash
git clone https://github.com/iheitlager/paper-scanner.git
cd paper-scanner
```

### 2. Install Python Dependencies

We use `uv` for fast, reliable dependency management:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies including dev tools
uv sync --all-groups
```

This installs:
- Core dependencies
- Development tools (testing, linting, formatting)
- Documentation tools
- Optional dependencies

### 3. Set up Environment

Create a `.env` file in the project root:
```env
# Claude API
ANTHROPIC_API_KEY=sk-ant-...

# Database (optional, SQLite default)
DATABASE_URL=postgresql://user:password@localhost/paper_scanner
PAPERS_DB=papers.db

# Cache
CACHE_DIR=.cache
```

### 4. Initialize Database

```bash
# Create tables
uv run paper-processor --init

# Or with custom database
uv run paper-processor --db custom.db --init
```

## Verification

Verify installation:
```bash
# Check version
uv run paper-processor --version

# Run tests
make test

# Run linter
make lint
```

## Development Setup

For contributing to paper-scanner:

```bash
# Install with all development dependencies
uv sync --all-groups

# Set up git hooks (optional)
pre-commit install

# Run tests in watch mode
make test-watch
```

## Platform-Specific Notes

### macOS
- Works out of the box with system Python
- Install PostgreSQL: `brew install postgresql@15`

### Linux (Ubuntu/Debian)
```bash
# Install dependencies
sudo apt-get install python3.11 python3.11-venv postgresql

# Verify Python
python3.11 --version
```

### Windows (WSL2)
Recommended to run inside WSL2:
```bash
# Inside WSL2 Ubuntu
sudo apt-get install python3.11 python3.11-venv postgresql
```

## Database Setup

### SQLite (Development/Testing)
Default, no setup needed:
```bash
uv run paper-processor definition.yml
# Uses ./papers.db
```

### PostgreSQL (Production)
```bash
# Create database
createdb paper_scanner

# Set connection string
export DATABASE_URL="postgresql://user:password@localhost/paper_scanner"

# Run migrations
uv run paper-processor --init
```

## Optional Dependencies

### For PDF Analysis
The tool works best with Claude, but you can configure alternative models:
```bash
# Set in .env
ANTHROPIC_API_KEY=sk-ant-...
```

### For Citation Sources
Install additional citation sources:
```bash
# Crossref (default)
# OpenAlex
# Semantic Scholar
# Already included in core dependencies
```

## Troubleshooting

### "uv command not found"
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### "Python 3.11 not found"
```bash
# Install Python 3.11
# macOS:
brew install python@3.11

# Ubuntu:
sudo apt-get install python3.11

# Then run uv sync
uv sync --all-groups
```

### Database Connection Error
```bash
# Check PostgreSQL is running
psql --version

# Start PostgreSQL
# macOS:
brew services start postgresql@15

# Test connection
psql postgres://user:password@localhost/paper_scanner
```

### "Module not found" errors
```bash
# Ensure virtual environment is activated
source .venv/bin/activate  # or source venv/bin/activate

# Reinstall dependencies
uv sync --all-groups
```

## Next Steps

1. [Quick Start](quick-start.md) - Run your first pipeline
2. [Architecture Overview](../architecture/overview.md) - Understand the system
3. [Step Reference](../steps/overview.md) - Available pipeline steps

## Getting Help

- 💬 [Open an issue](https://github.com/iheitlager/paper-scanner/issues)
- 📚 [Full documentation](https://paper-scanner.readthedocs.io)
