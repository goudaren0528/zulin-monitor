from flask import Flask, render_template, jsonify, request, send_file
import os
import json
import threading
import sqlite3
import zipfile
import tempfile
import shutil
from datetime import datetime
from main import scanner, LOG_BUFFER
from monitor import monitor, MONITOR_LOG_BUFFER
from db import get_daily_stats, get_merchant_totals, DB_PATH, db_lock, get_all_merchant_limits, set_merchant_limit, reset_merchant_limit, get_merchants_at_limit, set_merchant_config, get_merchant_webhooks, init_db, delete_merchant_config, get_merchant_config

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
        # 排除 keyword_mapping, webhook_configs, rpa_group_mapping, merchants
        simple_config = {}
        for key, value in order_config.items():
            if key not in ['keyword_mapping', 'webhook_configs', 'rpa_group_mapping', 'merchants']:
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
    """获取所有商户名称列表（从 keyword_mapping、rpa_group_mapping 和数据库中提取）"""
    config = _load_full_config()
    merchants = set()
    order_config = config.get('order_scanner', {})

    # 从 keyword_mapping 提取
    keyword_mapping = order_config.get('keyword_mapping', {})
    for keyword, value in keyword_mapping.items():
        if isinstance(value, str):
            merchants.add(value)
        elif isinstance(value, dict):
            for item in value.get('merchants', []):
                if isinstance(item, dict):
                    merchants.add(item.get('merchant', ''))

    # 从 rpa_group_mapping 提取
    rpa_mapping = order_config.get('rpa_group_mapping', {})
    for merchant in rpa_mapping.keys():
        merchants.add(merchant)

    # 从数据库提取（新增的商户可能尚未配置关键词映射）
    db_merchants = get_all_merchant_limits()
    for m in db_merchants:
        if m.get('merchant'):
            merchants.add(m['merchant'])

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
    """获取分单记录列表（支持分页）"""
    date = request.args.get('date', '')
    merchant = request.args.get('merchant', '')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))

    if not os.path.exists(DB_PATH):
        return jsonify({'records': [], 'total': 0, 'has_more': False})

    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 构建查询条件
        conditions = []
        params = []

        if date:
            conditions.append("created_at LIKE ?")
            params.append(date + "%")
        if merchant:
            conditions.append("merchant = ?")
            params.append(merchant)

        where_clause = ""
        if conditions:
            where_clause = " WHERE " + " AND ".join(conditions)

        # 先获取总数
        count_query = "SELECT COUNT(*) FROM assignment_records" + where_clause
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        # 获取记录
        query = "SELECT created_at, keyword_entry, matched_keyword, merchant, product, order_no, order_title FROM assignment_records"
        query += where_clause
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

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

    return jsonify({
        'records': records,
        'total': total,
        'has_more': offset + len(records) < total
    })

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
        try:
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
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': str(e)}), 500

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

@app.route('/api/merchants/delete', methods=['POST'])
def delete_merchant():
    """删除商户 - 清理数据库和配置文件所有引用"""
    data = request.json
    merchant = data.get('merchant')
    if not merchant:
        return jsonify({'status': 'error', 'message': '商户名称不能为空'}), 400

    deleted_items = []

    # 1. 删除数据库记录
    db_deleted = delete_merchant_config(merchant=merchant)
    if db_deleted:
        deleted_items.append('数据库配置')

    # 2. 清理配置文件
    config = _load_full_config()
    order_config = config.get('order_scanner', {})
    config_changed = False

    # 清理 keyword_mapping 中包含该商户的规则
    keyword_mapping = order_config.get('keyword_mapping', {})
    new_mapping = {}
    for kw, value in keyword_mapping.items():
        if isinstance(value, str):
            if value != merchant:
                new_mapping[kw] = value
            else:
                deleted_items.append(f'关键词映射 "{kw}"')
                config_changed = True
        elif isinstance(value, dict):
            merchants = value.get('merchants', [])
            new_merchants = [m for m in merchants if m.get('merchant') != merchant]
            if len(new_merchants) < len(merchants):
                config_changed = True
                deleted_items.append(f'关键词映射 "{kw}" 中的商户引用')
            if new_merchants:
                new_mapping[kw] = {
                    'product': value.get('product', ''),
                    'merchants': new_merchants
                }
            else:
                deleted_items.append(f'关键词映射 "{kw}" (规则已无商户)')
        elif isinstance(value, list):
            new_merchants = [m for m in value if m.get('merchant') != merchant]
            if new_merchants:
                new_mapping[kw] = new_merchants
            else:
                deleted_items.append(f'关键词映射 "{kw}"')
            if len(new_merchants) < len(value):
                config_changed = True

    if config_changed:
        config['order_scanner']['keyword_mapping'] = new_mapping

    # 清理 rpa_group_mapping
    rpa_mapping = order_config.get('rpa_group_mapping', {})
    if merchant in rpa_mapping:
        del rpa_mapping[merchant]
        config['order_scanner']['rpa_group_mapping'] = rpa_mapping
        deleted_items.append('RPA群映射')
        config_changed = True

    # 清理 merchants 数组（如果存在）
    merchants_list = order_config.get('merchants', [])
    if merchant in merchants_list:
        merchants_list = [m for m in merchants_list if m != merchant]
        config['order_scanner']['merchants'] = merchants_list
        deleted_items.append('配置商家列表')
        config_changed = True

    # 保存配置文件
    if config_changed:
        _save_full_config(config)

    if deleted_items:
        return jsonify({
            'status': 'success',
            'message': f'已删除商户 {merchant}',
            'deleted_items': deleted_items
        })
    else:
        return jsonify({
            'status': 'warning',
            'message': f'商户 {merchant} 无相关数据需要清理'
        })

