import time
import requests
import uiautomation as auto
import pyperclip
from playwright.sync_api import sync_playwright

# --- 配置区域 ---
# 目标网址
URL = "https://szguokuai.zlj.xyzulin.top/web/index.php?c=site&a=entry&m=ewei_shopv2&do=web&r=order.list.status1"
# 内部 Webhook 通知配置 (支持多 Webhook)
# 格式: {"url": "webhook地址", "targets": ["分配对象1", "分配对象2"]}
# 如果 targets 为 ["*"] 或空列表，则匹配所有分配对象
WEBHOOK_CONFIGS = [
    {
        # 默认通知群 (所有对象)
        "url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=d954ddc2-fe59-47ae-b0ae-44621040f33d",
        "targets": ["*"] 
    },
        {
        # 另一个企微审核群 (只推送支付宝米奇)
        "url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=69e5af6a-1d92-4b73-8bf9-157c22480833",
        "targets": ["米奇租赁官方"] 
    },
    # 示例: 仅通知星享生活
    # {
    #     "url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_OTHER_KEY",
    #     "targets": ["星享生活"]
    # }
]

# RPA通知配置: 针对特定分配对象的群名映射
# 格式: "分配对象名称": "企业微信群名"
RPA_GROUP_MAPPING = {
    "星享生活": "星享生活米奇支付宝入驻",
    # "米奇租赁官方": "", # 留空则不发送通知
}

# 登录账号配置 (如果为空则需手动登录)
USERNAME = "伟填" 
PASSWORD = "Test0528."

# 关键词与下拉选项的映射
# 格式: "关键词": "下拉菜单选项名称"
# 请根据实际情况修改此处，商家对应分配的商品关键词
KEYWORD_MAPPING = {
    # 星享生活
    "G7X3": "星享生活",
    "G7X2": "星享生活",
    "RF100-400mm": "星享生活",
    "佳能RF-S 55-210": "星享生活",
    "佳能RF-S 18-150": "星享生活",
    "佳能 RF50m": "星享生活",
    "佳能 R50": "星享生活",
    "松下": "星享生活",
    "尼康": "星享生活",

    # 米奇租赁官方
    "佳能ixus130": "米奇租赁官方",
    "SQ1": "米奇租赁官方",
    "mini12": "米奇租赁官方",
    "mini11": "米奇租赁官方",
    "mini99": "米奇租赁官方",
    "mini90": "米奇租赁官方",
    "mini40": "米奇租赁官方",
    "action5": "米奇租赁官方",
    "action4": "米奇租赁官方",
    "Galaxy S23Ultra": "米奇租赁官方",
    "X300": "米奇租赁官方",
    "X200": "米奇租赁官方",
    "SX740": "米奇租赁官方",
    "wide": "米奇租赁官方",
    "Ulike": "米奇租赁官方"
}
# ----------------

def send_notification(order_title, assigned_to):
    """
    根据分配对象决定通知方式
    :param order_title: 订单标题
    :param assigned_to: 分配给谁
    """
    # 商家后台链接 (用于通知)
    merchant_url = "https://szguokuai.zlj.xyzulin.top/web/merchant.php?c=site&a=entry&m=ewei_shopv2&do=web&r=order.list.status1"

    # --- 1. Webhook 通知 (内部群 - 支持多配置) ---
    if WEBHOOK_CONFIGS:
        for config in WEBHOOK_CONFIGS:
            webhook_url = config.get("url")
            targets = config.get("targets", [])
            
            # 检查是否匹配当前分配对象
            # 如果 targets 包含 "*" 或为空列表，或者是当前分配对象，则发送
            if not webhook_url:
                continue
                
            if "*" in targets or not targets or assigned_to in targets:
                try:
                    # 构造通知内容
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
                    print(f"-> Webhook 通知已发送至 [{webhook_url[-6:]}...]，状态码: {resp.status_code}")
                except Exception as e:
                    print(f"-> Webhook 发送失败: {e}")

    # --- 2. RPA 通知 (外部群 - 目前暂时禁用) ---
    target_group = RPA_GROUP_MAPPING.get(assigned_to)
    
    if target_group:
        # print(f"-> 分配给 [{assigned_to}]，触发 RPA 通知到群: [{target_group}]")
        # 暂时注释掉 RPA 通知
        # send_rpa_notification(order_title, assigned_to, target_group)
        print(f"-> [调试] RPA 通知已暂时禁用 (目标群: {target_group})")
    else:
        # print(f"-> 分配给 [{assigned_to}]，无需 RPA 通知")
        pass

