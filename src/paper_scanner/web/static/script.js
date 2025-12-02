/**
 * PDF Browser Application
 * Handles PDF file browsing, loading, and metadata display
 */

// Type definitions (using JSDoc for documentation)
/**
 * @typedef {Object} PDFFile
 * @property {number} id - Database ID
 * @property {string} file_path - Full file path
 * @property {string} file_name - File name
 * @property {string} directory - Directory path
 * @property {string} relative_path - Relative path
 * @property {number} size_bytes - File size in bytes
 * @property {string} created_time - Creation timestamp
 * @property {string} modified_time - Modification timestamp
 * @property {string} accessed_time - Access timestamp
 * @property {string} [tags] - Colon-separated tags
 */

/**
 * @typedef {Object} APIResponse
 * @property {boolean} success - Operation success status
 * @property {string} [error] - Error message if failed
 * @property {*} [data] - Response data
 */

// Application state
let files = [];
let currentFile = null;
let selectedFile = null;
let currentTab = 'pdf';
let isLoading = false;
let allTags = [];
let yearData = [];
let currentView = 'overview'; // 'overview', 'papers-list', or 'paper-detail'
let selectedYear = null;
let yearChart = null;

// Storage keys for localStorage
const STORAGE_KEYS = {
  LAST_TAB: 'paperScanner_lastTab',
  LAST_PAPER: 'paperScanner_lastPaper',
};

/**
 * Load last active tab from localStorage
 * @returns {string} Tab name or 'pdf' as default
 */
function getLastTab() {
  try {
    const lastTab = localStorage.getItem(STORAGE_KEYS.LAST_TAB);
    return lastTab && ['pdf', 'analysis', 'details', 'tags'].includes(lastTab) ? lastTab : 'pdf';
  } catch {
    return 'pdf';
  }
}

/**
 * Save current tab to localStorage
 * @param {string} tabName - Tab name to save
 */
function saveLastTab(tabName) {
  try {
    localStorage.setItem(STORAGE_KEYS.LAST_TAB, tabName);
  } catch (e) {
    console.warn('Failed to save last tab preference:', e);
  }
}

/**
 * Load last viewed paper from localStorage
 * @returns {string|null} Paper identifier (citekey or file_name) or null
 */
function getLastPaper() {
  try {
    return localStorage.getItem(STORAGE_KEYS.LAST_PAPER);
  } catch {
    return null;
  }
}

/**
 * Save current paper to localStorage
 * @param {string} paperId - Paper identifier (citekey or file_name)
 */
function saveLastPaper(paperId) {
  try {
    localStorage.setItem(STORAGE_KEYS.LAST_PAPER, paperId);
  } catch (e) {
    console.warn('Failed to save last paper preference:', e);
  }
}

// Error handling utility
class AppError extends Error {
  /**
   * @param {string} message - Error message
   * @param {string} [context] - Additional context
   */
  constructor(message, context = '') {
    super(message);
    this.name = 'AppError';
    this.context = context;
    this.timestamp = new Date().toISOString();
  }

  /**
   * Log error with context
   */
  log() {
    console.error(`[${this.name}] ${this.message}${this.context ? ` | ${this.context}` : ''}`);
  }
}

/**
 * Handle API errors consistently
 * @param {Error|Response} error - Error or response object
 * @param {string} [operation] - Operation name for context
 * @throws {AppError}
 */
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

// Utility functions for formatting

/**
 * Format file size for display
 * @param {number} bytes - File size in bytes
 * @returns {string} Formatted file size
 */
function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Format date for display
 * @param {string|null} timestamp - ISO timestamp string
 * @returns {string} Formatted date
 */
function formatDate(timestamp) {
  if (!timestamp) return 'N/A';
  try {
    return new Date(timestamp).toLocaleDateString();
  } catch {
    return 'Invalid date';
  }
}

/**
 * Format date and time for display
 * @param {string|null} timestamp - ISO timestamp string
 * @returns {string} Formatted date and time
 */
function formatDateTime(timestamp) {
  if (!timestamp) return 'N/A';
  try {
    return new Date(timestamp).toLocaleString();
  } catch {
    return 'Invalid date';
  }
}

/**
 * Safely encode URI component
 * @param {string} str - String to encode
 * @returns {string} Encoded string
 */
function safeEncodeURI(str) {
  try {
    return encodeURIComponent(str);
  } catch (error) {
    console.error('URI encoding failed:', error);
    return str;
  }
}

// Tab management

/**
 * Render analysis section from parsed analysis data
 * @param {Object} analysis - Analysis object containing paper analysis
 * @returns {string} HTML string for analysis section
 */
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

// Tab management

/**
 * Switch between PDF and Details tabs
 * @param {string} tabName - Tab name ('pdf', 'analysis', 'details' or 'tags')
 */
