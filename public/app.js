const apiBase = '/admin/api';

const elements = {
    userList: document.getElementById('userList'),
    totalUsers: document.getElementById('totalUsers'),
    activeSessions: document.getElementById('activeSessions'),
    createUserBtn: document.getElementById('createUserBtn'),
    userModal: document.getElementById('userModal'),
    closeModal: document.getElementById('closeModal'),
    saveUser: document.getElementById('saveUser'),
    usernameInput: document.getElementById('usernameInput'),
    logoutBtn: document.getElementById('logoutBtn'),
    usersTab: document.getElementById('usersTab'),
    filesTab: document.getElementById('filesTab'),
    testerTab: document.getElementById('testerTab'),
    usersSection: document.getElementById('usersSection'),
    filesSection: document.getElementById('filesSection'),
    testerSection: document.getElementById('testerSection'),
    sessionModal: document.getElementById('sessionModal'),
    sessionList: document.getElementById('sessionList'),
    closeSessionModal: document.getElementById('closeSessionModal'),
    dismissSessionModal: document.getElementById('dismissSessionModal'),
    sessionUserSub: document.getElementById('sessionUserSub'),
    clearAllSessionsBtn: document.getElementById('clearAllSessionsBtn'),
    // File Manager elements
    caravanFileList: document.getElementById('caravanFileList'),
    scFileList: document.getElementById('scFileList'),
    featureFileList: document.getElementById('featureFileList'),
    caravanFileCount: document.getElementById('caravanFileCount'),
    scFileCount: document.getElementById('scFileCount'),
    featureFileCount: document.getElementById('featureFileCount'),
    caravanUploadInput: document.getElementById('caravanUploadInput'),
    scUploadInput: document.getElementById('scUploadInput'),
    featureUploadInput: document.getElementById('featureUploadInput'),
    caravanDropZone: document.getElementById('caravanDropZone'),
    scDropZone: document.getElementById('scDropZone'),
    featureDropZone: document.getElementById('featureDropZone'),
    // File preview modal
    filePreviewModal: document.getElementById('filePreviewModal'),
    closePreviewModal: document.getElementById('closePreviewModal'),
    previewFileName: document.getElementById('previewFileName'),
    previewFileMeta: document.getElementById('previewFileMeta'),
    previewContent: document.getElementById('previewContent')
};

// State
let users = [];
let availableFiles = { CARAVAN: [], SC: [], FEATURE: [] };
let managedFiles = { CARAVAN: [], SC: [], FEATURE: [] };


// ==============================
// USER MANAGEMENT
// ==============================

async function fetchUsers() {
    try {
        const response = await fetch(`${apiBase}/users`);
        if (response.status === 401) {
            window.location.href = '/';
            return;
        }
        users = await response.json();
        renderUsers();
        updateStats();
    } catch (error) {
        console.error('Error fetching users:', error);
    }
}

function renderUsers() {
    elements.userList.innerHTML = '';

    if (users.length === 0) {
        elements.userList.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 40px; color: var(--text-dim);">No users found. Generate a new key to start!</td></tr>`;
        return;
    }

    users.forEach(user => {
        const row = document.createElement('tr');
        const date = new Date(user.created_at).toLocaleDateString();

        row.innerHTML = `
            <td>
                <div style="font-weight:600">${user.username}</div>
            </td>
            <td>
                <div class="key-badge" onclick="copyToClipboard('${user.public_id}')">
                   ${user.public_id} <i class="fas fa-copy" style="margin-left:8px; font-size:12px; cursor:pointer"></i>
                </div>
            </td>
            <td>${date}</td>
            <td>
                <div class="session-indicator" onclick="openSessionManager(${user.id}, '${user.username}')">
                    <div class="status-tag ${user.session_count > 0 ? 'active' : 'inactive'}">
                        ${user.session_count > 0 ? 'Active' : 'Offline'}
                    </div>
                    <i class="fas fa-network-wired" style="font-size:14px; color: var(--secondary)"></i>
                </div>
            </td>
            <td>
                <span class="status-tag ${user.is_active ? 'active' : 'inactive'}">
                    ${user.is_active ? 'Active' : 'Disabled'}
                </span>
            </td>
            <td>
                <div style="display:flex; gap: 10px;">
                    <button class="btn info" style="padding: 8px 12px;" onclick="openSessionManager(${user.id}, '${user.username}')" title="Manage Sessions">
                        <i class="fas fa-list-ul"></i>
                    </button>
                    <button class="btn danger" style="padding: 8px 12px;" onclick="deleteUser(${user.id})" title="Delete User">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        `;
        elements.userList.appendChild(row);
    });
}