def send_rpa_notification(order_title, assigned_to, group_name):
    """
    执行 RPA 发送逻辑
    """
    try:
        # 商家后台链接
        merchant_url = "https://szguokuai.zlj.xyzulin.top/web/merchant.php?c=site&a=entry&m=ewei_shopv2&do=web&r=order.list.status1"

        # 拟人化话术
        if assigned_to == "星享生活":
            content = f"老板，有新订单需要处理哈~ 辛苦处理下：\n{order_title}\n\n处理链接：{merchant_url}"
        else:
            # 默认话术
            content = f"您好，有新订单分配给您，请及时处理：\n{order_title}\n\n处理链接：{merchant_url}"
            
        # 1. 查找企业微信窗口
        wechat_window = auto.WindowControl(searchDepth=1, Name="企业微信")
        if not wechat_window.Exists(0):
            wechat_window = auto.WindowControl(searchDepth=1, ClassName="WeWorkWindow")
            
        if not wechat_window.Exists(0):
            print("-> [错误] 未找到企业微信窗口，RPA通知发送失败！")
            return
            
        # 2. 激活窗口并置顶
        wechat_window.SetActive()
        wechat_window.SetTopmost(True)
        time.sleep(0.5)
        
        # 3. 搜索群聊
        wechat_window.SendKeys('{Ctrl}f')
        time.sleep(0.5)
        
        pyperclip.copy(group_name)
        wechat_window.SendKeys('{Ctrl}v')
        time.sleep(1.5) # 等待搜索结果
        wechat_window.SendKeys('{Enter}') # 选中
        time.sleep(0.5)
        
        # 4. 发送消息
        pyperclip.copy(content)
        wechat_window.SendKeys('{Ctrl}v')
        time.sleep(0.5)
        wechat_window.SendKeys('{Enter}') # 发送
        
        # 5. 恢复窗口状态
        wechat_window.SetTopmost(False)
        wechat_window.Minimize()
        
        print(f"-> RPA 通知已发送")
        
    except Exception as e:
        print(f"-> RPA 发送通知时出错: {e}")

