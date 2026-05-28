"""Tests for tools/zit_image_generation_tool.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def zit_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    skill_root = home / "skills" / "creative" / "zit-image-generation"
    for workflow_name in ("rosie", "deepnight", "general"):
        workflow_dir = skill_root / "assets" / "workflows" / workflow_name
        workflow_dir.mkdir(parents=True, exist_ok=True)
        (workflow_dir / "workflow.json").write_text('{"1": {}}', encoding="utf-8")
        (workflow_dir / "schema.json").write_text("{}", encoding="utf-8")
        (workflow_dir / "manifest.json").write_text("{}", encoding="utf-8")
    comfy_script = home / "skills" / "creative" / "comfyui" / "scripts" / "run_workflow.py"
    comfy_script.parent.mkdir(parents=True, exist_ok=True)
    comfy_script.write_text("# fake runner\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("COMFY_CLOUD_API_KEY", "comfy-key-test")
    return home


@pytest.fixture
def zit_tool():
    import importlib
    import tools.zit_image_generation_tool as mod

    return importlib.reload(mod)


def test_resolves_auto_workflow_for_rosie_deepnight_and_general(zit_tool):
    assert zit_tool.resolve_workflow("auto", "Rosie beside a Taipei window") == "rosie"
    assert zit_tool.resolve_workflow("auto", "許御琪在窗邊喝咖啡") == "rosie"
    assert zit_tool.resolve_workflow("auto", "deepnight mood portrait by a rainy window") == "deepnight"
    assert zit_tool.resolve_workflow("auto", "深夜微醺的夢境感人像") == "deepnight"
    assert zit_tool.resolve_workflow("auto", "Rosie in a deepnight apartment scene") == "rosie"
    assert zit_tool.resolve_workflow("auto", "a cyberpunk alley at night") == "general"
    assert zit_tool.resolve_workflow("general", "Rosie portrait") == "general"
    assert zit_tool.resolve_workflow("deepnight", "Rosie portrait") == "deepnight"


def test_builds_runtime_args_with_workflow_specific_prompt_fields(zit_tool):
    rosie_args = zit_tool.build_runtime_args(
        workflow="rosie",
        prompt="Rosie portrait",
        width=1024,
        height=1536,
        seed=42,
    )
    assert rosie_args == {
        "user_prompt": "Rosie portrait",
        "width": 1024,
        "height": 1536,
        "seed": 42,
    }

    deepnight_args = zit_tool.build_runtime_args(
        workflow="deepnight",
        prompt="deepnight apartment portrait",
        width=960,
        height=1440,
        seed=77,
    )
    assert deepnight_args == {
        "user_prompt": "deepnight apartment portrait",
        "width": 960,
        "height": 1440,
        "seed": 77,
    }

    general_args = zit_tool.build_runtime_args(
        workflow="general",
        prompt="a mountain",
        width=768,
        height=1024,
        seed=99,
    )
    assert general_args == {
        "prompt": "a mountain",
        "width": 768,
        "height": 1024,
        "seed": 99,
    }


def test_handler_runs_comfy_cloud_and_copies_first_image_to_cache(zit_home, zit_tool, monkeypatch, tmp_path):
    generated = tmp_path / "generated.png"
    generated.write_bytes(b"PNGDATA")
    calls = []

    def fake_run(cmd, *, capture_output, text, timeout, env):
        calls.append((cmd, env))

        class Result:
            returncode = 0
            stdout = json.dumps({
                "status": "success",
                "prompt_id": "pid-123",
                "outputs": [
                    {"file": str(generated), "type": "image", "filename": "generated.png"}
                ],
                "warnings": [],
            })
            stderr = ""

        return Result()

    monkeypatch.setattr(zit_tool.subprocess, "run", fake_run)
    monkeypatch.setattr(zit_tool.secrets, "randbelow", lambda n: 123456)

    result = json.loads(zit_tool._handle_zit_image_generate({
        "prompt": "Rosie drinking coffee",
        "workflow": "auto",
        "width": 1024,
        "height": 1536,
    }))

    assert result["success"] is True
    assert result["workflow"] == "rosie"
    assert result["prompt_id"] == "pid-123"
    assert result["seed"] == 123456
    assert result["width"] == 1024
    assert result["height"] == 1536
    cached = Path(result["image"])
    assert cached.exists()
    assert cached.read_bytes() == b"PNGDATA"
    assert zit_home / "cache" / "images" in cached.parents

    cmd, env = calls[0]
    assert "--host" in cmd
    assert "https://cloud.comfy.org" in cmd
    assert "--api-key" in cmd
    assert "comfy-key-test" in cmd
    assert "--ws" in cmd
    assert "--schema" in cmd
    assert "--workflow" in cmd
    assert env["COMFY_CLOUD_API_KEY"] == "comfy-key-test"
    assert json.loads(cmd[cmd.index("--args") + 1]) == {
        "user_prompt": "Rosie drinking coffee",
        "width": 1024,
        "height": 1536,
        "seed": 123456,
    }


def test_handler_rejects_asset_write_requests_before_subprocess(zit_home, zit_tool, monkeypatch):
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("subprocess must not run for asset mutation requests")

    monkeypatch.setattr(zit_tool.subprocess, "run", fake_run)
    result = json.loads(zit_tool._handle_zit_image_generate({
        "prompt": "please modify assets/workflows/rosie/workflow.json",
        "workflow": "rosie",
    }))

    assert result["success"] is False
    assert result["error_type"] == "immutable_assets_policy"
    assert called is False