function switchTab(tabName) {
  if (!['pdf', 'analysis', 'details', 'tags'].includes(tabName)) {
    console.error(`Invalid tab name: ${tabName}`);
    return;
  }

  currentTab = tabName;
  saveLastTab(tabName);

  // Update URL to reflect current tab
  if (currentFile) {
    const paperId = currentFile.citekey || currentFile.file_name;
    const newUrl = `${window.location.pathname}?paper=${encodeURIComponent(paperId)}&tab=${tabName}`;
    window.history.replaceState({ tab: tabName }, '', newUrl);
  }

  // Update tab buttons
  document.getElementById('pdfTabBtn').classList.remove('active');
  document.getElementById('analysisTabBtn').classList.remove('active');
  document.getElementById('detailsTabBtn').classList.remove('active');
  document.getElementById('tagsTabBtn').classList.remove('active');

  if (tabName === 'pdf') {
    document.getElementById('pdfTabBtn').classList.add('active');
  } else if (tabName === 'analysis') {
    document.getElementById('analysisTabBtn').classList.add('active');
  } else if (tabName === 'details') {
    document.getElementById('detailsTabBtn').classList.add('active');
  } else {
    document.getElementById('tagsTabBtn').classList.add('active');
  }

  // Update tab panes
  document.getElementById('pdfTab').classList.remove('active');
  document.getElementById('analysisTab').classList.remove('active');
  document.getElementById('detailsTab').classList.remove('active');
  document.getElementById('tagsTab').classList.remove('active');

  if (tabName === 'pdf') {
    document.getElementById('pdfTab').classList.add('active');
  } else if (tabName === 'analysis') {
    document.getElementById('analysisTab').classList.add('active');
  } else if (tabName === 'details') {
    document.getElementById('detailsTab').classList.add('active');
  } else {
    document.getElementById('tagsTab').classList.add('active');
  }

  // Load content if switching to analysis, details, or tags tab and we have a file
  if (tabName === 'analysis' && currentFile) {
    loadFileAnalysis(currentFile.file_name);
  } else if (tabName === 'details' && currentFile) {
    loadFileDetails(currentFile.file_name);
  } else if (tabName === 'tags' && currentFile) {
    loadTagsEditor(currentFile.file_name);
  }
}

/**
 * Go back to overview from any view
 */
function goBackToOverview() {
  currentView = 'overview';
  selectedYear = null;
  currentFile = null;

  // Clean the query string
  const baseUrl = window.location.pathname;
  window.history.replaceState({}, '', baseUrl);

  // Hide breadcrumb
  document.getElementById('toolbarBreadcrumb').style.display = 'none';

  // Hide toolbar and tabs
  document.querySelector('.toolbar').style.display = 'none';
  document.getElementById('tabNavigation').style.display = 'none';

  // Show overview tab
  document.getElementById('overviewTab').classList.add('active');
  document.getElementById('papersListTab').classList.remove('active');
  document.getElementById('pdfTab').classList.remove('active');
  document.getElementById('analysisTab').classList.remove('active');
  document.getElementById('detailsTab').classList.remove('active');
  document.getElementById('tagsTab').classList.remove('active');

  // Load and display year overview
  loadYearOverview();
}

/**
 * Load and display year overview with histogram
 */
async function loadYearOverview() {
  try {
    const response = await fetch('/api/year-overview');

    if (!response.ok) {
      await handleApiError(response, 'Load year overview');
    }

    const data = await response.json();

    if (!data.success) {
      throw new AppError(data.error || 'Failed to load year overview', 'Year overview');
    }

    yearData = data.years || [];
    renderYearHistogram();
  } catch (error) {
    if (error instanceof AppError) {
      error.log();
    } else {
      console.error('Unexpected error loading year overview:', error);
    }

    const viewer = document.getElementById('overviewViewer');
    const errorMsg = error instanceof AppError ? error.message : error.message;
    viewer.innerHTML = `<div class="status-message">Error: ${escapeHtml(errorMsg)}</div>`;
  }
}

/**
 * Render year histogram using Chart.js
 */
function renderYearHistogram() {
  if (!yearData || yearData.length === 0) {
    const viewer = document.getElementById('overviewViewer');
    viewer.innerHTML = '<div class="status-message">No papers with publication years found</div>';
    return;
  }

  // Sort by year for better display
  const sortedData = yearData.sort((a, b) => (a.year || 0) - (b.year || 0));

  const years = sortedData.map((y) => y.year || 'Unknown');
  const counts = sortedData.map((y) => y.count || 0);

  const viewer = document.getElementById('overviewViewer');
  viewer.innerHTML = `
        <div class="histogram-container">
            <h2 class="histogram-title">📊 Papers by Publication Year</h2>
            <canvas id="yearHistogramCanvas"></canvas>
            <div class="histogram-info">Click on a bar to view papers from that year</div>
        </div>
    `;

  // Create chart
  const ctx = document.getElementById('yearHistogramCanvas').getContext('2d');

  if (yearChart) {
    yearChart.destroy();
  }

  yearChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: years,
      datasets: [
        {
          label: 'Number of Papers',
          data: counts,
          backgroundColor: 'rgba(14, 99, 156, 0.8)',
          borderColor: 'rgba(14, 99, 156, 1)',
          borderWidth: 2,
          hoverBackgroundColor: 'rgba(17, 119, 187, 1)',
          borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      indexAxis: 'x',
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          backgroundColor: 'rgba(0,0,0,0.8)',
          titleColor: '#fff',
          bodyColor: '#e0e0e0',
          borderColor: '#0e639c',
          borderWidth: 1,
          callbacks: {
            label: function (context) {
              return context.parsed.y + ' papers';
            },
          },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            stepSize: 1,
            color: '#858585',
          },
          grid: {
            color: 'rgba(62, 62, 66, 0.3)',
          },
        },
        x: {
          ticks: {
            color: '#858585',
          },
          grid: {
            display: false,
          },
        },
      },
      onClick: function (event, activeElements) {
        if (activeElements.length > 0) {
          const index = activeElements[0].index;
          const year = sortedData[index].year;
          showPapersForYear(year);
        }
      },
    },
  });
}

