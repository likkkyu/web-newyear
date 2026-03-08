import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))


def _load_env_file() -> None:
    """从 backend 目录加载 .env 到 os.environ。

    不依赖第三方库，需在首次读取环境变量和 Provider 初始化之前调用。
    """

    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.providers.llm import get_llm_provider
from backend.providers.storage import get_storage_provider
from backend.providers.t2i import get_t2i_provider
from backend.providers.vision import get_vision_provider


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


class GeneratePromptRequest(BaseModel):
    relation: Dict[str, Any]
    personality_profile: Optional[str] = None
    blessing_text: str
    image_description: Optional[str] = None
    style_key: Optional[str] = "auto"


class GenerateCardRequest(BaseModel):
    prompt: str
    style_key: Optional[str] = "auto"


# --------------------------- 辅助函数 ---------------------------


async def _save_upload_to_storage(file: UploadFile, category: str) -> str:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="上传文件为空")
    filename = file.filename or "image"
    return storage_provider.save_bytes(data=data, filename=filename, category=category)


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
    cursor.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
    conn.commit()
    return {"message": "User added", "id": cursor.lastrowid}


# --------------------------- 业务接口：原子能力 ---------------------------


@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...)) -> Dict[str, Any]:
    """接收文件并保存到本地 static，返回可公开访问的 URL。"""

    url = await _save_upload_to_storage(file, category="moment")
    return {"url": url}


@app.post("/api/parse-relation")
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


@app.post("/api/analyze-image")
async def analyze_image(payload: AnalyzeImageRequest) -> Dict[str, Any]:
    description = vision_provider.analyze_image(payload.image_url)
    return {"description": description}


@app.post("/api/generate-blessing")
async def generate_blessing(payload: GenerateBlessingRequest) -> Dict[str, Any]:
    text = llm_provider.generate_blessing(
        payload.relation,
        payload.personality_profile,
        payload.personality_tags,
    )
    return {"blessingText": text}


@app.post("/api/generate-prompt")
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


@app.post("/api/generate-card")
async def generate_card(payload: GenerateCardRequest) -> Dict[str, Any]:
    style_key = payload.style_key or "auto"
    image_url = t2i_provider.generate_card(payload.prompt, style_key)
    return {"cardImageUrl": image_url}


# --------------------------- 业务接口：一键生成 ---------------------------


@app.post("/api/generate")
async def generate(
    primary_relation: Optional[str] = Form(None),
    secondary_relation: Optional[str] = Form(None),
    custom_relation_text: Optional[str] = Form(None),
    personality_tags: Optional[str] = Form(None),
    style_key: Optional[str] = Form("auto"),
    mode: Optional[str] = Form("auto"),  # 兼容前端传入的模式字段，目前不做强校验
    file: Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    """编排完整工作流，返回祝福语与贺卡图片 URL。

    前端统一调用该接口，表单字段：
    - primary_relation: 一级关系（亲戚/朋友/同事/师生）
    - secondary_relation: 二级关系（长辈/平辈/晚辈等）
    - custom_relation_text: 自定义关系说明
    - personality_tags: JSON 数组或逗号分隔的性格标签
    - style_key: 风格 key（auto/guofeng/cyberpunk/handwritten）
    - file: 可选的朋友圈截图
    """

    tags_list = _parse_personality_tags(personality_tags)

    # 1. 关系解析
    relation_info = llm_provider.parse_relation(
        primary_relation,
        secondary_relation,
        custom_relation_text,
        None,
    )

    # 2. 图片上传 & 视觉理解 & 性格分析（如果有文件）
    image_url: Optional[str] = None
    image_description: Optional[str] = None
    personality_profile: Optional[str] = None

    if file is not None:
        image_url = await _save_upload_to_storage(file, category="moment")
        image_description = vision_provider.analyze_image(image_url)
        personality_profile = llm_provider.analyze_personality(
            image_description=image_description,
            personality_tags=tags_list,
        )
    else:
        personality_profile = llm_provider.analyze_personality(
            image_description=None,
            personality_tags=tags_list,
        )

    # 3. 祝福语生成
    blessing_text = llm_provider.generate_blessing(
        relation_info,
        personality_profile,
        tags_list,
    )

    # 4. 绘图 Prompt 生成
    style_key_final = style_key or "auto"
    prompt = llm_provider.generate_prompt(
        relation_info,
        personality_profile,
        blessing_text,
        image_description,
        style_key_final,
    )

    # 5. 贺卡图片生成
    card_image_url = t2i_provider.generate_card(prompt, style_key_final)

    providers_meta = {
        "llm": getattr(llm_provider, "name", "unknown"),
        "vision": getattr(vision_provider, "name", "unknown"),
        "t2i": getattr(t2i_provider, "name", "unknown"),
        "storage": getattr(storage_provider, "name", "unknown"),
    }

    return {
        "blessingText": blessing_text,
        "cardImageUrl": card_image_url,
        "imageUrl": image_url,
        "relation": relation_info,
        "personalityProfile": personality_profile,
        "imageDescription": image_description,
        "providers": providers_meta,
    }


# ---------------------------DO NOT EDIT CODE BELOW THIS LINE---------------------------------
# This is the entry point for the FastAPI application.
if __name__ == "__main__":
    port = int(os.environ.get("_BYTEFAAS_RUNTIME_PORT", 8000))
    config = uvicorn.Config("main:app", port=port, log_level="info", host=None)
    server = uvicorn.Server(config)
    server.run()
# --------------------------------------------------------------------------------------------
