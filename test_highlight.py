# test_highlight.py - 测试高亮功能
from playwright.sync_api import sync_playwright
from highlight_helper import init_highlight, highlight_by_selector, highlight_locator, HIGHLIGHT_ENABLED
import time

print(f"HIGHLIGHT_ENABLED = {HIGHLIGHT_ENABLED}")
print("开始测试高亮功能...")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    print("打开测试页面...")
    page.goto("https://example.com")
    
    print("初始化高亮功能...")
    init_highlight(page)
    
    print("测试高亮 h1 元素...")
    highlight_by_selector(page, "h1", "click")
    time.sleep(2)
    
    print("测试高亮 a 链接元素...")
    highlight_by_selector(page, "a", "focus: input")
    time.sleep(2)
    
    print("测试完成！")
    browser.close()

print("测试成功！")