/**
 * Show papers for selected year
 * @param {number} year - Publication year
 */
async function showPapersForYear(year) {
  selectedYear = year;
  currentView = 'papers-list';

  // Show breadcrumb in toolbar for papers list
  const paperListBreadcrumb = document.getElementById('paperListBreadcrumb');
  if (paperListBreadcrumb) {
    paperListBreadcrumb.style.display = 'flex';
    const breadcrumbCurrent = document.getElementById('breadcrumbCurrent');
    if (breadcrumbCurrent) {
      breadcrumbCurrent.innerHTML = `${year} (${year ? yearData.find((y) => y.year === year)?.count || 0 : '?'} papers)`;
    }
  }

  // Clear title/author info from toolbar
  const currentAuthors = document.getElementById('currentAuthors');
  if (currentAuthors) currentAuthors.innerHTML = '';
  const currentFileName = document.getElementById('currentFileName');
  if (currentFileName) currentFileName.innerHTML = '';
  const fileInfo = document.getElementById('fileInfo');
  if (fileInfo) fileInfo.innerHTML = '';

  // Hide toolbar and tabs
  const toolbar = document.querySelector('.toolbar');
  if (toolbar) toolbar.style.display = 'flex';
  const tabNav = document.getElementById('tabNavigation');
  if (tabNav) tabNav.style.display = 'none';

  // Switch to papers list tab
  const overviewTab = document.getElementById('overviewTab');
  if (overviewTab) overviewTab.classList.remove('active');
  const papersListTab = document.getElementById('papersListTab');
  if (papersListTab) papersListTab.classList.add('active');
  const pdfTab = document.getElementById('pdfTab');
  if (pdfTab) pdfTab.classList.remove('active');
  const analysisTab = document.getElementById('analysisTab');
  if (analysisTab) analysisTab.classList.remove('active');
  const detailsTab = document.getElementById('detailsTab');
  if (detailsTab) detailsTab.classList.remove('active');
  const tagsTab = document.getElementById('tagsTab');
  if (tagsTab) tagsTab.classList.remove('active');

  // Get papers for this year
  const yearEntry = yearData.find((y) => y.year === year);
  if (!yearEntry || !yearEntry.papers) {
    const viewer = document.getElementById('papersListViewer');
    viewer.innerHTML = '<div class="status-message">No papers found for this year</div>';
    return;
  }

  renderPapersList(yearEntry.papers);
}

/**
 * Render list of papers for selected year
 * @param {Array} papers - Array of paper objects
 */
function renderPapersList(papers) {
  const viewer = document.getElementById('papersListViewer');

  if (!papers || papers.length === 0) {
    viewer.innerHTML = '<div class="status-message">No papers found</div>';
    return;
  }

  const papersList = papers
    .map((paper, idx) => {
      const displayName = paper.citekey || paper.file_name || `Paper ${idx + 1}`;
      const title = paper.title || paper.file_name || 'Untitled';

      return `
            <div class="paper-list-item" onclick="selectPaperFromList('${escapeHtml(paper.file_name || '')}')" title="Click to view details">
                <div class="paper-list-item-header">
                    <div class="paper-list-item-name">${escapeHtml(displayName)}</div>
                </div>
                <div class="paper-list-item-title">${escapeHtml(title)}</div>
            </div>
        `;
    })
    .join('');

  viewer.innerHTML = `
        <div class="papers-list-container">
            <h2 class="papers-list-title">Papers from ${selectedYear}</h2>
            <div class="papers-list">
                ${papersList}
            </div>
        </div>
    `;
}

/**
 * Select a paper from the list and load its details
 * @param {string} fileName - File name of the paper
 */
async function selectPaperFromList(fileName) {
  if (!fileName) {
    console.error('Invalid file name');
    return;
  }

  // Find the paper in files array
  let paper = files.find((f) => f.file_name === fileName);

  if (!paper) {
    // Load all files if not found
    await loadFiles();
    paper = files.find((f) => f.file_name === fileName);
  }

  if (!paper) {
    alert('Paper not found');
    return;
  }

  // Set current file and switch to paper detail view
  currentFile = paper;
  currentView = 'paper-detail';

  // Show toolbar and tabs
  const toolbar = document.querySelector('.toolbar');
  if (toolbar) toolbar.style.display = 'flex';
  const tabNav = document.getElementById('tabNavigation');
  if (tabNav) tabNav.style.display = 'flex';

  // Clear the second part of breadcrumb when viewing paper from papers list
  const breadcrumbCurrent = document.getElementById('breadcrumbCurrent');
  if (breadcrumbCurrent) breadcrumbCurrent.innerHTML = '';

  // Switch to PDF tab
  switchTabToPaper();

  // Display the paper (with flag to keep breadcrumb from papers list)
  selectFile(paper, true);
}

/**
 * Switch to paper detail view (PDF tab)
 */
