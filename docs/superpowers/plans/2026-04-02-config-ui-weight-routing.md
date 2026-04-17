# 配置 UI 与权重分配功能实现计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为订单分配系统添加配置表单 UI 和多商户权重轮询分配功能

**Architecture:** 扩展现有 Flask + Bootstrap 架构，新增配置分区 API 端点，重构配置标签页为表单布局，修改订单匹配逻辑支持权重轮询

**Tech Stack:** Flask, Bootstrap 5, JavaScript (原生), Playwright (自动化)

---

## 文件结构

| 文件 | 责任 |
|------|------|
| `main.py` | 权重轮询算法实现，keyword_mapping 新旧格式兼容处理 |
| `app.py` | 新增配置分区 API 端点（common, order_scanner, keyword_mapping, interface_monitor, advanced） |
| `templates/index.html` | 重构配置标签页为分区表单布局，新增关键词映射表格编辑器 |

---

## Chunk 1: 权重轮询算法 (main.py)

### Task 1: 添加权重轮询辅助函数

**Files:**
- Modify: `main.py:163-200` (在 `_pick_interval_seconds` 函数后添加)

- [ ] **Step 1: 添加权重轮询状态字典和辅助函数**

在 `OrderScanner` 类的 `__init__` 方法中添加 `_weight_router` 属性，并在文件中添加辅助函数。

在 `main.py` 约 200 行后（`_pick_interval_seconds` 函数后）添加：

```python
def _normalize_keyword_mapping(keyword_mapping):
    """
    将 keyword_mapping 转换为统一的新格式（数组格式）。
    兼容旧格式（字符串）和新格式（数组）。
    """
    normalized = {}
    for keyword, value in keyword_mapping.items():
        if isinstance(value, str):
            # 旧格式：字符串，转换为单商家权重1
            normalized[keyword] = [{"merchant": value, "weight": 1}]
        elif isinstance(value, list):
            # 新格式：数组，直接使用
            normalized[keyword] = value
        else:
            # 未知格式，跳过
            continue
    return normalized


def _build_weight_sequence(merchant_list):
    """
    根据权重构建轮询序列。
    例如 [{"merchant": "A", "weight": 2}, {"merchant": "B", "weight": 1}]
    返回 ["A", "A", "B"]
    """
    sequence = []
    for item in merchant_list:
        merchant = item.get("merchant", "")
        weight = item.get("weight", 1)
        try:
            weight = int(weight)
            if weight < 1:
                weight = 1
        except Exception:
            weight = 1
        for _ in range(weight):
            sequence.append(merchant)
    return sequence
```

在 `OrderScanner` 类的 `__init__` 方法（约 224 行）中添加 `_weight_router` 属性：

```python
class OrderScanner:
    def __init__(self):
        self.config = {}
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self._weight_router = {}  # 存储每个关键词的轮询索引
        self.load_config()
```

- [ ] **Step 2: 添加获取商户的轮询方法**

在 `OrderScanner` 类中添加 `_get_merchant_by_weight` 方法（约 260 行后，`get_config` 方法后）：

```python
    def _get_merchant_by_weight(self, keyword, merchant_list):
        """
        根据权重轮询获取商户。
        返回 (商户名, 轮询信息字符串)
        """
        if not merchant_list:
            return ("米奇租赁官方", "默认规则")

        sequence = _build_weight_sequence(merchant_list)
        if not sequence:
            return ("米奇租赁官方", "默认规则")

        # 获取或初始化轮询索引
        if keyword not in self._weight_router:
            self._weight_router[keyword] = 0

        idx = self._weight_router[keyword]
        selected_merchant = sequence[idx % len(sequence)]

        # 更新索引
        self._weight_router[keyword] = (idx + 1) % len(sequence)

        # 构建轮询信息
        current_pos = idx % len(sequence) + 1
        total_pos = len(sequence)

        # 计算权重比例字符串
        weight_parts = []
        for item in merchant_list:
            weight_parts.append(f"{item.get('merchant', '')}({item.get('weight', 1)})")
        weight_ratio = ":".join([str(item.get("weight", 1)) for item in merchant_list])

        round_info = f"轮询: {current_pos}/{total_pos}"
        if current_pos == 1:
            round_info += f", 权重比 {weight_ratio}"

        return (selected_merchant, round_info)
```

