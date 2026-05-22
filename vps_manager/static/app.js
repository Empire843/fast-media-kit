// STATE SYSTEM
const state = {
    connected: false,
    vpsIp: '',
    vpsPort: 10056,
    activeTab: 'dashboard',
    statusInterval: null,
    currentLogContainer: null,
    currentFilePath: '',
    editingFilePath: ''
};

// DOM ELEMENTS
const dom = {
    navButtons: document.querySelectorAll('.nav-btn'),
    tabContents: document.querySelectorAll('.tab-content'),
    connBadge: document.getElementById('conn-badge'),
    connStatusText: document.getElementById('conn-status-text'),
    vpsIpDisplay: document.getElementById('vps-ip-display'),
    vpsPill: document.getElementById('vps-pill'),
    uptimeText: document.getElementById('uptime-text'),
    
    // Metrics
    cpuVal: document.getElementById('cpu-val'),
    cpuBar: document.getElementById('cpu-bar'),
    ramVal: document.getElementById('ram-val'),
    ramBar: document.getElementById('ram-bar'),
    ramSub: document.getElementById('ram-sub'),
    diskVal: document.getElementById('disk-val'),
    diskBar: document.getElementById('disk-bar'),
    diskSub: document.getElementById('disk-sub'),
    
    // Quick Status
    kitStatusDot: document.getElementById('kit-status-dot'),
    kitStatusText: document.getElementById('kit-status-text'),
    
    // Docker Table
    dockerTbody: document.getElementById('docker-tbody'),
    
    // Env Editor
    envTextarea: document.getElementById('env-textarea'),
    saveEnvBtn: document.getElementById('save-env-btn'),
    saveRestartEnvBtn: document.getElementById('save-restart-env-btn'),
    
    // Terminal
    termOutput: document.getElementById('term-output'),
    termInput: document.getElementById('term-input'),
    
    // Settings Form
    settingsForm: document.getElementById('settings-form'),
    vpsIpInput: document.getElementById('vps-ip'),
    vpsPortInput: document.getElementById('vps-port'),
    vpsUserInput: document.getElementById('vps-user'),
    vpsPassInput: document.getElementById('vps-pass'),
    saveConfigCheck: document.getElementById('save-config-check'),
    connectSubmitBtn: document.getElementById('connect-submit-btn'),
    
    // Modal Logs
    logsModal: document.getElementById('logs-modal'),
    modalContainerName: document.getElementById('modal-container-name'),
    logsPre: document.getElementById('logs-pre'),
    
    // Files Tab Elements
    filesTbody: document.getElementById('files-tbody'),
    filesCurrentPath: document.getElementById('files-current-path'),
    filesUpBtn: document.getElementById('files-up-btn'),
    
    // File Editor Modal Elements
    fileEditorModal: document.getElementById('file-editor-modal'),
    modalFileName: document.getElementById('modal-file-name'),
    modalFileTextarea: document.getElementById('modal-file-textarea'),
    saveFileContentBtn: document.getElementById('save-file-content-btn'),
    
    toastContainer: document.getElementById('toast-container')
};

// INITIALIZE APP
document.addEventListener('DOMContentLoaded', () => {
    setupNavigation();
    loadConnectionConfig();
    setupSettingsForm();
    setupEnvActions();
    setupTerminal();
    setupFilesTab();
    
    // Định kỳ refresh dữ liệu mỗi 8 giây nếu đã kết nối
    setInterval(() => {
        if (state.connected) {
            loadDashboardMetrics();
            loadDockerContainers();
        }
    }, 8000);
});

