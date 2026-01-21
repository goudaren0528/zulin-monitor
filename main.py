import time
import requests
import json
import os
import threading
import sys
from playwright.sync_api import sync_playwright

# Try importing Windows-specific libraries safely
try:
    import uiautomation as auto
    HAS_UIAUTOMATION = True
except ImportError:
    HAS_UIAUTOMATION = False

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

# Global log buffer for Web UI
LOG_BUFFER = []
MAX_LOG_SIZE = 500

def log(message):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    formatted_msg = f"[{timestamp}] {message}"
    print(formatted_msg)
    LOG_BUFFER.append(formatted_msg)
    if len(LOG_BUFFER) > MAX_LOG_SIZE:
        LOG_BUFFER.pop(0)

class OrderScanner:
    def __init__(self):
        self.config = {}
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self.load_config()

    def load_config(self):
        config_path = "config.json"
        if not os.path.exists(config_path):
            log(f"错误: 找不到配置文件 {config_path}")
            return False
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                raw_config = json.load(f)
            
            # Merge common config and order_scanner config
            common_config = raw_config.get("common", {})
            order_config = raw_config.get("order_scanner", {})
            self.config = {**common_config, **order_config}
            
            log("配置已加载")
            return True
        except Exception as e:
            log(f"读取配置文件失败: {e}")
            return False

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    def start(self):
        if self.running:
            log("服务已经在运行中...")
            return
        
        # Reload config before starting
        self.load_config()
        self.stop_event.clear()
        self.running = True
        self.thread = threading.Thread(target=self._run_loop)
        self.thread.daemon = True
        self.thread.start()
        log("服务启动中...")

    def stop(self):
        if not self.running:
            log("服务未运行")
            return
        
        log("正在停止服务...")
        self.stop_event.set()
        # Wait a bit for the thread to finish cleanly, but don't block forever
        self.running = False
        # Thread will exit when it checks stop_event

    def restart(self):
        self.stop()
        time.sleep(2) # Give it some time to shut down
        self.start()

    def send_notification(self, order_title, assigned_to):
        merchant_url = self.get_config("merchant_url", "")
        webhook_configs = self.get_config("webhook_configs", [])
        rpa_group_mapping = self.get_config("rpa_group_mapping", {})

        # 1. Webhook Notification
        if webhook_configs:
            for config in webhook_configs:
                webhook_url = config.get("url")
                targets = config.get("targets", [])
                
                if not webhook_url:
                    continue
                    
                if "*" in targets or not targets or assigned_to in targets:
                    try:
                        if assigned_to == "米奇租赁官方":
                            webhook_content = f"新订单已分配\n标题：{order_title}\n分配给：{assigned_to}\n处理链接：{merchant_url}"
                        else:
                            webhook_content = f"新订单已分配\n标题：{order_title}\n分配给：{assigned_to}"
                            
                        payload = {
                            "msgtype": "text",
                            "text": {
                                "content": webhook_content
                            }
                        }
                        resp = requests.post(webhook_url, json=payload)
                        log(f"-> Webhook 通知已发送至 [{webhook_url[-6:]}...]，状态码: {resp.status_code}")
                    except Exception as e:
                        log(f"-> Webhook 发送失败: {e}")

        # 2. RPA Notification (Windows only)
        target_group = rpa_group_mapping.get(assigned_to)
        if target_group:
            if sys.platform == 'win32' and HAS_UIAUTOMATION:
                # self.send_rpa_notification(order_title, assigned_to, target_group)
                log(f"-> [调试] RPA 通知已暂时禁用 (目标群: {target_group})")
            else:
                log(f"-> [提示] 跳过 RPA 通知 (非 Windows 环境或缺少依赖)")

    def send_rpa_notification(self, order_title, assigned_to, group_name):
        if not (sys.platform == 'win32' and HAS_UIAUTOMATION and HAS_PYPERCLIP):
            log("无法发送 RPA 通知：环境不支持")
            return

        try:
            merchant_url = self.get_config("merchant_url", "")
            if assigned_to == "星享生活":
                content = f"老板，有新订单需要处理哈~ 辛苦处理下：\n{order_title}\n\n处理链接：{merchant_url}"
            else:
                content = f"您好，有新订单分配给您，请及时处理：\n{order_title}\n\n处理链接：{merchant_url}"
                
            wechat_window = auto.WindowControl(searchDepth=1, Name="企业微信")
            if not wechat_window.Exists(0):
                wechat_window = auto.WindowControl(searchDepth=1, ClassName="WeWorkWindow")
                
            if not wechat_window.Exists(0):
                log("-> [错误] 未找到企业微信窗口，RPA通知发送失败！")
                return
                
            wechat_window.SetActive()
            wechat_window.SetTopmost(True)
            time.sleep(0.5)
            
            wechat_window.SendKeys('{Ctrl}f')
            time.sleep(0.5)
            
            pyperclip.copy(group_name)
            wechat_window.SendKeys('{Ctrl}v')
            time.sleep(1.5)
            wechat_window.SendKeys('{Enter}')
            time.sleep(0.5)
            
            pyperclip.copy(content)
            wechat_window.SendKeys('{Ctrl}v')
            time.sleep(0.5)
            wechat_window.SendKeys('{Enter}')
            
            wechat_window.SetTopmost(False)
            wechat_window.Minimize()
            
            log(f"-> RPA 通知已发送")
            
        except Exception as e:
            log(f"-> RPA 发送通知时出错: {e}")

    def _run_loop(self):
        url = self.get_config("url", "")
        username = self.get_config("username", "")
        password = self.get_config("password", "")
        keyword_mapping = self.get_config("keyword_mapping", {})
        scan_interval = self.get_config("scan_interval", 30)
        headless = self.get_config("headless", True)

        log(f"启动浏览器... (Headless: {headless})")
        
        try:
            with sync_playwright() as p:
                args = ["--window-position=0,0"] if not headless else []
                browser = p.chromium.launch(headless=headless, args=args)
                context = browser.new_context()
                page = context.new_page()

                log(f"正在访问: {url}")
                try:
                    page.goto(url)
                except Exception as e:
                    log(f"访问 URL 失败: {e}")
                    return

                # Auto Login
                if username and password:
                    user_selector = "#form1 > div > div:nth-child(3) > input"
                    pass_selector = "#form1 > div > div:nth-child(4) > input"
                    try:
                        try:
                            page.wait_for_selector(user_selector, timeout=5000)
                            log("检测到登录页面，开始自动登录...")
                            page.fill(user_selector, username)
                            page.fill(pass_selector, password)
                            page.press(pass_selector, "Enter")
                            page.wait_for_load_state("networkidle")
                            log("登录操作完成，正在跳转到目标页面...")
                            page.goto(url)
                            page.wait_for_load_state("networkidle")
                        except:
                            log("未检测到登录输入框，跳过自动登录...")
                    except Exception as e:
                        log(f"自动登录尝试失败: {e}")

                if not headless:
                    log("请在浏览器中完成登录（如果需要）...")
                
                try:
                    log("等待页面关键元素...")
                    page.wait_for_selector("#myTab, .nav-tabs, ul.nav, a:has-text('待审核'), a:has-text('待发货')", timeout=60000)
                except Exception as e:
                    log("等待超时或出错，请检查是否已登录。")
                    browser.close()
                    self.running = False
                    return

                log("检测到目标页面，开始执行自动化流程...")

                while not self.stop_event.is_set():
                    log(f"\n--- 开始新一轮检查 ({time.strftime('%H:%M:%S')}) ---")
                    
                    # 1. Check Count
                    found_count = False
                    try:
                        tab_locator = page.locator("a:has-text('待审核')").filter(has=page.locator("visible=true")).first
                        if tab_locator.count() > 0 and tab_locator.is_visible():
                            tab_text = tab_locator.inner_text()
                            if "(" in tab_text and ")" in tab_text:
                                import re
                                match = re.search(r"\((\d+)\)", tab_text)
                                if match:
                                    count_val = int(match.group(1))
                                    log(f"Tab 显示待审核数量: {count_val}")
                                    if count_val == 0:
                                        found_count = True
                    except Exception as e:
                        log(f"检查 Tab 数量出错: {e}")

                    if not found_count:
                         # Fallback to pagination count
                        count_selector = "#pagination > div > ul > li > span"
                        try:
                            if page.locator(count_selector).is_visible():
                                count_text = page.locator(count_selector).inner_text().strip()
                                log(f"分页器显示数量: {count_text}")
                                if count_text == "0":
                                    found_count = True
                        except:
                            pass

                    if found_count:
                        log(f"待审核数量为 0，等待 {scan_interval} 秒后重试...")
                        time.sleep(scan_interval)
                        log("正在刷新页面...")
                        try:
                            page.reload(timeout=60000)
                            page.wait_for_load_state("networkidle", timeout=60000)
                        except:
                            pass
                        continue

                    # 2. Click Tab
                    try:
                        target_link = page.locator("a:has-text('待审核')").filter(has=page.locator("visible=true")).first
                        is_active = False
                        try:
                            if target_link.count() > 0 and target_link.is_visible():
                                a_class = target_link.get_attribute("class")
                                parent_li = target_link.locator("xpath=..")
                                li_class = parent_li.get_attribute("class")
                                if (li_class and "active" in li_class) or (a_class and "active" in a_class):
                                    is_active = True
                        except:
                            pass

                        if not is_active and target_link.count() > 0:
                            log("点击 '待审' Tab...")
                            target_link.click()
                            page.wait_for_load_state("networkidle")
                            time.sleep(2)
                    except Exception as e:
                        log(f"点击 Tab 操作异常: {e}")

                    # 3. Process List
                    container_selector = "#table > div > div > div"
                    items_locator = page.locator(f"{container_selector} > div")
                    items_count = items_locator.count()
                    log(f"当前页面列表项总数: {items_count}")
                    
                    processed_count = 0
                    start_index = 3
                    for i in range(start_index, items_count):
                        if self.stop_event.is_set():
                            break

                        current_item_selector = f"{container_selector} > div:nth-child({i + 1})"
                        merchant_selector = f"{current_item_selector} > div.table-row.table-top > div > span:nth-child(3)"
                        
                        try:
                            if not page.locator(merchant_selector).is_visible():
                                continue
                                
                            merchant_name = page.locator(merchant_selector).inner_text().strip()
                            merchant_name_clean = merchant_name.replace("商户名称：", "").replace("商户名称:", "").strip()
                            
                            if merchant_name_clean != "米奇租赁":
                                # log(f"跳过商户: {merchant_name_clean}")
                                continue
                            
                            log(f"-> 发现米奇租赁订单 (索引: {i})...")
                            item_selector = current_item_selector
                            text_selector = f"{item_selector} > div:nth-child(2) > div.goods-des > a > div > div > span.text-primary"
                            
                            text_content = ""
                            try:
                                text_element = page.locator(text_selector)
                                text_content = text_element.inner_text()
                                log(f"订单内容: {text_content}")
                            except:
                                log("获取订单内容失败")
                                continue
            
                            target_option = "米奇租赁官方"
                            matched_info = "默认规则"
                            
                            for keyword, option in keyword_mapping.items():
                                if keyword in text_content:
                                    target_option = option
                                    matched_info = f"关键词匹配: {keyword}"
                                    break
                            
                            log(f"匹配结果: [{matched_info}] -> 分配给: [{target_option}]")
                            
                            # Assign
                            try:
                                # Try to find the assign button using specific column or text
                                # User reported it's in nth-child(7), but we use a more robust search for "分配" text within the row
                                assign_btn = page.locator(item_selector).locator("a").filter(has_text="分配")
                                
                                if assign_btn.count() == 0:
                                    # Fallback: try "订单分配"
                                    assign_btn = page.locator(item_selector).locator("a").filter(has_text="订单分配")

                                if assign_btn.count() > 0:
                                    log("点击分配按钮...")
                                    # Ensure we click the visible one if multiple
                                    btn_to_click = assign_btn.filter(has=page.locator("visible=true")).first
                                    if btn_to_click.count() > 0:
                                        btn_to_click.click()
                                    else:
                                        log("找到分配按钮但不加见，尝试强制点击第一个")
                                        assign_btn.first.click()
                                    
                                    # Handle Modal
                                    try:
                                        # Wait for modal to appear
                                        page.wait_for_selector(".modal", timeout=5000)
                                        
                                        # Click dropdown
                                        # Try user provided ID first, then fallback to generic class
                                        dropdown = page.locator("#select2-chosen-2")
                                        if not dropdown.is_visible():
                                            dropdown = page.locator(".select2-choice, .select2-selection").filter(has=page.locator("visible=true")).first
                                        
                                        log("点击商户下拉框...")
                                        dropdown.click()
                                        
                                        # Type merchant name in search box
                                        # Select2 search box usually is appended to body
                                        search_input = page.locator(".select2-search__field, input.select2-input").filter(has=page.locator("visible=true"))
                                        search_input.wait_for(timeout=5000)
                                        
                                        log(f"输入商户名称: {target_option}")
                                        search_input.fill(target_option)
                                        time.sleep(1) # Wait for search results
                                        search_input.press("Enter")
                                        
                                        # Click Confirm
                                        log("点击确定按钮...")
                                        try:
                                            # Scope to the visible modal
                                            visible_modal = page.locator(".modal").filter(has=page.locator("visible=true"))
                                            if visible_modal.count() > 0:
                                                confirm_btn = visible_modal.locator("button.btn-primary, button:has-text('确定'), button:has-text('确认'), input[value='确定'], input[value='确认']").first
                                                if confirm_btn.count() > 0 and confirm_btn.is_visible():
                                                    confirm_btn.click()
                                                    log("分配操作提交完成")
                                                else:
                                                    log("在弹窗中未找到确定按钮")
                                                    # Log visible buttons for debugging
                                                    buttons = visible_modal.locator("button, input[type='button'], input[type='submit']").all_inner_texts()
                                                    log(f"弹窗内可见按钮: {buttons}")
                                                    raise Exception("未找到确定按钮")
                                            else:
                                                 # Fallback to global search if modal structure is different
                                                confirm_btn = page.locator("button:has-text('确定'), button:has-text('确认'), input[value='确定']").filter(has=page.locator("visible=true")).last
                                                confirm_btn.click()
                                                log("分配操作提交完成 (Fallback)")
                                        except Exception as e:
                                            log(f"点击确定按钮失败: {e}")
                                            raise e

                                        # Send Notification
                                        self.send_notification(text_content, target_option)
                                        
                                        # Wait for modal to close
                                        time.sleep(2)
                                        
                                        # Mark as processed and break to refresh page (safer to avoid stale elements)
                                        processed_count += 1
                                        break
                                        
                                    except Exception as e:
                                        log(f"分配弹窗操作失败: {e}")
                                        # Try to close modal if stuck?
                                else:
                                    log("未找到分配按钮")
                                    # Debug: print available links in the row
                                    try:
                                        links = page.locator(item_selector).locator("a").all_inner_texts()
                                        log(f"当前行可用链接: {links}")
                                    except:
                                        pass
                            except Exception as e:
                                log(f"点击分配按钮失败: {e}")

                        except Exception as e:
                            log(f"处理订单行出错: {e}")
                    
                    # Wait for next scan
                    if not self.stop_event.is_set():
                        if processed_count > 0:
                            log(f"本轮已处理 {processed_count} 个订单，立即刷新页面继续...")
                            time.sleep(2)
                        else:
                            log(f"本轮结束，等待 {scan_interval} 秒...")
                            time.sleep(scan_interval)
                        
                        try:
                            page.reload()
                            page.wait_for_load_state("networkidle")
                        except:
                            pass

                browser.close()
                log("浏览器已关闭")

        except Exception as e:
            log(f"运行过程中发生严重错误: {e}")
        finally:
            self.running = False
            log("服务已停止")

# Singleton instance
scanner = OrderScanner()

if __name__ == "__main__":
    scanner.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scanner.stop()