- [ ] **Step 3: 修改订单匹配逻辑**

修改 `main.py` 约 930-939 行的匹配逻辑：

原代码：
```python
                            target_option = "米奇租赁官方"
                            matched_info = "默认规则"

                            for keyword, option in keyword_mapping.items():
                                if keyword in text_content:
                                    target_option = option
                                    matched_info = f"关键词匹配: {keyword}"
                                    break

                            log(f"匹配结果: [{matched_info}] -> 分配给: [{target_option}]")
```

替换为：
```python
                            target_option = "米奇租赁官方"
                            matched_info = "默认规则"
                            matched_keyword = None

                            # 规范化 keyword_mapping
                            normalized_mapping = _normalize_keyword_mapping(keyword_mapping)

                            for keyword, merchant_list in normalized_mapping.items():
                                if keyword in text_content:
                                    matched_keyword = keyword
                                    target_option, round_info = self._get_merchant_by_weight(keyword, merchant_list)
                                    matched_info = f"关键词匹配: {keyword}, {round_info}"
                                    break

                            log(f"匹配结果: [{matched_info}] -> 分配给: [{target_option}]")
```

- [ ] **Step 4: 验证改动**

运行服务确认无语法错误：

```bash
cd D:/order-auto/order-point && python -c "from main import OrderScanner; print('OK')"
```

Expected: 输出 `OK`

- [ ] **Step 5: 提交**

```bash
git add main.py
git commit -m "$(cat <<'EOF'
feat: add weight-based routing for keyword_mapping

- Support new array format with merchant and weight fields
- Backward compatible with old string format
- Add round-robin routing with weight sequence
- Log routing position and weight ratio

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 2: 配置分区 API 端点 (app.py)

### Task 2: 添加配置分区 API

**Files:**
- Modify: `app.py:86-105` (扩展现有 `/api/config` 端点区域)

- [ ] **Step 1: 添加配置读取辅助函数**

在 `app.py` 约 8 行后添加辅助函数：

```python
def _load_full_config():
    """加载完整配置文件"""
    config_path = "config.json"
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def _save_full_config(config):
    """保存完整配置文件"""
    config_path = "config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
