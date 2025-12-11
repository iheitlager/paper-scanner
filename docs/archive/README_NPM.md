# Paper Scanner Web Frontend - NPM Setup Guide

This directory contains the web frontend for the Paper Scanner application. This document explains the npm package management and testing framework setup.

## Quick Start

### Installation

```bash
npm install
```

This installs all dependencies including the testing framework.

### Running Tests

```bash
# Run tests once
npm test

# Run tests in watch mode (re-runs on file changes)
npm run test:watch

# Run tests with coverage report
npm run test:coverage
```

### Code Quality

```bash
# Check code style with ESLint
npm run lint

# Fix linting issues automatically
npm run lint:fix

# Format code with Prettier
npm run format

# Check if code is formatted correctly
npm run format:check
```

## Project Structure

```
src/paper_scanner/web/static/
├── script.js           # Main application file (1500+ lines)
├── script.test.js      # Comprehensive test suite (41 tests)
├── style.css           # Application styling
└── index.html          # HTML template
```

## Package Configuration

### package.json

The `package.json` file defines:

- **Name & Version**: `paper-scanner-web@1.0.0`
- **Dependencies**: 
  - `chart.js@^4.4.0` - For histograms and data visualization
  
- **Dev Dependencies**:
  - `jest@^29.7.0` - Testing framework
  - `babel-jest@^29.7.0` - JavaScript transpiler for tests
  - `jest-environment-jsdom@^29.7.0` - Browser-like test environment
  - `eslint@^8.54.0` - Code linting
  - `prettier@^3.1.0` - Code formatting
  - `jsdom@^22.1.0` - DOM implementation for tests

### Available npm Scripts

| Command | Purpose |
|---------|---------|
| `npm test` | Run all tests once |
| `npm run test:watch` | Run tests in watch mode |
| `npm run test:coverage` | Generate coverage reports |
| `npm run lint` | Check code for linting issues |
| `npm run lint:fix` | Automatically fix linting issues |
| `npm run format` | Format code with Prettier |
| `npm run format:check` | Check code formatting |

## Testing Framework

### Jest Configuration

- **Test Environment**: jsdom (browser-like)
- **Test Files**: `**/*.test.js` or `**/*.spec.js`
- **Coverage**: Reports generated in `coverage/` directory
- **Transpiler**: Babel (for ES6 syntax support)

### Test Setup Files

- **jest.setup.js** - Global test setup, mocks for:
  - `localStorage`
  - `fetch` API
  - `Chart.js`
  - `window.matchMedia`
  - `TextEncoder`/`TextDecoder`

- **.babelrc** - Babel configuration for test transpilation

- **jest.config.js** - Jest configuration

### Test Coverage

The test suite (`script.test.js`) includes 41 tests covering:

#### Utility Functions (21 tests)
- `formatFileSize()` - File size formatting (bytes, KB, MB, GB)
- `escapeHtml()` - XSS prevention through HTML escaping
- `formatDate()` - Date formatting with error handling
- `formatDateTime()` - DateTime formatting
- `safeEncodeURI()` - Safe URI encoding

#### Storage Management (7 tests)
- `getLastTab()` / `saveLastTab()` - Tab preference persistence
- `getLastPaper()` / `saveLastPaper()` - Paper selection persistence

#### Error Handling (4 tests)
- `AppError` class - Custom error with context
- `handleApiError()` - API error normalization

#### Content Rendering (9 tests)
- `renderAnalysisSection()` - Analysis HTML rendering with XSS protection

All tests verify:
- Core functionality
- Edge cases and error conditions
- Security (HTML escaping)
- Data handling and type conversion

## Code Quality Tools

### ESLint (.eslintrc.js)

Configuration:
- Based on Airbnb style guide
- Browser and Node.js environments
- Jest globals recognized
- Strict rules for unused variables

Key Rules:
- No unused variables (with `_` prefix allowed)
- Console warnings/errors allowed
- No strict property assignments

### Prettier (.prettierrc)

Formatting Options:
- Print width: 100 characters
- Single quotes
- Trailing commas (ES5 style)
- 2-space indentation
- Semicolons enabled

### EditorConfig (.editorconfig)

Ensures consistent editor settings:
- UTF-8 encoding
- LF line endings
- 2-space indentation
- Trailing whitespace removal

## Integration with CI/CD

These npm scripts can be integrated into CI/CD pipelines:

```bash
# Run linting and tests (recommended for CI)
npm run lint && npm run test:coverage
```

The coverage reports are compatible with:
- Codecov
- SonarQube
- Other coverage reporting tools

## Debugging Tests

### Run specific test file
```bash
npm test -- script.test.js
```

### Run specific test suite
```bash
npm test -- --testNamePattern="formatFileSize"
```

### Run with verbose output
```bash
npm test -- --verbose
```

### Update snapshots (if using snapshot testing)
```bash
npm test -- -u
```

## Common Issues

### Tests fail after script.js changes

The test file includes implementations of utility functions. If you modify these functions in `script.js`, you may need to update the corresponding implementations in `script.test.js`.

### Coverage shows 0%

This is expected - the test file includes its own implementations of functions rather than importing from `script.js`. This is intentional for test isolation.

### ESLint errors

Run `npm run lint:fix` to automatically fix common issues.

### Format issues with Prettier

Run `npm run format` to automatically format all files.

## Next Steps

### Extend Test Coverage

Current test areas to expand:
- DOM manipulation functions (`switchTab`, `selectFile`, etc.)
- API integration tests with mocked fetch
- Chart.js rendering
- File upload and JSONL parsing
- Event handler testing
- Integration tests with mock backend

### Add More Utility Modules

Consider extracting more utility functions into separate modules for better testability:
- DOM utilities
- API utilities
- Data transformation utilities

### Setup Pre-commit Hooks

Install `husky` and `lint-staged` to run tests/linting before commits:
```bash
npm install --save-dev husky lint-staged
npx husky install
```

## References

- [Jest Documentation](https://jestjs.io/)
- [ESLint Documentation](https://eslint.org/)
- [Prettier Documentation](https://prettier.io/)
- [Babel Documentation](https://babeljs.io/)
