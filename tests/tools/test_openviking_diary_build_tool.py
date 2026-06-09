import json

import tools.openviking_diary_build_tool as diary_tool
from tools.registry import registry


class FakeClient:
    def __init__(self, *, existing=None, session_entries=None, recursive_entries=None, content_map=None):
        self._existing = set(existing or [])
        self._session_entries = list(session_entries or [])
        self._recursive_entries = dict(recursive_entries or {})
        self._content_map = dict(content_map or {})
        self.health_checks = 0
        self.writes = []
        self.mkdir_calls = []
        self.mv_calls = []

    def health(self):
        self.health_checks += 1
        return True

    def get(self, path, params=None, **kwargs):
        params = params or {}
        uri = params.get("uri")
        if path == "/api/v1/fs/stat":
            if uri in self._existing:
                uri_str = str(uri or "")
                is_dir = not uri_str.endswith(".md") and not uri_str.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
                return {"result": {"uri": uri, "isDir": is_dir}}
            raise RuntimeError(f"missing: {uri}")
        if path == "/api/v1/fs/ls":
            if uri == "viking://session":
                return {"result": list(self._session_entries)}
            return {"result": list(self._recursive_entries.get(uri, []))}
        if path == "/api/v1/content/read":
            return {"result": self._content_map.get(uri, "")}
        raise AssertionError(f"Unexpected GET {path}")

    def post(self, path, payload=None, **kwargs):
        payload = payload or {}
        if path == "/api/v1/fs/mkdir":
            uri = payload["uri"]
            self._existing.add(uri)
            self.mkdir_calls.append(uri)
            return {"result": {"uri": uri}}
        if path == "/api/v1/content/write":
            uri = payload["uri"]
            self._existing.add(uri)
            self._content_map[uri] = payload["content"]
            self.writes.append(payload)
            return {"result": {"uri": uri, "written_bytes": len(payload["content"])}}
        if path == "/api/v1/fs/mv":
            self.mv_calls.append(payload)
            from_uri = payload["from_uri"]
            to_uri = payload["to_uri"]
            if from_uri in self._existing:
                self._existing.remove(from_uri)
            self._existing.add(to_uri)
            content = self._content_map.pop(from_uri, None)
            if content is not None:
                self._content_map[to_uri] = content
            return {"result": payload}
        if path == "/api/v1/resources":
            raise AssertionError("Image upload should not run in these tests")
        raise AssertionError(f"Unexpected POST {path}")

    def upload_temp_file(self, file_path):
        raise AssertionError("upload_temp_file should not run in these tests")


def test_registered_tool_entry_exists():
    entry = registry.get_entry("openviking_diary_build")
    assert entry is not None
    assert entry.toolset == "openviking"
    assert entry.check_fn is not None


def test_skip_if_exists_returns_existing_uris(monkeypatch):
    target = "viking://resources/diary/rosie_hsu/20260604/content/content.md"
    image = "viking://resources/diary/rosie_hsu/20260604/image/existing.png"
    image_dir = "viking://resources/diary/rosie_hsu/20260604/image"
    fake = FakeClient(
        existing={target, image_dir, image},
        recursive_entries={
            image_dir: [
                {"uri": image, "name": "existing.png", "isDir": False},
            ],
        },
    )
    monkeypatch.setattr(diary_tool, "_make_client", lambda: fake)

    result = json.loads(
        diary_tool.openviking_diary_build_tool(
            date="20260604",
            role_id="rosie",
            skip_if_exists=True,
            with_image=False,
        )
    )

    assert result["created"] is False
    assert result["reason"] == "already_exists_skipped"
    assert result["content_uri"] == target
    assert result["image_uri"] == image
    assert fake.writes == []


