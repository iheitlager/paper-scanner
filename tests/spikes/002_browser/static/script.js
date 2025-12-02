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
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
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
 * Switch between PDF and Details tabs
 * @param {string} tabName - Tab name ('pdf' or 'details')
 */
function switchTab(tabName) {
    if (!['pdf', 'details'].includes(tabName)) {
        console.error(`Invalid tab name: ${tabName}`);
        return;
    }
    
    currentTab = tabName;
    
    // Update tab buttons
    document.getElementById('pdfTabBtn').classList.remove('active');
    document.getElementById('detailsTabBtn').classList.remove('active');
    
    if (tabName === 'pdf') {
        document.getElementById('pdfTabBtn').classList.add('active');
    } else {
        document.getElementById('detailsTabBtn').classList.add('active');
    }
    
    // Update tab panes
    document.getElementById('pdfTab').classList.remove('active');
    document.getElementById('detailsTab').classList.remove('active');
    
    if (tabName === 'pdf') {
        document.getElementById('pdfTab').classList.add('active');
    } else {
        document.getElementById('detailsTab').classList.add('active');
    }
    
    // Load details if switching to details tab and we have a file
    if (tabName === 'details' && currentFile) {
        loadFileDetails(currentFile.file_name);
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
        
        const detailsHtml = `
            <div class="details-container">
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
                </div>
                
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
    document.getElementById('fileInputLabel').textContent = '📁 Click to select JSONL file or drag & drop';
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
document.addEventListener('click', function(event) {
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
            body: JSON.stringify({ records: records })
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
        fileList.innerHTML = '<div class="status-message">No files loaded. Load a JSONL file to begin.</div>';
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
        div.innerHTML = `
            <div class="file-item-name">${escapeHtml(file.file_name)}</div>
            <div class="file-item-size">${formatFileSize(file.size_bytes)}</div>
        `;
        div.onclick = () => selectFile(file);
        fileList.appendChild(div);
    });
}

/**
 * Select and display a file
 * @param {PDFFile} file - File to select
 */
function selectFile(file) {
    if (!file || !file.file_name) {
        console.error('Invalid file object:', file);
        return;
    }

    currentFile = file;
    renderFileList();

    // Update toolbar
    document.getElementById('currentFileName').textContent = escapeHtml(file.file_name);
    document.getElementById('fileInfo').textContent = 
        `${formatFileSize(file.size_bytes)} • Modified: ${formatDate(file.modified_time)}`;

    // Reset to PDF tab when selecting a new file
    currentTab = 'pdf';
    switchTab('pdf');
    
    // Display PDF
    const pdfUrl = `/api/pdf/${safeEncodeURI(file.file_name)}`;
    const viewer = document.getElementById('pdfViewer');
    viewer.innerHTML = `<iframe src="${pdfUrl}#toolbar=0" title="PDF Viewer"></iframe>`;
}

// Load files on page load
window.addEventListener('load', loadFiles);