@app.route('/api/merchants/add', methods=['POST'])
def add_merchant():
    """新增商户 - 仅在数据库创建记录"""
    data = request.json
    merchant = data.get('merchant', '').strip()

    if not merchant:
        return jsonify({'status': 'error', 'message': '商户名称不能为空'}), 400

    # 检查是否已存在（在 keyword_mapping 或数据库中）
    config = _load_full_config()
    order_config = config.get('order_scanner', {})
    keyword_mapping = order_config.get('keyword_mapping', {})

    # 检查 keyword_mapping 中是否已有此商户
    for kw, value in keyword_mapping.items():
        if isinstance(value, str) and value == merchant:
            return jsonify({'status': 'error', 'message': '商户已存在于关键词映射中'}), 400
        elif isinstance(value, dict):
            merchants = value.get('merchants', [])
            for m in merchants:
                if m.get('merchant') == merchant:
                    return jsonify({'status': 'error', 'message': '商户已存在于关键词映射中'}), 400
        elif isinstance(value, list):
            for m in value:
                if m.get('merchant') == merchant:
                    return jsonify({'status': 'error', 'message': '商户已存在于关键词映射中'}), 400

    # 检查数据库中是否已存在
    existing_config = get_merchant_config(merchant=merchant)
    if existing_config:
        return jsonify({'status': 'error', 'message': '商户已存在'}), 400

    # 创建记录 (初始限额9999即不限制, 可后续修改)
    set_merchant_config(merchant=merchant, limit_value=9999, webhook_urls=[])

    return jsonify({
        'status': 'success',
        'message': f'已添加商户 {merchant}（限额9999即不限制，请按需修改）'
    })

# --- Data Management API ---
BACKUP_DIR = "backups"
MAX_BACKUPS = 10

def _create_export_zip():
    """创建导出ZIP文件，返回临时文件路径"""
    temp_dir = tempfile.mkdtemp()
    export_files = []

    try:
        # 1. 配置文件
        config_path = _get_config_path()
        if os.path.exists(config_path):
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
            "config_file": config_path if os.path.exists(config_path) else None,
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

        return zip_path, zip_filename
    finally:
        # Always cleanup temp directory
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

def _ensure_backup_dir():
    """确保备份目录存在"""
    os.makedirs(BACKUP_DIR, exist_ok=True)

def _create_backup():
    """创建当前数据备份"""
    _ensure_backup_dir()
    backup_filename = f"backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        config_path = _get_config_path()
        if config_path and os.path.exists(config_path):
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

    # Create temp file safely (mktemp is deprecated)
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
        temp_zip = temp_file.name
    file.save(temp_zip)

    try:
        # 验证ZIP结构
        valid, filenames = _validate_import_zip(temp_zip)
        if not valid:
            return jsonify({'status': 'error', 'message': 'ZIP文件缺少必需数据（config.json或records.db）'}), 400

        # 创建备份
        backup_filename = _create_backup()

        # 解压并替换
        with zipfile.ZipFile(temp_zip, 'r') as zf:
            if "config.json" in filenames:
                # 提取到临时目录再复制
                temp_dir = tempfile.mkdtemp()
                try:
                    zf.extract("config.json", temp_dir)
                    shutil.copy(os.path.join(temp_dir, "config.json"), "config.local.json")
                finally:
                    shutil.rmtree(temp_dir, ignore_errors=True)

            if "records.db" in filenames:
                # 关闭可能的数据库连接
                temp_dir = tempfile.mkdtemp()
                try:
                    zf.extract("records.db", temp_dir)
                    with db_lock:
                        shutil.copy(os.path.join(temp_dir, "records.db"), DB_PATH)
                finally:
                    shutil.rmtree(temp_dir, ignore_errors=True)

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
    finally:
        # Always cleanup temp ZIP
        try:
            os.remove(temp_zip)
        except:
            pass

def _validate_backup_filename(filename):
    """验证备份文件名格式，防止路径遍历攻击"""
    # 必须是 backup-YYYYMMDD-HHMMSS.zip 格式
    if not filename.startswith("backup-"):
        return False
    if not filename.endswith(".zip"):
        return False
    # 不能包含路径分隔符
    if "/" in filename or "\\" in filename:
        return False
    return True

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
    if not _validate_backup_filename(filename):
        return jsonify({'status': 'error', 'message': '无效的备份文件名'}), 400
    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'message': '备份文件不存在'}), 404
    return send_file(filepath, mimetype='application/zip', as_attachment=True, download_name=filename)

@app.route('/api/data/backup/<filename>', methods=['POST'])
def restore_backup(filename):
    """恢复指定备份"""
    if not _validate_backup_filename(filename):
        return jsonify({'status': 'error', 'message': '无效的备份文件名'}), 400
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
            try:
                zf.extractall(temp_dir)

                if "config.json" in filenames:
                    shutil.copy(os.path.join(temp_dir, "config.json"), "config.local.json")
                if "records.db" in filenames:
                    with db_lock:
                        shutil.copy(os.path.join(temp_dir, "records.db"), DB_PATH)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

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
    if not _validate_backup_filename(filename):
        return jsonify({'status': 'error', 'message': '无效的备份文件名'}), 400
    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'message': '备份文件不存在'}), 404

    try:
        os.remove(filepath)
        return jsonify({'status': 'success', 'message': f'已删除备份 {filename}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/data/export', methods=['GET'])
def export_data():
    """导出数据为ZIP文件"""
    try:
        zip_path, zip_filename = _create_export_zip()
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

if __name__ == '__main__':
    # Initialize database
    init_db()
    # Listen on all interfaces for Docker
    app.run(host='0.0.0.0', port=5050, debug=True, use_reloader=False)
