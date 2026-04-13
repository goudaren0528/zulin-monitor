# 数据管理功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增数据管理Tab，支持配置文件和数据库的导出/导入功能，实现多设备间数据同步。

**Architecture:** 后端新增5个API端点处理导出/导入/备份操作；前端在现有Tab结构中新增「数据管理」Tab，包含导出、导入、备份管理三个区块。

**Tech Stack:** Flask后端API + Bootstrap前端UI + zipfile/tempfile Python库

---

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| `app.py` | 后端API实现 | 新增导出/导入/备份API |
| `templates/index.html` | 前端UI | 新增Tab导航和内容区块 |
| `backups/` | 备份存储目录 | 新建目录（运行时创建） |

---

### Task 1: 后端导出API

**Files:**
- Modify: `app.py` (末尾新增函数和路由)

- [ ] **Step 1: 导入必要模块**

在 `app.py` 文件顶部导入区添加：

```python
import zipfile
import tempfile
import shutil
from datetime import datetime
```

- [ ] **Step 2: 添加导出函数**

在 `app.py` 的 `add_merchant` 函数之后，`if __name__ == '__main__'` 之前添加：

```python
# --- Data Management API ---
BACKUP_DIR = "backups"
MAX_BACKUPS = 10

def _get_config_file_path():
    """获取优先使用的配置文件路径"""
    if os.path.exists("config.local.json"):
        return "config.local.json"
    if os.path.exists("config.json"):
        return "config.json"
    return None

def _create_export_zip():
    """创建导出ZIP文件，返回临时文件路径"""
    temp_dir = tempfile.mkdtemp()
    export_files = []

    # 1. 配置文件
    config_path = _get_config_file_path()
    if config_path:
        shutil.copy(config_path, os.path.join(temp_dir, "config.json"))
        export_files.append("config.json")

    # 2. 数据库文件
    if os.path.exists(DB_PATH):
        shutil.copy(DB_PATH, os.path.join(temp_dir, "records.db"))
        export_files.append("records.db")

    # 3. 导出元数据
    export_info = {
        "export_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "version": "1.0",
        "source": "order-point",
        "config_file": config_path,
        "files": export_files
    }
    if os.path.exists(DB_PATH):
        with db_lock:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM assignment_records")
            export_info["assignment_records_count"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM merchant_config")
            export_info["merchant_config_count"] = cursor.fetchone()[0]
            conn.close()

    with open(os.path.join(temp_dir, "export_info.json"), 'w', encoding='utf-8') as f:
        json.dump(export_info, f, indent=2, ensure_ascii=False)

    # 创建ZIP文件
    zip_filename = f"order-point-export-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    zip_path = os.path.join(tempfile.gettempdir(), zip_filename)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            zf.write(file_path, filename)

    # 清理临时目录
    shutil.rmtree(temp_dir)

    return zip_path, zip_filename

@app.route('/api/data/export', methods=['GET'])
def export_data():
    """导出数据为ZIP文件"""
    try:
        zip_path, zip_filename = _create_export_zip()
        from flask import send_file
        response = send_file(
            zip_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )
        # 延迟删除临时ZIP文件
        @response.call_on_close
        def cleanup():
            try:
                os.remove(zip_path)
            except:
                pass
        return response
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
```

- [ ] **Step 3: 测试导出API**

启动服务后访问：`http://localhost:5050/api/data/export`
Expected: 返回ZIP文件下载，包含 config.json、records.db、export_info.json

- [ ] **Step 4: 提交**

```bash
git add app.py
git commit -m "feat: add data export API endpoint"
```

---

### Task 2: 后端导入API

**Files:**
- Modify: `app.py` (继续新增函数)

- [ ] **Step 1: 添加备份和导入函数**

在 `_create_export_zip` 函数之后添加：

