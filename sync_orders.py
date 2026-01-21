import time
import requests
import json
import os
import threading
from playwright.sync_api import sync_playwright

# Global log buffer for Web UI
SYNC_LOG_BUFFER = []
MAX_LOG_SIZE = 500

def sync_log(message):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    formatted_msg = f"[{timestamp}] {message}"
    print(formatted_msg)
    SYNC_LOG_BUFFER.append(formatted_msg)
    if len(SYNC_LOG_BUFFER) > MAX_LOG_SIZE:
        SYNC_LOG_BUFFER.pop(0)

class OrderSync:
    def __init__(self):
        self.config = {}
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self.load_config()

    def load_config(self):
        config_path = "config.json"
        if not os.path.exists(config_path):
            sync_log(f"错误: 找不到配置文件 {config_path}")
            return False
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                raw_config = json.load(f)
            
            common_config = raw_config.get("common", {})
            sync_config = raw_config.get("order_sync", {})
            self.config = {**common_config, **sync_config}
            
            sync_log("同步服务配置已加载")
            return True
        except Exception as e:
            sync_log(f"读取配置文件失败: {e}")
            return False

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    def start(self):
        if self.running:
            sync_log("同步服务已经在运行中...")
            return
        
        self.load_config()
        self.stop_event.clear()
        self.running = True
        self.thread = threading.Thread(target=self._run_loop)
        self.thread.daemon = True
        self.thread.start()
        sync_log("同步服务启动中...")

    def stop(self):
        if not self.running:
            sync_log("同步服务未运行")
            return
        
        sync_log("正在停止同步服务...")
        self.stop_event.set()
        self.running = False

    def restart(self):
        self.stop()
        time.sleep(2)
        self.start()

    def fetch_orders_to_sync(self):
        api_url = self.get_config("fetch_orders_api")
        if not api_url:
            sync_log("警告: 未配置 fetch_orders_api，跳过同步")
            return []
        
        try:
            resp = requests.get(api_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # Expected format: {"code": 200, "data": ["SN1", "SN2"]} or ["SN1"]
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "data" in data:
                    return data["data"]
                else:
                    sync_log(f"获取订单接口返回格式无法解析: {data}")
                    return []
            else:
                sync_log(f"获取订单接口请求失败: {resp.status_code}")
                return []
        except Exception as e:
            sync_log(f"获取订单接口异常: {e}")
            return []

    def update_order_status(self, payload):
        api_url = self.get_config("update_order_api")
        if not api_url:
            sync_log(f"警告: 未配置 update_order_api，无法更新: {payload}")
            return
        
        try:
            resp = requests.post(api_url, json=payload, timeout=10)
            sync_log(f"订单更新接口响应: {resp.status_code} - {resp.text}")
        except Exception as e:
            sync_log(f"订单更新接口异常: {e}")

    def _run_loop(self):
        url = self.get_config("url", "")
        username = self.get_config("username", "")
        password = self.get_config("password", "")
        scan_interval = self.get_config("scan_interval", 60)
        headless = self.get_config("headless", True)

        sync_log(f"启动同步浏览器... (Headless: {headless})")
        
        try:
            with sync_playwright() as p:
                args = ["--window-position=0,0"] if not headless else []
                browser = p.chromium.launch(headless=headless, args=args)
                context = browser.new_context()
                page = context.new_page()

                sync_log(f"正在访问: {url}")
                try:
                    page.goto(url)
                except Exception as e:
                    sync_log(f"访问 URL 失败: {e}")
                    return

                # Auto Login (Same as main.py)
                if username and password:
                    user_selector = "#form1 > div > div:nth-child(3) > input"
                    pass_selector = "#form1 > div > div:nth-child(4) > input"
                    try:
                        try:
                            page.wait_for_selector(user_selector, timeout=5000)
                            sync_log("检测到登录页面，开始自动登录...")
                            page.fill(user_selector, username)
                            page.fill(pass_selector, password)
                            page.press(pass_selector, "Enter")
                            page.wait_for_load_state("networkidle")
                            sync_log("登录操作完成，正在跳转到目标页面...")
                            page.goto(url)
                            page.wait_for_load_state("networkidle")
                        except:
                            sync_log("未检测到登录输入框，跳过自动登录...")
                    except Exception as e:
                        sync_log(f"自动登录尝试失败: {e}")

                if not headless:
                    sync_log("请在浏览器中完成登录（如果需要）...")
                
                try:
                    sync_log("等待页面加载...")
                    # Wait for ordersn input to be available as a sign of loaded page
                    page.wait_for_selector("#ordersn", timeout=60000)
                except Exception as e:
                    sync_log("等待页面超时或出错，请检查是否已登录。")
                    browser.close()
                    self.running = False
                    return

                sync_log("检测到订单列表页面，开始同步循环...")

                while not self.stop_event.is_set():
                    sync_log(f"\n--- 开始新一轮同步 ({time.strftime('%H:%M:%S')}) ---")
                    
                    orders = self.fetch_orders_to_sync()
                    if not orders:
                        sync_log("没有需要同步的订单")
                    else:
                        sync_log(f"获取到 {len(orders)} 个待同步订单")
                        
                        for order_sn in orders:
                            if self.stop_event.is_set():
                                break
                            
                            sync_log(f"正在处理订单: {order_sn}")
                            try:
                                # 1. Input Order SN
                                page.fill("#ordersn", str(order_sn))
                                
                                # 2. Click Search
                                page.click("#search")
                                
                                # Wait for results
                                try:
                                    # Wait for table to update or spinner to disappear
                                    page.wait_for_load_state("networkidle")
                                    time.sleep(2) # Extra wait for AJAX
                                except:
                                    pass

                                # 3. Check Results Count
                                # Assuming rows are in #table > div > div > div > div.tables
                                # Selector provided by user for status is #table > div > div > div > div:nth-child(4) > div:nth-child(2) > div.ops.list-inner
                                # This implies the order item is div:nth-child(4) inside the container. 
                                # Usually there are header rows. 
                                # Let's count valid order rows.
                                
                                # We can use the status selector to check existence.
                                status_selector = "#table > div > div > div > div.tables > div:nth-child(2) > div.ops.list-inner"
                                # Note: User provided selector has specific nth-childs. 
                                # #table > div > div > div > div:nth-child(4)
                                # Let's try to find how many order tables/rows are visible.
                                order_rows = page.locator("#table .tables")
                                count = order_rows.count()
                                
                                if count == 0:
                                    sync_log(f"订单 {order_sn} 未找到")
                                    continue
                                elif count > 1:
                                    sync_log(f"订单 {order_sn} 匹配到多个结果 ({count})，跳过")
                                    continue
                                
                                # 4. Get Status
                                # User selector: #table > div > div > div > div:nth-child(4) > div:nth-child(2) > div.ops.list-inner
                                # Since we filtered to 1 result, we can probably scope to the first .tables
                                target_row = order_rows.first
                                status_el = target_row.locator(".ops.list-inner")
                                
                                status_text = ""
                                if status_el.is_visible():
                                    status_text = status_el.inner_text().strip()
                                    # status_text might contain buttons and newlines. 
                                    # Usually status is plain text like "待收货" or inside a span.
                                    # Let's extract just the text parts.
                                    lines = [line.strip() for line in status_text.split('\n') if line.strip()]
                                    # Heuristic: The status is usually the first line or distinguishable
                                    # For "待收货", it might be "待收货" followed by "确认收货" button text.
                                    # Let's assume the first non-empty line is status for now, or use the whole text.
                                    status_raw = lines[0] if lines else "未知"
                                else:
                                    sync_log("无法获取订单状态")
                                    continue
                                
                                sync_log(f"订单状态: {status_raw}")
                                
                                payload = {
                                    "order_sn": order_sn,
                                    "status": status_raw
                                }

                                # 5. Special Handling for "待收货"
                                if "待收货" in status_text:
                                    sync_log("检测到待收货状态，抓取物流信息...")
                                    # Click action button
                                    # User selector: ... > a.op.text-primary
                                    action_btn = status_el.locator("a.op.text-primary").filter(has_text="查看物流") 
                                    # Note: User didn't say "查看物流", just provided selector.
                                    # Selector: #table > div > div > div > div:nth-child(4) > div:nth-child(2) > div.ops.list-inner > a.op.text-primary
                                    # It might be the link that opens the modal.
                                    # Let's try clicking the first primary link in ops.
                                    action_btn = status_el.locator("a.op.text-primary").first
                                    
                                    if action_btn.is_visible():
                                        action_btn.click()
                                        
                                        # Wait for modal #ajaxModal
                                        try:
                                            page.wait_for_selector("#ajaxModal", state="visible", timeout=5000)
                                            time.sleep(1) 
                                            
                                            # Scrape details
                                            # Logistics Company
                                            company_sel = "#ajaxModal > div.modal-dialog > div > div.modal-body > div.logistics-summary > span:nth-child(1)"
                                            company = page.locator(company_sel).inner_text().replace("物流公司：", "").strip()
                                            
                                            # Tracking Number
                                            track_sel = "#ajaxModal > div.modal-dialog > div > div.modal-body > div.logistics-summary > span:nth-child(2)"
                                            track_no = page.locator(track_sel).inner_text().replace("快递单号：", "").strip()
                                            
                                            # Latest Info
                                            info_sel = "#ajaxModal > div.modal-dialog > div > div.modal-body > div.list-main > div:nth-child(1) > div.info.infoon > div.step"
                                            latest_info = page.locator(info_sel).inner_text().strip()
                                            
                                            payload["logistics_company"] = company
                                            payload["tracking_number"] = track_no
                                            payload["latest_logistics_info"] = latest_info
                                            
                                            sync_log(f"物流信息: {company} | {track_no} | {latest_info[:20]}...")
                                            
                                            # Close modal
                                            page.locator("#ajaxModal .close").click()
                                            time.sleep(0.5)
                                            
                                        except Exception as e:
                                            sync_log(f"抓取物流弹窗失败: {e}")
                                            # Try closing modal if open
                                            page.keyboard.press("Escape")
                                    else:
                                        sync_log("未找到物流查看按钮")

                                # 6. Update External API
                                self.update_order_status(payload)

                            except Exception as e:
                                sync_log(f"处理订单 {order_sn} 时出错: {e}")

                    # Wait for next scan
                    if not self.stop_event.is_set():
                        sync_log(f"本轮结束，等待 {scan_interval} 秒...")
                        time.sleep(scan_interval)
                        try:
                            page.reload()
                            page.wait_for_load_state("networkidle")
                        except:
                            pass

                browser.close()
                sync_log("浏览器已关闭")

        except Exception as e:
            sync_log(f"运行过程中发生严重错误: {e}")
        finally:
            self.running = False
            sync_log("同步服务已停止")

# Singleton
order_sync = OrderSync()

if __name__ == "__main__":
    order_sync.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        order_sync.stop()