function switchTabToPaper() {
  currentTab = 'pdf';
  saveLastTab('pdf');

  // Update tab buttons
  document.getElementById('pdfTabBtn').classList.add('active');
  document.getElementById('analysisTabBtn').classList.remove('active');
  document.getElementById('detailsTabBtn').classList.remove('active');
  document.getElementById('tagsTabBtn').classList.remove('active');

  // Update tab panes
  document.getElementById('overviewTab').classList.remove('active');
  document.getElementById('papersListTab').classList.remove('active');
  document.getElementById('pdfTab').classList.add('active');
  document.getElementById('analysisTab').classList.remove('active');
  document.getElementById('detailsTab').classList.remove('active');
  document.getElementById('tagsTab').classList.remove('active');
}

/**
 * Copy deeplink to current paper to clipboard
 */
function copyDeeplink() {
  if (!currentFile) {
    alert('Please select a paper first');
    return;
  }

  // Use citekey if available, otherwise file_name
  const paperId = currentFile.citekey || currentFile.file_name;
  const baseUrl = window.location.origin + window.location.pathname;
  const deeplinkUrl = `${baseUrl}?paper=${encodeURIComponent(paperId)}`;

  // Copy to clipboard
  navigator.clipboard
    .writeText(deeplinkUrl)
    .then(() => {
      // Show success feedback
      const btn = document.getElementById('deeplinkBtn');
      const origText = btn.textContent;
      btn.textContent = '✓ Copied!';
      btn.style.backgroundColor = 'var(--success-text)';

      setTimeout(() => {
        btn.textContent = origText;
        btn.style.backgroundColor = '';
      }, 2000);
    })
    .catch((err) => {
      console.error('Failed to copy deeplink:', err);
      alert('Failed to copy link to clipboard');
    });
}

/**
 * Load and display file analysis
 * @param {string} fileName - Name of the PDF file
 * @returns {Promise<void>}
 */
async function loadFileAnalysis(fileName) {
  try {
    const response = await fetch(`/api/file_details/${safeEncodeURI(fileName)}`);

    if (!response.ok) {
      await handleApiError(response, 'Load file analysis');
    }

    const data = await response.json();

    if (!data.success) {
      throw new AppError(data.error || 'Unknown error', 'File analysis');
    }

    const details = data.details;
    const viewer = document.getElementById('analysisViewer');

    // Parse analysis JSON if present
    let analysisHtml = '';
    if (details.analysis) {
      try {
        const analysis =
          typeof details.analysis === 'string' ? JSON.parse(details.analysis) : details.analysis;

        analysisHtml = renderAnalysisSection(analysis);
      } catch (e) {
        console.error('Error parsing analysis:', e);
        analysisHtml = '<div class="status-message">Error: Could not parse analysis data</div>';
      }
    } else {
      analysisHtml = '<div class="status-message">No analysis data available for this PDF</div>';
    }

    const viewerHtml = `
            <div class="analysis-container">
                ${analysisHtml}
            </div>
        `;

    viewer.innerHTML = viewerHtml;
  } catch (error) {
    if (error instanceof AppError) {
      error.log();
    } else {
      console.error('Unexpected error loading analysis:', error);
    }

    const viewer = document.getElementById('analysisViewer');
    const errorMsg = error instanceof AppError ? error.message : error.message;
    viewer.innerHTML = `<div class="status-message">Error: ${escapeHtml(errorMsg)}</div>`;
  }
}

/**
 * Load and display file details
 * @param {string} fileName - Name of the PDF file
 * @returns {Promise<void>}
 */
