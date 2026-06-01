import asyncio
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
load_dotenv()  # 手动加载 .env 文件

from services.reporting.report_renderer import ReportRenderer
from services.integrations import create_llm_client

async def main():
    logger.info("开始测试 Tectonic 排版引擎...")
    
    transcript_path = Path("reports/392e64d3-25e_开源与Agent技术演进圆桌讨论_transcript.txt")
    if transcript_path.exists():
        text = transcript_path.read_text(encoding="utf-8")
        # 截取前 2000 个字符进行快速测试，避免大模型生成太慢
        text = text[:2000]
        logger.info("成功加载真实会议纪要文本。")
    else:
        text = "## 动机\n这是一个测试用例。\n## 核心概念\n测试 Tectonic 引擎是否能够成功将中文字符渲染并直出 PDF。"
        logger.info("未找到纪要文本，使用内置测试内容。")

    llm = create_llm_client()
    renderer = ReportRenderer(llm_client=llm)
    
    md_path, pdf_path, html_path, generated = await renderer.render_report(
        meeting_id="test_meeting_001",
        final_report_md=text,
        kf_objects=[],
        title="开源与Agent技术圆桌(排版测试)"
    )
    
    if generated:
        logger.info(f"✅ 测试成功！PDF 已成功生成，存放于: {pdf_path}")
    else:
        logger.error("❌ PDF 生成失败，请查看上方日志。")

if __name__ == "__main__":
    asyncio.run(main())