def run():
    with sync_playwright() as p:
        # 启动浏览器，headless=False 表示显示浏览器窗口，方便手动登录
        print("正在启动浏览器...")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print(f"正在访问: {URL}")
        page.goto(URL)

        # 尝试自动登录
        if USERNAME and PASSWORD:
            # 登录框 Selector
            user_selector = "#form1 > div > div:nth-child(3) > input"
            pass_selector = "#form1 > div > div:nth-child(4) > input"
            
            try:
                # 检查是否在登录页（检查用户名输入框是否存在）
                # 等待一小会儿，如果是跳转到登录页的话
                try:
                    page.wait_for_selector(user_selector, timeout=5000)
                    print("检测到登录页面，开始自动登录...")
                    
                    # 输入账号
                    page.fill(user_selector, USERNAME)
                    # 输入密码
                    page.fill(pass_selector, PASSWORD)
                    
                    # 提交登录 (在密码框按回车，通常能提交表单)
                    print("提交登录信息...")
                    page.press(pass_selector, "Enter")
                    
                    # 等待跳转
                    page.wait_for_load_state("networkidle")
                    
                    # 登录后再次访问目标网址，防止停留在默认首页
                    print("登录操作完成，正在跳转到目标页面...")
                    page.goto(URL)
                    page.wait_for_load_state("networkidle")

                except:
                    print("未检测到登录输入框，跳过自动登录（可能已登录或选择器不匹配）...")
            except Exception as e:
                print(f"自动登录尝试失败: {e}")

        # 等待登录
        print("请在浏览器中完成登录（如果需要）...")
        print("注意：如果手动登录，登录后请确保跳转到订单列表页面...")
        print("脚本将在检测到目标页面元素（列表按钮）后继续执行，最长等待 120 秒...")
        
        try:
            # 等待登录完成，以看到 tab 为准
            # 用户更新：改为检测列表中的按钮是否显示
            page.wait_for_selector("#table > div > div > div > div:nth-child(2) > div > button", timeout=120000)
        except Exception as e:
            print("等待超时或出错，请检查是否已登录。")
            return

        print("检测到目标页面，开始执行自动化流程...")

        while True:
            # 循环开始前，先获取待处理数量
            # Selector: #pagination > div > ul > li > span
            count_selector = "#pagination > div > ul > li > span"
            try:
                # 尝试获取数量
                if page.locator(count_selector).is_visible():
                    count_text = page.locator(count_selector).inner_text().strip()
                    print(f"当前待处理数量: {count_text}")
                    if count_text == "0":
                        print("待处理数量为 0，等待 1 分钟后重试...")
                        time.sleep(60) # 等待 1 分钟
                        # 刷新页面以获取最新数据
                        print("正在刷新页面...")
                        page.reload()
                        page.wait_for_load_state("networkidle")
                        # 刷新后重新进入循环检查
                        continue
                else:
                     print("未找到数量统计元素，假设有数据继续执行...")
            except Exception as e:
                print(f"获取待处理数量失败: {e}，继续尝试执行...")

            # 1. 点击 Tab
            # Selector: #myTab > li:nth-child(3) > a
            # 优化：检查是否已经激活，避免重复点击；只点击可见元素
            try:
                tab_li_selector = "#myTab > li:nth-child(3)"
                tab_link_selector = f"{tab_li_selector} > a"
                
                is_active = False
                try:
                    # 获取可见的 Tab 链接
                    # 页面上可能有多个匹配元素（如响应式布局），只关注可见的
                    target_link = page.locator(tab_link_selector).filter(has=page.locator("visible=true")).first
                    
                    if target_link.count() > 0 and target_link.is_visible():
                        # 检查 a 标签的 class
                        a_class = target_link.get_attribute("class")
                        # 检查 li 标签的 class
                        li_class = page.get_attribute(tab_li_selector, "class")
                        
                        # 只要有一个包含 active，就认为是激活状态
                        # 注意：日志显示 class 可能是 "activesa activesdef"，包含 "active" 子串
                        if (li_class and "active" in li_class) or (a_class and "active" in a_class):
                            is_active = True
                    else:
                        print("未找到可见的 Tab 链接，可能选择器不匹配。")
                except Exception as e:
                    print(f"检查 Tab 状态时出错: {e}")
                    pass

                if not is_active:
                    print("点击 '待审' Tab...")
                    # 强制点击可见的那个
                    page.locator(tab_link_selector).filter(has=page.locator("visible=true")).first.click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(2)
                else:
                    print("当前已在 '待审' Tab，无需点击。")
            except Exception as e:
                print(f"点击 Tab 操作异常: {e}")
                # 如果点击失败，不要退出，尝试直接处理列表（也许已经在这个页面了）
    
    
            # --- 遍历列表寻找符合条件的订单 ---
            # 列表容器: #table > div > div > div
            # 列表项: > div (从第4个开始是订单，前3个可能是表头或其他)
            
            container_selector = "#table > div > div > div"
            items_locator = page.locator(f"{container_selector} > div")
            items_count = items_locator.count()
            
            print(f"当前页面列表项总数: {items_count}")
            
            processed_order = False
            
            # 从第4个子元素开始遍历 (Playwright 索引从 0 开始，nth-child 从 1 开始)
            # nth-child(4) 对应索引 3
            start_index = 3 
            
            for i in range(start_index, items_count):
                # 构建当前项的选择器
                # nth-child 是 1-based，所以是 i + 1
                current_item_selector = f"{container_selector} > div:nth-child({i + 1})"
                
                # 检查商户名称
                # Selector: ... > div.table-row.table-top > div > span:nth-child(3)
                merchant_selector = f"{current_item_selector} > div.table-row.table-top > div > span:nth-child(3)"
                
                try:
                    if not page.locator(merchant_selector).is_visible():
                        # 可能是分隔线或者非订单行，跳过
                        continue
                        
                    merchant_name = page.locator(merchant_selector).inner_text().strip()
                    # 清理 "商户名称：" 前缀
                    merchant_name_clean = merchant_name.replace("商户名称：", "").replace("商户名称:", "").strip()
                    print(f"检查第 {i - 2} 个订单，商户名称: [{merchant_name}] -> 清理后: [{merchant_name_clean}]")
                    
                    if merchant_name_clean != "米奇租赁":
                        print(f"-> 商户[{merchant_name_clean}]不是'米奇租赁'，不需要分配，跳过。")
                        continue
                    
                    print("-> 商户匹配，开始处理此订单...")
                    item_selector = current_item_selector
                    
                    # 3. 分析它的文本
                    # Selector: ... > div:nth-child(2) > div.goods-des > a > div > div > span.text-primary
                    text_selector = f"{item_selector} > div:nth-child(2) > div.goods-des > a > div > div > span.text-primary"
                    
                    try:
                        print("正在获取文本内容...")
                        text_element = page.locator(text_selector)
                        text_content = text_element.inner_text()
                        print(f"获取到的文本内容: {text_content}")
                    except Exception as e:
                        print(f"获取文本失败: {e}")
                        # 如果获取文本失败，可能结构不一样，跳过这个
                        continue
            
                    # 4. 检查是否包含指定关键词
                    # 默认分配给 "米奇租赁官方"
                    target_option = "米奇租赁官方"
                    matched_info = "默认规则 (无匹配关键词)"
                    
                    for keyword, option in KEYWORD_MAPPING.items():
                        if keyword in text_content:
                            target_option = option
                            matched_info = f"关键词匹配: {keyword}"
                            break
                    
                    print(f"匹配结果: [{matched_info}] -> 分配给: [{target_option}]")
                    
                    # 5. 点击操作按钮
                    # 策略升级：由于不同订单的“分配”按钮可能在第7列或第8列，使用 CSS 选择器定位列数不可靠。
                    # 最稳健的方式是：在当前订单行（item_selector）内部，查找包含“分配”文字的按钮/链接。
            
                    try:
                        print("点击操作按钮...")
                        # 在当前行内查找文本包含 "分配" 的 <a> 标签
                        # 这样无论它在第几列，只要文字没变都能找到
                        assign_btn = page.locator(item_selector).locator("a:has-text('分配')")
                        
                        if assign_btn.count() > 0:
                            # 如果有多个（比如“分配”和“取消分配”），默认点第一个，通常是“分配订单”
                            # 或者可以更精确匹配 "分配订单"
                            assign_btn.first.click()
                        else:
                            # 如果找不到 "分配"，尝试找 "订单" 相关的按钮作为兜底，或者打印错误
                            print("未找到'分配'按钮，尝试查找通用操作按钮...")
                            # 此时可能需要回退到位置点击，或者跳过
                            # 这里尝试打印当前行的 html 方便调试（如果需要）
                            print("当前行未检测到分配按钮，跳过此订单。")
                            continue
                        
                        time.sleep(1) # 等待弹窗或界面变化
                    except Exception as e:
                        print(f"点击操作按钮失败: {e}")
                        # 点击失败可能这个订单有问题，跳过
                        continue
        
                    # 6. 点击下拉组件
                    # Selector: #select2-chosen-2
                    dropdown_selector = "#select2-chosen-2"
                    
                    try:
                        print("点击下拉组件...")
                        page.click(dropdown_selector)
                        time.sleep(0.5)
                    except Exception as e:
                        print(f"点击下拉组件失败: {e}")
                        # 弹窗可能没出来或者选择器变了
                        # 尝试关闭弹窗（如果有）并继续下一个？
                        # 这里简单处理：刷新页面重试
                        processed_order = True # 标记为处理过（虽然失败），触发刷新
                        break # 点击下拉失败，跳出循环刷新
        
                    # 7. 选择对应关键词对应的下拉选项
                    try:
                        print(f"选择下拉选项: {target_option}")
                        # 策略 A: 键盘输入 + 回车
                        page.keyboard.type(target_option)
                        time.sleep(0.5)
                        page.keyboard.press("Enter")
                        time.sleep(0.5)
        
                        # 策略 B: 点击
                        opt_v4 = page.locator(f"li.select2-results__option:has-text('{target_option}')")
                        opt_v3 = page.locator(f"div.select2-result-label:has-text('{target_option}')")
                        
                        if opt_v4.is_visible():
                            opt_v4.last.click()
                        elif opt_v3.is_visible():
                            opt_v3.last.click()
                        
                        time.sleep(0.5)
                    except Exception as e:
                        print(f"选择下拉选项失败: {e}")
                        processed_order = True
                        break # 下拉选择失败，可能是弹窗问题，跳出循环刷新
        
                    # 8. 点击确认按钮
                    confirm_btn_selector = "#ajaxModal > form > div > div > div.modal-footer > button.btn.btn-primary"
                    
                    try:
                        print("准备点击确认按钮...")
                        # 显式等待按钮出现，防止弹窗还没加载出来
                        # 尝试等待 2 秒
                        try:
                            page.wait_for_selector(confirm_btn_selector, state="visible", timeout=3000)
                            print("找到确认按钮，点击中...")
                            page.click(confirm_btn_selector)
                        except:
                            print("标准确认按钮未出现或超时，尝试使用文字定位...")
                            # 尝试找包含 "提交" 或 "确定" 的按钮
                            # 缩小范围到 modal footer
                            modal_footer = page.locator("#ajaxModal .modal-footer")
                            if modal_footer.count() > 0:
                                modal_footer.locator("button").first.click()
                            else:
                                # 全局找
                                page.locator("button:has-text('提交')").click()
                        
                        print("订单提交动作已执行！")
                        
                        # 发送通知
                        send_notification(text_content, target_option)

                        # 等待一下看弹窗是否关闭，确认提交成功
                        time.sleep(2)
                        
                        processed_order = True
                        # break # 修改策略：不跳出循环，继续处理下一个
                        print("继续检查下一个订单...")
                        time.sleep(1) # 稍作等待，防止操作太快
                        
                    except Exception as e:
                        print(f"点击确认按钮失败: {e}")
                        processed_order = True # 即使失败也刷新一下，防止死循环在同一个状态
                        break # 出错了就先跳出吧，稳妥起见

                except Exception as e:
                    print(f"遍历检查订单时出错: {e}")
                    continue

            if processed_order:
                print("本轮循环已处理过订单，等待 3 秒后刷新页面...")
                time.sleep(3)
                page.reload()
                page.wait_for_load_state("networkidle")
            else:
                print("当前列表中没有符合条件（商户为'米奇租赁'）的订单。")
                print("等待 3 分钟后重试...")
                time.sleep(180)
                page.reload()
                page.wait_for_load_state("networkidle")

        # 保持浏览器开启一段时间以便查看结果 (这句在死循环后实际上达不到)

        # 保持浏览器开启一段时间以便查看结果 (这句在死循环后实际上达不到)
        # print("脚本执行完毕，浏览器将在 10 秒后关闭...")
        # time.sleep(10)
        # browser.close()


if __name__ == "__main__":
    run()