async function loadFileDetails(fileName) {
  try {
    const response = await fetch(`/api/file_details/${safeEncodeURI(fileName)}`);

    if (!response.ok) {
      await handleApiError(response, 'Load file details');
    }

    const data = await response.json();

    if (!data.success) {
      throw new AppError(data.error || 'Unknown error', 'File details');
    }

    const details = data.details;
    const viewer = document.getElementById('detailsViewer');

    // Parse tags if present
    const tags = details.tags ? details.tags.split(':').filter((t) => t.trim()) : [];
    const tagsHtml =
      tags.length > 0
        ? `<div class="detail-row">
                    <div class="detail-label">Tags</div>
                    <div class="detail-value tags-display">
                        ${tags.map((tag) => `<span class="tag-chip">${escapeHtml(tag)}</span>`).join('')}
                    </div>
                </div>`
        : '';

    // Parse title-details JSON if present
    let bibliographicHtml = '';
    if (details.title_details) {
      try {
        const bib =
          typeof details.title_details === 'string'
            ? JSON.parse(details.title_details)
            : details.title_details;

        bibliographicHtml = `
                    <div class="detail-section">
                        <div class="detail-section-title">📚 Bibliographic Details</div>
                        <div class="detail-row">
                            <div class="detail-label">Title</div>
                            <div class="detail-value">${escapeHtml(bib.title || 'N/A')}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Citation Key</div>
                            <div class="detail-value code-value">${escapeHtml(bib.citekey || 'N/A')}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Authors</div>
                            <div class="detail-value">${bib.authors && Array.isArray(bib.authors) ? escapeHtml(bib.authors.join('; ')) : 'N/A'}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Year</div>
                            <div class="detail-value">${escapeHtml(bib.year || 'N/A')}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Journal</div>
                            <div class="detail-value">${escapeHtml(bib.journal || 'N/A')}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Volume</div>
                            <div class="detail-value">${escapeHtml(bib.volume || 'N/A')}</div>
                        </div>
                        ${
                          bib.issue
                            ? `<div class="detail-row">
                            <div class="detail-label">Issue</div>
                            <div class="detail-value">${escapeHtml(bib.issue)}</div>
                        </div>`
                            : ''
                        }
                        <div class="detail-row">
                            <div class="detail-label">Pages</div>
                            <div class="detail-value">${escapeHtml(bib.pages || 'N/A')}</div>
                        </div>
                        ${
                          bib.doi
                            ? `<div class="detail-row">
                            <div class="detail-label">DOI</div>
                            <div class="detail-value code-value"><a href="https://doi.org/${escapeHtml(bib.doi)}" target="_blank">${escapeHtml(bib.doi)}</a></div>
                        </div>`
                            : ''
                        }
                        <div class="detail-row">
                            <div class="detail-label">APA Citation</div>
                            <div class="detail-value citation-value">${escapeHtml(bib.citation_apa || 'N/A')}</div>
                        </div>
                    </div>
                `;
      } catch (e) {
        console.error('Error parsing bibliographic details:', e);
      }
    }

    // Parse analysis JSON if present
    let analysisHtml = '';
    if (details.analysis) {
      try {
        const analysis =
          typeof details.analysis === 'string' ? JSON.parse(details.analysis) : details.analysis;

        analysisHtml = renderAnalysisSection(analysis);
      } catch (e) {
        console.error('Error parsing analysis:', e);
      }
    }

    const detailsHtml = `
            <div class="details-container">
                ${bibliographicHtml}
                <div class="detail-section">
                    <div class="detail-section-title">File Information</div>
                    <div class="detail-row">
                        <div class="detail-label">File Name</div>
                        <div class="detail-value">${escapeHtml(details.file_name || 'N/A')}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">File Size</div>
                        <div class="detail-value">${formatFileSize(details.size_bytes || 0)}</div>
                    </div>
                    ${tagsHtml}\n                </div>
                
                <div class="detail-section">
                    <div class="detail-section-title">Paths</div>
                    <div class="detail-row">
                        <div class="detail-label">Full Path</div>
                        <div class="detail-value">${escapeHtml(details.file_path || 'N/A')}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Directory</div>
                        <div class="detail-value">${escapeHtml(details.directory || 'N/A')}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Relative Path</div>
                        <div class="detail-value">${escapeHtml(details.relative_path || 'N/A')}</div>
                    </div>
                </div>
                
                <div class="detail-section">
                    <div class="detail-section-title">Timestamps</div>
                    <div class="detail-row">
                        <div class="detail-label">Created</div>
                        <div class="detail-value">${formatDateTime(details.created_time)}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Modified</div>
                        <div class="detail-value">${formatDateTime(details.modified_time)}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Accessed</div>
                        <div class="detail-value">${formatDateTime(details.accessed_time)}</div>
                    </div>
                </div>
                
                <div class="detail-section">
                    <div class="detail-section-title">Manage Tags</div>
                    <div class="tags-editor">
                        <input 
                            type="text" 
                            id="tagsInput" 
                            placeholder="Add tags separated by colons (e.g., tag1:tag2:tag3)"
                            value="${escapeHtml(details.tags || '')}"
                            class="tags-input"
                        />
                        <button onclick="saveTags('${escapeHtml(details.file_name)}')" class="tags-save-btn">💾 Save Tags</button>
                    </div>
                </div>
            </div>
        `;

    viewer.innerHTML = detailsHtml;
  } catch (error) {
    if (error instanceof AppError) {
      error.log();
    } else {
      console.error('Unexpected error loading details:', error);
    }

    const viewer = document.getElementById('detailsViewer');
    const errorMsg = error instanceof AppError ? error.message : error.message;
    viewer.innerHTML = `<div class="status-message">Error: ${escapeHtml(errorMsg)}</div>`;
  }
}

/**
 * Save tags for current file
 * @param {string} fileName - Name of the PDF file
 * @returns {Promise<void>}
 */