```

- [ ] **Step 2: 添加配置分区 API 端点**

在 `app.py` 约 105 行后（`handle_config` 函数后）添加：

```python
# --- Config Section APIs ---
@app.route('/api/config/common', methods=['GET', 'POST'])
def handle_config_common():
    if request.method == 'GET':
        config = _load_full_config()
        return jsonify(config.get('common', {}))
    elif request.method == 'POST':
        new_section = request.json
        config = _load_full_config()
        config['common'] = new_section
        try:
            _save_full_config(config)
            return jsonify({'status': 'success', 'message': 'common 配置已保存'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/config/order_scanner', methods=['GET', 'POST'])
def handle_config_order_scanner():
    if request.method == 'GET':
        config = _load_full_config()
        order_config = config.get('order_scanner', {})
        # 排除 keyword_mapping, webhook_configs, rpa_group_mapping
        simple_config = {}
        for key, value in order_config.items():
            if key not in ['keyword_mapping', 'webhook_configs', 'rpa_group_mapping']:
                simple_config[key] = value
        return jsonify(simple_config)
    elif request.method == 'POST':
        new_section = request.json
        config = _load_full_config()
        # 合并，保留高级配置
        order_config = config.get('order_scanner', {})
        for key in ['keyword_mapping', 'webhook_configs', 'rpa_group_mapping']:
            if key in order_config:
                new_section[key] = order_config[key]
        config['order_scanner'] = new_section
        try:
            _save_full_config(config)
            return jsonify({'status': 'success', 'message': 'order_scanner 配置已保存'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/config/keyword_mapping', methods=['GET', 'POST'])
def handle_config_keyword_mapping():
    if request.method == 'GET':
        config = _load_full_config()
        order_config = config.get('order_scanner', {})
        keyword_mapping = order_config.get('keyword_mapping', {})
        # 转换为新格式返回
        normalized = {}
        for keyword, value in keyword_mapping.items():
            if isinstance(value, str):
                normalized[keyword] = [{"merchant": value, "weight": 1}]
            elif isinstance(value, list):
                normalized[keyword] = value
            else:
                normalized[keyword] = [{"merchant": str(value), "weight": 1}]
        return jsonify(normalized)
    elif request.method == 'POST':
        new_mapping = request.json
        config = _load_full_config()
        config.setdefault('order_scanner', {})['keyword_mapping'] = new_mapping
        try:
            _save_full_config(config)
            return jsonify({'status': 'success', 'message': 'keyword_mapping 配置已保存'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/config/interface_monitor', methods=['GET', 'POST'])
def handle_config_interface_monitor():
    if request.method == 'GET':
        config = _load_full_config()
        monitor_config = config.get('interface_monitor', {})
        # 排除 items
        simple_config = {}
        for key, value in monitor_config.items():
            if key != 'items':
                simple_config[key] = value
        return jsonify(simple_config)
    elif request.method == 'POST':
        new_section = request.json
        config = _load_full_config()
        # 合并，保留 items
        monitor_config = config.get('interface_monitor', {})
        if 'items' in monitor_config:
            new_section['items'] = monitor_config['items']
        config['interface_monitor'] = new_section
        try:
            _save_full_config(config)
            return jsonify({'status': 'success', 'message': 'interface_monitor 配置已保存'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/config/advanced', methods=['GET', 'POST'])
def handle_config_advanced():
    if request.method == 'GET':
        config = _load_full_config()
        order_config = config.get('order_scanner', {})
        monitor_config = config.get('interface_monitor', {})
        return jsonify({
            'webhook_configs': order_config.get('webhook_configs', []),
            'rpa_group_mapping': order_config.get('rpa_group_mapping', {}),
            'items': monitor_config.get('items', [])
        })
    elif request.method == 'POST':
        new_advanced = request.json
        config = _load_full_config()
        config.setdefault('order_scanner', {})['webhook_configs'] = new_advanced.get('webhook_configs', [])
        config.setdefault('order_scanner', {})['rpa_group_mapping'] = new_advanced.get('rpa_group_mapping', {})
        config.setdefault('interface_monitor', {})['items'] = new_advanced.get('items', [])
        try:
            _save_full_config(config)
            return jsonify({'status': 'success', 'message': '高级配置已保存'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/merchants', methods=['GET'])
def get_merchants():
    """获取所有商户名称列表（从 keyword_mapping 和 rpa_group_mapping 中提取）"""
    config = _load_full_config()
    merchants = set()
    order_config = config.get('order_scanner', {})

    # 从 keyword_mapping 提取
    keyword_mapping = order_config.get('keyword_mapping', {})
    for keyword, value in keyword_mapping.items():
        if isinstance(value, str):
            merchants.add(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    merchants.add(item.get('merchant', ''))

    # 从 rpa_group_mapping 提取
    rpa_mapping = order_config.get('rpa_group_mapping', {})
    for merchant in rpa_mapping.keys():
        merchants.add(merchant)

    # 过滤空值
    merchants = [m for m in merchants if m]
    return jsonify(sorted(merchants))
```

- [ ] **Step 3: 验证 API 端点**

启动 Flask 应用验证端点可用：

```bash
cd D:/order-auto/order-point && python -c "from app import app; print([r.rule for r in app.url_map.iter_rules()])" 2>&1 | grep -E "config/(common|order_scanner|keyword_mapping|interface_monitor|advanced|merchants)"
```

Expected: 输出包含新端点路径

- [ ] **Step 4: 提交**

```bash
git add app.py
git commit -m "$(cat <<'EOF'
feat: add config section API endpoints

- /api/config/common for basic login config
- /api/config/order_scanner for scanner params
- /api/config/keyword_mapping for weight routing
- /api/config/interface_monitor for monitor params
- /api/config/advanced for webhook/rpa/items
- /api/merchants for merchant list extraction

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 3: 配置 UI 重构 (templates/index.html)

### Task 3: 重构配置标签页为分区表单

**Files:**
- Modify: `templates/index.html:163-175` (配置标签页区域)
- Modify: `templates/index.html:255-284` (JavaScript 函数区域)

- [ ] **Step 1: 重构配置标签页 HTML**

将 `templates/index.html` 第 163-175 行的配置标签页内容替换为：

```html
            <!-- Config Tab -->
            <div class="tab-pane fade" id="config" role="tabpanel">
                <!-- Common Config Section -->
                <div class="card shadow-sm mb-3">
                    <div class="card-header">📋 公共配置 (common)</div>
                    <div class="card-body">
                        <div class="row mb-2">
                            <div class="col-md-4">
                                <label class="form-label">用户名</label>
                                <input type="text" id="config-username" class="form-control" placeholder="登录用户名">
                            </div>
                            <div class="col-md-4">
                                <label class="form-label">密码</label>
                                <input type="password" id="config-password" class="form-control" placeholder="登录密码">
                            </div>
                            <div class="col-md-4">
                                <label class="form-label">无头模式</label>
                                <div class="form-check form-switch mt-2">
                                    <input class="form-check-input" type="checkbox" id="config-headless">
                                    <label class="form-check-label" for="config-headless">启用</label>
                                </div>
                            </div>
                        </div>
                        <button onclick="saveConfigSection('common')" class="btn btn-sm btn-primary">保存公共配置</button>
                    </div>
                </div>

                <!-- Order Scanner Config Section -->
                <div class="card shadow-sm mb-3">
                    <div class="card-header">📦 订单扫描配置 (order_scanner)</div>
                    <div class="card-body">
                        <div class="row mb-2">
                            <div class="col-md-12">
                                <label class="form-label">扫描地址</label>
                                <input type="text" id="config-url" class="form-control" placeholder="订单列表页面 URL">
                            </div>
                        </div>
                        <div class="row mb-2">
                            <div class="col-md-12">
                                <label class="form-label">商户后台地址</label>
                                <input type="text" id="config-merchant-url" class="form-control" placeholder="商户后台 URL">
                            </div>
                        </div>
                        <div class="row mb-2">
                            <div class="col-md-4">
                                <label class="form-label">扫描间隔 (秒)</label>
                                <input type="number" id="config-scan-interval" class="form-control" value="60">
                            </div>
                            <div class="col-md-4">
                                <label class="form-label">最小间隔 (秒)</label>
                                <input type="number" id="config-scan-interval-min" class="form-control" value="30">
                            </div>
                            <div class="col-md-4">
                                <label class="form-label">最大间隔 (秒)</label>
                                <input type="number" id="config-scan-interval-max" class="form-control" value="120">
                            </div>
                        </div>
                        <button onclick="saveConfigSection('order_scanner')" class="btn btn-sm btn-primary me-2">保存扫描配置</button>
                    </div>
                </div>

                <!-- Keyword Mapping Section -->
                <div class="card shadow-sm mb-3">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <span>🎯 关键词映射 (权重分配)</span>
                        <button onclick="addKeywordRow()" class="btn btn-sm btn-success">+ 添加关键词</button>
                    </div>
                    <div class="card-body">
                        <div id="keyword-mapping-table" class="table-responsive">
                            <table class="table table-bordered align-middle">
                                <thead class="table-light">
                                    <tr>
                                        <th style="width: 150px;">关键词</th>
                                        <th>商户分配</th>
                                        <th style="width: 80px;">操作</th>
                                    </tr>
                                </thead>
                                <tbody id="keyword-mapping-body">
                                    <!-- 动态生成 -->
                                </tbody>
                            </table>
                        </div>
                        <div class="mb-2">
                            <small class="text-muted">提示：同一关键词可添加多个商户，权重决定分配比例。如权重 2:1 表示 A 分配 2 次，B 分配 1 次，循环轮询。</small>
                        </div>
                        <button onclick="saveKeywordMapping()" class="btn btn-sm btn-primary">保存关键词映射</button>
                    </div>
                </div>

                <!-- Interface Monitor Config Section -->
                <div class="card shadow-sm mb-3">
                    <div class="card-header">💰 接口监控配置 (interface_monitor)</div>
                    <div class="card-body">
                        <div class="row mb-2">
                            <div class="col-md-12">
                                <label class="form-label">监控地址</label>
                                <input type="text" id="config-monitor-url" class="form-control" placeholder="接口监控页面 URL">
                            </div>
                        </div>
                        <div class="row mb-2">
                            <div class="col-md-4">
                                <label class="form-label">扫描间隔 (秒)</label>
                                <input type="number" id="config-monitor-scan-interval" class="form-control" value="7200">
                            </div>
                            <div class="col-md-4">
                                <label class="form-label">Webhook URL</label>
                                <input type="text" id="config-monitor-webhook" class="form-control" placeholder="通知 Webhook">
                            </div>
                            <div class="col-md-4">
                                <label class="form-label">无头模式</label>
                                <div class="form-check form-switch mt-2">
                                    <input class="form-check-input" type="checkbox" id="config-monitor-headless">
                                    <label class="form-check-label" for="config-monitor-headless">启用</label>
                                </div>
                            </div>
                        </div>
                        <button onclick="saveConfigSection('interface_monitor')" class="btn btn-sm btn-primary">保存监控配置</button>
                    </div>
                </div>

                <!-- Advanced Config Section -->
                <div class="card shadow-sm mb-3">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <span>🔧 高级配置 (JSON)</span>
                        <button onclick="saveAdvancedConfig()" class="btn btn-sm btn-primary">保存高级配置</button>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-4 mb-2">
                                <label class="form-label">Webhook 配置 (webhook_configs)</label>
                                <textarea id="config-webhook-configs" class="form-control" style="height: 200px; font-family: monospace;" placeholder="[]"></textarea>
                            </div>
                            <div class="col-md-4 mb-2">
                                <label class="form-label">RPA 群映射 (rpa_group_mapping)</label>
                                <textarea id="config-rpa-group-mapping" class="form-control" style="height: 200px; font-family: monospace;" placeholder="{}"></textarea>
                            </div>
                            <div class="col-md-4 mb-2">
                                <label class="form-label">监控项配置 (items)</label>
                                <textarea id="config-monitor-items" class="form-control" style="height: 200px; font-family: monospace;" placeholder="[]"></textarea>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
```

- [ ] **Step 2: 添加 JavaScript 函数**

在 `templates/index.html` 第 255 行后（`loadConfig` 函数前）添加：

```javascript
        // Keyword Mapping State
        let keywordMappingData = {};
        let merchantList = [];

        // Load all config sections
        function loadAllConfigSections() {
            fetch('/api/config/common')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('config-username').value = data.username || '';
                    document.getElementById('config-password').value = data.password || '';
                    document.getElementById('config-headless').checked = data.headless !== false;
                });

            fetch('/api/config/order_scanner')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('config-url').value = data.url || '';
                    document.getElementById('config-merchant-url').value = data.merchant_url || '';
                    document.getElementById('config-scan-interval').value = data.scan_interval || 60;
                    document.getElementById('config-scan-interval-min').value = data.scan_interval_min || 30;
                    document.getElementById('config-scan-interval-max').value = data.scan_interval_max || 120;
                });

            fetch('/api/config/keyword_mapping')
                .then(response => response.json())
                .then(data => {
                    keywordMappingData = data;
                    renderKeywordMappingTable();
                });

            fetch('/api/config/interface_monitor')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('config-monitor-url').value = data.url || '';
                    document.getElementById('config-monitor-scan-interval').value = data.scan_interval || 7200;
                    document.getElementById('config-monitor-webhook').value = data.webhook_url || '';
                    document.getElementById('config-monitor-headless').checked = data.headless !== false;
                });

            fetch('/api/config/advanced')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('config-webhook-configs').value = JSON.stringify(data.webhook_configs || [], null, 2);
                    document.getElementById('config-rpa-group-mapping').value = JSON.stringify(data.rpa_group_mapping || {}, null, 2);
                    document.getElementById('config-monitor-items').value = JSON.stringify(data.items || [], null, 2);
                });

            fetch('/api/merchants')
                .then(response => response.json())
                .then(data => {
                    merchantList = data;
                });
        }

        // Render keyword mapping table
        function renderKeywordMappingTable() {
            const tbody = document.getElementById('keyword-mapping-body');
            tbody.innerHTML = '';

            for (const [keyword, merchants] of Object.entries(keywordMappingData)) {
                const row = createKeywordRow(keyword, merchants);
                tbody.appendChild(row);
            }
        }

        // Create a keyword row
        function createKeywordRow(keyword, merchants) {
            const tr = document.createElement('tr');
            tr.dataset.keyword = keyword;

            // Keyword cell
            const tdKeyword = document.createElement('td');
            const inputKeyword = document.createElement('input');
            inputKeyword.type = 'text';
            inputKeyword.className = 'form-control';
            inputKeyword.value = keyword;
            inputKeyword.placeholder = '关键词';
            inputKeyword.onchange = function() {
                updateKeywordRow(tr);
            };
            tdKeyword.appendChild(inputKeyword);
            tr.appendChild(tdKeyword);

            // Merchants cell
            const tdMerchants = document.createElement('td');
            const merchantsContainer = document.createElement('div');
            merchantsContainer.className = 'merchants-container';

            for (const merchant of merchants) {
                const merchantDiv = createMerchantDiv(merchant.merchant, merchant.weight);
                merchantsContainer.appendChild(merchantDiv);
            }

            // Add merchant button
            const addBtn = document.createElement('button');
            addBtn.className = 'btn btn-sm btn-outline-success ms-2';
            addBtn.textContent = '+ 添加商户';
            addBtn.onclick = function() {
                const newDiv = createMerchantDiv('', 1);
                merchantsContainer.insertBefore(newDiv, addBtn);
            };
            merchantsContainer.appendChild(addBtn);

            tdMerchants.appendChild(merchantsContainer);
            tr.appendChild(tdMerchants);

            // Action cell
            const tdAction = document.createElement('td');
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn btn-sm btn-danger';
            deleteBtn.textContent = '删除';
            deleteBtn.onclick = function() {
                deleteKeywordRow(keyword);
            };
            tdAction.appendChild(deleteBtn);
            tr.appendChild(tdAction);

            return tr;
        }

        // Create merchant div with input and weight
        function createMerchantDiv(merchantName, weight) {
            const div = document.createElement('div');
            div.className = 'd-flex align-items-center mb-1';

            const selectMerchant = document.createElement('select');
            selectMerchant.className = 'form-select form-select-sm me-2';
            selectMerchant.style.width = '200px';

            // Add options from merchant list
            const defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.textContent = '选择商户...';
            selectMerchant.appendChild(defaultOption);

            for (const m of merchantList) {
                const option = document.createElement('option');
                option.value = m;
                option.textContent = m;
                if (m === merchantName) option.selected = true;
                selectMerchant.appendChild(option);
            }

            // If merchant not in list, add it
            if (merchantName && !merchantList.includes(merchantName)) {
                const option = document.createElement('option');
                option.value = merchantName;
                option.textContent = merchantName;
                option.selected = true;
                selectMerchant.appendChild(option);
            }

            const weightInput = document.createElement('input');
            weightInput.type = 'number';
            weightInput.className = 'form-control form-control-sm me-2';
            weightInput.style.width = '80px';
            weightInput.value = weight;
            weightInput.placeholder = '权重';
            weightInput.min = 1;

            const removeBtn = document.createElement('button');
            removeBtn.className = 'btn btn-sm btn-outline-danger';
            removeBtn.textContent = '×';
            removeBtn.onclick = function() {
                div.remove();
            };

            div.appendChild(selectMerchant);
            div.appendChild(weightInput);
            div.appendChild(removeBtn);

            return div;
        }

        // Add new keyword row
        function addKeywordRow() {
            const tbody = document.getElementById('keyword-mapping-body');
            const newRow = createKeywordRow('', [{"merchant": "", "weight": 1}]);
            tbody.appendChild(newRow);
        }

        // Update keyword row when keyword changes
        function updateKeywordRow(tr) {
            const inputKeyword = tr.querySelector('td:first-child input');
            tr.dataset.keyword = inputKeyword.value;
        }

        // Delete keyword row
        function deleteKeywordRow(keyword) {
            delete keywordMappingData[keyword];
            renderKeywordMappingTable();
        }

        // Save keyword mapping
        function saveKeywordMapping() {
            const tbody = document.getElementById('keyword-mapping-body');
            const newMapping = {};

            for (const row of tbody.rows) {
                const keywordInput = row.querySelector('td:first-child input');
                const keyword = keywordInput.value.trim();
                if (!keyword) continue;

                const merchantsContainer = row.querySelector('.merchants-container');
                const merchantDivs = merchantsContainer.querySelectorAll('div.d-flex');

                const merchants = [];
                for (const div of merchantDivs) {
                    const select = div.querySelector('select');
                    const weightInput = div.querySelector('input[type="number"]');
                    const merchant = select.value.trim();
                    const weight = parseInt(weightInput.value) || 1;

                    if (merchant && weight >= 1) {
                        merchants.push({"merchant": merchant, "weight": weight});
                    }
                }

                if (merchants.length > 0) {
                    newMapping[keyword] = merchants;
                }
            }

            fetch('/api/config/keyword_mapping', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newMapping)
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    alert('关键词映射已保存！');
                    keywordMappingData = newMapping;
                } else {
                    alert('保存失败: ' + data.message);
                }
            });
        }

        // Save config section
        function saveConfigSection(section) {
            let data = {};

            if (section === 'common') {
                data = {
                    username: document.getElementById('config-username').value,
                    password: document.getElementById('config-password').value,
                    headless: document.getElementById('config-headless').checked
                };
            } else if (section === 'order_scanner') {
                data = {
                    url: document.getElementById('config-url').value,
                    merchant_url: document.getElementById('config-merchant-url').value,
                    scan_interval: parseInt(document.getElementById('config-scan-interval').value) || 60,
                    scan_interval_min: parseInt(document.getElementById('config-scan-interval-min').value) || 30,
                    scan_interval_max: parseInt(document.getElementById('config-scan-interval-max').value) || 120
                };
            } else if (section === 'interface_monitor') {
                data = {
                    url: document.getElementById('config-monitor-url').value,
                    scan_interval: parseInt(document.getElementById('config-monitor-scan-interval').value) || 7200,
                    webhook_url: document.getElementById('config-monitor-webhook').value,
                    headless: document.getElementById('config-monitor-headless').checked
                };
            }

            fetch('/api/config/' + section, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    alert(section + ' 配置已保存！');
                } else {
                    alert('保存失败: ' + data.message);
                }
            });
        }

        // Save advanced config
        function saveAdvancedConfig() {
            try {
                const webhookConfigs = JSON.parse(document.getElementById('config-webhook-configs').value);
                const rpaGroupMapping = JSON.parse(document.getElementById('config-rpa-group-mapping').value);
                const items = JSON.parse(document.getElementById('config-monitor-items').value);

                fetch('/api/config/advanced', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        webhook_configs: webhookConfigs,
                        rpa_group_mapping: rpaGroupMapping,
                        items: items
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        alert('高级配置已保存！');
                    } else {
                        alert('保存失败: ' + data.message);
                    }
                });
            } catch (e) {
                alert('JSON 格式错误: ' + e);
            }
        }
```

- [ ] **Step 3: 修改初始化代码**

将 `templates/index.html` 第 180-184 行的初始化代码替换为：

```javascript
        // Init
        loadAllConfigSections();
        setInterval(updateTime, 1000);
        setInterval(updateAllStatus, 2000);
        updateAllStatus();
```

- [ ] **Step 4: 删除旧的 loadConfig 和 saveConfig 函数**

删除第 255-284 行的旧 `loadConfig` 和 `saveConfig` 函数（已被新函数替代）。

- [ ] **Step 5: 验证 UI**

启动 Flask 应用并检查配置页面：

```bash
cd D:/order-auto/order-point && python app.py &
```

访问 `http://localhost:5050`，切换到"全局配置"标签页，确认：
- 公共配置表单显示正常
- 关键词映射表格显示正常
- 高级配置 JSON 编辑器显示正常

- [ ] **Step 6: 提交**

```bash
git add templates/index.html
git commit -m "$(cat <<'EOF'
feat: refactor config tab to form-based UI

- Add section-based forms for common, order_scanner, interface_monitor
- Add keyword mapping table editor with weight support
- Add merchant dropdown from existing mapping
- Keep JSON editors for advanced configs

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Chunk 4: 验证与清理

### Task 4: 整体功能验证

**Files:**
- None (验证性操作)

- [ ] **Step 1: 启动服务并测试**

```bash
cd D:/order-auto/order-point && python app.py
```

访问 `http://localhost:5050`，执行以下验证：
1. 配置页面加载所有配置项
2. 修改关键词映射，添加权重配置，保存
3. 启动订单扫描服务，观察日志中的权重轮询输出

- [ ] **Step 2: 验证权重轮询日志**

当有订单匹配关键词时，检查日志格式：

Expected:
```
[时间] 订单 "xxx" 匹配关键词 [G7X2] -> 分配给 [星享生活] (轮询: 1/3, 权重比 1:1)
```

- [ ] **Step 3: 最终提交（如有遗漏修复）**

```bash
git status
git add -A
git commit -m "$(cat <<'EOF'
feat: complete config UI and weight routing implementation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```