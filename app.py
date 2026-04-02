from flask import Flask, render_template, jsonify, request
import os
import json
from main import scanner, LOG_BUFFER
from monitor import monitor, MONITOR_LOG_BUFFER
from sync_orders import order_sync, SYNC_LOG_BUFFER

app = Flask(__name__, static_folder='static', template_folder='templates')

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

@app.route('/')
def index():
    return render_template('index.html')

# --- Order Scanner API ---
@app.route('/api/status')
def get_status():
    return jsonify({
        'running': scanner.running,
        'logs': LOG_BUFFER[-50:]
    })

@app.route('/api/control', methods=['POST'])
def control_service():
    action = request.json.get('action')
    try:
        if action == 'start':
            scanner.start()
        elif action == 'stop':
            scanner.stop()
        elif action == 'restart':
            scanner.restart()
        else:
            return jsonify({'status': 'error', 'message': '无效的操作'}), 400
        return jsonify({'status': 'success', 'message': f'已执行操作: {action}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- Monitor API ---
@app.route('/api/monitor/status')
def get_monitor_status():
    return jsonify({
        'running': monitor.running,
        'logs': MONITOR_LOG_BUFFER[-50:]
    })

@app.route('/api/monitor/control', methods=['POST'])
def control_monitor():
    action = request.json.get('action')
    try:
        if action == 'start':
            monitor.start()
        elif action == 'stop':
            monitor.stop()
        elif action == 'restart':
            monitor.restart()
        else:
            return jsonify({'status': 'error', 'message': '无效的操作'}), 400
        return jsonify({'status': 'success', 'message': f'监控服务已执行操作: {action}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- Sync API ---
@app.route('/api/sync/status')
def get_sync_status():
    return jsonify({
        'running': order_sync.running,
        'logs': SYNC_LOG_BUFFER[-50:]
    })

@app.route('/api/sync/control', methods=['POST'])
def control_sync():
    action = request.json.get('action')
    try:
        if action == 'start':
            order_sync.start()
        elif action == 'stop':
            order_sync.stop()
        elif action == 'restart':
            order_sync.restart()
        else:
            return jsonify({'status': 'error', 'message': '无效的操作'}), 400
        return jsonify({'status': 'success', 'message': f'同步服务已执行操作: {action}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- Shared Config API ---
@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    config_path = "config.json"
    if request.method == 'GET':
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        return jsonify({})
    
    elif request.method == 'POST':
        new_config = request.json
        try:
            # Validate JSON
            json.dumps(new_config)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=4, ensure_ascii=False)
            return jsonify({'status': 'success', 'message': '配置已保存'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400

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

# --- Mock External API ---
# (Removed: External API should be implemented in the Next.js project on port 3000)

if __name__ == '__main__':
    # Listen on all interfaces for Docker
    app.run(host='0.0.0.0', port=5050, debug=True, use_reloader=False)
