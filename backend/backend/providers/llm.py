import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# LLM 请求超时或网络错误时回退到 Mock 使用
_REQUEST_ERRORS = (requests.exceptions.Timeout, requests.exceptions.RequestException, requests.exceptions.ConnectionError)


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def _load_json(filename: str) -> Any:
    path = DATA_DIR / filename
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


_RELATIONS: Dict[str, Any] = _load_json("relations.json")
_BLESSINGS: Dict[str, Any] = _load_json("blessings.json")
_STYLES: Dict[str, Any] = _load_json("styles.json")


class LLMProvider(object):
    """抽象的大模型 Provider 接口。

    约定：不要在业务代码里直接实例化具体实现，而是通过 get_llm_provider()
    获取单例，这样后续切换真实 Provider 时无需改动业务代码。
    """

    def __init__(self, name: str) -> None:
        self.name = name

    # 关系解析 -----------------------------------------------------------------
    def parse_relation(
        self,
        primary_label: Optional[str],
        secondary_label: Optional[str],
        custom_relation_text: Optional[str] = None,
        user_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    # 性格分析 -----------------------------------------------------------------
    def analyze_personality(
        self,
        image_description: Optional[str] = None,
        personality_tags: Optional[List[str]] = None,
    ) -> str:
        raise NotImplementedError

    def analyze_personality_from_extraction(
        self,
        extraction: Dict[str, Any],
        personality_tags: Optional[List[str]] = None,
    ) -> str:
        """PRD 4.3：基于五条提取信息生成性格画像，头像 100% 主导。"""
        raise NotImplementedError

    # 祝福语生成 ---------------------------------------------------------------
    def generate_blessing(
        self,
        relation_info: Dict[str, Any],
        personality_profile: Optional[str] = None,
        personality_tags: Optional[List[str]] = None,
    ) -> str:
        raise NotImplementedError

    def generate_blessings(
        self,
        relation_info: Dict[str, Any],
        personality_profile: Optional[str] = None,
        personality_tags: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """PRD 4.5：一次生成文言风、文艺风、大白话三条，每条 20-50 字。"""
        raise NotImplementedError

    # 绘图 Prompt 生成 ---------------------------------------------------------
    def generate_prompt(
        self,
        relation_info: Dict[str, Any],
        personality_profile: Optional[str],
        blessing_text: str,
        image_description: Optional[str],
        style_key: str,
        extraction: Optional[Dict[str, Any]] = None,
    ) -> str:
        raise NotImplementedError


# --------------------------- 工具函数 ---------------------------


def _find_relation_by_labels(
    primary_label: Optional[str], secondary_label: Optional[str]
) -> Dict[str, Any]:
    """根据中文文案反查配置中的 relation key。

    返回：
        {
          "primary_key": "family",
          "secondary_key": "elder",
          "primary_label": "亲戚",
          "secondary_label": "长辈"
        }
    如果匹配失败会尽量回退，只返回已有部分。
    """

    result: Dict[str, Any] = {
        "primary_key": None,
        "secondary_key": None,
        "primary_label": primary_label,
        "secondary_label": secondary_label,
    }

    primary_options = _RELATIONS.get("primary_options", [])
    for primary in primary_options:
        if primary_label and primary.get("label") == primary_label:
            result["primary_key"] = primary.get("key")
            # 二级
            sub_options = primary.get("sub_options") or []
            for sub in sub_options:
                if secondary_label and sub.get("label") == secondary_label:
                    result["secondary_key"] = sub.get("key")
                    break
            break
    return result


def _select_blessing_template(primary_key: str, secondary_key: str) -> str:
    """从本地祝福语模板中选出一条合适的文本。"""

    category = _BLESSINGS.get(primary_key) or {}
    candidates = category.get(secondary_key) or []
    if not candidates:
        # 兜底：任意找一条
        for cat in _BLESSINGS.values():
            for arr in cat.values():
                if isinstance(arr, list) and arr:
                    return arr[0]
        return "新年快乐，愿你在新的一年里平安喜乐、万事顺意。"
    # 固定取第一条，避免引入随机数依赖
    return candidates[0]


def _get_style_config(style_key: str) -> Dict[str, Any]:
    if not style_key:
        style_key = "auto"
    style = _STYLES.get(style_key)
    if not style:
        style = _STYLES.get("auto", {})
    return style


def _infer_style_from_avatar(extraction: Optional[Dict[str, Any]], profile: Optional[str]) -> str:
    """PRD 4.6.1：以头像风格为唯一核心匹配贺卡风格。"""
    text = ""
    if extraction:
        text += (extraction.get("avatar_desc") or "") + " " + (extraction.get("background_desc") or "")
    if profile:
        text += " " + profile
    text = (text or "").lower()


def _avatar_suggests_real_face(extraction: Optional[Dict[str, Any]]) -> bool:
    """判断头像描述是否暗示真人脸（非动漫/卡通/动物），贺卡中禁止生成真人面部。"""
    if not extraction:
        return False
    raw = ((extraction.get("avatar_desc") or "") + " " + (extraction.get("background_desc") or "")).lower()
    # 真人、自拍、人脸、真人自拍、写实人像、真人照片等 → 禁止在贺卡上画真人脸
    if any(k in raw for k in ("真人", "自拍", "人脸", "人像", "真人照片", "真人头像", "写实人", "真人脸")):
        # 若明确是动漫/卡通/动物，则不算真人脸
        if any(k in raw for k in ("动漫", "二次元", "卡通", "动物", "宠物", "猫", "狗", "插画")):
            return False
        return True
    return False
    if "二次元" in text or "动漫" in text:
        return "cyberpunk"
    if "佛系" in text or "中老年" in text or "禅" in text or "水墨" in text:
        return "guofeng"
    if "文艺" in text or "简约" in text or "ins" in text:
        return "handwritten"
    if "卡通" in text or "可爱" in text:
        return "handwritten"
    if "真人" in text or "自拍" in text or "写实" in text:
        return "handwritten"
    return "guofeng"


# --------------------------- Mock Provider 实现 ---------------------------


class MockLLMProvider(LLMProvider):
    """本地模板 + 规则驱动的 mock 实现。

    无密钥时默认走这个分支，保证接口可用，同时在 /api/generate 的
    providers 字段中会把 name 标为 "mock"，方便前端提示用户当前为模拟模式。
    """

    def __init__(self) -> None:
        super(MockLLMProvider, self).__init__(name="mock")

    def parse_relation(
        self,
        primary_label: Optional[str],
        secondary_label: Optional[str],
        custom_relation_text: Optional[str] = None,
        user_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        relation_keys = _find_relation_by_labels(primary_label, secondary_label)
        primary_key = relation_keys.get("primary_key") or "unknown"
        secondary_key = relation_keys.get("secondary_key") or "unknown"

        # 展示用中文文案
        primary_label_final = relation_keys.get("primary_label") or primary_label or "未指定"
        secondary_label_final = (
            relation_keys.get("secondary_label") or secondary_label or "未指定"
        )

        # 自然语言描述
        if custom_relation_text:
            description = "TA 是你的%s。" % custom_relation_text
        elif secondary_label_final != "未指定":
            description = "TA 是你的%s%s。" % (primary_label_final, secondary_label_final)
        elif primary_label_final != "未指定":
            description = "TA 和你属于%s关系。" % primary_label_final
        else:
            description = "暂未明确关系，以较为通用的祝福语为主。"

        if user_text:
            description += "（用户补充说明：%s）" % user_text

        return {
            "primary_key": primary_key,
            "secondary_key": secondary_key,
            "primary_label": primary_label_final,
            "secondary_label": secondary_label_final,
            "custom_relation_text": custom_relation_text,
            "description": description,
        }

    def analyze_personality(
        self,
        image_description: Optional[str] = None,
        personality_tags: Optional[List[str]] = None,
    ) -> str:
        parts: List[str] = []
        if image_description:
            parts.append(
                "从这张朋友圈截图里，可以看出对方的世界里有这些画面：%s。" % image_description
            )
        if personality_tags:
            tags_text = "、".join(personality_tags)
            parts.append("整体感觉 TA 是一个%s的人。" % tags_text)
        parts.append(
            "整体来看，TA给人的印象是温暖而真诚，在自己的节奏里稳稳生活，对亲近的人有耐心也有担当。"
        )
        return "".join(parts)

    def analyze_personality_from_extraction(
        self,
        extraction: Dict[str, Any],
        personality_tags: Optional[List[str]] = None,
    ) -> str:
        parts: List[str] = []
        avatar = extraction.get("avatar_desc") or ""
        background = extraction.get("background_desc") or ""
        signature = extraction.get("signature_text") or ""
        dynamic = extraction.get("dynamic_content") or ""
        visible = extraction.get("visible_range") or ""
        if avatar:
            parts.append("头像：%s。" % avatar)
        if background:
            parts.append("背景：%s。" % background)
        if signature and "未识别" not in signature:
            parts.append("个性签名：%s。" % signature)
        if dynamic and "未识别" not in dynamic:
            parts.append("动态：%s。" % dynamic)
        if visible and "未识别" not in visible:
            parts.append("可见范围：%s。" % visible)
        if personality_tags:
            parts.append("整体感觉 TA 是一个%s的人。" % "、".join(personality_tags))
        parts.append("综合性格画像：温暖而真诚，在自己的节奏里稳稳生活，对亲近的人有耐心也有担当。")
        return "".join(parts)

    def generate_blessing(
        self,
        relation_info: Dict[str, Any],
        personality_profile: Optional[str] = None,
        personality_tags: Optional[List[str]] = None,
    ) -> str:
        primary_key = relation_info.get("primary_key") or "family"
        secondary_key = relation_info.get("secondary_key") or "elder"
        base = _select_blessing_template(primary_key, secondary_key)
        extra: str = ""
        if personality_profile:
            extra = "\n\n从 TA 的状态里看得出：%s 所以这份祝福也更想贴近 TA 现在的节奏。" % (
                personality_profile
            )
        elif personality_tags:
            extra = "\n\n你眼中的 TA：%s，这也是这份祝福想去拥抱和回应的部分。" % "、".join(personality_tags)
        return base + extra

    def generate_blessings(
        self,
        relation_info: Dict[str, Any],
        personality_profile: Optional[str] = None,
        personality_tags: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        one = self.generate_blessing(relation_info, personality_profile, personality_tags)
        short = (one[: 50] + "…") if len(one) > 50 else one
        return [
            {"style": "文言风", "text": "丙午新正，骅骝启岁。敬祝龙马精神，福履绵长，万事胜意。"},
            {"style": "文艺风", "text": "丙午年的风吹来，愿你策马奔赴热爱，岁岁有暖，马不停蹄奔向美好。"},
            {"style": "大白话", "text": short},
        ]

    def generate_prompt(
        self,
        relation_info: Dict[str, Any],
        personality_profile: Optional[str],
        blessing_text: str,
        image_description: Optional[str],
        style_key: str,
        extraction: Optional[Dict[str, Any]] = None,
    ) -> str:
        primary_label = relation_info.get("primary_label") or "朋友"
        secondary_label = relation_info.get("secondary_label") or ""
        relation_desc = (
            primary_label if not secondary_label else "%s-%s" % (primary_label, secondary_label)
        )
        style_cfg = _get_style_config(style_key)
        style_suffix = style_cfg.get("prompt_suffix", "")
        style_name = style_cfg.get("name", "自动匹配风格")
        image_part = image_description or ""
        if extraction:
            image_part = "头像：%s；背景：%s；性格画像：%s。" % (
                extraction.get("avatar_desc") or "",
                extraction.get("background_desc") or "",
                (personality_profile or "")[:300],
            )
        prompt = (
            "你是一位擅长设计 2026 马年新年贺卡的插画师，现在要为一位『%s』对象设计一张适合微信发送的竖版新年贺卡。" % relation_desc
        )
        prompt += "画面中需要包含明显的马年元素：骏马、烟花、春节灯笼、祥云、中国结、红包、元宝等，整体氛围喜庆但不过度花哨。"
        prompt += "当前选择的整体风格是：%s。%s" % (style_name, style_suffix)
        if image_part:
            prompt += " " + image_part
        prompt += "贺卡上的祝福语需要与画面融为一体，文字清晰可读，排版居中或略偏下。"
        prompt += "下面是需要放在贺卡上的祝福语全文：%s" % blessing_text
        prompt += "请据此生成适合文生图模型的详细绘图指令。"
        return prompt


# --------------------------- Provider 工厂 ---------------------------


class SimpleHTTPLLMProvider(MockLLMProvider):
    """预留给真实大模型服务的 Provider。

    目前内部仍然复用 MockLLMProvider 的实现，确保没有密钥时也能正常工作。
    当你接入豆包 / OpenAI 等真实服务时，只需要在这里改造具体方法，
    对上层业务与前端接口不会有任何变化。
    """

    def __init__(self, provider_name: str, api_key: str) -> None:
        super(SimpleHTTPLLMProvider, self).__init__()
        self.name = provider_name
        self.api_key = api_key
        base = os.getenv("LLM_API_BASE", "").rstrip("/")
        self.base_url = base or "https://api.example.com/v1"
        self.model = os.getenv("LLM_MODEL", "doubao-seed-1.8")
        self._timeout = int(os.getenv("LLM_REQUEST_TIMEOUT", "120"))

    def _chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        # 兼容 OpenAI 风格
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if not isinstance(content, str):
            content = str(content)
        return content

    def analyze_personality(
        self,
        image_description: Optional[str] = None,
        personality_tags: Optional[List[str]] = None,
    ) -> str:
        tags_text = "、".join(personality_tags) if personality_tags else "（未提供标签）"
        image_part = image_description or "未提供朋友圈截图内容，仅依据性格标签进行判断。"
        system_prompt = (
            "你是一名擅长根据朋友圈截图与性格标签，总结对方性格气质的助理。"
            "请用 1 段自然、真诚的中文话，描述对方给人的整体感觉，字数控制在 80 字以内。"
        )
        user_prompt = (
            f"朋友圈截图描述：{image_part}\n"
            f"性格标签：{tags_text}\n"
            "请聚焦于气质、处事方式、对待生活和身边人的态度，避免陈词滥调。"
        )
        return self._chat(system_prompt, user_prompt, temperature=0.6)

    def analyze_personality_from_extraction(
        self,
        extraction: Dict[str, Any],
        personality_tags: Optional[List[str]] = None,
    ) -> str:
        # PRD 4.3.3：逐元素解读 + 综合性格画像，头像 100% 主导
        system_prompt = (
            "你是一位细腻、温柔、有洞察力的性格分析师，语言精准、有质感，像朋友在认真了解一个人，不毒舌、不贴标签、不使用网络梗。\n"
            "你的分析逻辑必须严格遵循以下框架：\n"
            "1. 逐元素解读：对头像、朋友圈背景图、个性签名、朋友圈动态、可见范围这5个元素，逐一解读其对应的性格侧面：\n"
            "   - 头像：解读其自我表达风格、内心的童真与亲和力；\n"
            "   - 背景图：解读其审美追求、对艺术与仪式感的执着；\n"
            "   - 个性签名：解读其自我认知、边界感与清醒度；\n"
            "   - 朋友圈动态：解读其生活方式、社交偏好与对热爱的投入；\n"
            "   - 可见范围：解读其隐私意识、对当下的重视程度。\n"
            "2. 综合性格画像：将所有元素的解读串联成一段完整、连贯的描述，语言温柔且有画面感。\n"
            "输出要求：先分点列出各元素的解读，再给出综合性格画像；避免空洞的形容词，用具体的细节支撑结论。\n"
            "风格优先级：头像风格100%主导，若头像与背景风格冲突，完全以头像为准。"
        )
        lines = [
            "1. 头像描述：%s" % (extraction.get("avatar_desc") or "未提供"),
            "2. 朋友圈背景图描述：%s" % (extraction.get("background_desc") or "未提供"),
            "3. 个性签名：%s" % (extraction.get("signature_text") or "未提供"),
            "4. 朋友圈动态内容：%s" % (extraction.get("dynamic_content") or "未提供"),
            "5. 朋友圈可见范围：%s" % (extraction.get("visible_range") or "未提供"),
        ]
        if personality_tags:
            lines.append("用户补充性格标签：%s" % "、".join(personality_tags))
        user_prompt = "\n".join(lines)
        try:
            return self._chat(system_prompt, user_prompt, temperature=0.6)
        except _REQUEST_ERRORS as e:
            print("LLM 性格画像调用超时或失败，回退到本地规则: %s" % e)
            return super().analyze_personality_from_extraction(extraction, personality_tags)

    def generate_blessing(
        self,
        relation_info: Dict[str, Any],
        personality_profile: Optional[str] = None,
        personality_tags: Optional[List[str]] = None,
    ) -> str:
        primary_label = relation_info.get("primary_label") or "朋友"
        secondary_label = relation_info.get("secondary_label") or ""
        relation_desc = (
            primary_label if not secondary_label else f"{primary_label}-{secondary_label}"
        )
        tags_text = "、".join(personality_tags) if personality_tags else "（未提供标签）"
        personality_text = personality_profile or "未额外提供性格画像，仅依据关系与标签生成。"
        system_prompt = (
            "你是一名擅长写微信新年祝福语的中文文案助手。"
            "请写一段适合 2026 马年、可直接发送到微信聊天或朋友圈的祝福语，避免油腻、避免套话。"
        )
        user_prompt = (
            f"你要写的对象关系是：{relation_desc}。\n"
            f"性格标签：{tags_text}。\n"
            f"补充性格画像：{personality_text}\n"
            "整体要求：语气真诚；自然提到马年意象；控制在 80～150 字之间；直接给出可发送内容，不要提示语。"
        )
        return self._chat(system_prompt, user_prompt, temperature=0.85)

    def generate_blessings(
        self,
        relation_info: Dict[str, Any],
        personality_profile: Optional[str] = None,
        personality_tags: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        # PRD 4.5.3：一次生成文言风、文艺风、大白话三条，每条 20-50 字
        relation_desc = (
            relation_info.get("primary_label") or "朋友"
        ) + (
            ("-" + (relation_info.get("secondary_label") or "")) if relation_info.get("secondary_label") else ""
        )
        personality_text = personality_profile or "未提供性格画像，仅按关系生成。"
        tags_text = "、".join(personality_tags) if personality_tags else "（未提供）"
        system_prompt = (
            "你是2026丙午马年专属祝福语生成专家，精通不同人际关系的礼仪规范，能结合对方性格特质，生成精准、贴合、符合场景的祝福语。\n"
            "核心任务：结合「关系信息」和「性格画像」，先完成1段关系+性格融合描述，再生成3条不同风格的马年祝福语（文言风、文艺风、大白话），严格遵循规则。\n"
            "硬性规则：2026丙午马年，必须嵌入马年核心关键词（龙马精神、马到成功、马不停蹄、策马扬鞭、丙午启岁、骏业日新等）；每条祝福语严格控制在20-50字；必须严格匹配关系子类的语气、用词、禁忌；祝福语要与性格画像高度契合。\n"
            "三种风格严格区分：文言风（典雅对仗、无口语）；文艺风（温柔意象、氛围感）；大白话（通俗直白、口语化）。\n"
            "若用户明确说了称呼（如弟弟、舅妈、叔叔），需在祝福语中把代词换成真实称呼。不要写过于大白话的祝福语如“祝你在你喜欢的二次元、音乐剧、游戏”等。\n"
            "输出格式必须严格按以下三行，每行一条，不要编号以外的多余内容：\n"
            "文言风：<20-50字祝福语>\n"
            "文艺风：<20-50字祝福语>\n"
            "大白话：<20-50字祝福语>"
        )
        user_prompt = (
            f"关系信息：{relation_desc}\n"
            f"性格画像：{personality_text}\n"
            f"性格标签：{tags_text}\n"
            "请只输出上述三行，每行以「文言风：」「文艺风：」「大白话：」开头。"
        )
        try:
            raw = self._chat(system_prompt, user_prompt, temperature=0.8)
        except _REQUEST_ERRORS as e:
            print("LLM 祝福语生成调用超时或失败，回退到本地三条: %s" % e)
            return super().generate_blessings(relation_info, personality_profile, personality_tags)
        result: List[Dict[str, str]] = []
        for prefix, style in [("文言风", "文言风"), ("文艺风", "文艺风"), ("大白话", "大白话")]:
            text = raw
            for p in [prefix + "：", prefix + ":", prefix + " "]:
                if p in text:
                    text = text.split(p, 1)[-1].split("\n")[0].strip()
                    text = text[:60].rstrip("，。！？")
                    result.append({"style": style, "text": text or "马年大吉，万事顺意。"})
                    break
            else:
                result.append({"style": style, "text": "丙午马年，龙马精神，万事胜意。"})
        if len(result) < 3:
            result.extend([
                {"style": "文言风", "text": "丙午新正，骅骝启岁。敬祝龙马精神，福履绵长。"},
                {"style": "文艺风", "text": "丙午年的风吹来，愿你策马奔赴热爱，岁岁有暖。"},
                {"style": "大白话", "text": "马年到啦，愿你马到成功，阖家安康，万事顺意！"},
            ])
        return result[:3]

    def generate_prompt(
        self,
        relation_info: Dict[str, Any],
        personality_profile: Optional[str],
        blessing_text: str,
        image_description: Optional[str],
        style_key: str,
        extraction: Optional[Dict[str, Any]] = None,
    ) -> str:
        # PRD 4.6.2：贺卡 prompt，祝福语写在贺卡上，风格匹配关系与性格
        primary_label = relation_info.get("primary_label") or "朋友"
        secondary_label = relation_info.get("secondary_label") or ""
        relation_desc = (
            primary_label if not secondary_label else f"{primary_label}-{secondary_label}"
        )
        style_cfg = _get_style_config(style_key)
        style_name = style_cfg.get("name", "自动匹配风格")
        style_suffix = style_cfg.get("prompt_suffix", "")
        personality_text = (personality_profile or "")[:400]
        image_part = image_description or ""
        if extraction:
            image_part = "头像：%s；背景：%s；性格画像：%s" % (
                extraction.get("avatar_desc") or "",
                extraction.get("background_desc") or "",
                personality_text,
            )
        no_real_face = _avatar_suggests_real_face(extraction)
        system_prompt = (
            "你是专业的2026马年贺卡设计师，任务是生成一张【带祝福语的新年贺卡】画图指令。\n"
            "规则：1）竖版新年贺卡，干净高级，居中排版，适合微信发送。\n"
            "2）马年元素：必须包含马、烟花、春字、灯笼、祥云、鞭炮、元宝、平安结、红包等其中2-3种，风格与整体画面统一。\n"
            "3）贺卡风格严格匹配关系与性格：长辈/上级红金喜庆典雅；朋友/密友温柔治愈或活泼；同事简洁商务；师生书香雅致。\n"
            "4）尽量贴合朋友圈元素（头像卡通→软萌细节；二次元→二次元风格；文艺→低饱和柔和）。\n"
            "5）必须把祝福语直接写在贺卡中，文字清晰可读，与贺卡融为一体。\n"
            "6）画风高清精致，无杂乱元素，不要AI水印。只输出画图Prompt，不要多余内容。"
        )
        if no_real_face:
            system_prompt += (
                "\n7）【重要】若用户头像为真人/自拍/人脸：贺卡画面中禁止出现任何真人面部、写实人像或照片级人物。"
                "仅允许插画化/剪影/装饰纹样/马与吉祥物等非真人元素，避免肖像权与观感问题。"
            )
        user_prompt = (
            f"贺卡接收者关系：{relation_desc}\n"
            f"整体性格与气质：{personality_text}\n"
            f"原始截图信息：{image_part}\n"
            f"需要写在贺卡上的祝福语全文：{blessing_text}\n"
            f"期望风格：{style_name}；{style_suffix}\n\n"
            "请用英文描述画面（豆包即梦 Seedream 文生图用），可保留少量中文（如福字）。"
        )
        if no_real_face:
            user_prompt += (
                "\n注意：用户头像是真人/自拍，请在画图指令中明确写出：no realistic human faces, no photorealistic portraits, "
                "illustration or decorative style only, no human facial features."
            )
        try:
            return self._chat(system_prompt, user_prompt, temperature=0.7)
        except _REQUEST_ERRORS as e:
            print("LLM 贺卡 prompt 调用超时或失败，回退到本地模板: %s" % e)
            return super().generate_prompt(
                relation_info, personality_profile, blessing_text,
                image_description, style_key, extraction,
            )


_LLMPROVIDER_SINGLETON: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    global _LLMPROVIDER_SINGLETON
    if _LLMPROVIDER_SINGLETON is not None:
        return _LLMPROVIDER_SINGLETON

    provider_name = os.getenv("LLM_PROVIDER", "mock").strip().lower()
    api_key = os.getenv("LLM_API_KEY")

    if provider_name == "mock" or not api_key:
        _LLMPROVIDER_SINGLETON = MockLLMProvider()
    else:
        _LLMPROVIDER_SINGLETON = SimpleHTTPLLMProvider(provider_name, api_key)

    return _LLMPROVIDER_SINGLETON
