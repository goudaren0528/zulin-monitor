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

def _parse_chromium_major(version_text, default_major=120):
    import re

    s = "" if version_text is None else str(version_text)
    m = re.search(r"(\d+)\.", s)
    if not m:
        m = re.search(r"\b(\d+)\b", s)
    if not m:
        return default_major
    try:
        return int(m.group(1))
    except Exception:
        return default_major

def _default_user_agent(chrome_major):
    major = chrome_major if chrome_major else 120
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.0.0 Safari/537.36"
    )

def _default_extra_http_headers(chrome_major):
    major = chrome_major if chrome_major else 120
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "DNT": "1",
        "Cache-Control": "max-age=0",
        "Pragma": "no-cache",
        "Sec-CH-UA": f"\"Chromium\";v=\"{major}\", \"Not:A-Brand\";v=\"99\", \"Google Chrome\";v=\"{major}\"",
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": "\"Windows\"",
    }

def _default_init_script():
    return """
(() => {
  try {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'language', { get: () => 'zh-CN' });
    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
  } catch (e) {}
})();
""".strip()

def _coerce_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except Exception:
        return None

def _pick_interval_seconds(fallback_seconds, min_seconds, max_seconds):
    fb = _coerce_float(fallback_seconds)
    if fb is None:
        fb = 0.0

    mn = _coerce_float(min_seconds)
    mx = _coerce_float(max_seconds)

    if mn is None and mx is None:
        return fb
    if mn is None:
        mn = fb
    if mx is None:
        mx = fb

    if mn < 0:
        mn = 0.0
    if mx < 0:
        mx = 0.0
    if mx < mn:
        mn, mx = mx, mn
    if mx == mn:
        return mn

    import random

    if mn.is_integer() and mx.is_integer():
        return float(random.randint(int(mn), int(mx)))
    return float(random.uniform(mn, mx))

def _env_truthy(name):
    v = os.getenv(name)
    if v is None:
        return False
    s = str(v).strip().lower()
    return s not in ("", "0", "false", "no", "off", "disable", "disabled")

def _is_production_env():
    v = (
        os.getenv("ORDER_POINT_ENV")
        or os.getenv("APP_ENV")
        or os.getenv("ENV")
        or os.getenv("PYTHON_ENV")
    )
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ("prod", "production", "online", "release")

def _linux_has_display():
    return bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY") or os.getenv("MIR_SOCKET"))

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


def _match_keyword(keyword_entry, text_content):
    """
    检查关键词条目是否匹配文本内容。
    支持逗号分隔的多个关键词，大小写不敏感。

    Args:
        keyword_entry: 关键词条目，可以是单个关键词或逗号分隔的多个关键词
        text_content: 要匹配的文本内容（已转小写）

    Returns:
        (bool, str): (是否匹配, 匹配到的具体关键词)
    """
    # 分割关键词（支持中英文逗号）
    keywords = [k.strip() for k in keyword_entry.replace('，', ',').split(',') if k.strip()]

    for kw in keywords:
        if kw.lower() in text_content:
            return True, kw

    return False, None


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

