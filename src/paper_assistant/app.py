# src\paper_assistant\app.py
from __future__ import annotations
import json
import logging
import os
import re
import textwrap
from typing import List
import uuid
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse
from google import genai
from google.genai import types

BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_ROOT = Path(__file__).resolve().parent / "template_images"
OUTPUT_FOLDER = BASE_DIR / "generated"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
FONT_PATH = BASE_DIR / "fonts" / "NotoSansSC-Regular.ttf"
FONT_NAME = "NotoSansSC"
pdfmetrics.registerFont(
    TTFont(
        FONT_NAME,
        str(FONT_PATH)
    )
)
app = FastAPI(title="Paper Assistant API", redoc_url=None, docs_url="/docs")

CORE_MODULES = [
    "题名",
    "作者署名",
    "作者单位全称",
    "摘要",
    "引言",
    "方法",
    "结果",
    "参考文献",
]

# 配置日志
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("paper_assistant")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.FileHandler(LOG_DIR / "api_calls.log", encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def read_env_api_key() -> str | None:
    # Prefer .env in project root, fallback to environment variable
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for ln in env_path.read_text(encoding="utf-8").splitlines():
            if ln.strip().startswith("GEMINI_API_KEY"):
                parts = ln.split("=", 1)
                if len(parts) == 2:
                    return parts[1].strip().strip('"').strip("'")
    return os.environ.get("GEMINI_API_KEY")


def sanitize_template_name(name: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff\- ]+", "", name).strip()


def load_template(template_name: str) -> str:
    folder_name = sanitize_template_name(template_name)
    template_dir = TEMPLATES_ROOT / folder_name
    if not template_dir.exists() or not template_dir.is_dir():
        raise HTTPException(status_code=400, detail="未找到对应的期刊模板目录。")

    template_file = template_dir / "template.txt"
    if not template_file.exists():
        raise HTTPException(status_code=400, detail="期刊模板文件 template.txt 不存在。")
    return template_file.read_text(encoding="utf-8")


def rewrite_to_academic_style(template_text: str, module_name: str, content: str) -> str:
    """Use Gemini to rewrite a module's content into academic style according to template requirements."""
    api_key = read_env_api_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="未配置 GEMINI_API_KEY（.env 或环境变量）。")
    client = genai.Client(api_key=api_key)
    prompt = (
        "请根据下面的期刊投稿要求（模板），将给定的模块文本转换为学术论文风格、符合格式要求和规范的段落。"
        "明确保留模块为：" + module_name + "。不要输出多余说明，只返回改写后的文本。\n\n"
        + "期刊模板：\n"
        + template_text
        + "\n\n要改写的文本：\n"
        + content
    )
    config = types.GenerateContentConfig(temperature=0.2, max_output_tokens=1024)
    try:
        logger.info(f"[rewrite_to_academic_style] 开始改写模块: {module_name}, 内容长度: {len(content)}")
        resp = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=config,
        )
        result = resp.text or ""
        logger.info(f"[rewrite_to_academic_style] 改写完成, 返回长度: {len(result)}")
        logger.debug(f"[rewrite_to_academic_style] 改写结果摘要: {result[:200]}...")
        return result
    except Exception as exc:
        logger.error(f"[rewrite_to_academic_style] 改写失败: {exc}")
        raise HTTPException(status_code=500, detail=f"Gemini 重写接口调用失败：{exc}") from exc


