#!/usr/bin/env python3
"""High-level OpenViking diary builder tool.

Builds a diary entry from OpenViking session logs for a specific date + role_id,
then publishes the markdown to OpenViking without relying on MCP add_resource.
Optional image generation uses the existing ZIT image tool implementation and
uploads the resulting file through OpenViking's HTTP API.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, cast

from agent.auxiliary_client import call_llm, extract_content_or_reasoning
from plugins.memory.openviking import _DEFAULT_ENDPOINT, _VikingClient
from tools.registry import registry, tool_error, tool_result
from tools.zit_image_generation_tool import _handle_zit_image_generate

logger = logging.getLogger(__name__)

DEFAULT_ASSISTANT_ROLE = "assistant"
DEFAULT_TARGET_BASE_URI = "viking://resources/diary/rosie_hsu"
DEFAULT_IMAGE_WIDTH = 1024
DEFAULT_IMAGE_HEIGHT = 1536
MAX_SOURCE_CHARS = 24_000
MAX_IMAGE_PROMPT_CHARS = 4_000
DIARY_READ_TIMEOUT_SECONDS = 120.0
DIARY_WRITE_TIMEOUT_SECONDS = 300.0
IMAGE_UPLOAD_TIMEOUT_SECONDS = 300.0
WRITE_VERIFY_ATTEMPTS = 20
WRITE_VERIFY_DELAY_SECONDS = 1.0
IMAGE_VERIFY_ATTEMPTS = 20
IMAGE_VERIFY_DELAY_SECONDS = 1.0
_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")

OPENVIKING_DIARY_BUILD_SCHEMA = {
    "name": "openviking_diary_build",
    "description": (
        "Build a diary entry from OpenViking session logs for a specific date and role_id. "
        "The tool scans viking://session/<date>* recursively, keeps only exact JSONL matches "
        "where role == assistant_role and the assistant identity matches the requested role_id "
        "via role_id (older archives) or peer_id (newer live sessions), then writes the "
        "resulting diary to OpenViking via HTTP API (content/write, fs/mkdir, fs/mv, fs/stat). "
        "If with_image=true, it also generates a matching image, uploads it through the OpenViking "
        "resource API, and appends the verified relative image link to the markdown."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Target date in YYYYMMDD format, e.g. 20260604.",
            },
            "role_id": {
                "type": "string",
                "description": "Assistant identity to match exactly, e.g. rosie.",
            },
            "assistant_role": {
                "type": "string",
                "description": "Message role to match exactly. Defaults to assistant.",
                "default": DEFAULT_ASSISTANT_ROLE,
            },
            "target_base_uri": {
                "type": "string",
                "description": (
                    "Base OpenViking diary directory, e.g. viking://resources/diary/rosie_hsu. "
                    "The tool writes to {target_base_uri}/{date}/content/content.md."
                ),
                "default": DEFAULT_TARGET_BASE_URI,
            },
            "skip_if_exists": {
                "type": "boolean",
                "description": "If the target markdown already exists, skip rebuilding and return the existing URIs.",
                "default": True,
            },
            "with_image": {
                "type": "boolean",
                "description": "Whether to generate, upload, and attach a matching image.",
                "default": True,
            },
            "overwrite_image_link": {
                "type": "boolean",
                "description": "Whether to append/update the markdown image link when an image is available.",
                "default": True,
            },
        },
        "required": ["date", "role_id"],
        "additionalProperties": False,
    },
}


def _normalize_uri_path(base_uri: str) -> str:
    return base_uri.rstrip("/")


def _build_target_uris(date: str, target_base_uri: str) -> Dict[str, str]:
    base = f"{_normalize_uri_path(target_base_uri)}/{date}"
    return {
        "date_root_uri": base,
        "content_dir_uri": f"{base}/content",
        "content_uri": f"{base}/content/content.md",
        "image_dir_uri": f"{base}/image",
    }


def _parse_bool(value: Any, default: bool) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _validate_date(date: str) -> str:
    normalized = str(date or "").strip()
    if not re.fullmatch(r"\d{8}", normalized):
        raise ValueError("date must be an 8-digit string in YYYYMMDD format")
    return normalized


def _validate_required_text(value: Any, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field} is required")
    return normalized


def _check_openviking_diary_requirements() -> bool:
    endpoint = os.environ.get("OPENVIKING_ENDPOINT", _DEFAULT_ENDPOINT)
    try:
        client = _VikingClient(
            endpoint,
            os.environ.get("OPENVIKING_API_KEY", ""),
            account=os.environ.get("OPENVIKING_ACCOUNT", "default"),
            user=os.environ.get("OPENVIKING_USER", "default"),
            agent=os.environ.get("OPENVIKING_AGENT", "hermes"),
        )
    except Exception:
        return False
    return client.health()


def _make_client() -> _VikingClient:
    endpoint = os.environ.get("OPENVIKING_ENDPOINT", _DEFAULT_ENDPOINT)
    return _VikingClient(
        endpoint,
        os.environ.get("OPENVIKING_API_KEY", ""),
        account=os.environ.get("OPENVIKING_ACCOUNT", "default"),
        user=os.environ.get("OPENVIKING_USER", "default"),
        agent=os.environ.get("OPENVIKING_AGENT", "hermes"),
    )


def _unwrap_result(resp: Any) -> Any:
    if isinstance(resp, dict) and "result" in resp:
        return resp.get("result")
    return resp


def _tenant_headers(client: _VikingClient) -> Dict[str, str]:
    headers_builder = getattr(client, "_headers", None)
    if not callable(headers_builder):
        raise RuntimeError("OpenViking client does not expose tenant-aware headers")
    return cast(Dict[str, str], headers_builder(include_tenant=True))


def _tenant_get(client: _VikingClient, path: str, **kwargs) -> Dict[str, Any]:
    httpx_client = getattr(client, "_httpx", None)
    url_builder = getattr(client, "_url", None)
    parse_response = getattr(client, "_parse_response", None)
    if httpx_client and callable(url_builder) and callable(parse_response):
        response = httpx_client.get(
            url_builder(path),
            headers=_tenant_headers(client),
            timeout=kwargs.pop("timeout", 30.0),
            **kwargs,
        )
        raw = parse_response(response)
        return raw if isinstance(raw, dict) else {}

    get_fn = getattr(client, "get", None)
    if callable(get_fn):
        raw = get_fn(path, **kwargs)
        return raw if isinstance(raw, dict) else {}
    raise RuntimeError("OpenViking client does not support tenant-scoped GET requests")


def _tenant_post(
    client: _VikingClient,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Dict[str, Any]:
    httpx_client = getattr(client, "_httpx", None)
    url_builder = getattr(client, "_url", None)
    parse_response = getattr(client, "_parse_response", None)
    if httpx_client and callable(url_builder) and callable(parse_response):
        response = httpx_client.post(
            url_builder(path),
            json=payload or {},
            headers=_tenant_headers(client),
            timeout=kwargs.pop("timeout", 30.0),
            **kwargs,
        )
        raw = parse_response(response)
        return raw if isinstance(raw, dict) else {}

    post_fn = getattr(client, "post", None)
    if callable(post_fn):
        raw = post_fn(path, payload, **kwargs)
        return raw if isinstance(raw, dict) else {}
    raise RuntimeError("OpenViking client does not support tenant-scoped POST requests")


def _tenant_upload_temp_file(
    client: _VikingClient,
    file_path: Path,
    *,
    timeout: float = IMAGE_UPLOAD_TIMEOUT_SECONDS,
) -> str:
    httpx_client = getattr(client, "_httpx", None)
    url_builder = getattr(client, "_url", None)
    parse_response = getattr(client, "_parse_response", None)
    if httpx_client and callable(url_builder) and callable(parse_response):
        import mimetypes

        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        with file_path.open("rb") as f:
            response = httpx_client.post(
                url_builder("/api/v1/resources/temp_upload"),
                files={"file": (file_path.name, f, mime_type)},
                headers={k: v for k, v in _tenant_headers(client).items() if k != "Content-Type"},
                timeout=timeout,
            )
        raw = parse_response(response)
        result = raw.get("result", {}) if isinstance(raw, dict) else {}
        temp_file_id = str(result.get("temp_file_id") or "")
        if not temp_file_id:
            raise RuntimeError("OpenViking temp upload did not return temp_file_id")
        return temp_file_id

    upload_fn = getattr(client, "upload_temp_file", None)
    if callable(upload_fn):
        return str(upload_fn(file_path, timeout=timeout) or "")
    raise RuntimeError("OpenViking client does not support tenant-scoped temp uploads")


def _stat(client: _VikingClient, uri: str) -> Optional[Dict[str, Any]]:
    try:
        raw = _tenant_get(client, "/api/v1/fs/stat", params={"uri": uri})
    except Exception:
        return None
    result = _unwrap_result(raw)
    return result if isinstance(result, dict) else None


def _exists(client: _VikingClient, uri: str) -> bool:
    return _stat(client, uri) is not None


def _is_file(client: _VikingClient, uri: str) -> bool:
    stat = _stat(client, uri)
    return bool(stat) and not _entry_is_dir(stat)


def _delete_uri(client: _VikingClient, uri: str, *, recursive: bool = True) -> Dict[str, Any]:
    delete_fn = getattr(client, "delete", None)
    if callable(delete_fn):
        raw = delete_fn("/api/v1/fs", params={"uri": uri, "recursive": recursive})
        result = _unwrap_result(raw)
        return result if isinstance(result, dict) else {}

    httpx_client = getattr(client, "_httpx", None)
    url_builder = getattr(client, "_url", None)
    parse_response = getattr(client, "_parse_response", None)
    if not httpx_client or not callable(url_builder) or not callable(parse_response):
        raise RuntimeError("OpenViking client does not support delete operations")

    response = httpx_client.request(
        "DELETE",
        url_builder("/api/v1/fs"),
        headers=_tenant_headers(client),
        params={"uri": uri, "recursive": recursive},
        timeout=30.0,
    )
    raw = parse_response(response)
    result = _unwrap_result(raw)
    return result if isinstance(result, dict) else {}


def _mkdir(client: _VikingClient, uri: str) -> None:
    if _exists(client, uri):
        return
    _tenant_post(client, "/api/v1/fs/mkdir", {"uri": uri})


def _read_content(client: _VikingClient, uri: str, *, timeout: float = DIARY_READ_TIMEOUT_SECONDS) -> str:
    raw = _tenant_get(client, "/api/v1/content/read", params={"uri": uri}, timeout=timeout)
    result = _unwrap_result(raw)
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return str(result.get("content", "") or result.get("text", "") or "")
    return ""


def _is_timeout_error(exc: Exception) -> bool:
    return "timed out" in str(exc).lower()


def _write_content(client: _VikingClient, uri: str, content: str, *, mode: str = "replace") -> Dict[str, Any]:
    requested_mode = mode
    if mode == "replace" and not _exists(client, uri):
        requested_mode = "create"
    try:
        raw = _tenant_post(
            client,
            "/api/v1/content/write",
            {"uri": uri, "content": content, "mode": requested_mode, "wait": True},
            timeout=DIARY_WRITE_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        if _is_timeout_error(exc):
            verifier_client = _make_client() if isinstance(client, _VikingClient) else client
            for attempt in range(WRITE_VERIFY_ATTEMPTS):
                if _is_file(verifier_client, uri):
                    verified = _read_content(verifier_client, uri)
                    if verified == content:
                        logger.warning(
                            "OpenViking content/write timed out but verified content exists at %s after %s attempt(s)",
                            uri,
                            attempt + 1,
                        )
                        return {
                            "uri": uri,
                            "timed_out_but_verified": True,
                            "written_bytes": len(content),
                            "verification_attempts": attempt + 1,
                        }
                if attempt < WRITE_VERIFY_ATTEMPTS - 1:
                    time.sleep(WRITE_VERIFY_DELAY_SECONDS)
        raise
    result = _unwrap_result(raw)
    return result if isinstance(result, dict) else {}


def _ls_entries(client: _VikingClient, uri: str, *, recursive: bool = False) -> List[Dict[str, Any]]:
    raw = _tenant_get(
        client,
        "/api/v1/fs/ls",
        params={
            "uri": uri,
            "recursive": recursive,
            "limit": 5000,
            "node_limit": 5000,
            "show_all_hidden": True,
        },
    )
    result = _unwrap_result(raw)
    if isinstance(result, list):
        return [entry for entry in result if isinstance(entry, dict)]
    if isinstance(result, dict):
        for key in ("entries", "items", "children"):
            value = result.get(key)
            if isinstance(value, list):
                return [entry for entry in value if isinstance(entry, dict)]
    return []


def _entry_uri(entry: Dict[str, Any]) -> str:
    return str(entry.get("uri") or "")


def _entry_name(entry: Dict[str, Any]) -> str:
    name = entry.get("name") or entry.get("rel_path") or entry.get("path")
    if name:
        return str(name)
    uri = _entry_uri(entry)
    return uri.rstrip("/").rsplit("/", 1)[-1] if uri else ""


def _entry_is_dir(entry: Dict[str, Any]) -> bool:
    if "isDir" in entry:
        return bool(entry.get("isDir"))
    if "is_dir" in entry:
        return bool(entry.get("is_dir"))
    return str(entry.get("type") or "").lower() == "dir"


def _list_markdown_files(client: _VikingClient, uri: str) -> List[str]:
    entries = _ls_entries(client, uri, recursive=True)
    matched = []
    for entry in entries:
        if _entry_is_dir(entry):
            continue
        child_uri = _entry_uri(entry)
        if child_uri.lower().endswith(".md"):
            matched.append(child_uri)
    return sorted(set(matched))


def _normalize_wrapped_markdown_target(client: _VikingClient, target_uri: str) -> Optional[str]:
    stat = _stat(client, target_uri)
    if not stat or not _entry_is_dir(stat):
        return None

    markdown_files = _list_markdown_files(client, target_uri)
    if not markdown_files:
        raise RuntimeError(
            f"Target content URI is a directory, not a file, and contains no markdown to recover: {target_uri}"
        )
    if len(markdown_files) != 1:
        raise RuntimeError(
            f"Target content URI is a directory wrapper with multiple markdown files; refusing ambiguous auto-repair: {target_uri}"
        )

    nested_uri = markdown_files[0]
    nested_content = _read_content(client, nested_uri)
    if not nested_content.strip():
        raise RuntimeError(f"Wrapped markdown target was empty and could not be normalized: {nested_uri}")

    _delete_uri(client, target_uri, recursive=True)
    _write_content(client, target_uri, nested_content, mode="create")
    if not _is_file(client, target_uri):
        raise RuntimeError(f"Failed to normalize wrapped markdown target into a file: {target_uri}")
    return nested_uri


def _collect_session_uris(client: _VikingClient, date: str) -> List[str]:
    entries = _ls_entries(client, "viking://session", recursive=False)
    matched = []
    for entry in entries:
        if not _entry_is_dir(entry):
            continue
        uri = _entry_uri(entry)
        name = _entry_name(entry)
        if name.startswith(date):
            matched.append(uri)
    return sorted(set(matched))


def _collect_messages_jsonl_uris(client: _VikingClient, session_uri: str) -> List[str]:
    entries = _ls_entries(client, session_uri, recursive=True)
    matched = []
    for entry in entries:
        if _entry_is_dir(entry):
            continue
        uri = _entry_uri(entry)
        if uri.endswith("/messages.jsonl"):
            matched.append(uri)
    # Fall back to the conventional root file if recursive ls omitted it.
    root_file = f"{session_uri.rstrip('/')}/messages.jsonl"
    if _exists(client, root_file):
        matched.append(root_file)
    return sorted(set(matched))


def _normalize_message_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                item_text = item.strip()
                if item_text:
                    parts.append(item_text)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
                    continue
                if item.get("type") == "input_text" and isinstance(item.get("text"), str):
                    text2 = item["text"].strip()
                    if text2:
                        parts.append(text2)
        return "\n".join(parts).strip()
    if isinstance(value, dict):
        for key in ("text", "content", "message"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _message_identity_matches(item: Dict[str, Any], *, role_id: str) -> bool:
    """Match assistant identity across old and new OpenViking session payloads.

    Older archives store the assistant identity as `role_id`, while newer live
    session JSONL stores it as `peer_id` on assistant messages.
    """
    message_role_id = str(item.get("role_id") or "").strip()
    if message_role_id == role_id:
        return True
    message_peer_id = str(item.get("peer_id") or "").strip()
    return message_peer_id == role_id



def _parse_jsonl_messages(text: str, *, source_uri: str, assistant_role: str, role_id: str) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for index, raw_line in enumerate((text or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("Skipping invalid JSONL line %s:%s", source_uri, index)
            continue
        if item.get("role") != assistant_role or not _message_identity_matches(item, role_id=role_id):
            continue
        content = _normalize_message_content(item.get("content"))
        if not content:
            content = _normalize_message_content(item.get("parts"))
        if not content:
            content = _normalize_message_content(item.get("message"))
        if not content:
            continue
        matches.append(
            {
                "source_uri": source_uri,
                "line_no": index,
                "message_id": item.get("id") or item.get("message_id"),
                "timestamp": item.get("created_at") or item.get("timestamp") or item.get("time"),
                "content": content,
            }
        )
    return matches


def _collect_matching_material(
    client: _VikingClient,
    *,
    date: str,
    assistant_role: str,
    role_id: str,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    session_uris = _collect_session_uris(client, date)
    matches: List[Dict[str, Any]] = []
    matched_sessions: set[str] = set()
    for session_uri in session_uris:
        for messages_uri in _collect_messages_jsonl_uris(client, session_uri):
            content = _read_content(client, messages_uri)
            items = _parse_jsonl_messages(
                content,
                source_uri=messages_uri,
                assistant_role=assistant_role,
                role_id=role_id,
            )
            if items:
                matched_sessions.add(session_uri)
                matches.extend(items)
    matches.sort(key=lambda item: (str(item.get("timestamp") or ""), item["source_uri"], item["line_no"]))
    return sorted(matched_sessions), matches


def _truncate_joined_material(matches: List[Dict[str, Any]], *, max_chars: int = MAX_SOURCE_CHARS) -> str:
    chunks: List[str] = []
    total = 0
    for item in matches:
        block = (
            f"[source] {item['source_uri']}#L{item['line_no']}\n"
            f"[timestamp] {item.get('timestamp') or 'unknown'}\n"
            f"{item['content']}\n"
        )
        if total and total + len(block) > max_chars:
            break
        chunks.append(block)
        total += len(block)
    return "\n".join(chunks)


def _generate_diary_markdown(*, date: str, role_id: str, assistant_role: str, matches: List[Dict[str, Any]]) -> str:
    source_material = _truncate_joined_material(matches)
    iso_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
    prompt = (
        f"你現在要根據提供的 session 素材，替 role_id={role_id} 寫一篇 {iso_date} 的日記。\n"
        "硬性規則：\n"
        "1. 只能使用提供素材中的事實，不可捏造未發生的事件。\n"
        "2. 使用第一人稱。\n"
        "3. 使用自然的繁體中文。\n"
        f"4. 只保留同時符合 role={assistant_role} 且 role_id={role_id} 的語氣與觀點。\n"
        "5. 若素材很少，就寫短一點，但仍要像真正的日記，不要變成條列摘要。\n"
        "6. 請直接輸出 markdown，不要加 ``` 區塊。\n"
        f"7. 標題固定為：# {iso_date}\n\n"
        "素材如下：\n\n"
        f"{source_material}"
    )
    response = call_llm(
        task="openviking_diary_build",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=4096,
        timeout=120,
    )
    text = extract_content_or_reasoning(response).strip()
    if not text:
        raise RuntimeError("Diary LLM returned empty content")
    if not text.lstrip().startswith("#"):
        text = f"# {iso_date}\n\n{text}"
    return text.strip() + "\n"


def _choose_image_workflow(role_id: str, target_base_uri: str) -> str:
    lowered = f"{role_id} {target_base_uri}".lower()
    return "rosie" if "rosie" in lowered else "general"


def _generate_image_prompt(*, date: str, role_id: str, diary_markdown: str) -> str:
    prompt = (
        f"根據下面這篇 {date} 的日記，生成一段單行圖片提示詞。\n"
        "要求：\n"
        "1. 適合生成寫實、生活感、情緒細膩的單人場景。\n"
        "2. 不要提到文字排版、logo、水印、分鏡。\n"
        f"3. 若角色是 {role_id}，提示詞要保留她當天的情緒氛圍。\n"
        "4. 只輸出提示詞本身，不要解釋。\n\n"
        f"日記：\n{diary_markdown[:MAX_IMAGE_PROMPT_CHARS]}"
    )
    response = call_llm(
        task="openviking_diary_build",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=400,
        timeout=90,
    )
    text = extract_content_or_reasoning(response).strip()
    if not text:
        raise RuntimeError("Image prompt LLM returned empty content")
    return text.replace("\n", " ").strip()


def _call_image_generator(*, prompt: str, role_id: str, target_base_uri: str) -> Path:
    workflow = _choose_image_workflow(role_id, target_base_uri)
    raw = _handle_zit_image_generate(
        {
            "prompt": prompt,
            "workflow": workflow,
            "width": DEFAULT_IMAGE_WIDTH,
            "height": DEFAULT_IMAGE_HEIGHT,
        }
    )
    data = json.loads(raw)
    if not data.get("success"):
        raise RuntimeError(data.get("error") or "Image generation failed")
    image_path = Path(str(data.get("image") or "")).expanduser()
    if not image_path.exists() or image_path.stat().st_size <= 0:
        raise RuntimeError(f"Generated image not found: {image_path}")
    return image_path


def _is_image_uri(uri: str) -> bool:
    lowered = uri.lower()
    return lowered.endswith(_IMAGE_EXTENSIONS)


def _list_image_files(client: _VikingClient, uri: str) -> List[str]:
    entries = _ls_entries(client, uri, recursive=True)
    result: List[str] = []
    for entry in entries:
        if _entry_is_dir(entry):
            continue
        child_uri = _entry_uri(entry)
        if _is_image_uri(child_uri):
            result.append(child_uri)
    stat = _stat(client, uri)
    if stat and not (_entry_is_dir(stat)) and _is_image_uri(uri):
        result.append(uri)
    return sorted(set(result))


def _finalize_uploaded_image_candidate(
    client: _VikingClient,
    *,
    image_dir_uri: str,
    candidate: str,
) -> str:
    final_uri = f"{image_dir_uri.rstrip('/')}/{Path(candidate).name}"
    if candidate != final_uri:
        _tenant_post(client, "/api/v1/fs/mv", {"from_uri": candidate, "to_uri": final_uri})
    if not _exists(client, final_uri):
        raise RuntimeError(f"Uploaded image could not be verified at {final_uri}")
    return final_uri


def _discover_uploaded_image_candidate(
    client: _VikingClient,
    *,
    image_dir_uri: str,
    before: set[str],
    root_uri: str = "",
) -> Optional[str]:
    after = set(_list_image_files(client, image_dir_uri))
    created = sorted(after - before)
    candidates: List[str] = created[:]
    if root_uri and root_uri not in candidates:
        if _is_image_uri(root_uri):
            candidates.append(root_uri)
        else:
            candidates.extend(uri for uri in _list_image_files(client, root_uri) if uri not in candidates)
    return candidates[0] if candidates else None


def _append_image_link(markdown: str, image_uri: str) -> str:
    relative_path = f"../image/{Path(image_uri).name}"
    stripped = markdown.rstrip()
    if re.search(r"!\[[^\]]*\]\([^\)]*\)", stripped):
        stripped = re.sub(r"!\[[^\]]*\]\([^\)]*\)", f"![diary image]({relative_path})", stripped, count=1)
        return stripped + "\n"
    return stripped + f"\n\n![diary image]({relative_path})\n"


def _upload_image_to_openviking(client: _VikingClient, *, image_path: Path, image_dir_uri: str) -> str:
    _mkdir(client, image_dir_uri)
    before = set(_list_image_files(client, image_dir_uri))
    temp_file_id = _tenant_upload_temp_file(client, image_path, timeout=IMAGE_UPLOAD_TIMEOUT_SECONDS)
    root_uri = ""
    try:
        response = _tenant_post(
            client,
            "/api/v1/resources",
            {
                "temp_file_id": temp_file_id,
                "parent": image_dir_uri,
                "create_parent": True,
                "wait": True,
                "timeout": 180,
                "source_name": image_path.name,
                "directly_upload_media": True,
            },
            timeout=IMAGE_UPLOAD_TIMEOUT_SECONDS,
        )
        result = response.get("result", {}) if isinstance(response, dict) else {}
        root_uri = str(result.get("root_uri") or "")
        candidate = _discover_uploaded_image_candidate(
            client,
            image_dir_uri=image_dir_uri,
            before=before,
            root_uri=root_uri,
        )
        if not candidate:
            raise RuntimeError("Image upload completed but no image URI was discovered")
        return _finalize_uploaded_image_candidate(client, image_dir_uri=image_dir_uri, candidate=candidate)
    except Exception as exc:
        if not _is_timeout_error(exc):
            raise
        verifier_client = _make_client() if isinstance(client, _VikingClient) else client
        for attempt in range(IMAGE_VERIFY_ATTEMPTS):
            candidate = _discover_uploaded_image_candidate(
                verifier_client,
                image_dir_uri=image_dir_uri,
                before=before,
                root_uri=root_uri,
            )
            if candidate:
                final_uri = _finalize_uploaded_image_candidate(
                    verifier_client,
                    image_dir_uri=image_dir_uri,
                    candidate=candidate,
                )
                logger.warning(
                    "OpenViking image upload timed out but verified image exists at %s after %s attempt(s)",
                    final_uri,
                    attempt + 1,
                )
                return final_uri
            if attempt < IMAGE_VERIFY_ATTEMPTS - 1:
                time.sleep(IMAGE_VERIFY_DELAY_SECONDS)
        raise


def _discover_existing_image_uri(client: _VikingClient, image_dir_uri: str) -> Optional[str]:
    if not _exists(client, image_dir_uri):
        return None
    images = _list_image_files(client, image_dir_uri)
    return images[0] if images else None


def openviking_diary_build_tool(
    *,
    date: str,
    role_id: str,
    assistant_role: str = DEFAULT_ASSISTANT_ROLE,
    target_base_uri: str = DEFAULT_TARGET_BASE_URI,
    skip_if_exists: bool = True,
    with_image: bool = True,
    overwrite_image_link: bool = True,
) -> str:
    try:
        date = _validate_date(date)
        role_id = _validate_required_text(role_id, "role_id")
        assistant_role = _validate_required_text(assistant_role, "assistant_role")
        target_base_uri = _validate_required_text(target_base_uri, "target_base_uri")
        skip_if_exists = _parse_bool(skip_if_exists, True)
        with_image = _parse_bool(with_image, True)
        overwrite_image_link = _parse_bool(overwrite_image_link, True)
        client = _make_client()
    except Exception as exc:
        return tool_error(str(exc), success=False, error_type="invalid_request")

    if not client.health():
        return tool_error("OpenViking server is not reachable", success=False, error_type="unavailable")

    uris = _build_target_uris(date, target_base_uri)
    content_uri = uris["content_uri"]
    image_dir_uri = uris["image_dir_uri"]

    try:
        normalized_from = None
        if _exists(client, content_uri):
            normalized_from = _normalize_wrapped_markdown_target(client, content_uri)

        if skip_if_exists and _is_file(client, content_uri):
            return tool_result(
                created=False,
                date=date,
                role_id=role_id,
                matched_sessions=[],
                matched_message_count=0,
                content_uri=content_uri,
                image_uri=_discover_existing_image_uri(client, image_dir_uri),
                reason="already_exists_skipped" if not normalized_from else "already_exists_normalized",
                normalized_from_uri=normalized_from,
            )

        matched_sessions, matches = _collect_matching_material(
            client,
            date=date,
            assistant_role=assistant_role,
            role_id=role_id,
        )
        if not matches:
            return tool_result(
                created=False,
                date=date,
                role_id=role_id,
                matched_sessions=matched_sessions,
                matched_message_count=0,
                content_uri=None,
                image_uri=None,
                reason="no_matching_material",
            )

        markdown = _generate_diary_markdown(
            date=date,
            role_id=role_id,
            assistant_role=assistant_role,
            matches=matches,
        )

        _mkdir(client, uris["content_dir_uri"])
        image_uri = None
        reason = None
        image_error = None

        if with_image:
            try:
                image_prompt = _generate_image_prompt(date=date, role_id=role_id, diary_markdown=markdown)
                image_path = _call_image_generator(prompt=image_prompt, role_id=role_id, target_base_uri=target_base_uri)
                image_uri = _upload_image_to_openviking(client, image_path=image_path, image_dir_uri=image_dir_uri)
                if overwrite_image_link and image_uri:
                    markdown = _append_image_link(markdown, image_uri)
            except Exception as exc:
                logger.warning("openviking_diary_build image step failed: %s", exc)
                image_error = str(exc)
                reason = "image_failed"

        write_result = _write_content(client, content_uri, markdown, mode="replace")
        warning = None
        warning_details: Optional[Dict[str, Any]] = None
        if write_result.get("timed_out_but_verified"):
            warning = "content_write_timeout_verified"
            warning_details = dict(write_result)

        verified_markdown = ""
        try:
            verified_markdown = _read_content(client, content_uri)
        except Exception as exc:
            if not _is_timeout_error(exc) or not _is_file(client, content_uri):
                raise
            logger.warning("OpenViking diary readback timed out but file exists at %s", content_uri)
            if warning is None:
                warning = "content_readback_timeout_file_exists"
                warning_details = {"uri": content_uri, "readback_timed_out": True}
            elif warning_details is not None:
                warning_details = dict(warning_details)
                warning_details["readback_timed_out"] = True

        if not verified_markdown.strip() and not _is_file(client, content_uri):
            raise RuntimeError(f"Diary write verification failed for {content_uri}")
        if image_uri and not _exists(client, image_uri):
            raise RuntimeError(f"Image verification failed for {image_uri}")

        payload: Dict[str, Any] = {
            "created": True,
            "date": date,
            "role_id": role_id,
            "matched_sessions": matched_sessions,
            "matched_message_count": len(matches),
            "content_uri": content_uri,
            "image_uri": image_uri,
            "reason": reason,
        }
        if warning:
            payload["warning"] = warning
        if warning_details:
            payload["warning_details"] = warning_details
        if image_error:
            payload["image_error"] = image_error
        return tool_result(payload)
    except Exception as exc:
        logger.exception("openviking_diary_build failed")
        return tool_error(str(exc), success=False, error_type="runtime_error")


registry.register(
    name="openviking_diary_build",
    toolset="openviking",
    schema=OPENVIKING_DIARY_BUILD_SCHEMA,
    handler=lambda args, **kw: openviking_diary_build_tool(
        date=args.get("date", ""),
        role_id=args.get("role_id", ""),
        assistant_role=args.get("assistant_role", DEFAULT_ASSISTANT_ROLE),
        target_base_uri=args.get("target_base_uri", DEFAULT_TARGET_BASE_URI),
        skip_if_exists=args.get("skip_if_exists", True),
        with_image=args.get("with_image", True),
        overwrite_image_link=args.get("overwrite_image_link", True),
    ),
    check_fn=_check_openviking_diary_requirements,
    emoji="📔",
)
