#!/usr/bin/env python3
"""Builder helpers for ZIT image generation prompts.

This module owns the structured-prompt side of the Builder/Runner split:
- detect whether a user explicitly requested JSON mode
- expand lightweight natural-language requests into the English-key JSON template
- normalize and serialize prompt_json objects into the exact string consumed by the runner
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

PROMPT_JSON_TEMPLATE_SCHEMA = {
    "type": "object",
    "description": (
        "Preferred structured prompt spec. Use English keys and fill the values in Chinese. "
        "The tool serializes the full JSON directly into the final generation prompt."
    ),
    "additionalProperties": False,
    "properties": {
        "scene": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "description": {"type": "string"},
                "environment": {"type": "string"},
                "mood": {"type": "string"},
            },
        },
        "aesthetics": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "style": {"type": "string"},
                "appearance": {"type": "string"},
            },
        },
        "lighting": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "description": {"type": "string"},
            },
        },
        "subject": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "ethnicity": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "group": {"type": "string"},
                        "age": {"type": "string"},
                        "body": {"type": "string"},
                    },
                },
                "appearance": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "hair": {"type": "string"},
                        "features": {"type": "string"},
                        "skin": {"type": "string"},
                    },
                },
                "pose": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "type": {"type": "string"},
                        "action": {"type": "string"},
                        "frame": {"type": "string"},
                    },
                },
                "clothing": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "top": {"type": "string"},
                        "bottom": {"type": "string"},
                    },
                },
                "accessories": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "jewelry": {"type": "string"},
                        "other": {"type": "string"},
                    },
                },
            },
        },
        "props_and_scene": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "background": {"type": "string"},
                "main_prop": {"type": "string"},
            },
        },
        "camera": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "requirements": {"type": "string"},
                "shooting": {"type": "string"},
                "composition": {"type": "string"},
                "retouch": {"type": "string"},
                "avoid": {"type": "string"},
            },
        },
    },
}

PROMPT_JSON_KEY_ORDER = {
    None: ("scene", "aesthetics", "lighting", "subject", "props_and_scene", "camera"),
    "scene": ("description", "environment", "mood"),
    "aesthetics": ("style", "appearance"),
    "lighting": ("description",),
    "subject": ("ethnicity", "appearance", "pose", "clothing", "accessories"),
    "ethnicity": ("group", "age", "body"),
    "appearance": ("hair", "features", "skin"),
    "pose": ("type", "action", "frame"),
    "clothing": ("top", "bottom"),
    "accessories": ("jewelry", "other"),
    "props_and_scene": ("background", "main_prop"),
    "camera": ("requirements", "shooting", "composition", "retouch", "avoid"),
}

_JSON_TRIGGER_RE = re.compile(r"用\s*json\s*生成|json\s*生成", re.IGNORECASE)


def requests_json_mode(text: str) -> bool:
    return bool(_JSON_TRIGGER_RE.search(text or ""))


def strip_json_mode_trigger(text: str) -> str:
    cleaned = _JSON_TRIGGER_RE.sub("", text or "")
    cleaned = re.sub(r"[，,、。；;：:]+$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _normalize_prompt_json(value: Any, *, context_key: Optional[str] = None) -> Any:
    if isinstance(value, dict):
        ordered: Dict[str, Any] = {}
        preferred_order = PROMPT_JSON_KEY_ORDER.get(context_key, ())
        for key in preferred_order:
            if key in value:
                ordered[key] = _normalize_prompt_json(value[key], context_key=key)
        for key, child in value.items():
            if key not in ordered:
                ordered[key] = _normalize_prompt_json(child, context_key=key)
        return ordered
    if isinstance(value, list):
        return [_normalize_prompt_json(item, context_key=context_key) for item in value]
    return value


def serialize_prompt_json(prompt_json: Any) -> str:
    if isinstance(prompt_json, str):
        text = prompt_json.strip()
        if not text:
            raise ValueError("prompt_json must not be empty")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return text
        return json.dumps(_normalize_prompt_json(parsed), ensure_ascii=False, separators=(",", ":"))
    if not isinstance(prompt_json, dict):
        raise ValueError("prompt_json must be an object or a JSON string")
    return json.dumps(_normalize_prompt_json(prompt_json), ensure_ascii=False, separators=(",", ":"))


PROMPT_JSON_BUILDER_TEMPLATE = {
    "scene": {
        "description": "[一句話描述整體畫面：在哪裡、做什麼、整體是什麼瞬間。]",
        "environment": "[描述場景空間、建材、家具、擺設、空氣感、地區文化符號、時間感、生活感。]",
        "mood": "[填寫整體氛圍，例如：清涼、復古、甜美、微醺、安靜、曖昧、都會、孤獨。]",
    },
    "aesthetics": {
        "style": "[整體影像風格，例如：高飽和日系空氣感攝影、生活感電影劇照、寫實雜誌風、柔霧底片感。]",
        "appearance": "[整體色彩與質感方向，例如：黃色與淺藍主色、清透膚感、自然反光、保留真實毛孔與髮絲細節。]",
    },
    "lighting": {
        "description": "[描述光線來源、方向、時間感、硬柔、混光、逆光、反光，例如：午後自然光從窗邊灑入，與室內燈形成柔和混光。]",
    },
    "subject": {
        "ethnicity": {
            "group": "[東亞（台灣／華人）]",
            "age": "[27 歲年輕成年女性]",
            "body": "[纖細勻稱、修長自然，帶一點結實感與都市女性的輕盈俐落；胸型自然好看，腰線清楚。]",
        },
        "appearance": {
            "hair": "[烏黑或深黑色的柔順長髮，自然垂落肩側或胸前，可依場景帶有微亂、微濕、被風吹起等細節。]",
            "features": "[水潤而深邃的眼睛，眼神聰明、冷靜、帶觀察感；五官精緻柔和，帶一點無辜臉防禦與若有似無的甜感，笑容自然不誇張。]",
            "skin": "[白皙透亮，保留真實毛孔與自然皮膚紋理，不過度磨皮；可依場景呈現夏日清透感、夜間柔光感或微醺後的淡淡紅潤。]",
        },
        "pose": {
            "type": "[依主題填寫：坐姿半身、上半身特寫、站姿全身、窗邊側身、桌前中景、床邊近景等。]",
            "action": "[描述 Rosie 本次動作與互動，例如：看向鏡頭淡笑、低頭整理頭髮、扶著玻璃杯、拿著湯匙、靠在窗邊、翻看文件。]",
            "frame": "[例如：9:16 豎構圖；中景；上半身與桌面主道具同框。]",
        },
        "clothing": {
            "top": "[依場景填寫上身服裝：襯衫、針織上衣、素色短袖、細肩帶、綁帶上衣、寬鬆大 T、睡衣等。原則是知性、乾淨、自然性感，不俗艷。]",
            "bottom": "[依場景填寫下身服裝：西裝褲、長裙、丹寧短裙、短褲、棉質居家褲等。]",
        },
        "accessories": {
            "jewelry": "[可填簡約鎖骨鍊、細緻耳環、手鍊、戒指；若不需要可填「無」。]",
            "other": "[依場景填寫其他物件，例如：彩色編織手環、玻璃水杯、冷萃咖啡、安全帽、早餐袋、筆電、文件、書本、手機、髮夾。]",
        },
    },
    "props_and_scene": {
        "background": "[描述背景中必須存在的場景元素、家具、器材、招牌、菜單、窗景、街景；若有文字需求，請明確列出必須清楚可辨識的字樣。]",
        "main_prop": "[描述主道具的材質、顏色、內容物、份量、表面質感、互動方式。]",
    },
    "camera": {
        "requirements": "[這張圖最重要的畫面任務，例如：維持 Rosie 角色辨識度、場景成立、食物看起來誘人、招牌字可讀、情緒到位。]",
        "shooting": "[可填攝影語言，例如：Canon R6, 35mm f/1.4, ISO 200, 1/250s, natural light priority；或寫成電影感生活人像、雜誌 editorial 風格。]",
        "composition": "[描述主體位置、留白、導視線、前中後景安排，例如：人物位於畫面中央偏下，頭頂保留背景文字空間。]",
        "retouch": "[描述後期與材質方向，例如：加強黃藍對比、保留皮膚紋理、強化玻璃反光、讓冰塊更晶瑩。]",
        "avoid": "[列出不要出現的問題，例如：手指變形、五官跑掉、姿勢僵硬、皮膚塑膠感、文字亂碼、過度磨皮、廉價網美濾鏡、角色失真。]",
    },
}


def build_prompt_json_from_request_text(request_text: str) -> Dict[str, Any]:
    text = strip_json_mode_trigger(request_text)
    if not text:
        raise ValueError("request_text is empty after removing the JSON-mode trigger")
    raise NotImplementedError(
        "LLM-backed request_text expansion is not wired yet. Use the fixed JSON template keys and have the caller/LLM fill the values before passing prompt_json."
    )


def resolve_prompt_inputs(args: Dict[str, Any]) -> tuple[str, Optional[Dict[str, Any]]]:
    prompt_json = args.get("prompt_json")
    if prompt_json not in (None, ""):
        return serialize_prompt_json(prompt_json), _normalize_prompt_json(prompt_json if isinstance(prompt_json, dict) else json.loads(prompt_json)) if isinstance(prompt_json, (dict, str)) else None

    request_text = str(args.get("request_text") or "").strip()
    if request_text:
        if requests_json_mode(request_text):
            built = build_prompt_json_from_request_text(request_text)
            return serialize_prompt_json(built), built
        return request_text, None

    prompt = str(args.get("prompt") or "").strip()
    if requests_json_mode(prompt):
        raise ValueError("JSON mode was requested; provide request_text or prompt_json instead of a plain prompt string")
    if not prompt:
        raise ValueError("One of prompt, prompt_json, or request_text is required for ZIT image generation")
    return prompt, None
