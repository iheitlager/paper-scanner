let files = [];
let currentFile = null;
let selectedFile = null;

// Format file size for display
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Format timestamp
function formatDate(timestamp) {
    if (!timestamp) return 'N/A';
    return new Date(timestamp).toLocaleDateString();
}

// Modal functions
function openFileModal() {
    document.getElementById('fileModal').classList.add('show');
    selectedFile = null;
    document.getElementById('loadBtn').disabled = true;
    document.getElementById('fileInputLabel').textContent = '📁 Click to select JSONL file or drag & drop';
    document.getElementById('modalStatusMessage').innerHTML = '';
}

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

// Handle file selection
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        selectedFile = file;
        document.getElementById('fileInputLabel').textContent = '✓ ' + file.name;
        document.getElementById('loadBtn').disabled = false;
    }
}

// Drag and drop
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
                document.getElementById('fileInputLabel').textContent = '✓ ' + file.name;
                document.getElementById('loadBtn').disabled = false;
            } else {
                showModalStatus('Please select a .jsonl file', 'error');
            }
        }
    });
}

// Show status in modal
function showModalStatus(message, type) {
    const statusDiv = document.getElementById('modalStatusMessage');
    if (type === 'error') {
        statusDiv.innerHTML = `<div class="error-message">✗ ${message}</div>`;
    } else if (type === 'success') {
        statusDiv.innerHTML = `<div class="success-message">✓ ${message}</div>`;
    } else {
        statusDiv.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
    }
}

// Load JSONL file into database
async function loadJsonLinesFile() {
    if (!selectedFile) {
        showModalStatus('Please select a file', 'error');
        return;
    }

    showModalStatus('Loading file...', 'loading');

    try {
        // Read file as text
        const fileContent = await selectedFile.text();
        const lines = fileContent.trim().split('\n');

        // Parse JSON lines and send to server
        const records = [];
        for (const line of lines) {
            if (line.trim()) {
                try {
                    records.push(JSON.parse(line));
                } catch (e) {
                    console.error('JSON parse error:', e);
                }
            }
        }

        // Send records to server
        const response = await fetch('/api/load-jsonlines', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ records: records })
        });

        const data = await response.json();

        if (data.success) {
            showModalStatus(`✓ Loaded ${data.loaded} files successfully`, 'success');
            setTimeout(() => {
                closeFileModal();
                loadFiles();
            }, 1500);
        } else {
            showModalStatus(data.error || 'Failed to load file', 'error');
        }
    } catch (error) {
        showModalStatus(`Error: ${error.message}`, 'error');
    }
}

// Load files from API
async function loadFiles() {
    try {
        const response = await fetch('/api/files');
        const data = await response.json();

        if (data.success) {
            files = data.files;
            renderFileList();
        }
    } catch (error) {
        console.error('Error loading files:', error);
    }
}

// Render file list in sidebar
function renderFileList() {
    const fileList = document.getElementById('fileList');
    fileList.innerHTML = '';

    if (files.length === 0) {
        fileList.innerHTML = '<div class="status-message">No files loaded. Load a JSONL file to begin.</div>';
        return;
    }

    files.forEach((file, index) => {
        const div = document.createElement('div');
        div.className = 'file-item';
        if (currentFile && currentFile.id === file.id) {
            div.classList.add('active');
        }
        div.innerHTML = `
            <div class="file-item-name">${file.file_name}</div>
            <div class="file-item-size">${formatFileSize(file.size_bytes)}</div>
        `;
        div.onclick = () => selectFile(file);
        fileList.appendChild(div);
    });
}

// Select and display a file
function selectFile(file) {
    currentFile = file;
    renderFileList();

    // Update toolbar
    document.getElementById('currentFileName').textContent = file.file_name;
    document.getElementById('fileInfo').textContent = 
        `${formatFileSize(file.size_bytes)} • Modified: ${formatDate(file.modified_time)}`;

    // Display PDF
    const pdfUrl = `/api/pdf/${encodeURIComponent(file.file_name)}`;
    const viewer = document.getElementById('pdfViewer');
    viewer.innerHTML = `<iframe src="${pdfUrl}#toolbar=0"></iframe>`;
}

// Load files on page load
window.addEventListener('load', loadFiles);