function updateStats() {
    elements.totalUsers.innerText = users.length;
    const onlineCount = users.reduce((acc, user) => acc + (user.session_count || 0), 0);
    elements.activeSessions.innerText = onlineCount;
}

async function saveUser() {
    const username = elements.usernameInput.value.trim();
    if (!username) return alert('Please enter a username');

    try {
        const response = await fetch(`${apiBase}/users`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });

        if (response.ok) {
            elements.usernameInput.value = '';
            closeModal();
            fetchUsers();
        }
    } catch (error) {
        console.error('Error saving user:', error);
    }
}

async function deleteUser(id) {
    if (!confirm('Are you sure you want to delete this user? This will invalidate their license key.')) return;

    try {
        await fetch(`${apiBase}/users/${id}`, { method: 'DELETE' });
        fetchUsers();
    } catch (error) {
        console.error('Error deleting user:', error);
    }
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text);
    showToast('Public ID copied to clipboard!', 'success');
}

function openModal() {
    elements.userModal.style.display = 'flex';
}

function closeModal() {
    elements.userModal.style.display = 'none';
}


// ==============================
// SESSION MANAGER
// ==============================

let currentUserIdForSessions = null;

async function openSessionManager(userId, username) {
    currentUserIdForSessions = userId;
    elements.sessionUserSub.innerText = `Managing sessions for character: ${username}`;
    elements.sessionModal.style.display = 'flex';
    loadSessions();
}

