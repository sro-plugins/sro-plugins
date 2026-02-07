const apiBase = '/admin/api';

const elements = {
    userList: document.getElementById('userList'),
    totalUsers: document.getElementById('totalUsers'),
    activeSessions: document.getElementById('activeSessions'),
    createUserBtn: document.getElementById('createUserBtn'),
    userModal: document.getElementById('userModal'),
    closeModal: document.getElementById('closeModal'),
    saveUser: document.getElementById('saveUser'),
    usernameInput: document.getElementById('usernameInput')
};

// State
let users = [];

// Fetch Users
async function fetchUsers() {
    try {
        const response = await fetch(`${apiBase}/users`);
        users = await response.json();
        renderUsers();
        updateStats();
    } catch (error) {
        console.error('Error fetching users:', error);
    }
}

// Render Users to Table
function renderUsers() {
    elements.userList.innerHTML = '';

    if (users.length === 0) {
        elements.userList.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #b0b0b0;">No users found. Generate a new key to start!</td></tr>`;
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
                <span class="status-tag ${user.is_active ? 'active' : 'inactive'}">
                    ${user.is_active ? 'Active' : 'Disabled'}
                </span>
            </td>
            <td>
                <div style="display:flex; gap: 10px;">
                    <button class="btn danger" style="padding: 8px 12px;" onclick="deleteUser(${user.id})">
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
    // Active sessions would ideally come from another endpoint
    elements.activeSessions.innerText = 'Online';
}

// Create User
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

// Delete User
async function deleteUser(id) {
    if (!confirm('Are you sure you want to delete this user? This will invalidate their license key.')) return;

    try {
        await fetch(`${apiBase}/users/${id}`, { method: 'DELETE' });
        fetchUsers();
    } catch (error) {
        console.error('Error deleting user:', error);
    }
}

// Copy to Clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text);
    alert('Public ID copied to clipboard!');
}

// Modal Toggle
function openModal() {
    elements.userModal.style.display = 'flex';
}

function closeModal() {
    elements.userModal.style.display = 'none';
}

// Event Listeners
elements.createUserBtn.addEventListener('click', openModal);
elements.closeModal.addEventListener('click', closeModal);
elements.saveUser.addEventListener('click', saveUser);

window.onclick = function (event) {
    if (event.target == elements.userModal) closeModal();
}

// Initial Load
fetchUsers();
setInterval(fetchUsers, 30000); // Refresh every 30s