```python
def _ensure_backup_dir():
    """确保备份目录存在"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

def _create_backup():
    """创建当前数据备份"""
    _ensure_backup_dir()
    backup_filename = f"backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        config_path = _get_config_file_path()
        if config_path:
            zf.write(config_path, "config.json")
        if os.path.exists(DB_PATH):
            zf.write(DB_PATH, "records.db")

    # 清理旧备份
    _cleanup_old_backups()

    return backup_filename

def _cleanup_old_backups():
    """清理超过限制的旧备份"""
    if not os.path.exists(BACKUP_DIR):
        return
    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.startswith("backup-") and f.endswith(".zip")],
        reverse=True
    )
    for old_backup in backups[MAX_BACKUPS:]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old_backup))
        except:
            pass

def _validate_import_zip(zip_path):
    """验证导入ZIP文件结构"""
    with zipfile.ZipFile(zip_path, 'r') as zf:
        filenames = zf.namelist()
        has_config = "config.json" in filenames
        has_db = "records.db" in filenames
        return has_config or has_db, filenames

@app.route('/api/data/import', methods=['POST'])
def import_data():
    """导入ZIP数据文件"""
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': '未上传文件'}), 400

    file = request.files['file']
    if not file.filename.endswith('.zip'):
        return jsonify({'status': 'error', 'message': '仅支持ZIP文件'}), 400

    try:
        # 保存上传文件到临时目录
        temp_zip = tempfile.mktemp(suffix='.zip')
        file.save(temp_zip)

        # 验证ZIP结构
        valid, filenames = _validate_import_zip(temp_zip)
        if not valid:
            os.remove(temp_zip)
            return jsonify({'status': 'error', 'message': 'ZIP文件缺少必需数据（config.json或records.db）'}), 400

        # 创建备份
        backup_filename = _create_backup()

        # 解压并替换
        with zipfile.ZipFile(temp_zip, 'r') as zf:
            if "config.json" in filenames:
                # 提取到临时目录再复制
                temp_dir = tempfile.mkdtemp()
                zf.extract("config.json", temp_dir)
                shutil.copy(os.path.join(temp_dir, "config.json"), "config.local.json")
                shutil.rmtree(temp_dir)

            if "records.db" in filenames:
                # 关闭可能的数据库连接
                temp_dir = tempfile.mkdtemp()
                zf.extract("records.db", temp_dir)
                shutil.copy(os.path.join(temp_dir, "records.db"), DB_PATH)
                shutil.rmtree(temp_dir)

        # 清理临时ZIP
        os.remove(temp_zip)

        # 重载配置
        scanner.load_config()

        return jsonify({
            'status': 'success',
            'message': '数据导入成功，配置已重载',
            'backup_file': backup_filename
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
```

- [ ] **Step 2: 测试导入API**

使用导出的ZIP文件测试导入：
```bash
curl -X POST -F "file=@order-point-export-*.zip" http://localhost:5050/api/data/import
```
Expected: 返回成功消息和备份文件名

- [ ] **Step 3: 提交**

```bash
git add app.py
git commit -m "feat: add data import API with automatic backup"
```

---

### Task 3: 后端备份管理API

**Files:**
- Modify: `app.py` (继续新增函数)

- [ ] **Step 1: 添加备份列表和恢复API**

在 `import_data` 函数之后添加：

```python
@app.route('/api/data/backups', methods=['GET'])
def list_backups():
    """获取备份列表"""
    _ensure_backup_dir()
    backups = []
    if os.path.exists(BACKUP_DIR):
        for filename in sorted(os.listdir(BACKUP_DIR), reverse=True):
            if filename.startswith("backup-") and filename.endswith(".zip"):
                filepath = os.path.join(BACKUP_DIR, filename)
                stat = os.stat(filepath)
                # 从文件名解析时间
                try:
                    time_str = filename.replace("backup-", "").replace(".zip", "")
                    created_at = datetime.strptime(time_str, "%Y%m%d-%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
                except:
                    created_at = ""
                backups.append({
                    "filename": filename,
                    "created_at": created_at,
                    "size": stat.st_size
                })
    return jsonify({"backups": backups})

@app.route('/api/data/backup/<filename>', methods=['GET'])
def download_backup(filename):
    """下载指定备份"""
    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'message': '备份文件不存在'}), 404
    from flask import send_file
    return send_file(filepath, mimetype='application/zip', as_attachment=True, download_name=filename)

@app.route('/api/data/backup/<filename>', methods=['POST'])
def restore_backup(filename):
    """恢复指定备份"""
    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'message': '备份文件不存在'}), 404

    try:
        # 创建新的备份（当前状态）
        new_backup = _create_backup()

        # 解压备份
        with zipfile.ZipFile(filepath, 'r') as zf:
            filenames = zf.namelist()
            temp_dir = tempfile.mkdtemp()
            zf.extractall(temp_dir)

            if "config.json" in filenames:
                shutil.copy(os.path.join(temp_dir, "config.json"), "config.local.json")
            if "records.db" in filenames:
                shutil.copy(os.path.join(temp_dir, "records.db"), DB_PATH)

            shutil.rmtree(temp_dir)

        # 重载配置
        scanner.load_config()

        return jsonify({
            'status': 'success',
            'message': f'已恢复备份 {filename}',
            'new_backup': new_backup
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/data/backup/<filename>', methods=['DELETE'])
def delete_backup(filename):
    """删除指定备份"""
    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'message': '备份文件不存在'}), 404

    try:
        os.remove(filepath)
        return jsonify({'status': 'success', 'message': f'已删除备份 {filename}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
```

