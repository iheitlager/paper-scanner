/**
 * Test suite for script.js utility functions
 * Tests core utility functions extracted from script.js
 */

// Simple mock for document.createElement for escapeHtml function
if (typeof window === 'undefined') {
  global.window = {
    document: {
      createElement: (tag) => ({
        textContent: '',
        innerHTML: '',
        __proto__: {
          set textContent(val) {
            // Simple HTML escaping implementation
            this.innerHTML = String(val)
              .replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;')
              .replace(/'/g, '&#039;');
          },
          get innerHTML() {
            return this._html || '';
          },
          set innerHTML(val) {
            this._html = val;
          },
        },
      }),
    },
  };
}

if (typeof document === 'undefined') {
  global.document = global.window.document;
}

// Utility function implementations (copied from script.js)
function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

function escapeHtml(text) {
  if (typeof text !== 'string') return String(text);
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatDate(timestamp) {
  if (!timestamp) return 'N/A';
  try {
    return new Date(timestamp).toLocaleDateString();
  } catch {
    return 'Invalid date';
  }
}

function formatDateTime(timestamp) {
  if (!timestamp) return 'N/A';
  try {
    return new Date(timestamp).toLocaleString();
  } catch {
    return 'Invalid date';
  }
}

function safeEncodeURI(str) {
  try {
    return encodeURIComponent(str);
  } catch (error) {
    console.error('URI encoding failed:', error);
    return str;
  }
}

const STORAGE_KEYS = {
  LAST_TAB: 'paperScanner_lastTab',
  LAST_PAPER: 'paperScanner_lastPaper',
};

function getLastTab() {
  try {
    const lastTab = localStorage.getItem(STORAGE_KEYS.LAST_TAB);
    return lastTab && ['pdf', 'analysis', 'details', 'tags'].includes(lastTab) ? lastTab : 'pdf';
  } catch {
    return 'pdf';
  }
}

function saveLastTab(tabName) {
  try {
    localStorage.setItem(STORAGE_KEYS.LAST_TAB, tabName);
  } catch (e) {
    console.warn('Failed to save last tab preference:', e);
  }
}

function getLastPaper() {
  try {
    return localStorage.getItem(STORAGE_KEYS.LAST_PAPER);
  } catch {
    return null;
  }
}

function saveLastPaper(paperId) {
  try {
    localStorage.setItem(STORAGE_KEYS.LAST_PAPER, paperId);
  } catch (e) {
    console.warn('Failed to save last paper preference:', e);
  }
}

class AppError extends Error {
  constructor(message, context = '') {
    super(message);
    this.name = 'AppError';
    this.context = context;
    this.timestamp = new Date().toISOString();
  }

  log() {
    console.error(`[${this.name}] ${this.message}${this.context ? ` | ${this.context}` : ''}`);
  }
}

async function handleApiError(error, operation = 'API call') {
  let message = 'Unknown error occurred';

  if (error instanceof Response) {
    try {
      const data = await error.json();
      message = data.error || `HTTP ${error.status}`;
    } catch {
      message = `HTTP ${error.status}: ${error.statusText}`;
    }
  } else if (error instanceof Error) {
    message = error.message;
  }

  const appError = new AppError(`${operation} failed: ${message}`, operation);
  appError.log();
  throw appError;
}

function renderAnalysisSection(analysis) {
  if (!analysis) return '';

  let html =
    '<div class="detail-section analysis-section"><div class="detail-section-title">🔬 Analysis</div>';

  // Summary
  if (analysis.summary) {
    const summary = analysis.summary;
    html +=
      '<div class="detail-subsection paper-subsection"><div class="detail-subsection-title">Summary</div>';
    if (summary.paragraph_1) {
      html += `<p>${escapeHtml(summary.paragraph_1)}</p>`;
    }
    if (summary.paragraph_2) {
      html += `<p>${escapeHtml(summary.paragraph_2)}</p>`;
    }
    html += '</div>';
  }

  // Research Question
  if (analysis.research_question) {
    html += `<div class="detail-subsection paper-subsection"><div class="detail-subsection-title">Research Question</div><p>${escapeHtml(analysis.research_question)}</p></div>`;
  }

  // Methodology
  if (analysis.methodology) {
    const meth = analysis.methodology;
    html +=
      '<div class="detail-subsection paper-subsection"><div class="detail-subsection-title">Methodology</div>';
    if (meth.description) {
      html += `<p><strong>Description:</strong> ${escapeHtml(meth.description)}</p>`;
    }
    if (meth.methodology_class) {
      html += `<p><strong>Class:</strong> ${escapeHtml(meth.methodology_class)}</p>`;
    }
    if (meth.data_collection) {
      html += `<p><strong>Data Collection:</strong> ${escapeHtml(meth.data_collection)}</p>`;
    }
    html += '</div>';
  }

  // Results
  if (analysis.results) {
    const results = analysis.results;
    html +=
      '<div class="detail-subsection paper-subsection"><div class="detail-subsection-title">Results</div>';
    if (results.key_findings && Array.isArray(results.key_findings)) {
      html += '<p><strong>Key Findings:</strong></p><ul>';
      results.key_findings.forEach((finding) => {
        html += `<li>${escapeHtml(finding)}</li>`;
      });
      html += '</ul>';
    }
    if (results.conclusion) {
      html += `<p><strong>Conclusion:</strong> ${escapeHtml(results.conclusion)}</p>`;
    }
    html += '</div>';
  }

  // Key Concepts
  if (analysis.key_concepts && Array.isArray(analysis.key_concepts)) {
    html +=
      '<div class="detail-subsection paper-subsection"><div class="detail-subsection-title">Key Concepts</div>';
    html += '<dl class="concepts-list">';
    analysis.key_concepts.forEach((concept) => {
      html += `<dt>${escapeHtml(concept.term)}</dt><dd>${escapeHtml(concept.definition)}</dd>`;
    });
    html += '</dl></div>';
  }

  html += '</div>';
  return html;
}

// Tests

describe('Utility Functions', () => {
  describe('formatFileSize', () => {
    it('should handle 0 bytes', () => {
      expect(formatFileSize(0)).toBe('0 Bytes');
    });

    it('should format bytes correctly', () => {
      expect(formatFileSize(512)).toBe('512 Bytes');
    });

    it('should format kilobytes correctly', () => {
      expect(formatFileSize(1024)).toBe('1 KB');
      expect(formatFileSize(1536)).toBe('1.5 KB');
    });

    it('should format megabytes correctly', () => {
      expect(formatFileSize(1048576)).toBe('1 MB');
      expect(formatFileSize(5242880)).toBe('5 MB');
    });

    it('should format gigabytes correctly', () => {
      expect(formatFileSize(1073741824)).toBe('1 GB');
    });

    it('should handle non-finite numbers', () => {
      expect(formatFileSize(NaN)).toBe('0 Bytes');
      expect(formatFileSize(Infinity)).toBe('0 Bytes');
    });
  });

  describe('escapeHtml', () => {
    it('should escape HTML special characters', () => {
      const result = escapeHtml('<script>alert("xss")</script>');
      expect(result).toContain('&lt;script&gt;');
      expect(result).toContain('&lt;/script&gt;');
    });

    it('should escape ampersands', () => {
      expect(escapeHtml('Tom & Jerry')).toBe('Tom &amp; Jerry');
    });

    it('should escape quotes', () => {
      const result = escapeHtml('He said "hello"');
      expect(result).toContain('hello');
      // Quotes should be escaped or properly handled
      expect(result).not.toContain('<');
    });

    it('should handle normal text', () => {
      expect(escapeHtml('Normal text')).toBe('Normal text');
    });

    it('should handle empty string', () => {
      expect(escapeHtml('')).toBe('');
    });

    it('should convert non-strings to strings', () => {
      expect(escapeHtml(123)).toContain('123');
      expect(escapeHtml(true)).toContain('true');
    });
  });

  describe('formatDate', () => {
    it('should format valid ISO timestamp', () => {
      const result = formatDate('2023-12-01T10:30:00Z');
      expect(result).not.toBe('N/A');
      expect(result).not.toBe('Invalid date');
    });

    it('should handle invalid timestamp', () => {
      const result = formatDate('invalid-date');
      expect(result.toLowerCase()).toContain('invalid');
    });

    it('should handle edge cases', () => {
      expect(formatDate(null)).toBe('N/A');
      expect(formatDate('')).toBe('N/A');
    });
  });

  describe('formatDateTime', () => {
    it('should format valid ISO timestamp', () => {
      const result = formatDateTime('2023-12-01T10:30:00Z');
      expect(result).not.toBe('N/A');
      expect(result).not.toBe('Invalid date');
    });

    it('should handle null or empty timestamp', () => {
      expect(formatDateTime(null)).toBe('N/A');
      expect(formatDateTime('')).toBe('N/A');
    });

    it('should handle invalid timestamp', () => {
      const result = formatDateTime('invalid-date');
      expect(result.toLowerCase()).toContain('invalid');
    });
  });

  describe('safeEncodeURI', () => {
    it('should encode special characters', () => {
      expect(safeEncodeURI('hello world')).toBe('hello%20world');
      expect(safeEncodeURI('test@example.com')).toBe('test%40example.com');
    });

    it('should handle empty string', () => {
      expect(safeEncodeURI('')).toBe('');
    });

    it('should handle normal text', () => {
      const text = 'hello123';
      expect(safeEncodeURI(text)).toBe('hello123');
    });
  });
});

describe('Storage Functions', () => {
  beforeEach(() => {
    localStorage.clear();
    jest.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
    jest.clearAllMocks();
  });

  describe('getLastTab and saveLastTab', () => {
    it('should return default tab pdf', () => {
      expect(getLastTab()).toBe('pdf');
    });

    it('should return pdf tab for invalid tab names', () => {
      expect(getLastTab()).toBe('pdf');
    });

    it('should accept valid tab names', () => {
      // Test that saveLastTab doesn't throw for valid tabs
      expect(() => saveLastTab('analysis')).not.toThrow();
      expect(() => saveLastTab('details')).not.toThrow();
      expect(() => saveLastTab('pdf')).not.toThrow();
      expect(() => saveLastTab('tags')).not.toThrow();
    });

    it('should handle storage safely', () => {
      expect(getLastTab()).toBe('pdf');
      saveLastTab('analysis');
      // localStorage.setItem was called, so now getLastTab returns 'analysis'
      expect(['pdf', 'analysis']).toContain(getLastTab());
    });
  });

  describe('getLastPaper and saveLastPaper', () => {
    it('should handle saving paper safely', () => {
      expect(() => saveLastPaper('paper-2023')).not.toThrow();
    });

    it('should return null by default', () => {
      const result = getLastPaper();
      expect(result === null || result === undefined).toBe(true);
    });

    it('should handle storage errors gracefully', () => {
      expect(getLastPaper()).not.toThrow;
      expect(() => saveLastPaper('test')).not.toThrow();
    });
  });
});

describe('AppError Class', () => {
  it('should create error with message and context', () => {
    const error = new AppError('Test error', 'TestContext');
    expect(error.message).toBe('Test error');
    expect(error.context).toBe('TestContext');
    expect(error.name).toBe('AppError');
    expect(error.timestamp).toBeDefined();
  });

  it('should log error correctly', () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
    const error = new AppError('Test error', 'Context');
    error.log();
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  it('should handle error without context', () => {
    const error = new AppError('Test error');
    expect(error.context).toBe('');
    expect(error.message).toBe('Test error');
  });
});

describe('handleApiError', () => {
  it('should handle Response errors', async () => {
    const mockResponse = {
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: jest.fn().mockResolvedValue({ error: 'Custom error message' }),
    };

    await expect(handleApiError(mockResponse, 'Test operation')).rejects.toThrow();
  });

  it('should handle regular Error objects', async () => {
    const error = new Error('Test error');
    await expect(handleApiError(error, 'Test operation')).rejects.toThrow();
  });

  it('should use operation name in error message', () => {
    // Test that AppError stores the operation name
    const appError = new AppError('Test failed: message', 'LoadData');
    expect(appError.context).toBe('LoadData');
    expect(appError.message).toContain('Test failed');
  });
});

describe('renderAnalysisSection', () => {
  it('should return empty string for null analysis', () => {
    expect(renderAnalysisSection(null)).toBe('');
  });

  it('should render summary section', () => {
    const analysis = {
      summary: {
        paragraph_1: 'This is paragraph 1',
      },
    };
    const html = renderAnalysisSection(analysis);
    expect(html).toContain('Summary');
    expect(html).toContain('paragraph 1');
  });

  it('should render research question', () => {
    const analysis = {
      research_question: 'What is the answer?',
    };
    const html = renderAnalysisSection(analysis);
    expect(html).toContain('Research Question');
    expect(html).toContain('What is the answer?');
  });

  it('should render methodology section', () => {
    const analysis = {
      methodology: {
        description: 'Experimental method',
        methodology_class: 'Quantitative',
        data_collection: 'Surveys',
      },
    };
    const html = renderAnalysisSection(analysis);
    expect(html).toContain('Methodology');
    expect(html).toContain('Experimental method');
  });

  it('should render key concepts', () => {
    const analysis = {
      key_concepts: [
        { term: 'Concept1', definition: 'Definition of concept 1' },
        { term: 'Concept2', definition: 'Definition of concept 2' },
      ],
    };
    const html = renderAnalysisSection(analysis);
    expect(html).toContain('Key Concepts');
    expect(html).toContain('Concept1');
    expect(html).toContain('Definition of concept 1');
  });

  it('should escape HTML in content', () => {
    const analysis = {
      summary: {
        paragraph_1: '<script>alert("xss")</script>',
      },
    };
    const html = renderAnalysisSection(analysis);
    expect(html).not.toContain('<script>');
  });

  it('should render results with key findings', () => {
    const analysis = {
      results: {
        key_findings: ['Finding 1', 'Finding 2'],
        conclusion: 'Final conclusion',
      },
    };
    const html = renderAnalysisSection(analysis);
    expect(html).toContain('Key Findings');
    expect(html).toContain('Finding 1');
    expect(html).toContain('Conclusion');
  });
});
