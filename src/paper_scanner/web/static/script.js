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
let currentTab = 'details';
let isLoading = false;
let allTags = [];
let yearData = [];
let currentView = 'overview'; // 'overview', 'papers-list', or 'paper-detail'
let selectedYear = null;
let yearChart = null;

// Sidebar pagination and search state
let sidebarSearchQuery = '';
let sidebarCurrentPage = 1;
let sidebarItemsPerPage = 25;
let sidebarFilteredFiles = [];
let sidebarSortBy = 'title';
let sidebarSortOrder = 'asc'; // 'asc' or 'desc'

// Storage keys for localStorage
const STORAGE_KEYS = {
  LAST_TAB: 'paperScanner_lastTab',
  LAST_PAPER: 'paperScanner_lastPaper',
};

/**
 * Load last active tab from localStorage
 * @returns {string} Tab name or 'details' as default
 */
function getLastTab() {
  try {
    const lastTab = localStorage.getItem(STORAGE_KEYS.LAST_TAB);
    return lastTab && ['pdf', 'analysis', 'details', 'references', 'tags'].includes(lastTab) ? lastTab : 'details';
  } catch {
    return 'details';
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

  // Title
  if (analysis.title) {
    html += `<div class="detail-subsection paper-subsection"><div class="detail-subsection-title">Title</div><p>${escapeHtml(analysis.title)}</p></div>`;
  }

  // Author, Year, Journal
  let metaHtml = '';
  if (analysis.authors) {
    const authorsStr = Array.isArray(analysis.authors) 
      ? analysis.authors.map(a => {
          if (typeof a === 'object' && a !== null) {
            return a.full_name || a.name || String(a);
          }
          return String(a);
        }).join('; ')
      : analysis.authors;
    metaHtml += `<strong>Authors:</strong> ${escapeHtml(authorsStr)}<br/>`;
  }
  if (analysis.year) {
    metaHtml += `<strong>Year:</strong> ${escapeHtml(analysis.year)}<br/>`;
  }
  if (analysis.journal) {
    metaHtml += `<strong>Journal:</strong> ${escapeHtml(analysis.journal)}`;
  }
  if (metaHtml) {
    html += `<div class="detail-subsection paper-subsection"><p>${metaHtml}</p></div>`;
  }

  // Abstract
  if (analysis.abstract) {
    html += `<div class="detail-subsection paper-subsection"><div class="detail-subsection-title">Abstract</div><p>${escapeHtml(analysis.abstract)}</p></div>`;
  }

  // Keywords
  if (analysis.keywords && Array.isArray(analysis.keywords) && analysis.keywords.length > 0) {
    html += `<div class="detail-subsection paper-subsection"><div class="detail-subsection-title">Keywords</div><p>${escapeHtml(analysis.keywords.join('; '))}</p></div>`;
  }

  // Topics
  if (analysis.topics && Array.isArray(analysis.topics) && analysis.topics.length > 0) {
    html += `<div class="detail-subsection paper-subsection"><div class="detail-subsection-title">Topics</div><p>${escapeHtml(analysis.topics.join('; '))}</p></div>`;
  }

  // Screening Details
  if (analysis.screening) {
    const screening = analysis.screening;
    html +=
      '<div class="detail-subsection paper-subsection"><div class="detail-subsection-title">📋 Screening</div>';

    if (screening.current_stage) {
      html += `<p><strong>Stage:</strong> ${escapeHtml(screening.current_stage)}</p>`;
    }

    if (screening.final_decision) {
      html += `<p><strong>Decision:</strong> ${escapeHtml(screening.final_decision)}</p>`;
    }

    // Categorization
    if (screening.categorization) {
      const cat = screening.categorization;
      html +=
        '<p><strong>Categorization:</strong></p><ul style="margin-top: 5px;">';
      if (cat.paper_type) {
        html += `<li>Type: ${escapeHtml(cat.paper_type)} (confidence: ${cat.paper_type_confidence ? (cat.paper_type_confidence * 100).toFixed(0) : 'N/A'}%)</li>`;
      }
      if (cat.study_type) {
        html += `<li>Study: ${escapeHtml(cat.study_type)} (confidence: ${cat.study_type_confidence ? (cat.study_type_confidence * 100).toFixed(0) : 'N/A'}%)</li>`;
      }
      if (cat.quality_tier) {
        html += `<li>Quality Tier: ${escapeHtml(cat.quality_tier)}</li>`;
      }
      html += `<li>Peer Reviewed: ${cat.is_peer_reviewed ? 'Yes' : 'No'}</li>`;
      html += `<li>Empirical: ${cat.is_empirical ? 'Yes' : 'No'}</li>`;
      html += `<li>Open Access: ${cat.is_open_access ? 'Yes' : 'No'}</li>`;
      html += '</ul>';
    }

    // Keyword Screening
    if (screening.keyword_screening) {
      const kws = screening.keyword_screening;
      html += '<p><strong>Keyword Screening:</strong></p><ul style="margin-top: 5px;">';
      html += `<li>Passed: ${kws.passed ? '✓ Yes' : '✗ No'}</li>`;
      html += `<li>Score: ${kws.score || 0}</li>`;
      if (kws.inclusion_keywords && kws.inclusion_keywords.length > 0) {
        html += `<li>Inclusion Keywords: ${escapeHtml(kws.inclusion_keywords.join(', '))}</li>`;
      }
      if (kws.abstract_matches !== undefined) {
        html += `<li>Abstract Matches: ${kws.abstract_matches}</li>`;
      }
      if (kws.title_matches !== undefined) {
        html += `<li>Title Matches: ${kws.title_matches}</li>`;
      }
      if (kws.keywords_matches !== undefined) {
        html += `<li>Keywords Matches: ${kws.keywords_matches}</li>`;
      }
      html += '</ul>';
    }

    html += '</div>';
  }

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
  if (!['pdf', 'analysis', 'details', 'references', 'tags'].includes(tabName)) {
    console.error(`Invalid tab name: ${tabName}`);
    return;
  }

  currentTab = tabName;
  saveLastTab(tabName);

  // Update URL to reflect current tab
  if (currentFile) {
    const dbId = currentFile.id;
    let newUrl = `${window.location.pathname}?db_id=${dbId}&tab=${tabName}&page=${sidebarCurrentPage}&limit=${sidebarItemsPerPage}&sort_by=${sidebarSortBy}&sort_order=${sidebarSortOrder}`;
    
    // Preserve year filter if active
    if (selectedYear) {
      newUrl += `&year=${selectedYear}`;
    }
    
    // Preserve search query if active
    if (sidebarSearchQuery) {
      newUrl += `&search=${encodeURIComponent(sidebarSearchQuery)}`;
    }
    
    window.history.replaceState({ tab: tabName }, '', newUrl);
  }

  // Update tab buttons
  document.getElementById('pdfTabBtn').classList.remove('active');
  document.getElementById('analysisTabBtn').classList.remove('active');
  document.getElementById('detailsTabBtn').classList.remove('active');
  document.getElementById('referencesTabBtn').classList.remove('active');
  document.getElementById('tagsTabBtn').classList.remove('active');

  if (tabName === 'pdf') {
    document.getElementById('pdfTabBtn').classList.add('active');
  } else if (tabName === 'analysis') {
    document.getElementById('analysisTabBtn').classList.add('active');
  } else if (tabName === 'details') {
    document.getElementById('detailsTabBtn').classList.add('active');
  } else if (tabName === 'references') {
    document.getElementById('referencesTabBtn').classList.add('active');
  } else {
    document.getElementById('tagsTabBtn').classList.add('active');
  }

  // Update tab panes
  document.getElementById('pdfTab').classList.remove('active');
  document.getElementById('analysisTab').classList.remove('active');
  document.getElementById('detailsTab').classList.remove('active');
  document.getElementById('referencesTab').classList.remove('active');
  document.getElementById('tagsTab').classList.remove('active');

  if (tabName === 'pdf') {
    document.getElementById('pdfTab').classList.add('active');
  } else if (tabName === 'analysis') {
    document.getElementById('analysisTab').classList.add('active');
  } else if (tabName === 'details') {
    document.getElementById('detailsTab').classList.add('active');
  } else if (tabName === 'references') {
    document.getElementById('referencesTab').classList.add('active');
  } else {
    document.getElementById('tagsTab').classList.add('active');
  }

  // Load content if switching to analysis, details, references, or tags tab and we have a file
  if (tabName === 'analysis' && currentFile) {
    const identifier = currentFile.file_name || currentFile.cite_key;
    if (identifier) loadFileAnalysis(identifier);
  } else if (tabName === 'details' && currentFile) {
    const identifier = currentFile.file_name || currentFile.cite_key;
    if (identifier) loadFileDetails(identifier);
  } else if (tabName === 'references' && currentFile) {
    const identifier = currentFile.file_name || currentFile.cite_key;
    if (identifier) loadFileReferences(identifier);
  } else if (tabName === 'tags' && currentFile) {
    const identifier = currentFile.file_name || currentFile.cite_key;
    if (identifier) loadTagsEditor(identifier);
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
 * Reset to histogram overview view - clears year filter and search
 */
function resetToHistogramView() {
  // Clear year filter and search
  selectedYear = null;
  sidebarSearchQuery = '';
  sidebarCurrentPage = 1;
  
  // Reset URL to just the base path
  window.history.replaceState({}, '', window.location.pathname);
  
  // Clear search input
  const searchInput = document.getElementById('sidebarSearchInput');
  if (searchInput) searchInput.value = '';
  
  // Show all papers
  sidebarFilteredFiles = [...files];
  renderSidebarFileList();
  updateSidebarPaginationControls();
  
  // Show overview histogram
  goBackToOverview();
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
  currentView = 'overview';

  // Update URL with year parameter
  const newUrl = `${window.location.pathname}?year=${year}`;
  window.history.replaceState({ year: year }, '', newUrl);

  // Filter sidebar by year
  sidebarSearchQuery = '';
  sidebarCurrentPage = 1;
  
  // Clear search input
  const searchInput = document.getElementById('sidebarSearchInput');
  if (searchInput) searchInput.value = '';

  // Filter files by selected year
  sidebarFilteredFiles = files.filter(file => file.year === year);
  
  // Render the filtered file list
  renderSidebarFileList();
  updateSidebarPaginationControls();

  // Clear any toolbar info
  const currentAuthors = document.getElementById('currentAuthors');
  if (currentAuthors) currentAuthors.innerHTML = '';
  const currentFileName = document.getElementById('currentFileName');
  if (currentFileName) currentFileName.innerHTML = '';
  const fileInfo = document.getElementById('fileInfo');
  if (fileInfo) fileInfo.innerHTML = '';

  // Hide tabs
  const tabNav = document.getElementById('tabNavigation');
  if (tabNav) tabNav.style.display = 'none';
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
    .map((paper) => {
      const title = paper.title || paper.file_name || 'Untitled';
      const year = paper.year || '';
      const authors = paper.authors
        ? Array.isArray(paper.authors)
          ? paper.authors.map((a) => (typeof a === 'object' ? a.family_name : a)).join(', ')
          : String(paper.authors)
        : '';
      const journal = paper.journal || '';
      const tags = paper.tags ? paper.tags.split(':').filter((t) => t.trim()) : [];

      return `
            <div class="paper-list-item" onclick="selectPaperFromList('${escapeHtml(paper.file_name || '')}')" title="Click to view details">
                <div class="paper-list-item-title">${escapeHtml(title)}</div>
                <div class="paper-list-item-metadata">
                    ${year ? `<span class="metadata-year">${escapeHtml(year)}</span>` : ''}
                    ${authors ? `<span class="metadata-dash"> – </span><span class="metadata-authors">${escapeHtml(authors)}</span>` : ''}
                    ${journal ? `<span class="metadata-dash"> – </span><span class="metadata-journal"><em>${escapeHtml(journal)}</em></span>` : ''}
                </div>
                ${tags.length > 0 ? `<div class="paper-list-item-tags">${tags.map((tag) => `<span class="tag-chip">${escapeHtml(tag)}</span>`).join('')}</div>` : ''}
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
 * Search for a paper by DOI or title and display its details
 * @param {string} doi - DOI of the paper to search for
 * @param {string} title - Title of the paper to search for
 */
async function searchAndDisplayPaperDetails(doi, title) {
  // Try to find the paper in files array by DOI or title
  let paper = null;

  if (doi) {
    paper = files.find(
      (f) =>
        f.title_details &&
        typeof f.title_details === 'string' &&
        f.title_details.includes(escapeHtml(doi))
    );
  }

  if (!paper && title) {
    paper = files.find(
      (f) =>
        f.title && f.title.toLowerCase().includes(title.toLowerCase())
    );
  }

  if (paper) {
    // Found matching paper - set as current and load details
    currentFile = paper;
    switchTab('details');
    loadFileDetails();
  } else {
    // Paper not in collection - show a message in details viewer
    const viewer = document.getElementById('detailsViewer');
    viewer.innerHTML = `
      <div class="status-message">
        <p>This referenced paper is not in your collection.</p>
        ${doi ? `<p><strong>DOI:</strong> ${escapeHtml(doi)}</p>` : ''}
        ${title ? `<p><strong>Title:</strong> ${escapeHtml(title)}</p>` : ''}
        <p>You can search for it online using the DOI or title.</p>
      </div>
    `;
    switchTab('details');
  }
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
  const dbId = currentFile.id;
  const baseUrl = window.location.origin + window.location.pathname;
  const deeplinkUrl = `${baseUrl}?db_id=${dbId}`;

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

    // Create analysis object from details (title, abstract, keywords, topics at top level)
    let analysisHtml = '';
    try {
      // Build analysis object from available fields
      const analysisData = {
        title: details.title,
        abstract: details.abstract,
        keywords: details.keywords,
        topics: details.topics,
        screening: details.screening,
        authors: details.authors,
        year: details.year,
        journal: details.journal,
      };
      
      analysisHtml = renderAnalysisSection(analysisData);
    } catch (e) {
      console.error('Error creating analysis data:', e);
      analysisHtml = '<div class="status-message">Error: Could not create analysis data</div>';
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
                        ${
                          bib.url
                            ? `<div class="detail-row">
                            <div class="detail-label">URL</div>
                            <div class="detail-value code-value"><a href="${escapeHtml(bib.url)}" target="_blank">${escapeHtml(bib.url)}</a></div>
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
                    ${tagsHtml}
                </div>
                
                <div class="detail-section">
                    <div class="detail-section-title">Paths</div>
                    <div class="detail-row">
                        <div class="detail-label">Full Path</div>
                        <div class="detail-value">${escapeHtml(details.file_path || 'N/A')}</div>
                    </div>
                </div>
                
                <div class="detail-section">
                    <div class="detail-section-title">Paper Details</div>
                    ${details.cite_key ? `<div class="detail-row">
                        <div class="detail-label">Citation Key</div>
                        <div class="detail-value code-value">${escapeHtml(details.cite_key)}</div>
                    </div>` : ''}
                    ${details.doi ? `<div class="detail-row">
                        <div class="detail-label">DOI</div>
                        <div class="detail-value code-value"><a href="https://doi.org/${escapeHtml(details.doi)}" target="_blank">${escapeHtml(details.doi)}</a></div>
                    </div>` : ''}
                    ${details.authors ? `<div class="detail-row">
                        <div class="detail-label">Authors</div>
                        <div class="detail-value">${details.authors && Array.isArray(details.authors) ? escapeHtml(details.authors.map(a => a.full_name || a.family_name).join('; ')) : 'N/A'}</div>
                    </div>` : ''}
                    ${details.title ? `<div class="detail-row">
                        <div class="detail-label">Title</div>
                        <div class="detail-value">${escapeHtml(details.title)}</div>
                    </div>` : ''}
                    ${details.journal ? `<div class="detail-row">
                        <div class="detail-label">Journal</div>
                        <div class="detail-value">${escapeHtml(details.journal)}</div>
                    </div>` : ''}
                    ${details.volume || details.issue || details.pages ? `<div class="detail-row">
                        <div class="detail-label">Volume/Issue/Pages</div>
                        <div class="detail-value">${escapeHtml((details.volume || '') + (details.issue ? `(${details.issue})` : '') + (details.pages ? `, pp. ${details.pages}` : ''))}</div>
                    </div>` : ''}
                    ${details.url ? `<div class="detail-row">
                        <div class="detail-label">URL</div>
                        <div class="detail-value code-value"><a href="${escapeHtml(details.url)}" target="_blank">${escapeHtml(details.url)}</a></div>
                    </div>` : ''}
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
 * Load and display references for a paper
 * @param {string} fileName - Name of the PDF file
 * @returns {Promise<void>}
 */
async function loadFileReferences(fileName) {
  try {
    const response = await fetch(`/api/references/${safeEncodeURI(fileName)}`);

    if (!response.ok) {
      await handleApiError(response, 'Load file references');
    }

    const data = await response.json();

    if (!data.success) {
      throw new AppError(data.error || 'Unknown error', 'File references');
    }

    const references = data.references || [];
    const viewer = document.getElementById('referencesViewer');

    if (!references || references.length === 0) {
      viewer.innerHTML = '<div class="status-message">No references found for this paper</div>';
      return;
    }

    // Build references list HTML
    let referencesHtml = '<div class="references-container">';
    referencesHtml += `<h3>📖 References (${references.length})</h3>`;
    referencesHtml += '<div class="references-list">';

    references.forEach((ref, index) => {
      // Parse authors if stored as JSON string
      let authors = ref.authors;
      if (typeof authors === 'string') {
        try {
          authors = JSON.parse(authors);
        } catch (e) {
          authors = [];
        }
      }

      // Build author string
      let authorString = '';
      if (Array.isArray(authors) && authors.length > 0) {
        authorString = authors
          .map((author) => {
            // Handle Author objects with family_name/given_name
            if (typeof author === 'object' && author.family_name) {
              return author.family_name + (author.given_name ? `, ${author.given_name}` : '');
            }
            // Handle Author objects with last_name/first_name (legacy)
            if (typeof author === 'object' && author.last_name) {
              return author.last_name + (author.first_name ? `, ${author.first_name}` : '');
            }
            // Handle full_name field
            if (typeof author === 'object' && author.full_name) {
              return author.full_name;
            }
            // Handle plain strings
            return String(author);
          })
          .join('; ');
      }

      // Build identifiers HTML
      let identifiersHtml = '';
      if (ref.doi) {
        identifiersHtml += `<a href="https://doi.org/${escapeHtml(ref.doi)}" target="_blank" class="ref-link">🔗 DOI</a> `;
      }
      if (ref.url) {
        identifiersHtml += `<a href="${escapeHtml(ref.url)}" target="_blank" class="ref-link">🔗 URL</a> `;
      }
      if (ref.arxiv_id) {
        identifiersHtml += `<a href="https://arxiv.org/abs/${escapeHtml(ref.arxiv_id)}" target="_blank" class="ref-link">📄 arXiv</a> `;
      }
      // Add details link - try to find paper by DOI, title, or just open details viewer
      const detailsSearchQuery = ref.doi || ref.title || '';
      if (detailsSearchQuery) {
        identifiersHtml += `<a href="javascript:void(0)" onclick="searchAndDisplayPaperDetails('${escapeHtml(ref.doi || '')}', '${escapeHtml(ref.title || '')}')" class="ref-link">📋 Details</a> `;
      }

      // Build reference entry
      // Build metadata line: year - authors - journal (only journal italic)
      const metadataParts = [];
      if (ref.year) metadataParts.push(escapeHtml(ref.year.toString()));
      if (authorString) metadataParts.push(escapeHtml(authorString));
      if (ref.journal) metadataParts.push(`<em>${escapeHtml(ref.journal)}</em>`);
      const metadataLine = metadataParts.join(' - ') || '';

      referencesHtml += `
        <div class="reference-item">
          <div class="reference-header">
            <span class="reference-number">[${index + 1}]</span>
            <span class="reference-type">${ref.reference_type ? escapeHtml(ref.reference_type) : 'article'}</span>
          </div>
          <div class="reference-title"><strong>${escapeHtml(ref.title || 'Untitled')}</strong></div>
          <div class="reference-metadata">${metadataLine}</div>
          ${ref.pages_range ? `<div class="reference-pages">pp. ${escapeHtml(ref.pages_range)}</div>` : ''}
          ${identifiersHtml ? `<div class="reference-links">${identifiersHtml}</div>` : ''}
          ${ref.parsing_status === 'warning' ? `<div class="reference-warning">⚠️ Parsing issues detected</div>` : ''}
        </div>
      `;
    });

    referencesHtml += '</div></div>';
    viewer.innerHTML = referencesHtml;
  } catch (error) {
    if (error instanceof AppError) {
      error.log();
    } else {
      console.error('Unexpected error loading references:', error);
    }

    const viewer = document.getElementById('referencesViewer');
    const errorMsg = error instanceof AppError ? error.message : error.message;
    viewer.innerHTML = `<div class="status-message">Error: ${escapeHtml(errorMsg)}</div>`;
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
    console.log(`Loaded ${files.length} files from API`);
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
  // Initialize sidebar search and pagination when files are loaded
  sidebarSearchQuery = '';
  sidebarCurrentPage = 1;
  sidebarFilteredFiles = [...files];
  
  // Clear search input and reset items per page
  const searchInput = document.getElementById('sidebarSearchInput');
  if (searchInput) searchInput.value = '';
  
  const select = document.getElementById('sidebarItemsPerPage');
  if (select) select.value = sidebarItemsPerPage.toString();
  
  // Render the file list with pagination
  updateSidebarFileList();
}


/**
 * Select and display a file
 * @param {PDFFile} file - File to select
 * @param {boolean} keepBreadcrumb - Whether to keep breadcrumb visible (for papers list view)
 */
function selectFile(file, keepBreadcrumb = false) {
  if (!file) {
    console.error('Invalid file object:', file);
    return;
  }

  // Require either file_name or cite_key
  const identifier = file.file_name || file.cite_key;
  if (!identifier) {
    console.error('File has neither file_name nor cite_key:', file);
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

  // Build metadata line: year - authors - journal
  const metadataParts = [];
  
  if (file.year) {
    metadataParts.push(file.year.toString());
  }
  
  if (file.authors && Array.isArray(file.authors) && file.authors.length > 0) {
    const authorNames = file.authors.slice(0, 2).map(auth => {
      if (typeof auth === 'string') return escapeHtml(auth);
      if (auth.family_name && auth.given_name) {
        return escapeHtml(`${auth.family_name}, ${auth.given_name}`);
      }
      if (auth.family_name) return escapeHtml(auth.family_name);
      if (auth.given_name) return escapeHtml(auth.given_name);
      return '';
    }).filter(a => a);
    
    if (authorNames.length > 0) {
      metadataParts.push(authorNames.join(', '));
    }
  }
  
  if (file.journal) {
    metadataParts.push(`<em>${escapeHtml(file.journal)}</em>`);
  }
  
  if (metadataParts.length > 0) {
    authorYearHtml = metadataParts.join(' - ');
  }

  // Make title a link if we have DOI
  if (file.doi) {
    const doiUrl = `https://doi.org/${escapeHtml(file.doi)}`;
    titleHtml = `<a href="${doiUrl}" target="_blank" title="Open DOI in new tab">${titleHtml}</a>`;
  }

  document.getElementById('currentAuthors').innerHTML = authorYearHtml;
  document.getElementById('currentAuthors').style.display = authorYearHtml ? 'block' : 'none';
  document.getElementById('currentFileName').innerHTML = titleHtml;
  document.getElementById('fileInfo').textContent =
    `${formatFileSize(file.size_bytes)} • Modified: ${formatDate(file.modified_time)}`;

  // Save paper reference and switch to last opened tab
  saveLastPaper(file.id.toString());
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
  const dbId = params.get('db_id');
  const tabParam = params.get('tab');
  const pageParam = params.get('page');
  const limitParam = params.get('limit');
  const yearParam = params.get('year');
  const searchParam = params.get('search');
  const sortByParam = params.get('sort_by');
  const sortOrderParam = params.get('sort_order');

  // Set sort state from URL if available
  if (sortByParam && ['title', 'year', 'author', 'journal'].includes(sortByParam)) {
    sidebarSortBy = sortByParam;
  }
  if (sortOrderParam && ['asc', 'desc'].includes(sortOrderParam)) {
    sidebarSortOrder = sortOrderParam;
  }
  updateSortIndicator();

  // Set pagination from URL if available
  if (pageParam) sidebarCurrentPage = Math.max(1, parseInt(pageParam));
  if (limitParam) sidebarItemsPerPage = parseInt(limitParam);

  // Restore search query if present
  if (searchParam) {
    sidebarSearchQuery = searchParam.toLowerCase();
    const searchInput = document.getElementById('sidebarSearchInput');
    if (searchInput) searchInput.value = searchParam;
  }

  if (dbId) {
    // Find and select the paper with matching id (handle both numeric and UUID string formats)
    const targetFile = files.find((f) => {
      // Try numeric ID first
      const numId = parseInt(dbId);
      if (!isNaN(numId) && f.id === numId) return true;
      // Try string UUID
      if (f.id === dbId) return true;
      return false;
    });

    if (targetFile) {
      currentView = 'paper-detail';
      currentFile = targetFile;

      // Show toolbar and tabs
      document.querySelector('.toolbar').style.display = 'flex';
      document.getElementById('tabNavigation').style.display = 'flex';

      // Show breadcrumb for paper link
      document.getElementById('toolbarBreadcrumb').style.display = 'flex';

      // Switch to the requested tab if specified, otherwise use default (details)
      if (tabParam && ['pdf', 'analysis', 'details', 'references', 'tags'].includes(tabParam)) {
        switchTab(tabParam);
      } else {
        switchTab('details');
      }

      // Apply year filter if present
      if (yearParam) {
        selectedYear = parseInt(yearParam);
        sidebarFilteredFiles = files.filter(file => file.year === selectedYear);
      } else if (sidebarSearchQuery) {
        // Apply search filter if present
        updateSidebarFileList();
      } else {
        sidebarFilteredFiles = [...files];
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
      console.warn(`Paper not found with db_id: ${dbId}`);
      goBackToOverview();
    }
  } else if (yearParam) {
    // Filter sidebar by year
    const year = parseInt(yearParam);
    selectedYear = year;
    currentView = 'overview';
    sidebarFilteredFiles = files.filter(file => file.year === year);
    renderSidebarFileList();
    updateSidebarPaginationControls();
  } else {
    // Default: show year overview
    goBackToOverview();
  }
});

/**
 * Update sidebar search filter
 */
function updateSidebarSearch() {
  const searchInput = document.getElementById('sidebarSearchInput');
  sidebarSearchQuery = (searchInput?.value || '').toLowerCase();
  sidebarCurrentPage = 1;
  updateSidebarFileList();
}

/**
 * Update sidebar pagination when items per page changes
 */
/**
 * Toggle sort menu visibility
 */
function toggleSortMenu() {
  const dropdown = document.getElementById('sortDropdown');
  if (dropdown) {
    dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
  }
}

/**
 * Cycle through sort direction (asc <-> desc) and update URL
 */
function cycleSortDirection() {
  sidebarSortOrder = sidebarSortOrder === 'asc' ? 'desc' : 'asc';
  updateSortIndicator();
  updateSidebarFileList();
  updateUrlWithSortState();
}

/**
 * Set sort field and update URL
 */
function setSortBy(field) {
  sidebarSortBy = field;
  sidebarCurrentPage = 1;
  updateSortIndicator();
  updateSidebarFileList();
  updateUrlWithSortState();
  toggleSortMenu(); // Close menu after selection
}

/**
 * Update the sort indicator display
 */
function updateSortIndicator() {
  const indicator = document.getElementById('sortIndicator');
  const directionIndicator = document.getElementById('directionIndicator');
  
  if (indicator) {
    const arrow = sidebarSortOrder === 'asc' ? '⬆' : '⬇';
    const fieldLabel = sidebarSortBy.charAt(0).toUpperCase() + sidebarSortBy.slice(1);
    indicator.textContent = `${arrow} ${fieldLabel}`;
  }
  
  if (directionIndicator) {
    const dir = sidebarSortOrder === 'asc' ? 'Ascending' : 'Descending';
    const arrow = sidebarSortOrder === 'asc' ? '⬆' : '⬇';
    directionIndicator.textContent = `${arrow} ${dir}`;
  }
}

/**
 * Update URL with sort state
 */
function updateUrlWithSortState() {
  const params = new URLSearchParams(window.location.search);
  params.set('sort_by', sidebarSortBy);
  params.set('sort_order', sidebarSortOrder);
  window.history.replaceState({}, '', `?${params.toString()}`);
}

/**
 * Toggle items per page menu
 */
function toggleItemsPerPageMenu() {
  const dropdown = document.getElementById('itemsPerPageDropdown');
  if (dropdown) {
    dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
  }
}

/**
 * Set items per page and update URL
 */
function setItemsPerPage(count) {
  sidebarItemsPerPage = count;
  sidebarCurrentPage = 1;
  updateItemsPerPageIndicator();
  updateSidebarFileList();
  updateUrlWithPaginationState();
  toggleItemsPerPageMenu(); // Close menu after selection
}

/**
 * Update the items per page indicator display
 */
function updateItemsPerPageIndicator() {
  const indicator = document.getElementById('itemsPerPageIndicator');
  if (indicator) {
    indicator.textContent = sidebarItemsPerPage.toString();
  }
}

/**
 * Update URL with pagination state
 */
function updateUrlWithPaginationState() {
  const params = new URLSearchParams(window.location.search);
  params.set('limit', sidebarItemsPerPage);
  window.history.replaceState({}, '', `?${params.toString()}`);
}

/**
 * Filter and paginate the sidebar file list
 */
function updateSidebarFileList() {
  // Filter files by search query
  sidebarFilteredFiles = files.filter(file => {
    if (!sidebarSearchQuery) return true;
    
    const searchTerm = sidebarSearchQuery.toLowerCase();
    
    // Title and cite_key
    const title = (file.title || file.cite_key || '').toLowerCase();
    if (title.includes(searchTerm)) return true;
    
    // Authors (both string and object formats)
    const authors = Array.isArray(file.authors) 
      ? file.authors.map(a => {
          if (typeof a === 'string') return a.toLowerCase();
          const parts = [];
          if (a.family_name) parts.push(a.family_name.toLowerCase());
          if (a.given_name) parts.push(a.given_name.toLowerCase());
          return parts.join(' ');
        }).join(' ')
      : '';
    if (authors.includes(searchTerm)) return true;
    
    // Journal
    const journal = (file.journal || '').toLowerCase();
    if (journal.includes(searchTerm)) return true;
    
    // Year
    const year = (file.year || '').toString();
    if (year.includes(searchTerm)) return true;
    
    // DOI
    const doi = (file.doi || '').toLowerCase();
    if (doi.includes(searchTerm)) return true;
    
    // Tags
    const tags = (file.tags || '').toLowerCase();
    if (tags.includes(searchTerm)) return true;
    
    // Research questions (if available)
    if (file.analysis && file.analysis.research_questions) {
      const questions = (file.analysis.research_questions || '').toLowerCase();
      if (questions.includes(searchTerm)) return true;
    }
    
    return false;
  });

  // Sort filtered files
  sidebarFilteredFiles.sort((a, b) => {
    let aVal, bVal;
    
    switch (sidebarSortBy) {
      case 'title':
        aVal = (a.title || a.file_name || '').toLowerCase();
        bVal = (b.title || b.file_name || '').toLowerCase();
        break;
      case 'year':
        aVal = a.year || 0;
        bVal = b.year || 0;
        break;
      case 'author':
        aVal = getFirstAuthorName(a.authors).toLowerCase();
        bVal = getFirstAuthorName(b.authors).toLowerCase();
        break;
      case 'journal':
        aVal = (a.journal || '').toLowerCase();
        bVal = (b.journal || '').toLowerCase();
        break;
      default:
        aVal = (a.title || a.file_name || '').toLowerCase();
        bVal = (b.title || b.file_name || '').toLowerCase();
    }
    
    // Handle numeric vs string comparison
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return sidebarSortOrder === 'asc' ? aVal - bVal : bVal - aVal;
    }
    
    // String comparison
    if (sidebarSortOrder === 'asc') {
      return aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
    } else {
      return aVal > bVal ? -1 : aVal < bVal ? 1 : 0;
    }
  });

  // Render with pagination
  renderSidebarFileList();
  updateSidebarPaginationControls();
}

/**
 * Get first author name from authors array
 */
function getFirstAuthorName(authors) {
  if (!Array.isArray(authors) || authors.length === 0) return '';
  const author = authors[0];
  if (typeof author === 'string') return author;
  if (author.family_name && author.given_name) {
    return `${author.family_name}, ${author.given_name}`;
  }
  if (author.family_name) return author.family_name;
  if (author.given_name) return author.given_name;
  return '';
}

/**
 * Render sidebar file list with pagination
 */
function renderSidebarFileList() {
  const fileList = document.getElementById('fileList');
  fileList.innerHTML = '';

  if (!sidebarFilteredFiles || sidebarFilteredFiles.length === 0) {
    fileList.innerHTML =
      '<div class="status-message">No papers match your search.</div>';
    return;
  }

  // Calculate pagination
  const start = (sidebarCurrentPage - 1) * sidebarItemsPerPage;
  const end = start + sidebarItemsPerPage;
  const pageFiles = sidebarFilteredFiles.slice(start, end);

  pageFiles.forEach((file) => {
    if (!file) {
      console.warn('Invalid file object:', file);
      return;
    }

    // Use file_name if available, otherwise cite_key as fallback
    const identifier = file.file_name || file.cite_key;
    if (!identifier) {
      console.warn('File has neither file_name nor cite_key:', file);
      return;
    }

    const div = document.createElement('div');
    div.className = 'file-item';
    if (currentFile && currentFile.id === file.id) {
      div.classList.add('active');
    }

    // Extract metadata
    const title = escapeHtml(file.title || file.cite_key || 'Unknown Title');
    const year = file.year || '';
    const authors = file.authors || [];
    const journal = escapeHtml(file.journal || '');
    
    // Format authors: "Author1, Author2, Author3"
    const authorNames = authors.slice(0, 2).map(auth => {
      if (typeof auth === 'string') return escapeHtml(auth);
      if (auth.family_name && auth.given_name) {
        return escapeHtml(`${auth.family_name}, ${auth.given_name}`);
      }
      if (auth.family_name) return escapeHtml(auth.family_name);
      if (auth.given_name) return escapeHtml(auth.given_name);
      return '';
    }).filter(a => a).join(', ');
    
    const authorText = authorNames || 'Unknown Authors';

    // Show tags if available
    const tags = file.tags ? file.tags.split(':').filter((t) => t.trim()) : [];
    const tagsHtml =
      tags.length > 0
        ? `<div class="file-item-tags">${tags.map((tag) => `<span class="file-tag">${escapeHtml(tag)}</span>`).join('')}</div>`
        : '';

    // Build metadata line: year - authors - journal (only journal italic)
    const metadataParts = [];
    if (year) metadataParts.push(escapeHtml(year));
    if (authorText) metadataParts.push(escapeHtml(authorText));
    if (journal) metadataParts.push(`<em>${escapeHtml(journal)}</em>`);
    const metadataLine = metadataParts.join(' - ') || 'No metadata available';

    div.innerHTML = `
            <div class="file-item-title">${title}</div>
            <div class="file-item-metadata">${metadataLine}</div>
            ${tagsHtml}
        `;
    div.onclick = () => selectFile(file);
    fileList.appendChild(div);
  });
}

/**
 * Update sidebar pagination controls
 */
function updateSidebarPaginationControls() {
  const totalPages = Math.ceil(sidebarFilteredFiles.length / sidebarItemsPerPage);
  const start = (sidebarCurrentPage - 1) * sidebarItemsPerPage + 1;
  const end = Math.min(sidebarCurrentPage * sidebarItemsPerPage, sidebarFilteredFiles.length);
  const total = sidebarFilteredFiles.length;

  // Update pagination info
  const infoEl = document.getElementById('sidebarPaginationInfo');
  if (infoEl) {
    infoEl.textContent = total > 0 ? `${start}-${end} of ${total}` : 'No papers';
  }

  // Update button states
  const prevBtn = document.getElementById('sidebarPrevBtn');
  const nextBtn = document.getElementById('sidebarNextBtn');
  if (prevBtn) prevBtn.disabled = sidebarCurrentPage <= 1;
  if (nextBtn) nextBtn.disabled = sidebarCurrentPage >= totalPages;
}

/**
 * Go to next sidebar page
 */
function goToNextSidebarPage() {
  const totalPages = Math.ceil(sidebarFilteredFiles.length / sidebarItemsPerPage);
  if (sidebarCurrentPage < totalPages) {
    sidebarCurrentPage++;
    renderSidebarFileList();
    updateSidebarPaginationControls();
    
    // Update URL with new page
    if (currentFile) {
      const dbId = currentFile.id;
      let newUrl = `${window.location.pathname}?db_id=${dbId}&tab=${currentTab}&page=${sidebarCurrentPage}&limit=${sidebarItemsPerPage}&sort_by=${sidebarSortBy}&sort_order=${sidebarSortOrder}`;
      
      // Preserve year and search filters
      if (selectedYear) {
        newUrl += `&year=${selectedYear}`;
      }
      if (sidebarSearchQuery) {
        newUrl += `&search=${encodeURIComponent(sidebarSearchQuery)}`;
      }
      
      window.history.replaceState({}, '', newUrl);
    }
  }
}

/**
 * Go to previous sidebar page
 */
function goToPreviousSidebarPage() {
  if (sidebarCurrentPage > 1) {
    sidebarCurrentPage--;
    renderSidebarFileList();
    updateSidebarPaginationControls();
    
    // Update URL with new page
    if (currentFile) {
      const dbId = currentFile.id;
      let newUrl = `${window.location.pathname}?db_id=${dbId}&tab=${currentTab}&page=${sidebarCurrentPage}&limit=${sidebarItemsPerPage}&sort_by=${sidebarSortBy}&sort_order=${sidebarSortOrder}`;
      
      // Preserve year and search filters
      if (selectedYear) {
        newUrl += `&year=${selectedYear}`;
      }
      if (sidebarSearchQuery) {
        newUrl += `&search=${encodeURIComponent(sidebarSearchQuery)}`;
      }
      
      window.history.replaceState({}, '', newUrl);
    }
  }
}

// Fallback initialization for Safari and other browsers
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', async () => {
    if (files.length === 0 && document.getElementById('fileList')) {
      await loadFiles();
      goBackToOverview();
    }
  });
} else if (files.length === 0 && document.getElementById('fileList')) {
  // Page already loaded
  (async () => {
    await loadFiles();
    goBackToOverview();
  })();
}
