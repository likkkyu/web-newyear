import os
import re
import base64
import requests
from pathlib import Path
from typing import Any, Dict, Optional


BASE_DIR = Path(__file__).resolve().parent.parent

# PRD 4.2.3：五条结构化提取 prompt（doubao-seed-1.8）
EXTRACTION_PROMPT = """你是一个专业的图片内容解析员。现在你会收到一张朋友圈截图的图片。
如果图片有效且清晰，请严格按以下5个条目，逐条输出客观信息，不要分析，不要评价：
1. 头像描述：描述头像的风格、内容、给人的感觉。
2. 朋友圈背景图描述：描述背景图的场景、风格、氛围。
3. 个性签名：提取截图中能看到的个性签名原文，看不到就写"未识别到个性签名"。
4. 朋友圈动态内容：列出所有能看到的朋友圈动态文字（包括置顶），并说明主题，看不到就写"未识别到朋友圈动态"。
5. 朋友圈可见范围：明确写出截图中显示的可见范围，看不到就写"未识别到可见范围"。
如果没有收到有效的图片，或者图片无法识别，请直接输出："未收到有效的朋友圈截图图片，请重新上传。"
"""


def _parse_five_items(raw: str) -> Dict[str, str]:
    """从模型回复中解析 1. 2. 3. 4. 5. 五条内容。"""
    result: Dict[str, str] = {
        "avatar_desc": "",
        "background_desc": "",
        "signature_text": "",
        "dynamic_content": "",
        "visible_range": "",
    }
    if not raw or "未收到有效的朋友圈截图" in raw:
        return result
    # 按 1. 2. 3. 4. 5. 分割，允许 "1." "1、"等
    parts = re.split(r"\n\s*[1-5][\.、．]\s*", raw.strip(), maxsplit=5)
    if len(parts) < 2:
        result["avatar_desc"] = raw.strip()[:500]
        return result
    # parts[0] 可能是前缀说明，从 parts[1] 起对应 1~5
    keys = ["avatar_desc", "background_desc", "signature_text", "dynamic_content", "visible_range"]
    for i, key in enumerate(keys):
        idx = i + 1
        if idx < len(parts):
            result[key] = parts[idx].strip()[:800]
    return result


class VisionProvider(object):
    """视觉理解 / OCR Provider 抽象接口。"""

    def __init__(self, name: str) -> None:
        self.name = name

    def analyze_image(self, image_url: str) -> str:
        """根据图片 URL 返回一段自然语言描述（兼容旧接口）。"""
        raise NotImplementedError

    def analyze_image_structured(self, image_url: str) -> Dict[str, Any]:
        """PRD 4.2：按五区域提取，返回结构化 5 项。"""
        desc = self.analyze_image(image_url)
        if isinstance(desc, dict):
            return desc
        return {"raw": desc, **_parse_five_items(desc)}


class MockVisionProvider(VisionProvider):
    """本地占位实现：不真正识别图片，只返回通用描述与五条占位。"""

    def __init__(self) -> None:
        super(MockVisionProvider, self).__init__(name="mock")

    def analyze_image(self, image_url: str) -> str:
        return (
            "1. 头像描述：一张来自朋友圈的截图，头像区域为默认风格。"
            "2. 朋友圈背景图描述：背景有新年或日常氛围。"
            "3. 个性签名：未识别到个性签名。"
            "4. 朋友圈动态内容：未识别到朋友圈动态。"
            "5. 朋友圈可见范围：未识别到可见范围。"
        )


class SimpleHTTPVisionProvider(MockVisionProvider):
    """接入火山豆包视觉大模型的 Provider，PRD 4.2.3 五条结构化输出。"""

    def __init__(self, provider_name: str, api_key: str) -> None:
        super(SimpleHTTPVisionProvider, self).__init__()
        self.name = provider_name
        self.api_key = api_key
        base = os.getenv("VISION_API_BASE", "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
        self.base_url = base
        self.model = os.getenv("VISION_MODEL", "doubao-seed-1-8-251228")

    def _get_image_base64(self, image_url: str) -> str:
        """将图片 URL（本地 /static/ 或公网 http(s)）转为 base64。"""
        if image_url.startswith(("http://", "https://")):
            resp = requests.get(image_url, timeout=30)
            resp.raise_for_status()
            return base64.b64encode(resp.content).decode("utf-8")
        if image_url.startswith("/static/"):
            image_path = BASE_DIR / image_url.lstrip("/")
            if image_path.exists():
                with open(image_path, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
        raise RuntimeError(f"无法读取图片: {image_url}")

    def analyze_image(self, image_url: str) -> str:
        """调用豆包多模态，按 PRD 4.2.3 输出五条客观信息。"""
        try:
            image_base64 = self._get_image_base64(image_url)
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": EXTRACTION_PROMPT},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                        ]
                    }
                ],
                "temperature": 0.3,
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content or super().analyze_image(image_url)
        except Exception as e:
            print(f"视觉模型调用失败: {e}，回退到 mock")
            return super().analyze_image(image_url)


_VISION_PROVIDER_SINGLETON: Optional[VisionProvider] = None


def get_vision_provider() -> VisionProvider:
    global _VISION_PROVIDER_SINGLETON
    if _VISION_PROVIDER_SINGLETON is not None:
        return _VISION_PROVIDER_SINGLETON

    provider_name = os.getenv("VISION_PROVIDER", "mock").strip().lower()
    api_key = os.getenv("VISION_API_KEY")

    if provider_name == "mock" or not api_key:
        _VISION_PROVIDER_SINGLETON = MockVisionProvider()
    else:
        _VISION_PROVIDER_SINGLETON = SimpleHTTPVisionProvider(provider_name, api_key)

    return _VISION_PROVIDER_SINGLETON