def build_module_instruction(
    discipline: str,
    module_list: List[str],
) -> str:
    modules = "\n".join([f"- {m}" for m in module_list])

    prompt = f"""
你是一位资深学术论文写作导师，熟悉各类学科论文写作规范。

你的任务：
对于给定的论文模块，为每个模块生成：

1. 模块简要作用说明（50-100字）
2. 写作要点（3~5条）
3. 一个简短范例，仅说明模块结构（50-100字）

要求：

- 专业领域：{discipline}
- 输出语言：中文
- 范例必须符合学术论文风格
- 不得输出模块之外的内容
- 必须返回合法 JSON
- JSON 的 key 必须与输入模块名称完全一致
- value 必须是一个字符串

====================
Few-shot 示例
====================

输入模块：

[
    "摘要",
    "研究背景"
]

输出：

{{
    "摘要": "【模块说明】摘要用于概括研究目的、方法、结果和结论。\n\n【写作要点】\n1. 简明概括研究问题\n2. 说明研究方法\n3. 总结核心发现\n4. 给出主要结论\n\n【范例】\n本文针对小学语文阅读教学中学生参与度不足的问题，采用行动研究法开展教学实验。研究结果表明，基于任务驱动的阅读活动能够显著提升学生课堂参与度和阅读理解能力。研究为小学语文阅读教学改革提供了实践参考。",
    
    "研究背景": "【模块说明】研究背景用于说明研究问题产生的现实环境和学术背景。\n\n【写作要点】\n1. 描述现实问题\n2. 引用已有研究\n3. 指出研究不足\n4. 引出研究意义\n\n【范例】\n随着新课程改革的不断推进，阅读能力培养逐渐成为小学语文教学的重要目标。然而现有研究更多关注阅读策略训练，对课堂参与机制的探讨仍相对不足，因此有必要开展进一步研究。"
}}

====================
待生成模块
====================

{modules}

请直接输出 JSON，不要使用 Markdown，不要添加 ```json。
"""

    return prompt


def generate_with_gemini(prompt: str) -> str:
    api_key = read_env_api_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="未配置 GEMINI_API_KEY（.env 或环境变量）。")
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(temperature=0.2, max_output_tokens=4096, response_mime_type="application/json")
    try:
        logger.info(f"[generate_with_gemini] 调用 Gemini 生成论文内容, 提示词长度: {len(prompt)}")
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=config,
        )
        result = response.text
        logger.info(f"[generate_with_gemini] 论文生成完成, 返回长度: {len(result)}")
        logger.debug(f"[generate_with_gemini] 生成结果摘要: {result[:200]}...")
        return result
    except Exception as exc:
        logger.error(f"[generate_with_gemini] 生成失败: {exc}")
        raise HTTPException(status_code=500, detail=f"Gemini API 调用失败：{exc}") from exc


def create_docx(content: str, path: Path) -> None:
    from docx import Document

    document = Document()
    for paragraph in content.split("\n\n"):
        document.add_paragraph(paragraph)
    document.save(path)

def add_page_number(canvas, doc):

    canvas.setFont(FONT_NAME, 9)

    page_num = canvas.getPageNumber()

    canvas.drawCentredString(
        A4[0] / 2,
        20,
        f"- {page_num} -"
    )
def create_pdf(content: str, path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    )
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=50,
        rightMargin=50,
        topMargin=50,
        bottomMargin=50,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "PaperTitle",
        parent=styles["Heading1"],
        fontName=FONT_NAME,
        fontSize=18,
        leading=24,
        alignment=TA_CENTER,
        spaceAfter=18,
    )

    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName=FONT_NAME,
        fontSize=14,
        leading=20,
        spaceBefore=12,
        spaceAfter=8,
        textColor=colors.black,
    )

    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName=FONT_NAME,
        fontSize=11,
        leading=20,
        alignment=TA_JUSTIFY,
        firstLineIndent=22,
        spaceAfter=6,
    )

    story = []

    sections = re.split(
        r"^##\s+(.+)$",
        content,
        flags=re.MULTILINE,
    )

    if len(sections) <= 1:
        story.append(
            Paragraph(
                content.replace("\n", "<br/>"),
                body_style,
            )
        )
    else:
        paper_title = None

        if len(sections) >= 3:

            first_title = sections[1].strip()

            if first_title == "题名":

                paper_title = sections[2].strip()

                story.append(
                    Paragraph(
                        paper_title,
                        title_style,
                    )
                )

                story.append(
                    Spacer(1, 12)
                )

                start_index = 3

            else:

                start_index = 1
        else:
            start_index = 1
        for i in range(start_index, len(sections), 2):

            section_title = sections[i].strip()
            section_content = sections[i + 1].strip()

            story.append(
                Paragraph(
                    section_title,
                    heading_style,
                )
            )

            paragraphs = [
                p.strip()
                for p in section_content.split("\n")
                if p.strip()
            ]

            for p in paragraphs:
                p = (
                    p.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )

                story.append(
                    Paragraph(
                        p,
                        body_style,
                    )
                )

            story.append(
                Spacer(1, 8)
            )

    doc.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )




