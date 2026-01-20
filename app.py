from flask import Flask, render_template, jsonify, request
import os
import json
from main import scanner, LOG_BUFFER
from monitor import monitor, MONITOR_LOG_BUFFER

app = Flask(__name__, static_folder='static', template_folder='templates')

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

if __name__ == '__main__':
    # Listen on all interfaces for Docker
    app.run(host='0.0.0.0', port=5050, debug=True, use_reloader=False)