// TOAST NOTIFICATIONS
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = 'fa-circle-info';
    if (type === 'success') icon = 'fa-circle-check';
    if (type === 'error') icon = 'fa-triangle-exclamation';
    
    toast.innerHTML = `
        <i class="fa-solid ${icon}"></i>
        <div>${message}</div>
    `;
    
    dom.toastContainer.appendChild(toast);
    
    // Tự biến mất sau 4 giây
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s reverse forwards';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// SETUP NAVIGATION
function setupNavigation() {
    dom.navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    // Ẩn tất cả tab và nút active
    dom.navButtons.forEach(b => b.classList.remove('active'));
    dom.tabContents.forEach(c => c.classList.remove('active'));
    
    // Kích hoạt tab và nút mới
    document.querySelector(`.nav-btn[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.add('active');
    
    state.activeTab = tabName;
    
    // Tải dữ liệu cụ thể cho từng tab khi được click vào
    if (state.connected) {
        if (tabName === 'dashboard') {
            loadDashboardMetrics();
        } else if (tabName === 'docker') {
            loadDockerContainers();
        } else if (tabName === 'env') {
            loadEnvContent();
        } else if (tabName === 'files') {
            loadFiles(state.currentFilePath);
        }
    } else {
        if (tabName !== 'settings') {
            showToast('Vui lòng cấu hình kết nối tới VPS trước.', 'info');
            switchTab('settings');
        }
    }
}

// UPDATE CONNECTION BADGE
function setConnectionState(isConnected, ip = '', port = 10056) {
    state.connected = isConnected;
    state.vpsIp = ip;
    state.vpsPort = port;
    
    if (isConnected) {
        dom.connBadge.className = 'connection-badge status-connected';
        dom.connStatusText.innerText = 'Đã kết nối VPS';
        dom.vpsIpDisplay.innerText = `${ip}:${port}`;
        dom.vpsPill.style.display = 'flex';
        
        // Tự động tải dữ liệu
        loadDashboardMetrics();
        loadDockerContainers();
    } else {
        dom.connBadge.className = 'connection-badge status-disconnected';
        dom.connStatusText.innerText = 'Chưa kết nối';
        dom.vpsIpDisplay.innerText = '93.127.135.137';
        dom.vpsPill.style.display = 'none';
        dom.uptimeText.innerText = 'Thời gian hoạt động: Chưa kết nối';
    }
}

// API CALLS: LOAD SAVED CONFIG ON STARTUP
async function loadConnectionConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        
        if (config.ip) {
            dom.vpsIpInput.value = config.ip;
            dom.vpsPortInput.value = config.port;
            dom.vpsUserInput.value = config.username;
            if (config.has_password) {
                dom.vpsPassInput.placeholder = '•••••••••••••••• (Đã lưu)';
            }
            
            // Tự động kiểm tra và kết nối ngầm nếu đã lưu cấu hình
            tryConnect(config.ip, config.port, config.username, '', true);
        } else {
            // Chuyển sang tab Settings nếu chưa cấu hình
            switchTab('settings');
        }
    } catch (error) {
        console.error('Không thể lấy cấu hình đã lưu:', error);
        switchTab('settings');
    }
}

// SETUP SETTINGS FORM
function setupSettingsForm() {
    dom.settingsForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const ip = dom.vpsIpInput.value.trim();
        const port = parseInt(dom.vpsPortInput.value);
        const username = dom.vpsUserInput.value.trim();
        const password = dom.vpsPassInput.value;
        const saveConfig = dom.saveConfigCheck.checked;
        
        dom.connectSubmitBtn.disabled = true;
        dom.connectSubmitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang kết nối tới VPS...';
        
        await tryConnect(ip, port, username, password, false, saveConfig);
        
        dom.connectSubmitBtn.disabled = false;
        dom.connectSubmitBtn.innerHTML = '<i class="fa-solid fa-circle-nodes"></i> Kiểm tra & Lưu cấu hình';
    });
}

// TRY TO CONNECT API
async function tryConnect(ip, port, username, password, isSilent = false, saveConfig = true) {
    try {
        const response = await fetch('/api/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip, port, username, password, save_config: saveConfig })
        });
        
        const res = await response.json();
        
        if (response.ok) {
            setConnectionState(true, ip, port);
            if (!isSilent) {
                showToast('Kết nối VPS thành công!', 'success');
                switchTab('dashboard');
            }
        } else {
            setConnectionState(false);
            if (!isSilent) {
                showToast(res.detail || 'Lỗi kết nối VPS.', 'error');
            }
        }
    } catch (err) {
        setConnectionState(false);
        if (!isSilent) {
            showToast('Lỗi mạng: Không kết nối được Backend Dashboard.', 'error');
        }
    }
}

// API CALLS: LOAD METRICS
async function loadDashboardMetrics() {
    try {
        const response = await fetch('/api/status');
        if (!response.ok) return;
        
        const data = await response.json();
        
        // Update Uptime
        dom.uptimeText.innerText = `Thời gian hoạt động: ${data.uptime.split('up')[1]?.split(',')[0]?.trim() || data.uptime}`;
        
        // Update CPU
        dom.cpuVal.innerText = `${data.cpu}%`;
        dom.cpuBar.style.width = `${data.cpu}%`;
        
        // Update RAM
        if (data.ram && data.ram.total) {
            const ramPercent = Math.round((data.ram.used / data.ram.total) * 100);
            dom.ramVal.innerText = `${data.ram.used} / ${data.ram.total} MB (${ramPercent}%)`;
            dom.ramBar.style.width = `${ramPercent}%`;
            dom.ramSub.innerText = `Khả dụng: ${data.ram.available} MB`;
        }
        
        // Update Disk
        if (data.disk) {
            dom.diskVal.innerText = `${data.disk.percent}%`;
            dom.diskBar.style.width = `${data.disk.percent}%`;
            dom.diskSub.innerText = `Đã dùng: ${data.disk.used} / ${data.disk.size} (Khả trống: ${data.disk.avail})`;
        }
    } catch (err) {
        console.error('Lỗi lấy status:', err);
    }
}

// API CALLS: LOAD DOCKER
async function loadDockerContainers() {
    try {
        const response = await fetch('/api/containers');
        if (!response.ok) {
            dom.dockerTbody.innerHTML = `<tr><td colspan="5" class="text-center text-danger">Lỗi lấy danh sách từ VPS.</td></tr>`;
            return;
        }
        
        const containers = await response.json();
        
        if (containers.length === 0) {
            dom.dockerTbody.innerHTML = `<tr><td colspan="5" class="text-center">Không tìm thấy Docker container nào trên VPS.</td></tr>`;
            dom.kitStatusDot.parentElement.className = 'status-indicator stopped';
            dom.kitStatusText.innerText = 'Chưa tạo container';
            return;
        }
        
        dom.dockerTbody.innerHTML = '';
        
        let hasFastMedia = false;
        let fastMediaRunning = false;
        
        containers.forEach(c => {
            const isRunning = c.State === 'running' || c.Status.toLowerCase().includes('up');
            
            if (c.Names === 'fast-media-container') {
                hasFastMedia = true;
                fastMediaRunning = isRunning;
            }
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${c.Names}</strong></td>
                <td><code style="background: rgba(255,255,255,0.05); padding: 2px 6px; border-radius: 4px; font-family: var(--font-mono); font-size: 12px;">${c.Image}</code></td>
                <td>
                    <span class="badge ${isRunning ? 'badge-success' : 'badge-danger'}">
                        ${isRunning ? 'Running' : 'Stopped'}
                    </span>
                </td>
                <td><code style="font-family: var(--font-mono); font-size: 12px;">${c.Ports || 'Không ánh xạ'}</code></td>
                <td>
                    <div style="display: flex; gap: 8px;">
                        ${isRunning ? 
                            `<button class="tbl-action-btn" title="Stop Container" onclick="triggerContainerAction('${c.Names}', 'stop')"><i class="fa-solid fa-square-minus"></i> Stop</button>` :
                            `<button class="tbl-action-btn" style="color: var(--neon-green)" title="Start Container" onclick="triggerContainerAction('${c.Names}', 'start')"><i class="fa-solid fa-circle-play"></i> Start</button>`
                        }
                        <button class="tbl-action-btn" title="Restart Container" onclick="triggerContainerAction('${c.Names}', 'restart')"><i class="fa-solid fa-rotate-left"></i> Restart</button>
                        <button class="tbl-action-btn" title="Xem Logs" onclick="viewContainerLogs('${c.Names}')"><i class="fa-solid fa-receipt"></i> Logs</button>
                    </div>
                </td>
            `;
            dom.dockerTbody.appendChild(tr);
        });
        
        // Cập nhật trạng thái "Fast Media Kit" Quick Status ở trang chủ
        if (hasFastMedia) {
            if (fastMediaRunning) {
                dom.kitStatusDot.parentElement.className = 'status-indicator active';
                dom.kitStatusText.innerText = 'Hoạt động (Đang chạy ở cổng 10057)';
            } else {
                dom.kitStatusDot.parentElement.className = 'status-indicator stopped';
                dom.kitStatusText.innerText = 'Đã tắt (Stopped)';
            }
        } else {
            dom.kitStatusDot.parentElement.className = 'status-indicator stopped';
            dom.kitStatusText.innerText = 'Không tìm thấy container fast-media-container';
        }
    } catch (err) {
        console.error('Lỗi danh sách docker:', err);
    }
}