async function loadSessions() {
    if (!currentUserIdForSessions) return;
    elements.sessionList.innerHTML = '<tr><td colspan="3" style="text-align:center; padding:20px;">Loading...</td></tr>';

    try {
        const response = await fetch(`${apiBase}/sessions/${currentUserIdForSessions}`);
        const sessions = await response.json();

        if (sessions.length === 0) {
            elements.sessionList.innerHTML = '<tr><td colspan="3" style="text-align:center; padding:20px; color:var(--text-dim);">No active sessions</td></tr>';
            return;
        }

        elements.sessionList.innerHTML = sessions.map(s => {
            const lastSeen = new Date(s.last_active).toLocaleTimeString();
            return `
                <tr>
                    <td style="padding:12px;"><code>${s.ip_address}</code></td>
                    <td style="padding:12px;">${lastSeen}</td>
                    <td style="padding:12px;">
                        <button class="btn danger" style="padding:5px 10px; font-size:12px;" onclick="kickSession(${s.id})">
                            <i class="fas fa-times"></i> Kick
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        console.error(e);
    }
}

async function kickSession(sessionId) {
    if (!confirm('Kick this character session?')) return;
    try {
        await fetch(`${apiBase}/sessions/${sessionId}`, { method: 'DELETE' });
        loadSessions();
        fetchUsers();
    } catch (e) {
        console.error(e);
    }
}

async function clearAllSessions() {
    if (!currentUserIdForSessions) return;
    if (!confirm('Are you sure you want to clear ALL sessions for this user?')) return;

    try {
        await fetch(`${apiBase}/sessions/user/${currentUserIdForSessions}`, { method: 'DELETE' });
        loadSessions();
        fetchUsers();
    } catch (e) {
        console.error(e);
    }
}

function closeSessionModal() {
    elements.sessionModal.style.display = 'none';
}


// ==============================
// FILE MANAGER
// ==============================

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function formatDate(isoStr) {
    const d = new Date(isoStr);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

async function fetchManagedFiles() {
    try {
        const response = await fetch(`${apiBase}/files`);
        if (response.status === 401) return;
        managedFiles = await response.json();
        renderFileList('CARAVAN', managedFiles.CARAVAN || [], elements.caravanFileList);
        renderFileList('SC', managedFiles.SC || [], elements.scFileList);
        renderFileList('FEATURE', managedFiles.FEATURE || [], elements.featureFileList);
        elements.caravanFileCount.textContent = (managedFiles.CARAVAN || []).length;
        elements.scFileCount.textContent = (managedFiles.SC || []).length;
        elements.featureFileCount.textContent = (managedFiles.FEATURE || []).length;
    } catch (error) {
        console.error('Error fetching files:', error);
    }
}

function renderFileList(category, files, container) {
    if (files.length === 0) {
        container.innerHTML = `<div class="file-card-empty"><i class="fas fa-folder-open" style="font-size: 32px; margin-bottom: 10px; display: block; opacity: 0.3;"></i>No files uploaded yet</div>`;
        return;
    }

    container.innerHTML = files.map((f, i) => {
        const ext = f.name.split('.').pop().toLowerCase();
        const iconClass = ext === 'json' ? 'json' : ext === 'py' ? 'py' : 'txt';
        const icon = ext === 'json' ? 'fa-file-code' : ext === 'py' ? 'fa-file-code' : 'fa-file-lines';

        return `
            <div class="file-card" style="animation-delay: ${i * 0.05}s">
                <div class="file-icon ${iconClass}">
                    <i class="fas ${icon}"></i>
                </div>
                <div class="file-info">
                    <div class="file-name" title="${f.name}">${f.name}</div>
                    <div class="file-meta">${formatFileSize(f.size)} • ${formatDate(f.modified)}</div>
                </div>
                <div class="file-actions">
                    <button class="action-btn view" onclick="previewFile('${category}', '${f.name}')" title="Preview">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="action-btn download" onclick="downloadFile('${category}', '${f.name}')" title="Download">
                        <i class="fas fa-download"></i>
                    </button>
                    <button class="action-btn delete" onclick="deleteFileFromManager('${category}', '${f.name}')" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

async function uploadFiles(files, category) {
    for (const file of files) {
        if (!file.name.endsWith('.txt') && !file.name.endsWith('.json') && !file.name.endsWith('.py')) {
            showToast(`Skipped "${file.name}" — only .txt, .json and .py files allowed`, 'error');
            continue;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('category', category);

        try {
            const response = await fetch(`${apiBase}/files/upload`, {
                method: 'POST',
                body: formData,
            });

            if (response.ok) {
                showToast(`"${file.name}" uploaded to ${category}`, 'success');
            } else {
                const err = await response.json();
                showToast(`Upload failed: ${err.detail}`, 'error');
            }
        } catch (e) {
            showToast(`Upload error: ${e.message}`, 'error');
        }
    }
    fetchManagedFiles();
}

async function deleteFileFromManager(category, filename) {
    if (!confirm(`Delete "${filename}" from ${category}?`)) return;

    try {
        const response = await fetch(`${apiBase}/files/${category}/${encodeURIComponent(filename)}`, { method: 'DELETE' });
        if (response.ok) {
            showToast(`"${filename}" deleted`, 'success');
            fetchManagedFiles();
        } else {
            const err = await response.json();
            showToast(`Delete failed: ${err.detail}`, 'error');
        }
    } catch (e) {
        showToast(`Delete error: ${e.message}`, 'error');
    }
}

async function previewFile(category, filename) {
    elements.filePreviewModal.style.display = 'flex';
    elements.previewFileName.textContent = filename;
    elements.previewFileMeta.textContent = `Loading...`;
    elements.previewContent.textContent = 'Loading...';

    try {
        const response = await fetch(`${apiBase}/files/${category}/${encodeURIComponent(filename)}/content`);
        if (!response.ok) {
            elements.previewContent.textContent = 'Error loading file content';
            return;
        }
        const data = await response.json();
        elements.previewFileName.textContent = `${data.name}`;
        elements.previewFileMeta.textContent = `${data.category} • ${data.lines} lines • ${formatFileSize(data.size)} • Modified: ${formatDate(data.modified)}`;
        elements.previewContent.textContent = data.content;
    } catch (e) {
        elements.previewContent.textContent = 'Error: ' + e.message;
    }
}

function downloadFile(category, filename) {
    // Use the public download mechanism - just open the admin API file content in a new tab
    // Or provide direct download via a simple window open
    const link = document.createElement('a');
    link.href = `${apiBase}/files/${category}/${encodeURIComponent(filename)}/content`;
    link.target = '_blank';
    link.click();
}

function closePreviewModal() {
    elements.filePreviewModal.style.display = 'none';
}

// Drag and Drop setup
function setupDropZone(dropZone, category, uploadInput) {
    ['dragenter', 'dragover'].forEach(event => {
        dropZone.addEventListener(event, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(event => {
        dropZone.addEventListener(event, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('drag-over');
        });
    });

    dropZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            uploadFiles(files, category);
        }
    });

    dropZone.addEventListener('click', () => {
        uploadInput.click();
    });

    uploadInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadFiles(e.target.files, category);
            e.target.value = ''; // Reset input
        }
    });
}


// ==============================
// SIGNED API CLIENT SIMULATOR
// ==============================

let selectedEndpoint = 'validate';

async function fetchFiles() {
    try {
        const response = await fetch(`${apiBase}/files`);
        if (response.status === 401) return;
        const data = await response.json();
        availableFiles = {
            CARAVAN: (data.CARAVAN || []).map(f => f.name || f),
            SC: (data.SC || []).map(f => f.name || f),
            FEATURE: (data.FEATURE || []).map(f => f.name || f)
        };
        updateFileDropdown();
    } catch (error) {
        console.error('Error fetching files:', error);
    }
}

function updateFileDropdown() {
    const type = document.getElementById('testType').value;
    const dropdown = document.getElementById('testFilename');
    const files = availableFiles[type] || [];
    dropdown.innerHTML = files.map(f => `<option value="${f}">${f}</option>`).join('') || '<option value="">No files</option>';
}

function selectEndpoint(endpoint) {
    selectedEndpoint = endpoint;
    document.querySelectorAll('.endpoint-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.endpoint === endpoint);
    });
    // Show/hide download-specific fields
    const downloadFields = document.getElementById('downloadFields');
    if (downloadFields) downloadFields.style.display = (endpoint === 'download' || endpoint === 'list') ? 'block' : 'none';

    // Auto-update payload when endpoint changes
    updateDefaultPayload();
}