async function saveTags(fileName) {
  try {
    const tagsInput =
      document.getElementById('tagsInputField') || document.getElementById('tagsInput');
    const tags = tagsInput.value.trim();

    const response = await fetch(`/api/file_tags/${safeEncodeURI(fileName)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tags: tags }),
    });

    if (!response.ok) {
      await handleApiError(response, 'Save tags');
    }

    const data = await response.json();

    if (!data.success) {
      throw new AppError(data.error || 'Unknown error', 'Save tags');
    }

    // Update current file
    if (currentFile && currentFile.file_name === fileName) {
      currentFile.tags = tags;
    }

    // Show success message
    const button = document.querySelector('.tags-save-btn');
    if (button) {
      const origText = button.textContent;
      button.textContent = '✓ Saved!';
      setTimeout(() => {
        button.textContent = origText;
      }, 2000);
    }

    // Reload files to update list and reload editor
    await loadFiles();
    if (currentTab === 'tags') {
      await loadTagsEditor(fileName);
    }
  } catch (error) {
    if (error instanceof AppError) {
      error.log();
      alert('Error saving tags: ' + error.message);
    } else {
      console.error('Unexpected error:', error);
    }
  }
}

/**
 * Load and display tags editor
 * @param {string} fileName - Name of the PDF file
 * @returns {Promise<void>}
 */
async function loadTagsEditor(fileName) {
  try {
    const response = await fetch(`/api/file_details/${safeEncodeURI(fileName)}`);

    if (!response.ok) {
      await handleApiError(response, 'Load file details');
    }

    const data = await response.json();

    if (!data.success) {
      throw new AppError(data.error || 'Unknown error', 'File details');
    }

    const details = data.details;
    const viewer = document.getElementById('tagsViewer');

    // Parse current tags
    const tags = details.tags ? details.tags.split(':').filter((t) => t.trim()) : [];

    const tagsHtml = `
            <div class="tags-editor-container">
                <div class="tags-editor-section">
                    <h3>📝 Manage Tags for ${escapeHtml(details.file_name)}</h3>
                    
                    <div class="tags-input-area">
                        <label for="tagsInputField">Enter tags separated by colons (tag1:tag2:tag3)</label>
                        <textarea 
                            id="tagsInputField" 
                            placeholder="Add tags separated by colons&#10;Example: research:important:to-read"
                            class="tags-textarea"
                        >${escapeHtml(details.tags || '')}</textarea>
                    </div>
                    
                    <div class="tags-display-section">
                        <h4>Current Tags</h4>
                        <div class="tags-display">
                            ${
                              tags.length > 0
                                ? tags
                                    .map(
                                      (tag) => `<span class="tag-chip">${escapeHtml(tag)}</span>`
                                    )
                                    .join('')
                                : '<div class="status-message">No tags assigned yet</div>'
                            }
                        </div>
                    </div>
                    
                    <div class="tags-button-area">
                        <button onclick="saveTags('${escapeHtml(details.file_name)}')" class="tags-save-btn">💾 Save Tags</button>
                        <button onclick="clearTags('${escapeHtml(details.file_name)}')" class="tags-clear-btn">🗑️ Clear Tags</button>
                    </div>
                </div>
            </div>
        `;

    viewer.innerHTML = tagsHtml;
  } catch (error) {
    if (error instanceof AppError) {
      error.log();
    } else {
      console.error('Unexpected error loading tags editor:', error);
    }

    const viewer = document.getElementById('tagsViewer');
    const errorMsg = error instanceof AppError ? error.message : error.message;
    viewer.innerHTML = `<div class="status-message">Error: ${escapeHtml(errorMsg)}</div>`;
  }
}

/**
 * Clear tags for current file
 * @param {string} fileName - Name of the PDF file
 * @returns {Promise<void>}
 */
async function clearTags(fileName) {
  if (confirm('Are you sure you want to clear all tags for this file?')) {
    try {
      const response = await fetch(`/api/file_tags/${safeEncodeURI(fileName)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tags: '' }),
      });

      if (!response.ok) {
        await handleApiError(response, 'Clear tags');
      }

      const data = await response.json();

      if (!data.success) {
        throw new AppError(data.error || 'Unknown error', 'Clear tags');
      }

      // Update current file
      if (currentFile && currentFile.file_name === fileName) {
        currentFile.tags = '';
      }

      // Reload tags editor
      await loadTagsEditor(fileName);
      await loadFiles();
    } catch (error) {
      if (error instanceof AppError) {
        error.log();
        alert('Error clearing tags: ' + error.message);
      } else {
        console.error('Unexpected error:', error);
      }
    }
  }
}

/**
 * Escape HTML special characters to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
  if (typeof text !== 'string') return String(text);
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Modal functions

/**
 * Open file upload modal
 */
function openFileModal() {
  document.getElementById('fileModal').classList.add('show');
  selectedFile = null;
  document.getElementById('loadBtn').disabled = true;
  document.getElementById('fileInputLabel').textContent =
    '📁 Click to select JSONL file or drag & drop';
  document.getElementById('modalStatusMessage').innerHTML = '';
}

/**
 * Close file upload modal
 */
function closeFileModal() {
  document.getElementById('fileModal').classList.remove('show');
  selectedFile = null;
  document.getElementById('jsonlFileInput').value = '';
}

// Close modal when clicking outside
document.addEventListener('click', function (event) {
  const modal = document.getElementById('fileModal');
  if (event.target === modal) {
    closeFileModal();
  }
});

/**
 * Handle file selection from input
 * @param {Event} event - Change event from file input
 */
function handleFileSelect(event) {
  const file = event.target.files[0];
  if (file) {
    selectedFile = file;
    document.getElementById('fileInputLabel').textContent = '✓ ' + escapeHtml(file.name);
    document.getElementById('loadBtn').disabled = false;
  }
}

/**
 * Show status message in modal
 * @param {string} message - Status message
 * @param {string} type - Message type ('loading', 'success', or 'error')
 */
function showModalStatus(message, type) {
  const statusDiv = document.getElementById('modalStatusMessage');
  if (type === 'error') {
    statusDiv.innerHTML = `<div class="error-message">✗ ${escapeHtml(message)}</div>`;
  } else if (type === 'success') {
    statusDiv.innerHTML = `<div class="success-message">✓ ${escapeHtml(message)}</div>`;
  } else {
    statusDiv.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  }
}