// TRIGGER CONTAINER ACTION (START, STOP, RESTART)
async function triggerContainerAction(name, action) {
    showToast(`Đang gửi lệnh ${action.toUpperCase()} tới container ${name}...`, 'info');
    try {
        const response = await fetch('/api/container/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, action })
        });
        
        const res = await response.json();
        
        if (response.ok) {
            showToast(res.message, 'success');
            loadDockerContainers();
        } else {
            showToast(res.detail || `Lỗi thực hiện lệnh ${action}.`, 'error');
        }
    } catch (err) {
        showToast('Lỗi mạng kết nối tới máy chủ quản lý.', 'error');
    }
}

// VIEW CONTAINER LOGS
async function viewContainerLogs(name) {
    state.currentLogContainer = name;
    dom.modalContainerName.innerText = name;
    dom.logsPre.innerText = 'Đang lấy dữ liệu logs từ VPS...';
    dom.logsModal.classList.add('active');
    
    await fetchLogs(name);
}

async function fetchLogs(name) {
    try {
        const response = await fetch(`/api/container/logs?name=${encodeURIComponent(name)}`);
        const data = await response.json();
        
        if (response.ok) {
            dom.logsPre.innerText = data.logs || 'Container hiện chưa có log nào.';
            // Auto scroll xuống cuối log
            dom.logsPre.scrollTop = dom.logsPre.scrollHeight;
        } else {
            dom.logsPre.innerText = `Lỗi: Không lấy được log từ VPS. ${data.detail || ''}`;
        }
    } catch (err) {
        dom.logsPre.innerText = 'Lỗi mạng khi tải logs.';
    }
}