function updateDefaultPayload() {
    const publicId = document.getElementById('testPublicId')?.value.trim() || '';
    const ip = document.getElementById('testIp')?.value.trim() || '127.0.0.1';

    const payload = {
        endpoint: selectedEndpoint,
        ip: ip,
        license: publicId,
        nonce: Array.from(crypto.getRandomValues(new Uint8Array(16))).map(b => b.toString(16).padStart(2, '0')).join(''),
        ts: Math.floor(Date.now() / 1000)
    };

    const textarea = document.getElementById('payloadTextarea');
    if (textarea) {
        // Sort keys and use compact JSON (no spaces) to match server's expected signature input
        const sortedPayload = {};
        Object.keys(payload).sort().forEach(k => sortedPayload[k] = payload[k]);
        textarea.value = JSON.stringify(sortedPayload); // COMPACT JSON (no spaces)
    }
}

// HMAC-SHA256 using Web Crypto API
async function hmacSHA256(key, message) {
    const encoder = new TextEncoder();
    const cryptoKey = await crypto.subtle.importKey(
        'raw',
        encoder.encode(key),
        { name: 'HMAC', hash: 'SHA-256' },
        false,
        ['sign']
    );
    const sig = await crypto.subtle.sign('HMAC', cryptoKey, encoder.encode(message));
    return Array.from(new Uint8Array(sig)).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function generateSignedHeaders(licenseKey, manualPayloadJson = null) {
    let payloadJson = manualPayloadJson;
    let payload;

    try {
        payload = JSON.parse(payloadJson);
    } catch (e) {
        payload = { error: 'Invalid JSON' };
    }

    // Standardize: Re-stringify with NO spaces to ensure consistency 
    // This is what we will sign AND what we will send in the payload header
    payloadJson = JSON.stringify(payload, Object.keys(payload).sort());

    const uint8Array = new TextEncoder().encode(payloadJson);
    const payloadB64 = btoa(String.fromCharCode.apply(null, uint8Array));
    const secret = licenseKey || 'none';
    const signature = await hmacSHA256(secret, payloadJson);

    return {
        headers: {
            'User-Agent': 'phBot-SROManager/1.7.0',
            'Accept': 'application/json',
            'X-SROMANAGER-Payload': payloadB64,
            'X-SROMANAGER-Signature': signature,
            'X-SROMANAGER-Tester': 'true'
        },
        payload: payload,
        payloadJson: payloadJson
    };
}

async function runSignedTest() {
    const publicId = document.getElementById('testPublicId').value.trim();
    const ip = document.getElementById('testIp').value.trim();

    if (!publicId) {
        showToast('Please enter a Public ID (license key)', 'error');
        return;
    }
    if (!ip) {
        showToast('Please enter an IP address', 'error');
        return;
    }

    // Build URL based on endpoint
    let url = '';
    if (selectedEndpoint === 'validate') {
        url = `/api/validate?publicId=${encodeURIComponent(publicId)}&ip=${encodeURIComponent(ip)}`;
    } else if (selectedEndpoint === 'download') {
        const type = document.getElementById('testType').value;
        const filename = document.getElementById('testFilename').value;
        if (!filename) { showToast('Please select a filename', 'error'); return; }
        url = `/api/download?publicId=${encodeURIComponent(publicId)}&ip=${encodeURIComponent(ip)}&type=${type}&filename=${encodeURIComponent(filename)}`;
    } else if (selectedEndpoint === 'list') {
        const type = document.getElementById('testType').value;
        url = `/api/list?publicId=${encodeURIComponent(publicId)}&ip=${encodeURIComponent(ip)}&type=${type}`;
    }

    // Generate signed headers
    const btn = document.getElementById('runTestBtn');
    const manualPayload = document.getElementById('payloadTextarea').value;

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing & Sending...';

    try {
        const signed = await generateSignedHeaders(publicId, manualPayload);

        // Display headers
        document.getElementById('hdrUserAgent').textContent = signed.headers['User-Agent'];
        document.getElementById('hdrPayload').textContent = signed.headers['X-SROMANAGER-Payload'];
        document.getElementById('hdrSignature').textContent = signed.headers['X-SROMANAGER-Signature'];
        document.getElementById('testHeadersSection').style.display = 'block';

        // Send request
        const startTime = performance.now();
        const response = await fetch(url, {
            method: 'GET',
            headers: signed.headers
        });
        const elapsed = Math.round(performance.now() - startTime);

        // Display response
        const statusEl = document.getElementById('responseStatus');
        const statusClass = response.ok ? 'success' : (response.status >= 400 && response.status < 500 ? 'error' : 'warning');
        statusEl.className = `status-tag ${statusClass}`;
        statusEl.textContent = `${response.status} ${response.statusText}`;

        document.getElementById('responseTime').textContent = `${elapsed}ms`;

        let bodyText;
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            const json = await response.json();
            bodyText = JSON.stringify(json, null, 2);
        } else if (contentType.includes('text/')) {
            bodyText = await response.text();
        } else {
            bodyText = `[Binary response: ${contentType}, ${response.headers.get('content-length') || '?'} bytes]`;
        }
        document.getElementById('responseBody').textContent = bodyText;
        document.getElementById('testResponseSection').style.display = 'block';

    } catch (error) {
        document.getElementById('responseStatus').className = 'status-tag error';
        document.getElementById('responseStatus').textContent = 'Network Error';
        document.getElementById('responseTime').textContent = '';
        document.getElementById('responseBody').textContent = error.message;
        document.getElementById('testResponseSection').style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-paper-plane"></i> Send Signed Request';
    }
}


