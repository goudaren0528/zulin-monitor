from flask import Flask, render_template, jsonify, request
import os
import json
import threading
import sqlite3
from main import scanner, LOG_BUFFER
from monitor import monitor, MONITOR_LOG_BUFFER
from db import get_daily_stats, get_merchant_totals, DB_PATH, db_lock, get_all_merchant_limits, set_merchant_limit, reset_merchant_limit, get_merchants_at_limit, set_merchant_config, get_merchant_webhooks

app = Flask(__name__, static_folder='static', template_folder='templates')
config_lock = threading.Lock()

def _get_config_path():
    """获取优先使用的配置文件路径"""
    candidates = ["config.local.json", "config.json"]
    for pth in candidates:
        if os.path.exists(pth):
            return pth
    # 如果都不存在，默认使用 config.local.json
    return "config.local.json"

def _load_full_config():
    """加载完整配置文件（带锁确保一致性）"""
    config_path = _get_config_path()
    with config_lock:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

def _save_full_config(config):
    """保存完整配置文件（带锁防止并发冲突）"""
    config_path = "config.local.json"
    with config_lock:
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

# --- Shared Config API ---
@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    config_path = _get_config_path()
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
            # 保存到 config.local.json
            with open("config.local.json", 'w', encoding='utf-8') as f:
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
                normalized[keyword] = {"product": "", "merchants": [{"merchant": value, "weight": 1}]}
            elif isinstance(value, list):
                normalized[keyword] = {"product": "", "merchants": value}
            elif isinstance(value, dict):
                normalized[keyword] = value
            else:
                normalized[keyword] = {"product": "", "merchants": [{"merchant": str(value), "weight": 1}]}
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

    # 从配置文件读取商家列表
    config_merchants = order_config.get('merchants', [])
    for m in config_merchants:
        if m:
            merchants.add(m)

    # 过滤空值
    merchants = [m for m in merchants if m]
    return jsonify(sorted(merchants))

# --- Mock External API ---
# (Removed: External API should be implemented in the Next.js project on port 3000)

# --- Statistics API ---
@app.route('/api/stats/daily')
def get_daily_statistics():
    """获取指定日期各商家分单数量"""
    date = request.args.get('date', '')
    from datetime import datetime
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')

    stats = get_daily_stats(date=date)
    total_count = sum(s['count'] for s in stats)

    # 获取累计数据
    totals = get_merchant_totals()
    totals_dict = {t['merchant']: t['total'] for t in totals}

    # 合并当日和累计数据
    result = []
    for s in stats:
        result.append({
            'merchant': s['merchant'],
            'daily_count': s['count'],
            'total_count': totals_dict.get(s['merchant'], 0)
        })

    # 补充当日无分单但有累计的商家
    merchants_with_daily = {s['merchant'] for s in stats}
    for t in totals:
        if t['merchant'] not in merchants_with_daily:
            result.append({
                'merchant': t['merchant'],
                'daily_count': 0,
                'total_count': t['total']
            })

    return jsonify({
        'date': date,
        'total': total_count,
        'merchants': result
    })

@app.route('/api/stats/records')
def get_assignment_records():
    """获取分单记录列表"""
    date = request.args.get('date', '')
    merchant = request.args.get('merchant', '')
    limit = int(request.args.get('limit', 100))

    if not os.path.exists(DB_PATH):
        return jsonify({'records': []})

    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        query = "SELECT created_at, keyword_entry, matched_keyword, merchant, product, order_no, order_title FROM assignment_records"
        conditions = []
        params = []

        if date:
            conditions.append("created_at LIKE ?")
            params.append(date + "%")
        if merchant:
            conditions.append("merchant = ?")
            params.append(merchant)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        records = [{
            'created_at': row[0],
            'keyword_entry': row[1],
            'matched_keyword': row[2],
            'merchant': row[3],
            'product': row[4],
            'order_no': row[5],
            'order_title': row[6]
        } for row in cursor.fetchall()]
        conn.close()

    return jsonify({'records': records})

# --- Merchant Config API ---
@app.route('/api/merchants/limits', methods=['GET', 'POST'])
def handle_merchant_limits():
    """获取或设置商户配置"""
    if request.method == 'GET':
        limits = get_all_merchant_limits()
        # 合并商户列表中尚未设置限额的商户
        config = _load_full_config()
        order_config = config.get('order_scanner', {})
        all_merchants = set(order_config.get('merchants', []))

        # 从 keyword_mapping 提取商户
        keyword_mapping = order_config.get('keyword_mapping', {})
        for keyword, value in keyword_mapping.items():
            if isinstance(value, str):
                all_merchants.add(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        all_merchants.add(item.get('merchant', ''))
            elif isinstance(value, dict):
                merchants = value.get('merchants', [])
                for item in merchants:
                    if isinstance(item, dict):
                        all_merchants.add(item.get('merchant', ''))

        # 补充未设置限额的商户
        existing_merchants = {m['merchant'] for m in limits}
        for m in all_merchants:
            if m and m not in existing_merchants:
                limits.append({
                    'merchant': m,
                    'limit_value': 0,
                    'webhook_urls': [],
                    'current_count': 0,
                    'last_reset_at': '',
                    'is_at_limit': False
                })

        return jsonify({'merchants': limits})

    elif request.method == 'POST':
        data = request.json
        merchant = data.get('merchant')
        limit_value = data.get('limit_value')
        webhook_urls = data.get('webhook_urls')
        if not merchant:
            return jsonify({'status': 'error', 'message': '商户名称不能为空'}), 400
        set_merchant_config(merchant=merchant, limit_value=limit_value, webhook_urls=webhook_urls)
        msg_parts = []
        if limit_value is not None:
            msg_parts.append(f'限额为 {limit_value}')
        if webhook_urls is not None:
            msg_parts.append(f'webhook 已更新')
        return jsonify({'status': 'success', 'message': f'已设置 {merchant}: ' + ', '.join(msg_parts)})

@app.route('/api/merchants/reset', methods=['POST'])
def reset_merchant():
    """重置单个商户进度"""
    data = request.json
    merchant = data.get('merchant')
    if not merchant:
        return jsonify({'status': 'error', 'message': '商户名称不能为空'}), 400
    reset_merchant_limit(merchant=merchant)
    return jsonify({'status': 'success', 'message': f'已重置 {merchant} 进度'})

@app.route('/api/merchants/reset-all', methods=['POST'])
def reset_all_merchants():
    """重置所有商户进度"""
    limits = get_all_merchant_limits()
    count = 0
    for m in limits:
        reset_merchant_limit(merchant=m['merchant'])
        count += 1
    return jsonify({'status': 'success', 'message': f'已重置 {count} 个商户进度', 'reset_count': count})

if __name__ == '__main__':
    # Listen on all interfaces for Docker
    app.run(host='0.0.0.0', port=5050, debug=True, use_reloader=False)