function refreshCurrentLogs() {
    if (state.currentLogContainer) {
        fetchLogs(state.currentLogContainer);
    }
}

function closeLogsModal() {
    dom.logsModal.classList.remove('active');
    state.currentLogContainer = null;
}

// TAB: ENVIRONMENT ACTIONS
async function loadEnvContent() {
    dom.envTextarea.value = '# Đang tải file cấu hình .env từ VPS...';
    try {
        const response = await fetch('/api/env');
        const data = await response.json();
        if (response.ok) {
            dom.envTextarea.value = data.content;
        } else {
            dom.envTextarea.value = `# Không đọc được file .env từ VPS: ${data.detail || ''}`;
        }
    } catch (err) {
        dom.envTextarea.value = '# Lỗi mạng không thể kết nối tới Backend.';
    }
}

function setupEnvActions() {
    dom.saveEnvBtn.addEventListener('click', () => saveEnv(false));
    dom.saveRestartEnvBtn.addEventListener('click', () => saveEnv(true));
}

async function saveEnv(shouldRestart) {
    const content = dom.envTextarea.value;
    
    dom.saveEnvBtn.disabled = true;
    dom.saveRestartEnvBtn.disabled = true;
    showToast('Đang lưu cấu hình .env lên VPS...', 'info');
    
    try {
        const response = await fetch('/api/env', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        });
        
        const res = await response.json();
        
        if (response.ok) {
            showToast('Đã lưu file .env thành công lên VPS!', 'success');
            
            if (shouldRestart) {
                await triggerContainerAction('fast-media-container', 'restart');
            }
        } else {
            showToast(res.detail || 'Lỗi lưu cấu hình .env.', 'error');
        }
    } catch (err) {
        showToast('Lỗi mạng không thể gửi file .env.', 'error');
    } finally {
        dom.saveEnvBtn.disabled = false;
        dom.saveRestartEnvBtn.disabled = false;
    }
}

