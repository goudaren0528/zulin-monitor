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

def _truncate_text(text, max_len=240):
    try:
        s = "" if text is None else str(text)
    except Exception:
        return ""
    s = s.replace("\r", " ").replace("\n", " ").strip()
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."

def _mask_sensitive(text):
    import re

    s = "" if text is None else str(text)

    def _mask_mobile(m):
        num = m.group(0)
        if len(num) == 11:
            return num[:3] + "****" + num[-4:]
        return num

    try:
        s = re.sub(r"\b1\d{10}\b", _mask_mobile, s)
    except Exception:
        pass

    return s

def _safe_locator_info(locator):
    info = {"count": None, "visible": None}
    try:
        info["count"] = locator.count()
    except Exception:
        info["count"] = None
    try:
        info["visible"] = locator.is_visible()
    except Exception:
        info["visible"] = None
    return info

def _safe_inner_text(locator, default=""):
    try:
        return locator.inner_text()
    except Exception:
        return default

def _extract_order_fields(block_text):
    import re

    text = "" if block_text is None else str(block_text)
    fields = {}

    patterns = {
        "order_no": r"订单号[:：]\s*([A-Za-z0-9_-]+)",
        "pay_no": r"支付单号[:：]\s*([A-Za-z0-9_-]+)",
        "mobile": r"(?:手机|电话)[:：]\s*(1\d{10})",
    }

    for key, pattern in patterns.items():
        try:
            m = re.search(pattern, text)
            if m:
                val = m.group(1).strip()
                if key == "mobile" and len(val) == 11:
                    val = val[:3] + "****" + val[-4:]
                fields[key] = val
        except Exception:
            continue

    return fields

