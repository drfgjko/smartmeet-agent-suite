# -*- coding: utf-8 -*-
"""
飞书独立连通性测试脚本 (Standalone Feishu Integration Test)

本脚本用于在不启动全套 Agent 和 LLM 模型的情况下，直接测试：
1. 自动查询该自建机器人所在的群聊名称及 chat_id
2. Webhook 卡片推送
3. 企业自建应用卡片推送
4. 企业自建应用文件/脑图上传及发送
5. 企业自建应用任务(待办)创建

使用方法：
确保 .env 中已配置 FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_WEBHOOK_URL
然后运行：
conda run -n smartmeet python tests/test_feishu_direct.py
"""

import os
import sys
import asyncio
from pathlib import Path

# 将项目根目录加入到环境变量，以便找到 services 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 解决 Windows cmd 控制台打印中文乱码问题
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
import httpx

# 加载环境变量
load_dotenv()

from services.integrations.feishu_client import FeishuClient


async def get_chats(client: FeishuClient):
    """自动查询并打印机器人所在的群聊"""
    print("\n--- [1] 正在自动查询机器人加入的群聊列表 ---")
    token = await client._get_tenant_token()
    if not token:
        print("❌ 未获取到 Token，请检查 .env 中的 FEISHU_APP_ID 和 FEISHU_APP_SECRET 是否正确。")
        return []
    
    async with httpx.AsyncClient() as http_client:
        resp = await http_client.get(
            "https://open.feishu.cn/open-apis/im/v1/chats",
            headers={"Authorization": f"Bearer {token}"},
            params={"page_size": 20}
        )
        data = resp.json()
        if data.get("code") == 0:
            items = data.get("data", {}).get("items", [])
            if not items:
                print("⚠️ 机器人目前没有加入任何群聊。")
            else:
                print("✅ 找到机器人所在的群聊：")
                for item in items:
                    print(f"   - 群名称: {item.get('name')} | Chat ID: {item.get('chat_id')}")
            return items
        else:
            print(f"❌ 获取群列表失败: {data}")
            return []


async def test_feishu():
    print("开始执行飞书连通性测试...\n")
    
    app_id = os.getenv("FEISHU_APP_ID")
    receive_id = os.getenv("FEISHU_RECEIVE_ID")
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL")
    
    print(f"当前配置状态:")
    print(f" - APP ID: {'[已配置]' if app_id else '[未配置]'}")
    print(f" - RECEIVE ID: {receive_id if receive_id else '[未配置]'}")
    print(f" - WEBHOOK: {'[已配置]' if webhook_url else '[未配置]'}\n")

    client = FeishuClient()
    
    # 1. 扫描群聊
    if app_id:
        await get_chats(client)
    else:
        print("--- [1] 未配置 APP ID，跳过群聊查询 ---")

    # 2. 推送 Webhook
    print("\n--- [2] 测试发送 Webhook 卡片 ---")
    if webhook_url:
        res = await client.send_meeting_summary(
            title="[测试] Webhook连通性测试",
            summary_md="这是一条来自 `test_feishu_direct.py` 的测试摘要内容。",
            action_items_md="- [ ] 测试待办 1\n- [ ] 测试待办 2",
            insights_md="一切正常！",
        )
        print(f"Webhook 推送结果: {'✅ 成功' if res else '❌ 失败'}")
    else:
        print("⚠️ 未配置 Webhook URL，跳过。")

    # 3. 推送文件附件
    print("\n--- [3] 测试上传和发送文件附件 (需 App ID & Receive ID) ---")
    if app_id and receive_id:
        # 找一个真实存在的 PDF 测试文件
        demo_dir = Path(__file__).parent.parent / "demos" / "01557ab5-2ac"
        pdf_file = demo_dir / "01557ab5-2ac_创业产品立项讨论会.pdf"
        
        if pdf_file.exists():
            print(f"正在上传 PDF: {pdf_file.name}...")
            file_key = await client.upload_file(pdf_file, file_type="pdf")
            if file_key:
                print(f"✅ 上传成功，File Key: {file_key}")
                print(f"正在发送到接收方 {receive_id}...")
                sent = await client.send_file(receive_id=receive_id, file_key=file_key)
                print(f"文件发送结果: {'✅ 成功' if sent else '❌ 失败'}")
            else:
                print("❌ 上传文件失败。")
        else:
            print(f"⚠️ 测试用 PDF 文件未找到: {pdf_file}")
    else:
        print("⚠️ 缺少 APP ID 或 RECEIVE ID，跳过文件上传测试。")

    # 4. 创建任务
    print("\n--- [4] 测试创建飞书任务 (需 App ID) ---")
    if app_id:
        res = await client.create_task(
            summary="[测试] 验证待办事项同步",
            description="如果看到这个任务，说明飞书 Task 接口连通正常！",
        )
        if res.get("task_id"):
            print(f"✅ 任务创建成功！Task ID: {res['task_id']}")
        else:
            print(f"❌ 任务创建失败: {res.get('error')}")
    else:
        print("⚠️ 未配置 APP ID，跳过任务创建测试。")

    await client.close()
    print("\n测试完成！")


if __name__ == "__main__":
    asyncio.run(test_feishu())