// TAB: TERMINAL INTERACTION
function setupTerminal() {
    dom.termInput.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
            const command = dom.termInput.value.trim();
            if (!command) return;
            
            // Thêm lệnh vào màn hình terminal
            appendTermOutput(`vps-administrator@vps-zksx:~$ ${command}`);
            dom.termInput.value = '';
            
            // Xử lý clear
            if (command === 'clear') {
                dom.termOutput.innerText = 'vps-administrator@vps-zksx:~$ Console cleared.';
                return;
            }
            
            try {
                const response = await fetch('/api/terminal', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command })
                });
                
                const data = await response.json();
                if (response.ok) {
                    if (data.output) appendTermOutput(data.output);
                    if (data.error) appendTermOutput(data.error, true);
                    if (!data.output && !data.error) appendTermOutput('(Lệnh đã chạy nhưng không có output trả về)');
                } else {
                    appendTermOutput(`Lỗi thực thi lệnh: ${data.detail || 'Unknown error'}`, true);
                }
            } catch (err) {
                appendTermOutput('Lỗi mạng: Không thể truyền lệnh đến Backend.', true);
            }
        }
    });
}

function appendTermOutput(text, isError = false) {
    const color = isError ? 'color: var(--neon-red)' : '';
    const span = document.createElement('span');
    span.style = color;
    span.innerText = text + '\n';
    dom.termOutput.appendChild(span);
    
    // Cuộn xuống cuối
    dom.termOutput.scrollTop = dom.termOutput.scrollHeight;
}

// ==========================================
// FILE MANAGER ACTIONS
// ==========================================

function setupFilesTab() {
    dom.filesUpBtn.addEventListener('click', () => {
        const parent = dom.filesUpBtn.getAttribute('data-parent');
        if (parent) {
            loadFiles(parent);
        }
    });
    
    dom.saveFileContentBtn.addEventListener('click', () => {
        if (state.editingFilePath) {
            saveFileContent(state.editingFilePath);
        }
    });
}

async function loadFiles(path = '') {
    dom.filesTbody.innerHTML = `<tr><td colspan="3" class="text-center"><i class="fa-solid fa-spinner fa-spin"></i> Đang đọc thư mục trên VPS...</td></tr>`;
    
    try {
        const url = `/api/files?path=${encodeURIComponent(path)}`;
        const response = await fetch(url);
        const data = await response.json();
        
        if (response.ok) {
            state.currentFilePath = data.current_path;
            dom.filesCurrentPath.innerText = data.current_path;
            
            // Cập nhật nút Lên một cấp
            if (data.parent_path) {
                dom.filesUpBtn.disabled = false;
                dom.filesUpBtn.setAttribute('data-parent', data.parent_path);
            } else {
                dom.filesUpBtn.disabled = true;
                dom.filesUpBtn.removeAttribute('data-parent');
            }
            
            // Hiển thị danh sách file
            dom.filesTbody.innerHTML = '';
            
            if (data.files.length === 0) {
                dom.filesTbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">Thư mục trống.</td></tr>`;
                return;
            }
            
            data.files.forEach(f => {
                const tr = document.createElement('tr');
                const icon = f.is_dir ? '<i class="fa-solid fa-folder" style="color: var(--warning-color); margin-right: 8px;"></i>' : '<i class="fa-solid fa-file" style="color: var(--neon-blue); margin-right: 8px;"></i>';
                
                // Clicking folders navigates inside them, files opens editor
                const nameLink = f.is_dir ? 
                    `<a href="#" onclick="event.preventDefault(); loadFiles('${f.path}')" style="color: var(--neon-green); font-weight: 500; text-decoration: none;">${icon}${f.name}</a>` :
                    `<a href="#" onclick="event.preventDefault(); viewFileContent('${f.path}')" style="color: var(--text-color); text-decoration: none;">${icon}${f.name}</a>`;
                    
                const sizeText = f.is_dir ? '--' : formatBytes(f.size);
                
                tr.innerHTML = `
                    <td>${nameLink}</td>
                    <td><code style="font-family: var(--font-mono); font-size: 12px;">${sizeText}</code></td>
                    <td>
                        <div style="display: flex; gap: 8px;">
                            ${!f.is_dir ? `<button class="tbl-action-btn" style="color: var(--neon-blue);" onclick="viewFileContent('${f.path}')"><i class="fa-solid fa-file-pen"></i> Sửa</button>` : ''}
                            <button class="tbl-action-btn" style="color: var(--neon-red);" onclick="deleteFile('${f.path}')"><i class="fa-solid fa-trash"></i> Xóa</button>
                        </div>
                    </td>
                `;
                dom.filesTbody.appendChild(tr);
            });
        } else {
            dom.filesTbody.innerHTML = `<tr><td colspan="3" class="text-center text-danger">Lỗi: ${data.detail || 'Không lấy được danh sách file.'}</td></tr>`;
        }
    } catch (err) {
        dom.filesTbody.innerHTML = `<tr><td colspan="3" class="text-center text-danger">Lỗi kết nối tới server dashboard.</td></tr>`;
    }
}