def save_generated_files(content: str) -> tuple[str, Path, Path]:
    key = uuid.uuid4().hex
    docx_path = OUTPUT_FOLDER / f"{key}.docx"
    pdf_path = OUTPUT_FOLDER / f"{key}.pdf"
    create_docx(content, docx_path)
    create_pdf(content, pdf_path)
    return key, docx_path, pdf_path


@app.post("/api/convert")
async def convert(
    discipline: str = Form(...),
    journal_level: str | None = Form(None),
    journal_template: str = Form(...),
    title: str | None = Form(None),
    authors: str | None = Form(None),
    affiliation: str | None = Form(None),
    abstract: str | None = Form(None),
    introduction: str | None = Form(None),
    method: str | None = Form(None),
    result: str | None = Form(None),
    references: str | None = Form(None),
):
    template_text = load_template(journal_template)
    module_order = CORE_MODULES
    prompt = build_module_instruction(
        discipline,
        module_order,
    )
    generated_text = generate_with_gemini(prompt)
    try:
        sections = json.loads(generated_text)

        if not isinstance(sections, dict):
            raise ValueError("Gemini返回结果不是dict")

    except Exception as exc:
        logger.error(f"解析Gemini JSON失败: {exc}")

        sections = {
            name: generated_text
            for name in module_order
        }
    formatted_text = "\n\n".join(
        [
            f"## {name}\n{content}"
            for name, content in sections.items()
        ]
    )
    download_id, _, _ = save_generated_files(formatted_text)
    return {
        "generated_text": formatted_text,
        "sections": sections,
        "section_order": module_order,
        "download_id": download_id,
    }

@app.post("/api/add_module")
async def add_module(
    discipline: str = Form(...),
    module_name: str = Form(...),
):
    prompt = build_module_instruction(
        discipline,
        [module_name],
    )

    generated_text = generate_with_gemini(prompt)

    try:
        sections = json.loads(generated_text)

        if not isinstance(sections, dict):
            raise ValueError("返回结果不是dict")

        content = sections.get(module_name, "")

    except Exception as exc:
        logger.error(f"新增模块解析失败: {exc}")
        content = generated_text

    return {
        "module_name": module_name,
        "content": content,
    }

@app.post("/api/rewrite")
async def rewrite_module(
    journal_template: str = Form(...),
    module_name: str = Form(...),
    content: str = Form(...),
):
    template_text = load_template(journal_template)
    rewritten = rewrite_to_academic_style(template_text, module_name, content)
    return {"rewritten": rewritten}


@app.get("/download/{download_id}/{file_type}")
async def download_file(download_id: str, file_type: str):
    if file_type not in {"docx", "pdf"}:
        raise HTTPException(status_code=404, detail="未知的下载类型。")
    file_path = OUTPUT_FOLDER / f"{download_id}.{file_type}"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="下载文件不存在。")
    media_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if file_type == "docx"
        else "application/pdf"
    )
    return FileResponse(file_path, media_type=media_type, filename=f"paper_assistant_output.{file_type}")


@app.get("/")
async def root():
    index_path = BASE_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="未找到首页 index.html。")
    return FileResponse(index_path)