def _extract_merchant_from_text(block_text):
    import re

    text = "" if block_text is None else str(block_text)
    try:
        m = re.search(r"商户名称[:：]\s*([^\s]+)", text)
        if m:
            return m.group(1).strip()
    except Exception:
        return None
    return None

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
        self.thread = threading.Thread(target=self._run_loop, name="OrderScannerThread")
        self.thread.daemon = True
        self.thread.start()
        log("服务启动中...")

    def stop(self):
        if not self.running:
            log("服务未运行")
            return
        
        log("正在停止服务...")
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            try:
                self.thread.join(timeout=5)
            except Exception:
                pass

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
                # args = ["--window-position=0,0"] if not headless else []
                # Remove window hiding to allow user to see the browser
                args = [] 
                browser = p.chromium.launch(headless=headless, args=args)
                
                context = browser.new_context()
                page = context.new_page()

                # Reuse login logic (accessing target_url directly might redirect to login)
                # Strategy: Access login page first, then navigate to target URL
                from urllib.parse import urlparse
                parsed = urlparse(url)
                login_url = ""
                if parsed.scheme and parsed.netloc:
                    login_url = f"{parsed.scheme}://{parsed.netloc}/web/index.php?c=user&a=login&"
                
                log(f"准备访问: {login_url or url}")
                resp = None
                try:
                    if login_url:
                        log(f"优先访问登录页: {login_url}")
                        resp = page.goto(login_url)
                    else:
                        resp = page.goto(url)
                except Exception as e:
                    log(f"访问 URL 失败: {e}")
                    return

                # Helper for login
                def perform_login(p_page):
                    if username and password:
                        user_selector = "#form1 > div > div:nth-child(3) > input"
                        pass_selector = "#form1 > div > div:nth-child(4) > input"
                        try:
                            # Check if login form exists
                            if p_page.locator(user_selector).count() > 0:
                                log("检测到登录页面，开始自动登录...")
                                p_page.fill(user_selector, username)
                                p_page.fill(pass_selector, password)
                                p_page.press(pass_selector, "Enter")
                                p_page.wait_for_load_state("networkidle")
                                log("登录操作完成...")
                                return True
                        except Exception as e:
                            log(f"自动登录尝试失败: {e}")
                    return False

                # Check current page state
                current_url = page.url
                page_title = page.title()
                status_code = None
                try:
                    if resp:
                        status_code = resp.status
                except Exception:
                    status_code = None
                log(f"当前页面: {current_url} | 标题: {page_title} | 状态码: {status_code}")

                # Initial Login Check
                try:
                    # Try to find login form
                    try:
                        page.wait_for_selector("#form1", timeout=5000)
                        perform_login(page)
                    except:
                        pass # Not on login page
                        
                    # After potential login, ensure we are at the target URL
                    if "order.list.status1" not in page.url:
                        log(f"正在跳转到订单列表页: {url}")
                        resp = page.goto(url)
                        page.wait_for_load_state("networkidle")
                        
                        # Update status code after jump
                        try:
                             if resp: status_code = resp.status
                        except: status_code = None
                        log(f"跳转后页面: {page.url} | 状态码: {status_code}")
                        
                except Exception as e:
                    log(f"初始化页面/登录流程出错: {e}")
                    pass # Proceed to loop to let it retry or fail gracefully

                log("检测到目标页面，开始执行自动化流程...")
                
                key_selector = "#myTab, .nav-tabs, ul.nav, a:has-text('待审核'), a:has-text('待发货')"
                while not self.stop_event.is_set():
                    try:
                        if status_code is not None and status_code >= 400:
                            try:
                                snippet = _truncate_text(page.content(), 600)
                                log(f"页面异常响应: {status_code} content={snippet}")
                            except Exception:
                                pass
                            try:
                                page.screenshot(path="debug_last_page.png", full_page=True)
                                log("已保存页面截图: debug_last_page.png")
                            except Exception:
                                pass
                            log("5秒后将尝试重新加载...")
                            self.stop_event.wait(5)
                            try:
                                resp = page.goto(url, timeout=60000, wait_until="domcontentloaded")
                                try:
                                    page.wait_for_load_state("networkidle", timeout=15000)
                                except Exception:
                                    pass
                                status_code = resp.status if resp else None
                            except Exception:
                                status_code = None
                            try:
                                current_url = page.url
                                page_title = page.title()
                                log(f"当前页面: {current_url} | 标题: {page_title} | 状态码: {status_code}")
                            except Exception:
                                pass
                            continue

                        log("等待页面关键元素...")
                        ready = False
                        for _ in range(12):
                            if self.stop_event.is_set():
                                break
                            try:
                                page.wait_for_selector(key_selector, timeout=5000, state="visible")
                                ready = True
                                break
                            except Exception:
                                continue
                        if ready:
                            break

                        try:
                            snippet = _truncate_text(page.content(), 600)
                            log(f"等待关键元素超时 content={snippet}")
                        except Exception:
                            log("等待关键元素超时")
                        try:
                            page.screenshot(path="debug_last_page.png", full_page=True)
                            log("已保存页面截图: debug_last_page.png")
                        except Exception:
                            pass
                        log("5秒后将尝试重新加载...")
                        self.stop_event.wait(5)
                        try:
                            page.reload(timeout=60000)
                        except Exception:
                            try:
                                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                            except Exception:
                                pass
                        continue
                    except Exception as e:
                        log(f"页面初始化阶段异常: {e}")
                        log("5秒后将尝试重新加载...")
                        self.stop_event.wait(5)
                        try:
                            page.reload(timeout=60000)
                        except Exception:
                            pass

                if self.stop_event.is_set():
                    try:
                        browser.close()
                    except Exception:
                        pass
                    return

                log("检测到目标页面，开始执行自动化流程...")

                while not self.stop_event.is_set():
                    log(f"\n--- 开始新一轮检查 ({time.strftime('%H:%M:%S')}) ---")
                    try:
                        log(f"页面信息: url={page.url}")
                    except Exception:
                        pass
                    
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
                        self.stop_event.wait(scan_interval)
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
                            self.stop_event.wait(2)
                    except Exception as e:
                        log(f"点击 Tab 操作异常: {e}")

                    # 3. Process List
                    container_selector = "#table > div > div > div"
                    items_locator = page.locator(f"{container_selector} > div")
                    items_count = items_locator.count()
                    log(f"当前页面列表项总数: {items_count}")

                    scan_stats = {
                        "row_total": 0,
                        "merchant_selector_missing": 0,
                        "merchant_not_visible": 0,
                        "merchant_text_empty": 0,
                        "merchant_non_target": 0,
                        "merchant_target": 0,
                        "order_text_missing": 0,
                        "order_text_empty": 0,
                    }
                    merchant_top = {}
                    
                    processed_count = 0
                    start_index = 3
                    for i in range(start_index, items_count):
                        if self.stop_event.is_set():
                            break

                        current_item_selector = f"{container_selector} > div:nth-child({i + 1})"
                        merchant_selector = f"{current_item_selector} > div.table-row.table-top > div > span:nth-child(3)"
                        
                        try:
                            scan_stats["row_total"] += 1
                            item_loc = page.locator(current_item_selector)

                            merchant_loc = page.locator(merchant_selector)
                            merchant_info = _safe_locator_info(merchant_loc)
                            merchant_name = ""
                            merchant_name_clean = ""
                            merchant_source = "selector"

                            if merchant_info.get("count") == 0:
                                row_text = _safe_inner_text(item_loc, "")
                                parsed = _extract_merchant_from_text(row_text)
                                if parsed:
                                    merchant_name_clean = parsed
                                    merchant_source = "text_parse"
                                else:
                                    scan_stats["merchant_selector_missing"] += 1
                                    if scan_stats["merchant_selector_missing"] <= 6:
                                        has_kw = "商户名称" in row_text
                                        log(
                                            f"[调试] 未找到商户字段: idx={i} selector={merchant_selector} "
                                            f"has_kw={has_kw} row={_truncate_text(_mask_sensitive(row_text))}"
                                        )
                                    continue
                            else:
                                if not merchant_info.get("visible"):
                                    scan_stats["merchant_not_visible"] += 1
                                    if scan_stats["merchant_not_visible"] <= 3:
                                        log(f"[调试] 商户字段不可见: idx={i} info={merchant_info}")
                                    continue
                                merchant_name = _safe_inner_text(merchant_loc, "").strip()
                                merchant_name_clean = merchant_name.replace("商户名称：", "").replace("商户名称:", "").strip()
                                merchant_name_clean = "".join(merchant_name_clean.split())

                            if not merchant_name_clean:
                                scan_stats["merchant_text_empty"] += 1
                                if scan_stats["merchant_text_empty"] <= 3:
                                    row_text = _safe_inner_text(item_loc, "")
                                    log(
                                        f"[调试] 商户文本为空: idx={i} source={merchant_source} "
                                        f"raw={_truncate_text(_mask_sensitive(merchant_name))} row={_truncate_text(_mask_sensitive(row_text))}"
                                    )
                                continue

                            merchant_top[merchant_name_clean] = merchant_top.get(merchant_name_clean, 0) + 1
                            
                            if merchant_name_clean != "米奇租赁":
                                scan_stats["merchant_non_target"] += 1
                                if scan_stats["merchant_non_target"] <= 6:
                                    row_text = _safe_inner_text(item_loc, "")
                                    log(
                                        f"[调试] 跳过非目标商户: idx={i} source={merchant_source} "
                                        f"merchant={merchant_name_clean} raw={_truncate_text(_mask_sensitive(merchant_name))} "
                                        f"row={_truncate_text(_mask_sensitive(row_text))}"
                                    )
                                continue

                            scan_stats["merchant_target"] += 1
                            
                            log(f"-> 发现米奇租赁订单 (索引: {i})...")
                            item_selector = current_item_selector
                            text_selector = f"{item_selector} > div:nth-child(2) > div.goods-des > a > div > div > span.text-primary"
                            
                            text_content = ""
                            try:
                                text_element = page.locator(text_selector)
                                text_info = _safe_locator_info(text_element)
                                if text_info.get("count") == 0:
                                    scan_stats["order_text_missing"] += 1
                                    row_text = _safe_inner_text(item_loc, "")
                                    log(f"[调试] 未找到订单内容元素: idx={i} selector={text_selector} row={_truncate_text(_mask_sensitive(row_text))}")
                                    continue

                                text_content = _safe_inner_text(text_element, "").strip()
                                if not text_content:
                                    scan_stats["order_text_empty"] += 1
                                    row_text = _safe_inner_text(item_loc, "")
                                    log(f"[调试] 订单内容为空: idx={i} info={text_info} row={_truncate_text(_mask_sensitive(row_text))}")
                                    continue

                                row_text = _safe_inner_text(item_loc, "")
                                extra_fields = _extract_order_fields(row_text)
                                extra_kv = " ".join([f"{k}={v}" for k, v in extra_fields.items()])
                                extra_part = f" {extra_kv}" if extra_kv else ""
                                log(f"订单内容: {_truncate_text(_mask_sensitive(text_content), 500)} | merchant={merchant_name_clean}{extra_part}")
                            except Exception as e:
                                scan_stats["order_text_missing"] += 1
                                log(f"获取订单内容失败: idx={i} err={e}")
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
                                assign_btn = item_loc.locator("a").filter(has_text="订单分配")
                                assign_btn_label = "订单分配"

                                if assign_btn.count() == 0:
                                    assign_btn = item_loc.locator("div:nth-child(7) a").filter(has_text="订单分配")

                                if assign_btn.count() == 0:
                                    assign_btn = item_loc.locator("div:nth-child(7) > div > a:nth-child(4)")

                                if assign_btn.count() == 0:
                                    assign_btn = item_loc.locator("a").filter(has_text="分配").filter(has_not_text="分配人员")
                                    assign_btn_label = "分配"

                                if assign_btn.count() == 0:
                                    assign_btn = item_loc.locator("div:nth-child(7) a").filter(has_text="分配").filter(has_not_text="分配人员")
                                    assign_btn_label = "分配"

                                if assign_btn.count() > 0:
                                    log(f"点击{assign_btn_label}按钮...")
                                    # Ensure we click the visible one if multiple
                                    btn_to_click = assign_btn.filter(has=page.locator("visible=true")).first
                                    if btn_to_click.count() > 0:
                                        try:
                                            btn_to_click.scroll_into_view_if_needed(timeout=5000)
                                        except Exception:
                                            pass
                                        try:
                                            btn_to_click.click(timeout=8000, no_wait_after=True)
                                        except Exception:
                                            btn_to_click.click(timeout=8000, force=True, no_wait_after=True)
                                    else:
                                        log("找到分配按钮但不加见，尝试强制点击第一个")
                                        try:
                                            assign_btn.first.scroll_into_view_if_needed(timeout=5000)
                                        except Exception:
                                            pass
                                        try:
                                            assign_btn.first.click(timeout=8000, no_wait_after=True)
                                        except Exception:
                                            assign_btn.first.click(timeout=8000, force=True, no_wait_after=True)
                                    
                                    # Handle Modal
                                    try:
                                        # Wait for modal to appear
                                        page.wait_for_selector("#ajaxModal", state="visible", timeout=10000)
                                        modal = page.locator("#ajaxModal").filter(has=page.locator("visible=true")).first
                                        
                                        # Click dropdown
                                        # Try user provided ID first, then fallback to generic class
                                        dropdown = modal.locator("#select2-chosen-2, .select2-choice, .select2-selection").filter(has=page.locator("visible=true")).first
                                        
                                        log("点击商户下拉框...")
                                        dropdown.wait_for(state="visible", timeout=8000)
                                        try:
                                            dropdown.scroll_into_view_if_needed(timeout=5000)
                                        except Exception:
                                            pass
                                        try:
                                            dropdown.click(timeout=8000, no_wait_after=True)
                                        except Exception:
                                            dropdown.click(timeout=8000, force=True, no_wait_after=True)
                                        
                                        # Type merchant name in search box
                                        # Select2 search box usually is appended to body
                                        search_input = page.locator(
                                            ".select2-dropdown input, .select2-drop input, .select2-search input, .select2-search__field, input.select2-input"
                                        ).filter(has=page.locator("visible=true")).first
                                        search_input.wait_for(state="visible", timeout=8000)
                                        
                                        log(f"输入商户名称: {target_option}")
                                        search_input.fill(target_option)
                                        time.sleep(1) # Wait for search results
                                        search_input.press("Enter")
                                        
                                        # Click Confirm
                                        log("点击确定按钮...")
                                        try:
                                            ajax_confirm = modal.locator("form > div > div > div.modal-footer > button.btn.btn-primary").first
                                            if ajax_confirm.count() > 0 and ajax_confirm.is_visible():
                                                ajax_confirm.click(timeout=8000, no_wait_after=True)
                                                log("分配操作提交完成")
                                            else:
                                                # Scope to the visible modal
                                                visible_modal = page.locator(".modal").filter(has=page.locator("visible=true"))
                                                if visible_modal.count() > 0:
                                                    confirm_btn = visible_modal.locator("button.btn-primary, button:has-text('确定'), button:has-text('确认'), input[value='确定'], input[value='确认']").first
                                                    if confirm_btn.count() > 0 and confirm_btn.is_visible():
                                                        confirm_btn.click(timeout=8000, no_wait_after=True)
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
                                                    confirm_btn.click(timeout=8000, no_wait_after=True)
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

                    try:
                        top_items = sorted(merchant_top.items(), key=lambda x: x[1], reverse=True)[:8]
                        top_text = ", ".join([f"{name}:{cnt}" for name, cnt in top_items]) if top_items else "无"
                        log(
                            "本轮扫描统计: "
                            f"rows={scan_stats['row_total']} "
                            f"target={scan_stats['merchant_target']} "
                            f"non_target={scan_stats['merchant_non_target']} "
                            f"merchant_missing={scan_stats['merchant_selector_missing']} "
                            f"merchant_invisible={scan_stats['merchant_not_visible']} "
                            f"order_missing={scan_stats['order_text_missing']} "
                            f"order_empty={scan_stats['order_text_empty']} "
                            f"merchant_top={top_text}"
                        )
                    except Exception:
                        pass
                    
                    # Wait for next scan
                    if not self.stop_event.is_set():
                        if processed_count > 0:
                            log(f"本轮已处理 {processed_count} 个订单，立即刷新页面继续...")
                            self.stop_event.wait(2)
                        else:
                            log(f"本轮结束，等待 {scan_interval} 秒...")
                            self.stop_event.wait(scan_interval)
                        
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
