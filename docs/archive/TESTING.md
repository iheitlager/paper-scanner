# JavaScript Testing & Package Management Setup

This document describes the npm package management and testing setup for the paper-scanner web frontend.

## Setup Overview

### Package Management (`package.json`)
- **Dependencies**: 
  - `chart.js@^4.4.0` - For data visualization (histogram)
  
- **Dev Dependencies**:
  - `jest@^29.7.0` - Testing framework
  - `@babel/core`, `@babel/preset-env`, `babel-jest` - JavaScript transpilation for tests
  - `jest-environment-jsdom` - Browser-like environment for testing
  - `eslint` + plugins - Code linting
  - `prettier` - Code formatting

### Available npm Scripts

```bash
npm test                 # Run all tests once
npm run test:watch      # Run tests in watch mode (re-runs on file changes)
npm run test:coverage   # Run tests with coverage report
npm run lint            # Check code style with ESLint
npm run lint:fix        # Fix linting issues automatically
npm run format          # Format code with Prettier
npm run format:check    # Check if code is properly formatted
```

### Testing Framework Setup

- **Jest Configuration** (`jest.config.js`)
  - Uses jsdom test environment (simulates browser)
  - Test files: `**/*.test.js` or `**/*.spec.js`
  - Coverage reports in `coverage/` directory
  - Babel transformation enabled

- **Jest Setup** (`jest.setup.js`)
  - Mock `localStorage` for storage tests
  - Mock `fetch` API for HTTP testing
  - Mock `Chart.js` for visualization tests
  - Mock `window.matchMedia` for media queries

### Code Quality Tools

- **ESLint** (`.eslintrc.js`)
  - Airbnb style guide with browser/Node.js environment
  - Jest globals recognized
  - Strict rules for unused variables

- **Prettier** (`.prettierrc`)
  - Print width: 100 characters
  - Single quotes, trailing commas (ES5 style)
  - 2-space indentation

- **EditorConfig** (`.editorconfig`)
  - Ensures consistent formatting across editors

## Test Coverage

The test suite (`script.test.js`) covers:

### Utility Functions
- `formatFileSize()` - File size formatting with various units
- `escapeHtml()` - XSS protection through HTML escaping
- `formatDate()` - Date formatting with error handling
- `formatDateTime()` - DateTime formatting
- `safeEncodeURI()` - Safe URI encoding

### Storage Management
- `getLastTab()` / `saveLastTab()` - Tab persistence
- `getLastPaper()` / `saveLastPaper()` - Paper selection persistence
- Error handling for storage failures

### Error Handling
- `AppError` class - Custom error with context
- `handleApiError()` - API error normalization

### Content Rendering
- `renderAnalysisSection()` - Analysis content rendering with XSS protection

## Installation & First Run

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Run tests**:
   ```bash
   npm test
   ```

3. **Check coverage**:
   ```bash
   npm run test:coverage
   ```

4. **Format and lint code**:
   ```bash
   npm run format
   npm run lint:fix
   ```

## Future Enhancements

Potential areas for test expansion:
- DOM manipulation functions (switchTab, selectFile, etc.)
- API integration tests with mocked fetch
- Chart.js rendering tests
- File upload and JSONL parsing
- Event handler tests
- Integration tests with mock backend

## CI/CD Integration

These npm scripts can be integrated into CI/CD pipelines:
```bash
npm run lint && npm run test:coverage
```

Generates coverage reports suitable for codecov, SonarQube, or similar tools.
