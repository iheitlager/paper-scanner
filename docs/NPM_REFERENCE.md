# NPM & Testing Quick Reference

## Installation
```bash
npm install
```

## Run Tests
```bash
npm test              # Run all tests once
npm run test:watch   # Watch mode (re-run on changes)
npm run test:coverage # Generate coverage reports
```

## Code Quality
```bash
npm run lint         # Check code for issues
npm run lint:fix     # Automatically fix issues
npm run format       # Format all code
npm run format:check # Check formatting
```

## Test Results ✅
- **Total Tests**: 41
- **Passing**: 41 ✅
- **Coverage**: Utility functions, storage, errors, rendering
- **Execution Time**: ~0.6 seconds

## Configuration Files
| File | Purpose |
|------|---------|
| `package.json` | Project dependencies & scripts |
| `jest.config.js` | Test framework configuration |
| `jest.setup.js` | Test environment setup & mocks |
| `.babelrc` | JavaScript transpiler config |
| `.eslintrc.js` | Code linting rules |
| `.prettierrc` | Code formatting rules |
| `.editorconfig` | Editor consistency settings |
| `.npmignore` | Files excluded from npm |

## Test Coverage
- ✅ formatFileSize (6 tests)
- ✅ escapeHtml (6 tests) - XSS prevention
- ✅ formatDate (3 tests)
- ✅ formatDateTime (3 tests)
- ✅ safeEncodeURI (3 tests)
- ✅ Storage functions (7 tests)
- ✅ Error handling (4 tests)
- ✅ Content rendering (9 tests)

## Quick Troubleshooting
```bash
# Tests fail after code changes
npm test

# Fix linting issues
npm run lint:fix

# Auto-format code
npm run format

# Full quality check
npm run lint && npm test:coverage
```

## Documentation Files
- `README_NPM.md` - Complete setup guide
- `TESTING.md` - Testing framework details
- `SETUP_SUMMARY.md` - Setup overview
- `script.test.js` - 41 tests with documentation

## Node Info
- Node: v25.2.1
- NPM: 11.6.2
- Total Dependencies: 617 packages
- Dev Dependencies: 7 main tools

## Status
✅ All 41 tests passing  
✅ ESLint configured  
✅ Prettier configured  
✅ Jest configured  
✅ Ready for CI/CD integration
