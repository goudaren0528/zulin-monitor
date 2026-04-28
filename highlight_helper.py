﻿# highlight_helper.py
# Playwright 运行时元素高亮辅助模块
# 功能：在脚本正常执行的同时，高亮显示当前操作的元素

HIGHLIGHT_ENABLED = True

HIGHLIGHT_CSS = """
#playwright-highlight-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 2147483647;
}

.playwright-highlight-box {
    position: absolute;
    border: 3px solid #ff0000;
    border-radius: 4px;
    box-shadow: 0 0 10px rgba(255, 0, 0, 0.5);
    animation: highlight-pulse 0.5s ease-in-out;
}

.playwright-highlight-label {
    position: absolute;
    top: -28px;
    left: 0;
    background: #ff0000;
    color: white;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: bold;
    white-space: nowrap;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.playwright-highlight-dot {
    position: absolute;
    width: 12px;
    height: 12px;
    background: #ff0000;
    border-radius: 50%;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    animation: dot-pulse 1.5s ease-in-out infinite;
}

@keyframes highlight-pulse {
    0% { opacity: 0; transform: scale(0.95); }
    50% { opacity: 1; transform: scale(1.02); }
    100% { opacity: 1; transform: scale(1); }
}

@keyframes dot-pulse {
    0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.8; }
    50% { transform: translate(-50%, -50%) scale(1.5); opacity: 0.3; }
}
"""

HIGHLIGHT_JS = """
(function() {
    if (!window.__playwrightHighlight) {
        window.__playwrightHighlight = {
            overlay: null,
            timer: null,
            
            initOverlay: function() {
                if (!this.overlay) {
                    this.overlay = document.createElement('div');
                    this.overlay.id = 'playwright-highlight-overlay';
                    document.body.appendChild(this.overlay);
                }
                return this.overlay;
            },
            
            highlight: function(element, actionType, duration) {
                if (!element) return;
                
                duration = duration || 1500;
                actionType = actionType || 'action';
                
                var overlay = this.initOverlay();
                
                if (this.timer) {
                    clearTimeout(this.timer);
                    overlay.innerHTML = '';
                }
                
                var rect = element.getBoundingClientRect();
                
                var box = document.createElement('div');
                box.className = 'playwright-highlight-box';
                box.style.left = rect.left + 'px';
                box.style.top = rect.top + 'px';
                box.style.width = rect.width + 'px';
                box.style.height = rect.height + 'px';
                
                var label = document.createElement('div');
                label.className = 'playwright-highlight-label';
                label.textContent = actionType;
                box.appendChild(label);
                
                var dot = document.createElement('div');
                dot.className = 'playwright-highlight-dot';
                box.appendChild(dot);
                
                overlay.appendChild(box);
                
                var self = this;
                this.timer = setTimeout(function() {
                    overlay.innerHTML = '';
                }, duration);
            }
        };
    }
})();
"""

def init_highlight(page):
    """初始化高亮功能，在页面加载后调用一次"""
    if not HIGHLIGHT_ENABLED:
        return
    try:
        page.evaluate(HIGHLIGHT_JS)
        page.evaluate("""
            (function() {
                var style = document.createElement('style');
                style.textContent = `""" + HIGHLIGHT_CSS + """`;
                if (!document.getElementById('playwright-highlight-style')) {
                    style.id = 'playwright-highlight-style';
                    document.head.appendChild(style);
                }
            })();
        """)
    except Exception:
        pass

def highlight_by_selector(page, selector, action_type="click", duration=1500):
    """通过 CSS 选择器高亮元素"""
    if not HIGHLIGHT_ENABLED:
        return
    try:
        page.evaluate(HIGHLIGHT_JS)
        js_code = f"""
            (function() {{
                var elements = document.querySelectorAll('{selector}');
                if (elements.length > 0) {{
                    window.__playwrightHighlight.highlight(elements[0], '{action_type}', {duration});
                }}
            }})();
        """
        page.evaluate(js_code)
    except Exception:
        pass

def highlight_locator(page, locator, action_type="click", duration=1500):
    """通过 Playwright locator 高亮元素"""
    if not HIGHLIGHT_ENABLED:
        return
    try:
        page.evaluate(HIGHLIGHT_JS)
        element = locator.first if hasattr(locator, 'first') else locator
        page.evaluate("""
            (function(el, action, duration) {
                if (el && el.length > 0) {
                    window.__playwrightHighlight.highlight(el[0], action, duration);
                }
            })(arguments[0], arguments[1], arguments[2]);
        """, element, action_type, duration)
    except Exception:
        pass