- [ ] **Step 2: 测试备份API**

```bash
# 列出备份
curl http://localhost:5050/api/data/backups

# 恢复备份
curl -X POST http://localhost:5050/api/data/backup/backup-YYYYMMDD-HHMMSS.zip
```

- [ ] **Step 3: 提交**

```bash
git add app.py
git commit -m "feat: add backup management APIs (list, download, restore, delete)"
```

---

### Task 4: 前端Tab导航

**Files:**
- Modify: `templates/index.html` (Tab导航区和内容区)

- [ ] **Step 1: 添加Tab导航按钮**

找到 `<ul class="nav nav-tabs mb-4" id="myTab" role="tablist">` 部分，在 `stats-tab` 之后添加新Tab：

```html
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="data-tab" data-bs-toggle="tab" data-bs-target="#data" type="button" role="tab" aria-selected="false">
                    <!-- Database Icon -->
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <ellipse cx="12" cy="5" rx="9" ry="3"/>
                        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
                        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
                    </svg>
                    数据管理
                </button>
            </li>
```

位置：在 `</li>` (stats-tab 结束) 后面，`</ul>` 之前

- [ ] **Step 2: 提交**

```bash
git add templates/index.html
git commit -m "feat: add data management tab navigation"
```

---

### Task 5: 前端Tab内容区块

**Files:**
- Modify: `templates/index.html` (Tab内容区)

- [ ] **Step 1: 添加Tab内容**

找到 `<!-- Statistics Tab -->` 的结束位置（`<div class="tab-pane fade" id="stats"...>` 的结束 `</div>`），在其后添加：

```html
        <!-- Data Management Tab -->
        <div class="tab-pane fade" id="data" role="tabpanel" aria-labelledby="data-tab">
            <!-- Export Section -->
            <div class="card mb-4">
                <div class="card-header">
                    <span class="section-title">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" x2="12" y1="15" y2="3"/>
                        </svg>
                        导出数据
                    </span>
                </div>
                <div class="card-body">
                    <p class="text-muted mb-3">将配置文件和数据库打包导出，用于备份或同步到其他设备。</p>
                    <button class="btn btn-primary" onclick="exportData()">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" x2="12" y1="15" y2="3"/>
                        </svg>
                        一键导出
                    </button>
                    <span id="export-status" class="ms-3 text-muted small"></span>
                </div>
            </div>

            <!-- Import Section -->
            <div class="card mb-4">
                <div class="card-header">
                    <span class="section-title">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="17 8 12 3 7 8"/>
                            <line x1="12" x2="12" y1="3" y2="15"/>
                        </svg>
                        导入数据
                    </span>
                </div>
                <div class="card-body">
                    <p class="text-muted mb-3">上传ZIP文件导入数据，导入前会自动备份当前数据。<strong class="text-warning">注意：导入将完全替换当前数据。</strong></p>
                    <div class="import-upload-area" id="import-drop-zone">
                        <input type="file" id="import-file-input" accept=".zip" style="display:none" onchange="handleImportFile(this)">
                        <button class="btn btn-outline-primary" onclick="document.getElementById('import-file-input').click()">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                <polyline points="17 8 12 3 7 8"/>
                                <line x1="12" x2="12" y1="3" y2="15"/>
                            </svg>
                            选择ZIP文件
                        </button>
                        <span class="ms-3 text-muted small" id="import-file-name"></span>
                    </div>
                    <div id="import-progress" class="mt-3" style="display:none;">
                        <div class="progress">
                            <div class="progress-bar progress-bar-striped progress-bar-animated" style="width: 100%"></div>
                        </div>
                        <span class="small text-muted">正在导入...</span>
                    </div>
                    <div id="import-result" class="mt-3"></div>
                </div>
            </div>

            <!-- Backups Section -->
            <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <span class="section-title">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                            <path d="M3 3v5h5"/>
                        </svg>
                        备份管理
                    </span>
                    <button class="btn btn-sm btn-outline-secondary" onclick="loadBackups()">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M21 21v-5h-5"/></svg>
                        刷新
                    </button>
                </div>
                <div class="card-body">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>备份文件</th>
                                <th>创建时间</th>
                                <th>大小</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="backups-list-body">
                            <tr>
                                <td colspan="4" class="text-center text-muted">加载中...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
```

