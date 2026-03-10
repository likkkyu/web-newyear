import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_env_file() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.providers.llm import (
    _infer_style_from_avatar,
    get_llm_provider,
)
from backend.providers.storage import LocalStorageProvider, get_storage_provider
from backend.providers.t2i import get_t2i_provider
from backend.providers.vision import _parse_five_items, get_vision_provider


# --------------------------- 应用与基础配置 ---------------------------

app = FastAPI(title="New Year Card Generator API")

# CORS：允许前端站点访问，默认 *，可通过环境变量 CORS_ALLOW_ORIGINS 调整
_cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]
if not origins:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

# 静态文件挂载，用于访问上传图片和 mock 贺卡图片
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Provider 单例
llm_provider = get_llm_provider()
vision_provider = get_vision_provider()
storage_provider = get_storage_provider()
t2i_provider = get_t2i_provider()


# --------------------------- Demo 用内存数据库（保留示例接口） ---------------------------

conn = sqlite3.connect(":memory:", check_same_thread=False)

# create simple user table
cursor = conn.cursor()
cursor.execute(
    """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        name TEXT,
        email TEXT
    )
"""
)
conn.commit()


# --------------------------- Pydantic 数据模型 ---------------------------


class ParseRelationRequest(BaseModel):
    primary_relation: Optional[str] = None
    secondary_relation: Optional[str] = None
    custom_relation_text: Optional[str] = None
    user_text: Optional[str] = None


class AnalyzeImageRequest(BaseModel):
    image_url: str


class GenerateBlessingRequest(BaseModel):
    relation: Dict[str, Any]
    personality_profile: Optional[str] = None
    personality_tags: Optional[List[str]] = None


class RegenerateBlessingsRequest(BaseModel):
    relation: Dict[str, Any]
    personality_profile: Optional[str] = None
    personality_tags: Optional[List[str]] = None


class GeneratePromptRequest(BaseModel):
    relation: Dict[str, Any]
    personality_profile: Optional[str] = None
    blessing_text: str
    image_description: Optional[str] = None
    style_key: Optional[str] = "auto"


class GenerateCardRequest(BaseModel):
    prompt: Optional[str] = None
    style_key: Optional[str] = "auto"
    # 两阶段流程：用选中的祝福语 + 上下文生成贺卡
    selected_blessing_text: Optional[str] = None
    relation: Optional[Dict[str, Any]] = None
    personality_profile: Optional[str] = None
    image_description: Optional[str] = None
    extraction: Optional[Dict[str, Any]] = None
    blessing_size: Optional[str] = None  # 小/中/大，可选


# --------------------------- 辅助函数 ---------------------------


async def _save_upload_to_storage(file: UploadFile, category: str) -> str:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="上传文件为空")
    filename = file.filename or "image"
    try:
        return storage_provider.save_bytes(data=data, filename=filename, category=category)
    except Exception as e:
        print("存储上传失败，回退到本地保存: %s" % e)
        local = LocalStorageProvider()
        return local.save_bytes(data=data, filename=filename, category=category)


def _parse_personality_tags(raw: Optional[str]) -> Optional[List[str]]:
    if not raw:
        return None
    # 兼容 JSON 数组或逗号分隔字符串
    try:
        loaded = json.loads(raw)
        if isinstance(loaded, list):
            return [str(x) for x in loaded if str(x).strip()]
    except Exception:
        pass
    return [s.strip() for s in raw.split(",") if s.strip()]


# --------------------------- 基础健康检查接口 ---------------------------


@app.get("/")
def index_handler() -> Dict[str, Any]:
    return {"message": "New Year Card Generator API", "version": "1.0.0"}


@app.get("/v1/ping")
async def ping_handler() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/providers")
async def providers_handler() -> Dict[str, Any]:
    """返回当前 Provider 运行模式，方便前端展示是否为 mock。"""

    return {
        "llm": getattr(llm_provider, "name", "unknown"),
        "vision": getattr(vision_provider, "name", "unknown"),
        "t2i": getattr(t2i_provider, "name", "unknown"),
        "storage": getattr(storage_provider, "name", "unknown"),
    }


# --------------------------- Demo 示例接口（保留） ---------------------------


# get all users
@app.get("/users")
async def get_users() -> Dict[str, Any]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    return {"users": users}


# add user
@app.post("/users")
async def add_user(name: str, email: str) -> Dict[str, Any]:
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
    conn.commit()
    return {"message": "User added", "id": cursor.lastrowid}


# --------------------------- 业务接口：原子能力 ---------------------------


@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)) -> Dict[str, Any]:
    """接收文件并保存到本地 static，返回可公开访问的 URL。"""

    url = await _save_upload_to_storage(file, category="moment")
    return {"url": url}


@app.post("/parse-relation")
async def parse_relation(payload: ParseRelationRequest) -> Dict[str, Any]:
    """将前端选项组合为结构化关系。

    无密钥时走本地规则解析，有密钥时仍由同一个 Provider 负责，方便后续接入 LLM。
    """  

    relation_info = llm_provider.parse_relation(
        payload.primary_relation,
        payload.secondary_relation,
        payload.custom_relation_text,
        payload.user_text,
    )
    return {"relation": relation_info}


@app.post("/analyze-image")
async def analyze_image(payload: AnalyzeImageRequest) -> Dict[str, Any]:
    description = vision_provider.analyze_image(payload.image_url)
    return {"description": description}


@app.post("/generate-blessing")
async def generate_blessing(payload: GenerateBlessingRequest) -> Dict[str, Any]:
    text = llm_provider.generate_blessing(
        payload.relation,
        payload.personality_profile,
        payload.personality_tags,
    )
    return {"blessingText": text}