// Drag and drop setup
const label = document.querySelector('.file-input-label');
if (label) {
  label.addEventListener('dragover', (e) => {
    e.preventDefault();
    label.style.borderColor = 'var(--accent-color)';
  });

  label.addEventListener('dragleave', () => {
    label.style.borderColor = 'var(--border-color)';
  });

  label.addEventListener('drop', (e) => {
    e.preventDefault();
    label.style.borderColor = 'var(--border-color)';
    if (e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      if (file.name.endsWith('.jsonl')) {
        selectedFile = file;
        document.getElementById('jsonlFileInput').files = e.dataTransfer.files;
        document.getElementById('fileInputLabel').textContent = '✓ ' + escapeHtml(file.name);
        document.getElementById('loadBtn').disabled = false;
      } else {
        showModalStatus('Please select a .jsonl file', 'error');
      }
    }
  });
}

// File loading operations

/**
 * Load JSONL file into database
 * @returns {Promise<void>}
 */
async function loadJsonLinesFile() {
  if (!selectedFile) {
    showModalStatus('Please select a file', 'error');
    return;
  }

  if (isLoading) {
    showModalStatus('Already loading a file...', 'error');
    return;
  }

  isLoading = true;
  showModalStatus('Loading file...', 'loading');

  try {
    // Read file as text
    const fileContent = await selectedFile.text();
    const lines = fileContent.trim().split('\n');

    // Parse JSON lines
    const records = [];
    for (const line of lines) {
      if (line.trim()) {
        try {
          records.push(JSON.parse(line));
        } catch (e) {
          console.warn(`Invalid JSON line: ${escapeHtml(line.substring(0, 50))}`);
        }
      }
    }

    if (records.length === 0) {
      throw new AppError('No valid JSON records found in file', 'File parsing');
    }

    // Send records to server
    const response = await fetch('/api/load-jsonlines', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ records: records }),
    });

    if (!response.ok) {
      await handleApiError(response, 'Upload records');
    }

    const data = await response.json();

    if (!data.success) {
      throw new AppError(data.error || 'Server rejected upload', 'Upload');
    }

    const message = `✓ Loaded ${data.loaded} files successfully`;
    if (data.failed > 0) {
      showModalStatus(`${message} (${data.failed} failed)`, 'success');
    } else {
      showModalStatus(message, 'success');
    }

    setTimeout(() => {
      closeFileModal();
      loadFiles();
    }, 1500);
  } catch (error) {
    if (error instanceof AppError) {
      error.log();
      showModalStatus(error.message, 'error');
    } else {
      console.error('Unexpected error:', error);
      showModalStatus(error.message || 'Unknown error occurred', 'error');
    }
  } finally {
    isLoading = false;
  }
}

/**
 * Load files from API
 * @returns {Promise<void>}
 */
async function loadFiles() {
  try {
    const response = await fetch('/api/files');

    if (!response.ok) {
      await handleApiError(response, 'Load files');
    }

    const data = await response.json();

    if (!data.success) {
      throw new AppError(data.error || 'Failed to load files', 'Files API');
    }

    files = data.files || [];
    renderFileList();
  } catch (error) {
    if (error instanceof AppError) {
      error.log();
    } else {
      console.error('Unexpected error loading files:', error);
    }
  }
}

/**
 * Render file list in sidebar
 */
function renderFileList() {
  const fileList = document.getElementById('fileList');
  fileList.innerHTML = '';

  if (!files || files.length === 0) {
    fileList.innerHTML =
      '<div class="status-message">No files loaded. Load a JSONL file to begin.</div>';
    return;
  }

  files.forEach((file) => {
    if (!file || !file.file_name) {
      console.warn('Invalid file object:', file);
      return;
    }

    const div = document.createElement('div');
    div.className = 'file-item';
    if (currentFile && currentFile.file_name === file.file_name) {
      div.classList.add('active');
    }

    // Use citekey if available, otherwise file_name
    const displayName = file.citekey ? escapeHtml(file.citekey) : escapeHtml(file.file_name);

    // Show tags if available
    const tags = file.tags ? file.tags.split(':').filter((t) => t.trim()) : [];
    const tagsHtml =
      tags.length > 0
        ? `<div class="file-item-tags">${tags.map((tag) => `<span class="file-tag">${escapeHtml(tag)}</span>`).join('')}</div>`
        : '';

    div.innerHTML = `
            <div class="file-item-name">${displayName}</div>
            <div class="file-item-size">${formatFileSize(file.size_bytes)}</div>
            ${tagsHtml}
        `;
    div.onclick = () => selectFile(file);
    fileList.appendChild(div);
  });
}

/**
 * Select and display a file
 * @param {PDFFile} file - File to select
 * @param {boolean} keepBreadcrumb - Whether to keep breadcrumb visible (for papers list view)
 */
