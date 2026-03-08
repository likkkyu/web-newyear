import os
from typing import Any, Dict, Optional

import requests


class T2IProvider(object):
    """文生图 Provider 抽象接口。"""

    def __init__(self, name: str) -> None:
        self.name = name

    def generate_card(self, prompt: str, style_key: str) -> str:
        """根据绘图 Prompt 生成图片，并返回可访问的图片 URL。

        在 mock 实现中不会真正调用模型，只返回占位图片地址。
        """

        raise NotImplementedError


class MockT2IProvider(T2IProvider):
    """本地占位文生图 Provider。

    实际项目中建议接入 doubao-seedream 等模型。当前实现返回固定占位图路径：
    /static/mock_card.png
    """

    def __init__(self) -> None:
        super(MockT2IProvider, self).__init__(name="mock")

    def generate_card(self, prompt: str, style_key: str) -> str:
        # 这里仅返回占位图片路径，真实实现请根据需要自行接入文生图服务
        return "/static/mock_card.png"


class SimpleHTTPT2IProvider(MockT2IProvider):
    """预留给真实文生图服务的 Provider。

    当前继承 Mock 实现以保证开箱可用，接入真实服务时只需改造本类内部逻辑。
    """

    def __init__(self, provider_name: str, api_key: str) -> None:
        super(SimpleHTTPT2IProvider, self).__init__()
        self.name = provider_name
        self.api_key = api_key
        # 通过环境变量配置 HTTP 接口，默认兼容 OpenAI / Seedream 4.0 代理风格
        # 例如：T2I_API_BASE=https://www.dmxapi.cn/v1  T2I_MODEL=doubao-seedream-4-0-250828
        base = os.getenv("T2I_API_BASE", "").rstrip("/")
        self.base_url = base or "https://api.example.com/v1"
        self.model = os.getenv("T2I_MODEL", "doubao-seedream-4-0-250828")

    def generate_card(self, prompt: str, style_key: str) -> str:
        # 接入远端文生图服务，返回图片 URL
        url = f"{self.base_url}/images/generations"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # 以 Seedream / OpenAI 兼容风格构造请求；watermark=false 关闭右下角「AI生成」水印
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "size": "720x1280",
            "n": 1,
            "response_format": "url",
            "watermark": False,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        # 兼容常见返回结构
        first = (data.get("data") or [{}])[0]
        image_url = first.get("url") or first.get("image_url") or first.get("b64_json")
        if not image_url:
            raise RuntimeError("文生图接口未返回有效图片 URL")
        return image_url


_T2I_PROVIDER_SINGLETON: Optional[T2IProvider] = None


def get_t2i_provider() -> T2IProvider:
    global _T2I_PROVIDER_SINGLETON
    if _T2I_PROVIDER_SINGLETON is not None:
        return _T2I_PROVIDER_SINGLETON

    provider_name = os.getenv("T2I_PROVIDER", "mock").strip().lower()
    api_key = os.getenv("T2I_API_KEY")

    if provider_name == "mock" or not api_key:
        _T2I_PROVIDER_SINGLETON = MockT2IProvider()
    else:
        _T2I_PROVIDER_SINGLETON = SimpleHTTPT2IProvider(provider_name, api_key)

    return _T2I_PROVIDER_SINGLETON