位置：在 `<!-- Statistics Tab -->` 的 `</div>` 之后，`<!-- Toast Container -->` 之前

- [ ] **Step 2: 提交**

```bash
git add templates/index.html
git commit -m "feat: add data management tab content section"
```

---

### Task 6: 前端JavaScript实现

**Files:**
- Modify: `templates/index.html` (script区域)

- [ ] **Step 1: 添加数据管理相关函数**

在 `<script>` 区域内，`showToast` 函数之后添加：

```javascript
        // --- Data Management Functions ---
        function exportData() {
            const statusEl = document.getElementById('export-status');
            statusEl.textContent = '正在导出...';

            fetch('/api/data/export')
                .then(response => {
                    if (!response.ok) throw new Error('导出失败');
                    return response.blob();
                })
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'order-point-export.zip';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    a.remove();
                    statusEl.textContent = '导出完成';
                    showToast('数据已成功导出', 'success');
                })
                .catch(err => {
                    statusEl.textContent = '导出失败';
                    showToast('导出失败: ' + err.message, 'error');
                });
        }

        function handleImportFile(input) {
            const file = input.files[0];
            if (!file) return;

            const fileNameEl = document.getElementById('import-file-name');
            fileNameEl.textContent = file.name;

            // 确认导入
            if (!confirm('导入将完全替换当前数据，确定继续吗？')) {
                input.value = '';
                fileNameEl.textContent = '';
                return;
            }

            const progressEl = document.getElementById('import-progress');
            const resultEl = document.getElementById('import-result');
            progressEl.style.display = 'block';
            resultEl.innerHTML = '';

            const formData = new FormData();
            formData.append('file', file);

            fetch('/api/data/import', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                progressEl.style.display = 'none';
                if (data.status === 'success') {
                    resultEl.innerHTML = `<div class="alert alert-success">${data.message}<br><small>备份文件: ${data.backup_file}</small></div>`;
                    showToast('数据导入成功', 'success');
                    // 刷新备份列表
                    loadBackups();
                } else {
                    resultEl.innerHTML = `<div class="alert alert-danger">${data.message}</div>`;
                    showToast('导入失败', 'error');
                }
            })
            .catch(err => {
                progressEl.style.display = 'none';
                resultEl.innerHTML = `<div class="alert alert-danger">导入失败: ${err.message}</div>`;
                showToast('导入失败', 'error');
            });
        }

        function loadBackups() {
            fetch('/api/data/backups')
                .then(response => response.json())
                .then(data => {
                    const tbody = document.getElementById('backups-list-body');
                    if (data.backups.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">暂无备份</td></tr>';
                        return;
                    }
                    tbody.innerHTML = data.backups.map(b => `
                        <tr>
                            <td><small>${b.filename}</small></td>
                            <td><small>${b.created_at}</small></td>
                            <td><small>${formatFileSize(b.size)}</small></td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary me-1" onclick="restoreBackup('${b.filename}')">恢复</button>
                                <button class="btn btn-sm btn-outline-secondary me-1" onclick="downloadBackup('${b.filename}')">下载</button>
                                <button class="btn btn-sm btn-outline-danger" onclick="deleteBackup('${b.filename}')">删除</button>
                            </td>
                        </tr>
                    `).join('');
                })
                .catch(err => {
                    document.getElementById('backups-list-body').innerHTML = `<tr><td colspan="4" class="text-center text-danger">加载失败</td></tr>`;
                });
        }

        function formatFileSize(bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        }

        function restoreBackup(filename) {
            if (!confirm(`恢复备份 ${filename} 将替换当前数据，确定继续吗？`)) return;

            fetch(`/api/data/backup/${filename}`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        showToast(data.message, 'success');
                        loadBackups();
                    } else {
                        showToast('恢复失败: ' + data.message, 'error');
                    }
                })
                .catch(err => showToast('恢复失败', 'error'));
        }

        function downloadBackup(filename) {
            const a = document.createElement('a');
            a.href = `/api/data/backup/${filename}`;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
        }

        function deleteBackup(filename) {
            if (!confirm(`确定删除备份 ${filename} 吗？`)) return;

            fetch(`/api/data/backup/${filename}`, { method: 'DELETE' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        showToast(data.message, 'success');
                        loadBackups();
                    } else {
                        showToast('删除失败: ' + data.message, 'error');
                    }
                })
                .catch(err => showToast('删除失败', 'error'));
        }

        // 加载备份列表（页面加载时）
        // 在data tab被点击时加载
        document.getElementById('data-tab').addEventListener('shown.bs.tab', loadBackups);
```