@app.post("/regenerate-blessings")
async def regenerate_blessings(payload: RegenerateBlessingsRequest) -> Dict[str, Any]:
    """PRD 4.5：重新生成三条祝福语（文言/文艺/大白话），不重新解析图片。"""
    tags = payload.personality_tags or []
    options = llm_provider.generate_blessings(
        payload.relation,
        payload.personality_profile,
        tags,
    )
    return {"blessingOptions": options}


@app.post("/generate-prompt")
async def generate_prompt(payload: GeneratePromptRequest) -> Dict[str, Any]:
    style_key = payload.style_key or "auto"
    prompt = llm_provider.generate_prompt(
        payload.relation,
        payload.personality_profile,
        payload.blessing_text,
        payload.image_description,
        style_key,
    )
    return {"prompt": prompt}


# PRD 4.7 异常兜底：通用马年三类祝福语
DEFAULT_BLESSING_OPTIONS = [
    {"style": "文言风", "text": "丙午新正，骅骝启岁。敬祝龙马精神，福履绵长，万事胜意。"},
    {"style": "文艺风", "text": "丙午年的风吹来，愿你策马奔赴热爱，岁岁有暖，马不停蹄奔向美好。"},
    {"style": "大白话", "text": "马年到啦，愿你马到成功，阖家安康，万事顺意！"},
]


@app.post("/generate-card")
async def generate_card(payload: GenerateCardRequest) -> Dict[str, Any]:
    style_key = payload.style_key or "auto"
    if payload.prompt:
        image_url = t2i_provider.generate_card(payload.prompt, style_key)
    else:
        # 两阶段流程：用选中祝福语 + 关系/性格/提取信息生成贺卡
        blessing_text = payload.selected_blessing_text or "马年大吉，万事顺意。"
        relation = payload.relation or {}
        personality_profile = payload.personality_profile
        extraction = payload.extraction
        image_desc = payload.image_description
        if style_key == "auto":
            style_key = _infer_style_from_avatar(extraction, personality_profile)
        prompt = llm_provider.generate_prompt(
            relation,
            personality_profile,
            blessing_text,
            image_desc,
            style_key,
            extraction=extraction,
        )
        image_url = t2i_provider.generate_card(prompt, style_key)
    if image_url and image_url.startswith("http"):
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: requests.get(image_url, timeout=30),
            )
            if resp.ok and resp.content:
                try:
                    image_url = storage_provider.save_bytes(
                        resp.content, "card.png", category="cards"
                    )
                except Exception as e:
                    print("贺卡保存到存储失败，回退到本地: %s" % e)
                    image_url = LocalStorageProvider().save_bytes(
                        resp.content, "card.png", category="cards"
                    )
        except Exception:
            pass
    return {"cardImageUrl": image_url}


# --------------------------- 业务接口：一键生成 ---------------------------


@app.post("/generate")
async def generate(
    primary_relation: Optional[str] = Form(None),
    secondary_relation: Optional[str] = Form(None),
    custom_relation_text: Optional[str] = Form(None),
    personality_tags: Optional[str] = Form(None),
    style_key: Optional[str] = Form("auto"),
    mode: Optional[str] = Form("auto"),
    file: Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    """PRD 5.1 主流程第一阶段：上传 → 提取五条 → 性格画像 → 生成三类祝福语。贺卡由 /api/generate-card 生成。"""
    tags_list = _parse_personality_tags(personality_tags)
    relation_info = llm_provider.parse_relation(
        primary_relation, secondary_relation, custom_relation_text, None,
    )

    image_url: Optional[str] = None
    extraction: Optional[Dict[str, Any]] = None
    personality_profile: Optional[str] = None
    use_fallback_blessings = False

    if file is not None:
        image_url = await _save_upload_to_storage(file, category="moment")
        try:
            raw = vision_provider.analyze_image(image_url)
            if isinstance(raw, dict):
                extraction = raw
            else:
                extraction = {"raw": raw, **_parse_five_items(raw)}
            if (extraction.get("raw") or "").strip().startswith("未收到有效的朋友圈截图"):
                use_fallback_blessings = True
                extraction = None
        except Exception as e:
            print(f"视觉提取失败: {e}，使用兜底祝福语")
            use_fallback_blessings = True
            extraction = None

    if extraction:
        personality_profile = llm_provider.analyze_personality_from_extraction(
            extraction, tags_list
        )
    else:
        personality_profile = llm_provider.analyze_personality(
            image_description=None,
            personality_tags=tags_list,
        )

    if use_fallback_blessings:
        blessing_options = DEFAULT_BLESSING_OPTIONS
    else:
        blessing_options = llm_provider.generate_blessings(
            relation_info, personality_profile, tags_list,
        )

    providers_meta = {
        "llm": getattr(llm_provider, "name", "unknown"),
        "vision": getattr(vision_provider, "name", "unknown"),
        "t2i": getattr(t2i_provider, "name", "unknown"),
        "storage": getattr(storage_provider, "name", "unknown"),
    }
    return {
        "blessingOptions": blessing_options,
        "relation": relation_info,
        "personalityProfile": personality_profile,
        "extraction": extraction,
        "imageUrl": image_url,
        "providers": providers_meta,
        "useFallback": use_fallback_blessings,
    }


# ---------------------------DO NOT EDIT CODE BELOW THIS LINE---------------------------------
# This is the entry point for the FastAPI application.
if __name__ == "__main__":
    port = int(os.environ.get("_BYTEFAAS_RUNTIME_PORT", 8000))
    config = uvicorn.Config("main:app", port=port, log_level="info", host=None)
    server = uvicorn.Server(config)
    server.run()
# --------------------------------------------------------------------------------------------