function promptMkdir() {
    const name = prompt('Nhập tên thư mục mới cần tạo:');
    if (!name) return;
    
    mkdir(state.currentFilePath, name.trim());
}

async function mkdir(path, name) {
    try {
        const response = await fetch('/api/files/mkdir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path, name })
        });
        
        const data = await response.json();
        if (response.ok) {
            showToast('Tạo thư mục thành công!', 'success');
            loadFiles(state.currentFilePath);
        } else {
            showToast(data.detail || 'Lỗi khi tạo thư mục.', 'error');
        }
    } catch (err) {
        showToast('Lỗi kết nối tới Backend.', 'error');
    }
}

function promptCreateFile() {
    const name = prompt('Nhập tên file mới cần tạo:');
    if (!name) return;
    
    createFile(state.currentFilePath, name.trim());
}

async function createFile(path, name) {
    try {
        const response = await fetch('/api/files/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path, name })
        });
        
        const data = await response.json();
        if (response.ok) {
            showToast('Tạo file thành công!', 'success');
            loadFiles(state.currentFilePath);
        } else {
            showToast(data.detail || 'Lỗi khi tạo file.', 'error');
        }
    } catch (err) {
        showToast('Lỗi kết nối tới Backend.', 'error');
    }
}

async function viewFileContent(filePath) {
    state.editingFilePath = filePath;
    dom.modalFileName.innerText = filePath.split('/').pop();
    dom.modalFileTextarea.value = 'Đang đọc nội dung file từ VPS...';
    dom.fileEditorModal.classList.add('active');
    
    try {
        const response = await fetch(`/api/files/content?path=${encodeURIComponent(filePath)}`);
        const data = await response.json();
        
        if (response.ok) {
            dom.modalFileTextarea.value = data.content;
        } else {
            dom.modalFileTextarea.value = `Lỗi đọc file: ${data.detail}`;
        }
    } catch (err) {
        dom.modalFileTextarea.value = 'Lỗi kết nối mạng.';
    }
}

function closeFileEditorModal() {
    dom.fileEditorModal.classList.remove('active');
    state.editingFilePath = '';
}

async function saveFileContent(filePath) {
    const content = dom.modalFileTextarea.value;
    dom.saveFileContentBtn.disabled = true;
    dom.saveFileContentBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang lưu...';
    
    try {
        const response = await fetch('/api/files/content', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: filePath, content })
        });
        
        const data = await response.json();
        if (response.ok) {
            showToast('Đã lưu file thành công!', 'success');
            closeFileEditorModal();
            loadFiles(state.currentFilePath);
        } else {
            showToast(data.detail || 'Lỗi khi lưu file.', 'error');
        }
    } catch (err) {
        showToast('Lỗi kết nối mạng.', 'error');
    } finally {
        dom.saveFileContentBtn.disabled = false;
        dom.saveFileContentBtn.innerHTML = 'Lưu File';
    }
}

async function deleteFile(filePath) {
    if (!confirm(`Bạn có chắc chắn muốn xóa file/thư mục:\n${filePath}?\nHành động này không thể hoàn tác!`)) return;
    
    try {
        const response = await fetch(`/api/files?path=${encodeURIComponent(filePath)}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        if (response.ok) {
            showToast('Đã xóa thành công!', 'success');
            loadFiles(state.currentFilePath);
        } else {
            showToast(data.detail || 'Lỗi khi xóa.', 'error');
        }
    } catch (err) {
        showToast('Lỗi kết nối mạng.', 'error');
    }
}

function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}
