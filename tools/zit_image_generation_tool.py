#!/usr/bin/env python3
"""ZIT Image Generation tool.

Runs the rosie-agent profile's bundled ZIT Comfy Cloud workflows as a first-class
Hermes tool. The workflow assets are immutable: this module only validates and
reads them, then passes their paths to the ComfyUI runner.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from hermes_constants import get_hermes_home
from tools.registry import registry, tool_error, tool_result

COMFY_CLOUD_HOST = "https://cloud.comfy.org"
MAX_SEED = 1_125_899_906_842_624
DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 1024
VALID_WORKFLOWS = {"rosie", "general"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

ZIT_IMAGE_GENERATE_SCHEMA = {
    "name": "zit_image_generate",
    "description": (
        "Generate an image through the bundled ZIT Comfy Cloud workflows. "
        "Use workflow='rosie' for Rosie/許御琪 images, workflow='general' for "
        "non-Rosie images, or workflow='auto' to infer from the prompt. The "
        "workflow assets are immutable and must never be modified."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Final English image prompt to send to the selected workflow.",
            },
            "workflow": {
                "type": "string",
                "enum": ["auto", "rosie", "general"],
                "description": "Workflow selector. auto infers rosie when the prompt clearly concerns Rosie.",
                "default": "auto",
            },
            "width": {
                "type": "integer",
                "description": "Image width in pixels. Defaults to 1024.",
                "default": DEFAULT_WIDTH,
            },
            "height": {
                "type": "integer",
                "description": "Image height in pixels. Defaults to 1024.",
                "default": DEFAULT_HEIGHT,
            },
            "seed": {
                "type": "integer",
                "description": f"Optional seed. If omitted, a random integer from 0 to {MAX_SEED} is used.",
            },
        },
        "required": ["prompt"],
        "additionalProperties": False,
    },
}


def _skill_dir() -> Path:
    return get_hermes_home() / "skills" / "creative" / "zit-image-generation"


def _comfy_runner() -> Path:
    return get_hermes_home() / "skills" / "creative" / "comfyui" / "scripts" / "run_workflow.py"


def _workflow_dir(workflow: str) -> Path:
    return _skill_dir() / "assets" / "workflows" / workflow


def _asset_paths(workflow: str) -> tuple[Path, Path]:
    base = _workflow_dir(workflow)
    return base / "workflow.json", base / "schema.json"


def _image_cache_dir() -> Path:
    path = get_hermes_home() / "cache" / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_output_dir() -> Path:
    path = get_hermes_home() / "cache" / "zit-image-generation" / f"run_{uuid.uuid4().hex[:12]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _contains_rosie_reference(prompt: str) -> bool:
    lowered = prompt.lower()
    tokens = (
        "rosie",
        "許御琪",
        "御琪",
        "小琪",
        "逾期",
        "產學合作專員",
    )
    return any(token in lowered or token in prompt for token in tokens)


def resolve_workflow(workflow: Optional[str], prompt: str) -> str:
    """Resolve auto/explicit workflow selection to rosie or general."""
    selected = (workflow or "auto").strip().lower()
    if selected in VALID_WORKFLOWS:
        return selected
    if selected and selected != "auto":
        raise ValueError("workflow must be one of: auto, rosie, general")
    return "rosie" if _contains_rosie_reference(prompt or "") else "general"


def _coerce_positive_int(value: Any, default: int, field: str) -> int:
    if value is None or value == "":
        return default
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if number <= 0:
        raise ValueError(f"{field} must be greater than 0")
    return number


def _coerce_seed(seed: Any) -> int:
    if seed is None or seed == "":
        return secrets.randbelow(MAX_SEED + 1)
    try:
        number = int(seed)
    except (TypeError, ValueError) as exc:
        raise ValueError("seed must be an integer") from exc
    if number < 0 or number > MAX_SEED:
        raise ValueError(f"seed must be between 0 and {MAX_SEED}")
    return number


def build_runtime_args(*, workflow: str, prompt: str, width: int, height: int, seed: int) -> Dict[str, Any]:
    """Build the --args object for the selected immutable workflow."""
    prompt_key = "user_prompt" if workflow == "rosie" else "prompt"
    return {
        prompt_key: prompt,
        "width": width,
        "height": height,
        "seed": seed,
    }


def _looks_like_asset_mutation_request(prompt: str) -> bool:
    """Reject attempts to use the generator prompt as an asset-edit command.

    The tool has no asset-write parameters, but fail closed when a caller puts an
    explicit mutation instruction in the prompt. The real protection is that this
    module never opens assets in write mode or passes them to a mutating helper.
    """
    lowered = (prompt or "").lower()
    mentions_assets = "assets" in lowered or "workflow.json" in lowered or "schema.json" in lowered
    mutation_words = (
        "modify", "patch", "overwrite", "rewrite", "regenerate", "delete",
        "remove", "rename", "move", "format", "update", "edit", "改", "修改",
        "覆寫", "刪除", "搬移", "重新命名", "格式化", "更新",
    )
    return mentions_assets and any(word in lowered for word in mutation_words)


def _validate_assets(workflow: str) -> tuple[Path, Path]:
    workflow_path, schema_path = _asset_paths(workflow)
    missing = [str(path) for path in (workflow_path, schema_path) if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing ZIT workflow asset(s): " + ", ".join(missing))
    return workflow_path, schema_path


def _parse_runner_stdout(stdout: str) -> Dict[str, Any]:
    text = (stdout or "").strip()
    if not text:
        raise ValueError("Comfy runner produced empty stdout")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Be forgiving if a future runner emits incidental text before/after JSON.
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def _first_downloaded_image(outputs: Any) -> Path:
    if not isinstance(outputs, list):
        raise ValueError("Comfy runner did not return a downloaded outputs list")
    for entry in outputs:
        if not isinstance(entry, dict):
            continue
        file_path = entry.get("file")
        if not file_path:
            continue
        path = Path(file_path).expanduser()
        suffix = path.suffix.lower()
        entry_type = str(entry.get("type") or "").lower()
        if path.exists() and (entry_type == "image" or suffix in IMAGE_SUFFIXES):
            return path
    raise ValueError("Comfy runner returned no downloaded image file")


def _copy_to_cache(image_path: Path, *, workflow: str, prompt_id: str) -> Path:
    suffix = image_path.suffix.lower() or ".png"
    safe_prompt_id = "".join(ch for ch in (prompt_id or "") if ch.isalnum() or ch in "-_")[:64]
    if not safe_prompt_id:
        safe_prompt_id = "no_prompt_id"
    dest = _image_cache_dir() / f"zit_{workflow}_{safe_prompt_id}_{uuid.uuid4().hex[:8]}{suffix}"
    shutil.copy2(image_path, dest)
    if not dest.exists() or dest.stat().st_size <= 0:
        raise ValueError("Failed to copy generated image into Hermes media cache")
    return dest


def check_zit_image_generation_requirements() -> bool:
    if not os.getenv("COMFY_CLOUD_API_KEY"):
        return False
    if not _comfy_runner().exists():
        return False
    for workflow in VALID_WORKFLOWS:
        try:
            _validate_assets(workflow)
        except FileNotFoundError:
            return False
    return True


def _handle_zit_image_generate(args, **kw):
    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        return tool_error("prompt is required for ZIT image generation", success=False)
    if _looks_like_asset_mutation_request(prompt):
        return tool_error(
            "ZIT workflow assets are immutable; this tool may only read and run them, not modify them.",
            success=False,
            error_type="immutable_assets_policy",
        )

    try:
        workflow = resolve_workflow(args.get("workflow", "auto"), prompt)
        width = _coerce_positive_int(args.get("width"), DEFAULT_WIDTH, "width")
        height = _coerce_positive_int(args.get("height"), DEFAULT_HEIGHT, "height")
        seed = _coerce_seed(args.get("seed"))
        workflow_path, schema_path = _validate_assets(workflow)
    except Exception as exc:
        return tool_error(str(exc), success=False, error_type="invalid_request")

    api_key = os.getenv("COMFY_CLOUD_API_KEY")
    if not api_key:
        return tool_error("COMFY_CLOUD_API_KEY is required for ZIT Comfy Cloud generation", success=False)

    runner = _comfy_runner()
    if not runner.exists():
        return tool_error(f"ComfyUI runner not found: {runner}", success=False, error_type="missing_runner")

    runtime_args = build_runtime_args(
        workflow=workflow,
        prompt=prompt,
        width=width,
        height=height,
        seed=seed,
    )
    output_dir = _run_output_dir()
    cmd = [
        sys.executable,
        str(runner),
        "--workflow", str(workflow_path),
        "--schema", str(schema_path),
        "--api-key", api_key,
        "--args", json.dumps(runtime_args, ensure_ascii=False),
        "--host", COMFY_CLOUD_HOST,
        "--output-dir", str(output_dir),
        "--ws",
    ]

    env = os.environ.copy()
    env["COMFY_CLOUD_API_KEY"] = api_key
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1200,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return tool_error("ZIT image generation timed out", success=False, error_type="timeout")
    except Exception as exc:
        return tool_error(f"Failed to run ZIT image generation: {exc}", success=False, error_type="runner_exception")

    try:
        runner_result = _parse_runner_stdout(completed.stdout)
    except Exception as exc:
        return tool_error(
            f"Could not parse Comfy runner output: {exc}",
            success=False,
            error_type="runner_output_parse_error",
            stderr=(completed.stderr or "")[-1000:],
        )

    if completed.returncode != 0 or runner_result.get("status") != "success":
        return tool_result({
            "success": False,
            "image": None,
            "error": runner_result.get("error") or "ZIT image generation failed",
            "error_type": "runner_failed",
            "workflow": workflow,
            "prompt": prompt,
            "width": width,
            "height": height,
            "seed": seed,
            "runner_status": runner_result.get("status"),
            "prompt_id": runner_result.get("prompt_id"),
        })

    try:
        source_image = _first_downloaded_image(runner_result.get("outputs"))
        cached_image = _copy_to_cache(source_image, workflow=workflow, prompt_id=runner_result.get("prompt_id") or "")
    except Exception as exc:
        return tool_error(str(exc), success=False, error_type="media_cache_error")

    return tool_result({
        "success": True,
        "image": str(cached_image),
        "provider": "zit",
        "model": workflow,
        "workflow": workflow,
        "prompt": prompt,
        "prompt_id": runner_result.get("prompt_id"),
        "seed": seed,
        "width": width,
        "height": height,
        "outputs": runner_result.get("outputs"),
        "warnings": runner_result.get("warnings") or [],
    })


registry.register(
    name="zit_image_generate",
    toolset="image_gen",
    schema=ZIT_IMAGE_GENERATE_SCHEMA,
    handler=_handle_zit_image_generate,
    check_fn=check_zit_image_generation_requirements,
    requires_env=["COMFY_CLOUD_API_KEY"],
    is_async=False,
    emoji="🖼️",
)