function selectFile(file, keepBreadcrumb = false) {
  if (!file || !file.file_name) {
    console.error('Invalid file object:', file);
    return;
  }

  currentFile = file;
  renderFileList();

  // If we're on the overview, switch to paper-detail view
  if (currentView === 'overview' || currentView === 'papers-list') {
    const previousView = currentView;
    currentView = 'paper-detail';

    // Show toolbar and tabs
    document.querySelector('.toolbar').style.display = 'flex';
    document.getElementById('tabNavigation').style.display = 'flex';

    // Hide breadcrumbs only if not coming from papers-list (or if keepBreadcrumb is not set)
    if (!keepBreadcrumb && previousView === 'overview') {
      const toolbarBreadcrumb = document.getElementById('toolbarBreadcrumb');
      if (toolbarBreadcrumb) toolbarBreadcrumb.style.display = 'none';
      const paperListBreadcrumb = document.getElementById('paperListBreadcrumb');
      if (paperListBreadcrumb) paperListBreadcrumb.style.display = 'none';
    }
  }

  // Update toolbar with author/year and title
  let authorYearHtml = '';
  let titleHtml = escapeHtml(file.title || file.file_name);

  // If we have title_details with authors and year, display them
  let titleDetailsObj = null;
  if (file.title_details) {
    try {
      titleDetailsObj =
        typeof file.title_details === 'string'
          ? JSON.parse(file.title_details)
          : file.title_details;
    } catch (e) {
      console.error('Error parsing title_details:', e);
    }
  }

  if (titleDetailsObj) {
    // Build author (year) line
    let authorLine = '';
    if (
      titleDetailsObj.authors &&
      Array.isArray(titleDetailsObj.authors) &&
      titleDetailsObj.authors.length > 0
    ) {
      const firstAuthor = titleDetailsObj.authors[0];
      const authorsDisplay =
        titleDetailsObj.authors.length > 1 ? `${firstAuthor} et al.` : firstAuthor;
      authorLine = authorsDisplay;
    }

    if (titleDetailsObj.year) {
      authorLine += (authorLine ? ' ' : '') + `(${titleDetailsObj.year})`;
    }

    // Add journal and month/edition if available
    let journalLine = '';
    if (titleDetailsObj.journal) {
      journalLine = escapeHtml(titleDetailsObj.journal);
    }

    if (titleDetailsObj.volume) {
      journalLine += (journalLine ? ' • ' : '') + `Vol. ${escapeHtml(titleDetailsObj.volume)}`;
    }

    if (titleDetailsObj.issue) {
      journalLine += (journalLine ? ' • ' : '') + `Issue ${escapeHtml(titleDetailsObj.issue)}`;
    }

    if (titleDetailsObj.month) {
      journalLine += (journalLine ? ' • ' : '') + escapeHtml(titleDetailsObj.month);
    }

    if (journalLine) {
      authorLine += (authorLine ? ' • ' : '') + journalLine;
    }

    if (authorLine) {
      authorYearHtml = escapeHtml(authorLine);
    }

    // Make title a link if we have DOI
    if (titleDetailsObj.doi) {
      const doiUrl = `https://doi.org/${escapeHtml(titleDetailsObj.doi)}`;
      titleHtml = `<a href="${doiUrl}" target="_blank" title="Open DOI in new tab">${titleHtml}</a>`;
    }
  }

  document.getElementById('currentAuthors').innerHTML = authorYearHtml;
  document.getElementById('currentAuthors').style.display = authorYearHtml ? 'block' : 'none';
  document.getElementById('currentFileName').innerHTML = titleHtml;
  document.getElementById('fileInfo').textContent =
    `${formatFileSize(file.size_bytes)} • Modified: ${formatDate(file.modified_time)}`;

  // Save paper reference and switch to last opened tab
  const paperId = file.citekey || file.file_name;
  saveLastPaper(paperId);
  const lastTab = getLastTab();

  // Switch all tabs to inactive first
  document.getElementById('overviewTab').classList.remove('active');
  document.getElementById('papersListTab').classList.remove('active');
  document.getElementById('pdfTab').classList.remove('active');
  document.getElementById('analysisTab').classList.remove('active');
  document.getElementById('detailsTab').classList.remove('active');
  document.getElementById('tagsTab').classList.remove('active');

  switchTab(lastTab);

  // Display PDF
  const pdfUrl = `/api/pdf/${safeEncodeURI(file.file_name)}`;
  const viewer = document.getElementById('pdfViewer');
  viewer.innerHTML = `<iframe src="${pdfUrl}#toolbar=0" title="PDF Viewer"></iframe>`;
}

// Load files on page load
window.addEventListener('load', async () => {
  await loadFiles();

  // Check for deeplink parameter in URL
  const params = new URLSearchParams(window.location.search);
  const paperId = params.get('paper');
  const tabParam = params.get('tab');

  if (paperId) {
    // Find and select the paper with matching file_name or citekey
    const targetFile = files.find(
      (f) =>
        f.file_name === decodeURIComponent(paperId) || f.citekey === decodeURIComponent(paperId)
    );

    if (targetFile) {
      currentView = 'paper-detail';
      currentFile = targetFile;

      // Show toolbar and tabs
      document.querySelector('.toolbar').style.display = 'flex';
      document.getElementById('tabNavigation').style.display = 'flex';

      // Show breadcrumb for paper link
      document.getElementById('toolbarBreadcrumb').style.display = 'flex';

      // Switch to the requested tab if specified
      if (tabParam && ['pdf', 'analysis', 'details', 'tags'].includes(tabParam)) {
        switchTab(tabParam);
      } else {
        switchTab('pdf');
      }

      // Scroll the file into view in the sidebar
      setTimeout(() => {
        const fileItems = document.querySelectorAll('.file-item.active');
        if (fileItems.length > 0) {
          fileItems[0].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }, 100);

      selectFile(targetFile);
    } else {
      console.warn(`Paper not found: ${paperId}`);
      goBackToOverview();
    }
  } else {
    // Default: show year overview
    goBackToOverview();
  }
});
