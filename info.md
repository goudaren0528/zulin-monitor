# 企业微信外部群自动通知方案 (RPA)

## 背景
当前企业微信 Webhook 仅支持向企业内部群发送消息，无法直接通知包含非企业成员的**外部群**（如客户群、跨企业协作群）。

## 推荐方案：PC 客户端 UI 自动化 (RPA)

利用 Python 脚本直接模拟人工操作，控制电脑上已登录的 **PC 版企业微信客户端** 发送消息。

### 核心原理
1.  脚本在后台运行，当需要发送通知时触发。
2.  自动查找并激活“企业微信”窗口。
3.  模拟快捷键 (Ctrl+F) 搜索指定的 **“群名称”**。
4.  模拟键盘粘贴通知内容并回车发送。
5.  发送完成后可自动最小化窗口，减少干扰。

### 优缺点分析
*   **优点**：
    *   ✅ **支持所有类型的群**：包括外部群、客户群、甚至个人微信群（如果在企业微信中关联了）。
    *   ✅ **零成本**：无需企业微信管理员权限，无需申请和维护 API Token。
    *   ✅ **安全可靠**：完全模拟真实用户操作，不涉及协议破解，无封号风险。
*   **缺点**：
    *   **占用焦点**：发送消息的那 1-2 秒内，企业微信窗口会弹窗并占用鼠标/键盘焦点（建议在专用挂机电脑运行）。
    *   **依赖客户端**：运行脚本的电脑必须保持 PC 版企业微信登录状态。

### 实施步骤 (下次处理)

1.  **安装依赖库**：
    需要安装 Windows UI 自动化库和剪贴板管理库。
    ```bash
    pip install uiautomation pyperclip
    ```

2.  **代码实现逻辑** (Python 示例)：
    ```python
    import uiautomation as auto
    import pyperclip
    import time

    def send_wechat_msg(group_name, msg_content):
        # 查找企业微信窗口
        wechat_window = auto.WindowControl(searchDepth=1, Name="企业微信")
        if not wechat_window.Exists(0):
            print("未找到企业微信窗口，请确保已登录")
            return
        
        # 激活窗口并置顶
        wechat_window.SetActive()
        wechat_window.SetTopmost(True)
        
        # 搜索群聊
        wechat_window.SendKeys('{Ctrl}f')
        time.sleep(0.5)
        pyperclip.copy(group_name)
        wechat_window.SendKeys('{Ctrl}v')
        time.sleep(1)
        wechat_window.SendKeys('{Enter}') # 进入群聊
        
        # 发送消息
        pyperclip.copy(msg_content)
        wechat_window.SendKeys('{Ctrl}v')
        time.sleep(0.5)
        wechat_window.SendKeys('{Enter}') # 发送
        
        # 恢复窗口状态 (可选取消置顶或最小化)
        wechat_window.SetTopmost(False)
        print(f"消息已发送至: {group_name}")
    ```

3.  **配置**：
    只需要在 `main.py` 中配置准确的 **群名称** 即可。