- [ ] **Step 2: 测试前端功能**

启动服务后访问 `http://localhost:5050`，切换到「数据管理」Tab：
- 点击导出按钮，确认ZIP文件下载
- 上传ZIP文件导入，确认导入成功提示
- 查看备份列表，测试恢复、下载、删除操作

- [ ] **Step 3: 提交**

```bash
git add templates/index.html
git commit -m "feat: add data management frontend JavaScript functions"
```

---

### Task 7: 样式美化

**Files:**
- Modify: `templates/index.html` (CSS区域)

- [ ] **Step 1: 添加导入区域样式**

在 `<style>` 区域内，`.unsaved-indicator` 之后添加：

```css
        .import-upload-area {
            border: 2px dashed var(--color-border);
            border-radius: 8px;
            padding: 24px;
            text-align: center;
            transition: border-color var(--transition-normal) var(--ease-out);
            background-color: var(--color-muted);
        }

        .import-upload-area:hover {
            border-color: var(--color-primary);
            background-color: #F1F5FD;
        }

        .import-upload-area.dragover {
            border-color: var(--color-accent);
            background-color: #ECFDF5;
        }
```

- [ ] **Step 2: 添加拖拽上传支持**

在 `handleImportFile` 函数之后添加拖拽事件处理：

```javascript
        // 拖拽上传支持
        const dropZone = document.getElementById('import-drop-zone');
        if (dropZone) {
            dropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropZone.classList.add('dragover');
            });
            dropZone.addEventListener('dragleave', () => {
                dropZone.classList.remove('dragover');
            });
            dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('dragover');
                const files = e.dataTransfer.files;
                if (files.length > 0 && files[0].name.endsWith('.zip')) {
                    const input = document.getElementById('import-file-input');
                    input.files = files;
                    handleImportFile(input);
                } else {
                    showToast('请上传ZIP文件', 'error');
                }
            });
        }
```

- [ ] **Step 3: 提交**

```bash
git add templates/index.html
git commit -m "feat: add drag-drop upload styling for data management"
```

---

### Task 8: 最终测试与集成

- [ ] **Step 1: 启动服务测试完整流程**

```bash
python app.py
```

测试清单：
1. 导出功能：点击导出 → ZIP下载 → 解压验证内容
2. 导入功能：上传ZIP → 自动备份 → 数据替换 → 配置重载
3. 备份管理：列出备份 → 恢复备份 → 下载备份 → 删除备份
4. 边界测试：上传非ZIP文件 → 上传空ZIP → 删除不存在备份

- [ ] **Step 2: 确认所有功能正常后最终提交**

```bash
git status
git add -A
git commit -m "feat: complete data management feature - export/import/backups"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ 导出功能：config.json + records.db + export_info.json
- ✅ 导入功能：ZIP上传 + 验证 + 自动备份 + 替换 + 重载配置
- ✅ 备份管理：列表 + 恢复 + 下载 + 删除
- ✅ 保留最近10个备份
- ✅ UI: 导出区 + 导入区 + 备份列表

**Placeholder scan:** 无 TBD/TODO

**Type consistency:** API路径和函数名前后端一致（exportData, loadBackups等）