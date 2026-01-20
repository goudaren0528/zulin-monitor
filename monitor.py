import time
import requests
import json
import os
import threading
import re
from playwright.sync_api import sync_playwright

# Global log buffer for Monitor
MONITOR_LOG_BUFFER = []
MAX_LOG_SIZE = 500

def monitor_log(message):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    formatted_msg = f"[{timestamp}] {message}"
    print(f"[Monitor] {formatted_msg}")
    MONITOR_LOG_BUFFER.append(formatted_msg)
    if len(MONITOR_LOG_BUFFER) > MAX_LOG_SIZE:
        MONITOR_LOG_BUFFER.pop(0)

class InterfaceMonitor:
    def __init__(self):
        self.config = {}
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self.load_config()

    def load_config(self):
        config_path = "config.json"
        if not os.path.exists(config_path):
            monitor_log(f"错误: 找不到配置文件 {config_path}")
            return False
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            monitor_log("监控配置已加载")
            return True
        except Exception as e:
            monitor_log(f"读取配置文件失败: {e}")
            return False

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    def start(self):
        if self.running:
            monitor_log("监控服务已经在运行中...")
            return
        
        # Reload config before starting
        self.load_config()
        self.stop_event.clear()
        self.running = True
        self.thread = threading.Thread(target=self._run_loop)
        self.thread.daemon = True
        self.thread.start()
        monitor_log("监控服务启动中...")

    def stop(self):
        if not self.running:
            monitor_log("监控服务未运行")
            return
        
        monitor_log("正在停止监控服务...")
        self.stop_event.set()
        self.running = False

    def restart(self):
        self.stop()
        time.sleep(2)
        self.start()

    def send_notification(self, content):
        monitor_config = self.get_config("monitor_config", {})
        webhook_url = monitor_config.get("webhook_url")
        
        if not webhook_url:
            monitor_log("未配置 Webhook URL，无法发送通知")
            return

        try:
            payload = {
                "msgtype": "text",
                "text": {
                    "content": f"【测试测试测试接口余额告警】\n{content}"
                }
            }
            resp = requests.post(webhook_url, json=payload)
            monitor_log(f"-> 告警通知已发送，状态码: {resp.status_code}")
        except Exception as e:
            monitor_log(f"-> 告警通知发送失败: {e}")

    def _run_loop(self):
        # Shared login credentials
        username = self.get_config("username", "")
        password = self.get_config("password", "")
        headless = self.get_config("headless", True)
        
        # Monitor specific config
        monitor_config = self.get_config("monitor_config", {})
        target_url = monitor_config.get("url", "")
        scan_interval = monitor_config.get("scan_interval", 300)
        threshold = monitor_config.get("threshold", 100)
        # Allow monitor-specific headless override, default to global headless setting
        headless = monitor_config.get("headless", self.get_config("headless", True))

        monitor_log(f"启动监控浏览器... (Headless: {headless})")
        
        try:
            with sync_playwright() as p:
                # args = ["--window-position=-2400,-2400"] if not headless else []
                # Remove window hiding to allow user to see the browser
                args = [] 
                browser = p.chromium.launch(headless=headless, args=args)
                context = browser.new_context()
                page = context.new_page()

                # Reuse login logic (accessing target_url directly might redirect to login)
                monitor_log(f"正在访问: {target_url}")
                try:
                    page.goto(target_url)
                except Exception as e:
                    monitor_log(f"访问 URL 失败: {e}")
                    return

                # Auto Login Check
                if username and password:
                    user_selector = "#form1 > div > div:nth-child(3) > input"
                    pass_selector = "#form1 > div > div:nth-child(4) > input"
                    try:
                        try:
                            page.wait_for_selector(user_selector, timeout=5000)
                            monitor_log("检测到登录页面，开始自动登录...")
                            page.fill(user_selector, username)
                            page.fill(pass_selector, password)
                            page.press(pass_selector, "Enter")
                            page.wait_for_load_state("networkidle")
                            monitor_log("登录操作完成，正在跳转到目标页面...")
                            page.goto(target_url)
                            page.wait_for_load_state("networkidle")
                        except:
                            monitor_log("未检测到登录输入框，假设已登录...")
                    except Exception as e:
                        monitor_log(f"自动登录尝试失败: {e}")

                monitor_log("开始监控循环...")

                while not self.stop_event.is_set():
                    monitor_log(f"\n--- 开始新一轮监控 ({time.strftime('%H:%M:%S')}) ---")
                    
                    try:
                        # Selector provided: body > div.wb-container.right-panel > div.page-content > div:nth-child(1) > div:nth-child(2)
                        # Updated to be more generic as per user feedback
                        container_selector = ".page-content"
                        
                        try:
                            page.wait_for_selector(container_selector, timeout=10000)
                            # Wait for data to load
                            try:
                                page.wait_for_selector("text=可用条数", timeout=10000)
                            except:
                                monitor_log("警告: 未检测到'可用条数'文本，可能是页面加载慢或无数据")
                        except:
                            monitor_log("等待监控元素超时，尝试刷新页面...")
                            page.reload()
                            continue

                        # Config Items
                        monitor_items = monitor_config.get("items", [])
                        target_items_map = {item["name"]: item.get("threshold", 100) for item in monitor_items}

                        # Robust parsing strategy: Find all 'Available' labels and trace back to their card containers
                        items_to_notify = []
                        processed_cards = set()
                        
                        # Find all elements containing "可用条数"
                        try:
                            labels = page.get_by_text("可用条数").all()
                            monitor_log(f"找到 {len(labels)} 个数据块")
                            
                            for label in labels:
                                # Search upwards for the best container
                                current_el = label
                                best_card = None
                                best_text = ""
                                found_target_name = False
                                
                                # Traverse up to 8 levels
                                for _ in range(8):
                                    try:
                                        current_el = current_el.locator("..")
                                        text = current_el.inner_text()
                                        
                                        # Safety check: if too big, stop
                                        if len(text) > 1000:
                                            break
                                            
                                        # Essential check: must look like a stats card
                                        if "消费条数" not in text:
                                            continue

                                        # Critical check: A single card should not contain multiple "Consumed" labels
                                        # If it does, we've gone up too far and hit a container for multiple cards
                                        if text.count("消费条数") > 1:
                                            break
                                            
                                        # Level 1: Valid card candidate
                                        best_card = current_el
                                        best_text = text
                                        
                                        # Level 2: Contains a known interface name?
                                        for config_name in target_items_map.keys():
                                            if config_name in text:
                                                found_target_name = True
                                                break
                                        
                                        if found_target_name:
                                            break
                                            
                                    except:
                                        break
                                
                                if not best_card:
                                    continue
                                    
                                card = best_card
                                card_text = best_text
                                
                                if card_text in processed_cards:
                                    continue
                                processed_cards.add(card_text)
                                
                                # Parse this card
                                lines = [line.strip() for line in card_text.split('\n') if line.strip()]
                                
                                # Heuristic for Name: First line that is NOT a keyword
                                keywords = ["可用条数", "消费条数", "查看详情", "余额", "条", "(", ")"]
                                name_line = "未知接口"
                                for line in lines:
                                    # If line contains known keywords, skip
                                    is_keyword = False
                                    for kw in keywords:
                                        if kw in line:
                                            is_keyword = True
                                            break
                                    if not is_keyword:
                                        name_line = line
                                        break
                                
                                # Check if this interface is in our target list
                                matched_name = None
                                
                                # Method 1: Check if the heuristic name matches
                                if name_line in target_items_map:
                                    matched_name = name_line
                                else:
                                    # Method 2: Check if any configured name exists in the card text
                                    for config_name in target_items_map.keys():
                                        if config_name in card_text:
                                            matched_name = config_name
                                            break
                                
                                if not matched_name:
                                    # Debug: Show what we found vs what we expected
                                    monitor_log(f"--- 未匹配调试 ---")
                                    monitor_log(f"解析到的首行: {name_line}")
                                    monitor_log(f"完整卡片文本: {repr(card_text)}")
                                    monitor_log(f"尝试匹配的配置项: {list(target_items_map.keys())}")
                                    monitor_log(f"----------------")
                                    continue

                                current_threshold = target_items_map[matched_name]
                                name_line = matched_name # Use the matched config name for display

                                # Regex for different fields within this card
                                balance_match = re.search(r"余额[^\d]*([\d\.]+)", card_text)
                                avail_match = re.search(r"可用[^\d]*(\d+)", card_text)
                                consumed_match = re.search(r"消费[^\d]*(\d+)", card_text)
                                
                                log_msg_parts = [f"接口 [{name_line}]"]
                                
                                if balance_match:
                                    log_msg_parts.append(f"余额: {balance_match.group(1)}")
                                
                                if consumed_match:
                                    log_msg_parts.append(f"消费: {consumed_match.group(1)}")
                                    
                                if avail_match:
                                    avail_count = int(avail_match.group(1))
                                    log_msg_parts.append(f"可用: {avail_count}")
                                    
                                    if avail_count < current_threshold:
                                        items_to_notify.append(f"【{name_line}】 剩余: {avail_count} 条 (阈值: {current_threshold})")
                                else:
                                    if not (balance_match or consumed_match):
                                            monitor_log(f"未能解析接口数据: {name_line}")
                                            continue

                                monitor_log(" | ".join(log_msg_parts))

                        except Exception as e:
                            monitor_log(f"解析页面数据时出错: {e}")
                            # Fallback: log full text for debugging
                            # monitor_log(f"页面文本片段: {page.locator(container_selector).inner_text()[:200]}")

                        if items_to_notify:
                            self.send_notification("\n".join(items_to_notify))
                            
                    except Exception as e:
                        monitor_log(f"监控逻辑出错: {e}")

                    # Wait for next scan
                    if not self.stop_event.is_set():
                        monitor_log(f"等待 {scan_interval} 秒...")
                        time.sleep(scan_interval)
                        try:
                            page.reload()
                            page.wait_for_load_state("networkidle")
                        except:
                            pass

                browser.close()
                monitor_log("浏览器已关闭")

        except Exception as e:
            monitor_log(f"运行过程中发生严重错误: {e}")
        finally:
            self.running = False
            monitor_log("监控服务已停止")

# Singleton instance
monitor = InterfaceMonitor()

if __name__ == "__main__":
    monitor.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