def test_no_matching_material_returns_noop(monkeypatch):
    fake = FakeClient(
        session_entries=[
            {"uri": "viking://session/20260604_000001_abcd", "name": "20260604_000001_abcd", "isDir": True},
        ],
        recursive_entries={
            "viking://session/20260604_000001_abcd": [
                {"uri": "viking://session/20260604_000001_abcd/messages.jsonl", "name": "messages.jsonl", "isDir": False},
            ],
        },
        content_map={
            "viking://session/20260604_000001_abcd/messages.jsonl": '{"role":"assistant","role_id":"hermes","content":"not rosie"}\n'
        },
    )
    monkeypatch.setattr(diary_tool, "_make_client", lambda: fake)

    result = json.loads(
        diary_tool.openviking_diary_build_tool(
            date="20260604",
            role_id="rosie",
            with_image=False,
        )
    )

    assert result["created"] is False
    assert result["reason"] == "no_matching_material"
    assert result["matched_message_count"] == 0
    assert result["content_uri"] is None


def test_builds_markdown_for_matching_material(monkeypatch):
    session_uri = "viking://session/20260604_000001_abcd"
    messages_uri = f"{session_uri}/messages.jsonl"
    content_uri = "viking://resources/diary/rosie_hsu/20260604/content/content.md"
    content_dir = "viking://resources/diary/rosie_hsu/20260604/content"

    fake = FakeClient(
        session_entries=[
            {"uri": session_uri, "name": "20260604_000001_abcd", "isDir": True},
        ],
        recursive_entries={
            session_uri: [
                {"uri": messages_uri, "name": "messages.jsonl", "isDir": False},
            ],
        },
        content_map={
            messages_uri: '{"role":"assistant","role_id":"rosie","content":"今天整理了好多資料。"}\n'
        },
    )
    monkeypatch.setattr(diary_tool, "_make_client", lambda: fake)

    class DummyResponse:
        class Choice:
            class Message:
                content = "# 2026-06-04\n\n今天我整理了好多資料，也把思緒慢慢收攏。"

            message = Message()

        choices = [Choice()]

    monkeypatch.setattr(diary_tool, "call_llm", lambda **kwargs: DummyResponse())
    monkeypatch.setattr(diary_tool, "extract_content_or_reasoning", lambda response: response.choices[0].message.content)

    result = json.loads(
        diary_tool.openviking_diary_build_tool(
            date="20260604",
            role_id="rosie",
            with_image=False,
        )
    )

    assert result["created"] is True
    assert result["matched_message_count"] == 1
    assert result["content_uri"] == content_uri
    assert result["image_uri"] is None
    assert fake.mkdir_calls == [content_dir]
    assert fake.writes and fake.writes[0]["uri"] == content_uri
    assert "今天我整理了好多資料" in fake._content_map[content_uri]


def test_builds_markdown_from_archived_messages_with_parts_payload(monkeypatch):
    session_uri = "viking://session/20260608_112942_6e2bee56"
    archived_messages_uri = f"{session_uri}/history/archive_001/messages.jsonl"
    content_uri = "viking://resources/diary/rosie_hsu/20260608/content/content.md"

    fake = FakeClient(
        session_entries=[
            {"uri": session_uri, "name": "20260608_112942_6e2bee56", "isDir": True},
        ],
        recursive_entries={
            session_uri: [
                {"uri": archived_messages_uri, "name": "history/archive_001/messages.jsonl", "isDir": False},
            ],
        },
        content_map={
            archived_messages_uri: (
                '{"role":"assistant","role_id":"rosie","parts":[{"type":"text","text":"我重新確認了 session 與 role_id 的對應。"}],"created_at":"2026-06-08T04:19:31Z"}\n'
            )
        },
    )
    monkeypatch.setattr(diary_tool, "_make_client", lambda: fake)

    class DummyResponse:
        class Choice:
            class Message:
                content = "# 2026-06-08\n\n今天我重新確認了 session 與 role_id 的對應。"

            message = Message()

        choices = [Choice()]

    monkeypatch.setattr(diary_tool, "call_llm", lambda **kwargs: DummyResponse())
    monkeypatch.setattr(diary_tool, "extract_content_or_reasoning", lambda response: response.choices[0].message.content)

    result = json.loads(
        diary_tool.openviking_diary_build_tool(
            date="20260608",
            role_id="rosie",
            with_image=False,
        )
    )

    assert result["created"] is True
    assert result["matched_sessions"] == [session_uri]
    assert result["matched_message_count"] == 1
    assert result["content_uri"] == content_uri
    assert "session 與 role_id 的對應" in fake._content_map[content_uri]