class OrderScanner:
    def __init__(self):
        self.config = {}
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self._weight_router = {}  # 存储每个关键词的轮询索引
        self.load_config()

    def load_config(self):
        candidates = ["config.local.json", "config.json"]
        config_path = None
        for pth in candidates:
            if os.path.exists(pth):
                config_path = pth
                break
        if not config_path:
            log("错误: 找不到配置文件 config.local.json 或 config.json")
            return False
        
        try:
            log(f"使用配置文件: {config_path}")
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
        weight_ratio = ":".join([str(item.get("weight", 1)) for item in merchant_list])

        round_info = f"轮询: {current_pos}/{total_pos}"
        if current_pos == 1:
            round_info += f", 权重比 {weight_ratio}"

        return (selected_merchant, round_info)

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
        target_platform = self.get_config("target_platform", "米奇租赁")
        scan_interval = self.get_config("scan_interval", 30)
        scan_interval_min = self.get_config("scan_interval_min", None)
        scan_interval_max = self.get_config("scan_interval_max", None)
        headless_cfg = self.get_config("headless", True)
        headless = bool(headless_cfg)
        if _env_truthy("ORDER_POINT_HEADLESS") or _env_truthy("HEADLESS"):
            headless = True
        elif _env_truthy("ORDER_POINT_HEADED") or _env_truthy("HEADED"):
            headless = False
        elif _is_production_env() and sys.platform.startswith("linux"):
            headless = False

        if (not headless) and sys.platform.startswith("linux") and (not _linux_has_display()):
            log("检测到 Linux 未配置 DISPLAY/WAYLAND_DISPLAY，自动切回 Headless 运行")
            headless = True

        slow_mo_val = self.get_config("slow_mo_ms", None)
        if slow_mo_val is None:
            slow_mo_val = os.getenv("SLOW_MO_MS")
        try:
            slow_mo_ms = int(float(slow_mo_val)) if slow_mo_val is not None else (80 if not headless else 0)
        except Exception:
            slow_mo_ms = 80 if not headless else 0

        log(f"启动浏览器... (Headless: {headless})")
        
        try:
            with sync_playwright() as p:
                base_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--lang=zh-CN",
                ]
                config_args = self.get_config("chromium_args", [])
                if not isinstance(config_args, list):
                    config_args = []
                args = []
                for a in base_args + config_args:
                    if isinstance(a, str) and a and a not in args:
                        args.append(a)

                channel = self.get_config("browser_channel", None)
                launch_kwargs = {"headless": headless, "args": args, "slow_mo": slow_mo_ms}
                if channel:
                    launch_kwargs["channel"] = channel
                try:
                    browser = p.chromium.launch(**launch_kwargs)
                except Exception:
                    launch_kwargs.pop("channel", None)
                    browser = p.chromium.launch(**launch_kwargs)

                storage_state_path = self.get_config("storage_state_path", "")
                if not storage_state_path:
                    storage_state_path = "storage_state_order_scanner.json"
                chrome_major = None
                try:
                    version_val = getattr(browser, "version", None)
                    if callable(version_val):
                        version_val = version_val()
                    chrome_major = _parse_chromium_major(version_val)
                except Exception:
                    chrome_major = None

                user_agent = self.get_config("user_agent", None) or _default_user_agent(chrome_major)
                locale = self.get_config("locale", "zh-CN") or "zh-CN"
                timezone_id = self.get_config("timezone_id", "Asia/Shanghai") or "Asia/Shanghai"
                viewport = self.get_config("viewport", {"width": 1920, "height": 1080})
                if not isinstance(viewport, dict) or "width" not in viewport or "height" not in viewport:
                    viewport = {"width": 1920, "height": 1080}
                screen = self.get_config("screen", viewport)
                if not isinstance(screen, dict) or "width" not in screen or "height" not in screen:
                    screen = viewport
                device_scale_factor = self.get_config("device_scale_factor", 1)
                try:
                    device_scale_factor = float(device_scale_factor)
                except Exception:
                    device_scale_factor = 1
                color_scheme = self.get_config("color_scheme", "light") or "light"
                extra_http_headers = self.get_config("extra_http_headers", None)
                if not isinstance(extra_http_headers, dict):
                    extra_http_headers = _default_extra_http_headers(chrome_major)
                init_script = self.get_config("init_script", None) or _default_init_script()

                context_options = {
                    "user_agent": user_agent,
                    "viewport": viewport,
                    "screen": screen,
                    "device_scale_factor": device_scale_factor,
                    "locale": locale,
                    "timezone_id": timezone_id,
                    "color_scheme": color_scheme,
                }
                if storage_state_path and os.path.exists(storage_state_path):
                    context_options["storage_state"] = storage_state_path

                context = browser.new_context(**context_options)
                try:
                    context.set_extra_http_headers(extra_http_headers)
                except Exception:
                    pass
                try:
                    context.add_init_script(init_script)
                except Exception:
                    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
                page = context.new_page()

                import random

                action_delay_min_ms = self.get_config("action_delay_min_ms", 80)
                action_delay_max_ms = self.get_config("action_delay_max_ms", 260)
                typing_delay_min_ms = self.get_config("typing_delay_min_ms", 40)
                typing_delay_max_ms = self.get_config("typing_delay_max_ms", 120)
                manual_intervention_seconds = self.get_config("manual_intervention_seconds", 180)
                try:
                    manual_intervention_seconds = float(manual_intervention_seconds)
                except Exception:
                    manual_intervention_seconds = 180.0

                def _human_pause(min_ms=None, max_ms=None):
                    mn = action_delay_min_ms if min_ms is None else min_ms
                    mx = action_delay_max_ms if max_ms is None else max_ms
                    try:
                        mn = int(float(mn))
                    except Exception:
                        mn = 80
                    try:
                        mx = int(float(mx))
                    except Exception:
                        mx = 260
                    if mx < mn:
                        mn, mx = mx, mn
                    delay_ms = random.randint(max(0, mn), max(0, mx))
                    self.stop_event.wait(delay_ms / 1000.0)

                def _human_type(selector, text, timeout_ms=15000):
                    loc = page.locator(selector).first
                    loc.wait_for(state="visible", timeout=timeout_ms)
                    try:
                        loc.scroll_into_view_if_needed(timeout=timeout_ms)
                    except Exception:
                        pass
                    try:
                        loc.click(timeout=timeout_ms)
                    except Exception:
                        loc.click(timeout=timeout_ms, force=True)
                    try:
                        loc.fill("")
                    except Exception:
                        try:
                            loc.press("Control+A")
                            loc.press("Backspace")
                        except Exception:
                            pass
                    try:
                        mn = int(float(typing_delay_min_ms))
                    except Exception:
                        mn = 40
                    try:
                        mx = int(float(typing_delay_max_ms))
                    except Exception:
                        mx = 120
                    if mx < mn:
                        mn, mx = mx, mn
                    delay = random.randint(max(0, mn), max(0, mx))
                    loc.type("" if text is None else str(text), delay=delay)
                    _human_pause()

                from urllib.parse import urlparse
                parsed = urlparse(url)
                login_url = f"{parsed.scheme}://{parsed.netloc}/web/index.php?c=user&a=login"
                safe_entry_url = f"{parsed.scheme}://{parsed.netloc}/web/index.php?c=site&a=entry&m=ewei_shopv2&do=web&r=statistics.interface_log"

                def perform_login():
                    if not (username and password):
                        return False
                    user_selector = "#form1 > div > div:nth-child(3) > input"
                    pass_selector = "#form1 > div > div:nth-child(4) > input"
                    try:
                        if page.locator(user_selector).count() > 0:
                            log("检测到登录页面，开始自动登录...")
                            _human_type(user_selector, username)
                            _human_type(pass_selector, password)
                            try:
                                page.press(pass_selector, "Enter")
                            except Exception:
                                try:
                                    page.keyboard.press("Enter")
                                except Exception:
                                    pass
                            page.wait_for_load_state("networkidle")
                            log("登录操作完成")
                            try:
                                if storage_state_path:
                                    context.storage_state(path=storage_state_path)
                                    log(f"已保存登录态: {storage_state_path}")
                            except Exception as e:
                                log(f"保存登录态失败: {e}")
                            return True
                    except Exception as e:
                        log(f"自动登录尝试失败: {e}")
                    return False

                if self.stop_event.is_set():
                    try:
                        browser.close()
                    except Exception:
                        pass
                    return

                def _safe_page_state():
                    try:
                        return f"url={page.url} title={page.title()}"
                    except Exception:
                        return "url=<unknown> title=<unknown>"

                def _click_nav(selector, label, timeout_ms=20000, wait_networkidle=True):
                    selectors = selector if isinstance(selector, (list, tuple)) else [selector]
                    last_err = None
                    for sel in selectors:
                        try:
                            log(f"导航点击准备: {label} selector={sel} {_safe_page_state()}")
                            loc = page.locator(sel).first
                            loc.wait_for(state="visible", timeout=timeout_ms)
                            try:
                                loc.hover(timeout=timeout_ms)
                            except Exception:
                                pass
                            _human_pause()
                            try:
                                loc.click()
                            except Exception:
                                try:
                                    loc.scroll_into_view_if_needed(timeout=timeout_ms)
                                except Exception:
                                    pass
                                loc.click(force=True)
                            _human_pause()
                            log(f"导航点击完成: {label} selector={sel} {_safe_page_state()}")
                            if wait_networkidle:
                                try:
                                    page.wait_for_load_state("networkidle", timeout=timeout_ms)
                                except Exception:
                                    pass
                            log(f"导航等待完成: {label} selector={sel} {_safe_page_state()}")
                            return
                        except Exception as e:
                            last_err = e
                    raise last_err if last_err else Exception("click failed")

                def navigate_to_pending_review():
                    nonlocal page
                    max_attempts = 3
                    for attempt in range(1, max_attempts + 1):
                        if self.stop_event.is_set():
                            return False
                        try:
                            try:
                                if page.is_closed():
                                    page = context.new_page()
                                    log("检测到页面已关闭，已重建新页面")
                            except Exception:
                                pass
                            def _goto_with_status(go_url, label):
                                log(f"准备访问{label}: {go_url}")
                                r = page.goto(go_url, timeout=60000, wait_until="domcontentloaded")
                                try:
                                    page.wait_for_load_state("networkidle", timeout=20000)
                                except Exception:
                                    pass
                                s = None
                                try:
                                    s = r.status if r else None
                                except Exception:
                                    s = None
                                log(f"{label}加载完成 status={s} {_safe_page_state()}")
                                return r, s

                            resp, status_code = _goto_with_status(login_url, "登录页")

                            try:
                                title_val = page.title()
                            except Exception:
                                title_val = ""
                            is_405 = (status_code == 405) or ("405" in str(title_val))
                            if is_405:
                                if not headless:
                                    log(f"检测到访问被拦截/风控(405)，请在有头浏览器中手动处理后继续 (等待 {manual_intervention_seconds:.0f}s)")
                                    try:
                                        page.screenshot(path="debug_405.png", full_page=True)
                                    except Exception:
                                        pass
                                    self.stop_event.wait(max(0.0, manual_intervention_seconds))
                                    continue
                                fallback_urls = [
                                    safe_entry_url,
                                    f"{parsed.scheme}://{parsed.netloc}/web/index.php?c=site&a=entry&m=ewei_shopv2&do=web",
                                    f"{parsed.scheme}://{parsed.netloc}/web/",
                                ]
                                for idx, fb_url in enumerate(fallback_urls, start=1):
                                    resp, status_code = _goto_with_status(fb_url, f"入口页#{idx}")
                                    try:
                                        title_val = page.title()
                                    except Exception:
                                        title_val = ""
                                    is_405 = (status_code == 405) or ("405" in str(title_val))
                                    if not is_405:
                                        break
                                if is_405:
                                    raise Exception(f"页面返回405，疑似被风控/反爬拦截 status={status_code} title={title_val}")

                            if page.locator("#form1").count() > 0:
                                perform_login()
                            else:
                                log("未检测到登录表单，可能已处于登录态，跳过登录")
                            log(f"登录流程结束 {_safe_page_state()}")

                            _click_nav("#navheight > li:nth-child(5) > a", "订单菜单")
                            _click_nav("body > div.wb-subnav > div > div:nth-child(4)", "订单列表菜单")
                            _click_nav(
                                [
                                    "body > div.wb-subnav > div > ul:nth-child(5) > li:nth-child(1) > a",
                                    "body > div.wb-subnav > div > ul:nth-child(5) > li.menu_web.active > a",
                                ],
                                "订单列表",
                                timeout_ms=30000,
                            )
                            try:
                                page.wait_for_selector("#table", timeout=60000, state="visible")
                            except Exception:
                                pass
                            log(f"订单列表页面就绪 {_safe_page_state()}")
                            try:
                                if storage_state_path:
                                    context.storage_state(path=storage_state_path)
                                    log(f"已刷新保存登录态: {storage_state_path}")
                            except Exception:
                                pass
                            return True
                        except Exception as e:
                            log(f"导航到待审核页失败 (attempt={attempt}/{max_attempts}): {e}")
                            log(f"失败现场 {_safe_page_state()}")
                            try:
                                page.screenshot(path="debug_last_page.png", full_page=True)
                                log("已保存页面截图: debug_last_page.png")
                            except Exception:
                                pass
                            self.stop_event.wait(5)
                    return False

                if not navigate_to_pending_review():
                    try:
                        browser.close()
                    except Exception:
                        pass
                    return

                log("已进入待审核页面，开始执行自动化流程...")

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
                        wait_seconds = _pick_interval_seconds(scan_interval, scan_interval_min, scan_interval_max)
                        log(f"待审核数量为 0，等待 {wait_seconds:.1f} 秒后重试...")
                        self.stop_event.wait(wait_seconds)
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

                            if merchant_name_clean != target_platform:
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

                            log(f"-> 发现 {target_platform} 订单 (索引: {i})...")
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
                            matched_keyword = None

                            # 规范化 keyword_mapping
                            normalized_mapping = _normalize_keyword_mapping(keyword_mapping)

                            # 将文本内容转为小写用于匹配
                            text_content_lower = text_content.lower()

                            for keyword_entry, merchant_list in normalized_mapping.items():
                                matched, matched_kw = _match_keyword(keyword_entry, text_content_lower)
                                if matched:
                                    matched_keyword = keyword_entry
                                    target_option, round_info = self._get_merchant_by_weight(keyword_entry, merchant_list)
                                    matched_info = f"关键词匹配: {matched_kw} (规则: {keyword_entry}), {round_info}"
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
                            wait_seconds = _pick_interval_seconds(scan_interval, scan_interval_min, scan_interval_max)
                            log(f"本轮结束，等待 {wait_seconds:.1f} 秒...")
                            self.stop_event.wait(wait_seconds)
                        
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