// ==============================
// TAB SWITCHING
// ==============================

function showTab(tabName) {
    const tabs = {
        users: elements.usersTab,
        files: elements.filesTab,
        tester: elements.testerTab
    };
    const sections = {
        users: elements.usersSection,
        files: elements.filesSection,
        tester: elements.testerSection
    };

    // Update header
    const headerInfo = {
        users: { title: 'User Management', desc: 'Generate and manage license keys for SRO Bot users.' },
        files: { title: 'File Manager', desc: 'Upload and manage caravan & SC script files.' },
        tester: { title: 'API Client Simulator', desc: 'Simulate signed phBot-SROManager requests and test all public API endpoints.' }
    };

    // Hide all sections, deactivate all tabs
    Object.values(tabs).forEach(t => t && t.classList.remove('active'));
    Object.values(sections).forEach(s => { if (s) s.style.display = 'none'; });

    // Activate selected
    if (tabs[tabName]) tabs[tabName].classList.add('active');
    if (sections[tabName]) sections[tabName].style.display = 'block';

    // Update header
    const h1 = document.querySelector('header h1');
    const p = document.querySelector('header p');
    const headerRight = document.querySelector('.header-right');

    if (h1 && headerInfo[tabName]) h1.textContent = headerInfo[tabName].title;
    if (p && headerInfo[tabName]) p.textContent = headerInfo[tabName].desc;

    // Show/hide create user button
    if (headerRight) headerRight.style.display = tabName === 'users' ? 'flex' : 'none';

    // Load data for the tab
    if (tabName === 'users') fetchUsers();
    if (tabName === 'files') fetchManagedFiles();
    if (tabName === 'tester') {
        fetchFiles();
        updateDefaultPayload();
    }
}


// ==============================
// TOAST NOTIFICATIONS
// ==============================

function showToast(message, type = 'success') {
    const existing = document.querySelector('.upload-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `upload-toast ${type}`;
    toast.innerHTML = `
        <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}" 
           style="font-size: 20px; color: ${type === 'success' ? '#4ade80' : '#ff006e'};"></i>
        <span style="font-size: 14px;">${message}</span>
    `;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'toastSlideOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}


// ==============================
// LOGOUT
// ==============================

async function doLogout() {
    await fetch('/auth/logout', { method: 'POST' });
    window.location.href = '/';
}


// ==============================
// EVENT LISTENERS
// ==============================

if (elements.logoutBtn) elements.logoutBtn.addEventListener('click', doLogout);
if (elements.usersTab) elements.usersTab.addEventListener('click', () => showTab('users'));
if (elements.filesTab) elements.filesTab.addEventListener('click', () => showTab('files'));
if (elements.testerTab) elements.testerTab.addEventListener('click', () => showTab('tester'));
if (document.getElementById('testType')) document.getElementById('testType').addEventListener('change', updateFileDropdown);
if (document.getElementById('testPublicId')) document.getElementById('testPublicId').addEventListener('input', updateDefaultPayload);
if (document.getElementById('testIp')) document.getElementById('testIp').addEventListener('input', updateDefaultPayload);
if (document.getElementById('testType')) document.getElementById('testType').addEventListener('change', updateDefaultPayload);
elements.createUserBtn.addEventListener('click', openModal);
elements.closeModal.addEventListener('click', closeModal);
elements.saveUser.addEventListener('click', saveUser);
elements.closeSessionModal.addEventListener('click', closeSessionModal);
elements.dismissSessionModal.addEventListener('click', closeSessionModal);
if (elements.clearAllSessionsBtn) elements.clearAllSessionsBtn.addEventListener('click', clearAllSessions);
if (elements.closePreviewModal) elements.closePreviewModal.addEventListener('click', closePreviewModal);

// Setup drop zones
if (elements.caravanDropZone && elements.caravanUploadInput) {
    setupDropZone(elements.caravanDropZone, 'CARAVAN', elements.caravanUploadInput);
}
if (elements.scDropZone && elements.scUploadInput) {
    setupDropZone(elements.scDropZone, 'SC', elements.scUploadInput);
}
if (elements.featureDropZone && elements.featureUploadInput) {
    setupDropZone(elements.featureDropZone, 'FEATURE', elements.featureUploadInput);
}

// Modal close on backdrop click
window.onclick = function (event) {
    if (event.target == elements.userModal) closeModal();
    if (event.target == elements.sessionModal) closeSessionModal();
    if (event.target == elements.filePreviewModal) closePreviewModal();
}

// ==============================
// INITIAL LOAD
// ==============================

fetchUsers();
setInterval(fetchUsers, 30000);
