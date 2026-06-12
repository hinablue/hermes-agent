import json

import tools.openviking_diary_build_tool as diary_tool
from tools.registry import registry


class FakeClient:
    def __init__(self, *, existing=None, dir_uris=None, session_entries=None, recursive_entries=None, content_map=None):
        self._existing = set(existing or [])
        self._dir_uris = set(dir_uris or [])
        self._session_entries = list(session_entries or [])
        self._recursive_entries = dict(recursive_entries or {})
        self._content_map = dict(content_map or {})
        self.health_checks = 0
        self.writes = []
        self.mkdir_calls = []
        self.mv_calls = []
        self.delete_calls = []

    def _uri_is_dir(self, uri):
        return uri in self._dir_uris

    def health(self):
        self.health_checks += 1
        return True

    def get(self, path, params=None, **kwargs):
        params = params or {}
        uri = params.get("uri")
        if path == "/api/v1/fs/stat":
            if uri in self._existing:
                uri_str = str(uri or "")
                is_dir = self._uri_is_dir(uri) or (
                    not uri_str.endswith(".md")
                    and not uri_str.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
                )
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
            self._dir_uris.add(uri)
            self.mkdir_calls.append(uri)
            return {"result": {"uri": uri}}
        if path == "/api/v1/content/write":
            uri = payload["uri"]
            self._existing.add(uri)
            self._dir_uris.discard(uri)
            self._content_map[uri] = payload["content"]
            self.writes.append(payload)
            return {"result": {"uri": uri, "written_bytes": len(payload["content"])}}
        if path == "/api/v1/fs/mv":
            self.mv_calls.append(payload)
            from_uri = payload["from_uri"]
            to_uri = payload["to_uri"]
            if from_uri in self._existing:
                self._existing.remove(from_uri)
            self._dir_uris.discard(from_uri)
            self._existing.add(to_uri)
            content = self._content_map.pop(from_uri, None)
            if content is not None:
                self._content_map[to_uri] = content
            return {"result": payload}
        if path == "/api/v1/resources":
            raise AssertionError("Image upload should not run in these tests")
        raise AssertionError(f"Unexpected POST {path}")

    def delete(self, path, params=None, **kwargs):
        params = params or {}
        if path != "/api/v1/fs":
            raise AssertionError(f"Unexpected DELETE {path}")
        uri = params["uri"]
        self.delete_calls.append({"path": path, "params": dict(params)})
        to_remove = {item for item in self._existing if item == uri or item.startswith(uri.rstrip("/") + "/")}
        for item in to_remove:
            self._existing.discard(item)
            self._dir_uris.discard(item)
            self._content_map.pop(item, None)
        self._recursive_entries.pop(uri, None)
        return {"result": {"uri": uri, "deleted": sorted(to_remove)}}

    def upload_temp_file(self, file_path, *, timeout=None) -> str:
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
    assert fake.writes[0]["mode"] == "create"
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


def test_skip_if_exists_normalizes_wrapped_markdown_dir(monkeypatch):
    content_uri = "viking://resources/diary/rosie_hsu/20260605/content/content.md"
    nested_uri = f"{content_uri}/diary_20260605.md"
    image_uri = "viking://resources/diary/rosie_hsu/20260605/image/existing.png"
    image_dir = "viking://resources/diary/rosie_hsu/20260605/image"

    fake = FakeClient(
        existing={content_uri, nested_uri, image_dir, image_uri},
        dir_uris={content_uri, image_dir},
        recursive_entries={
            content_uri: [
                {"uri": nested_uri, "name": "diary_20260605.md", "isDir": False},
            ],
            image_dir: [
                {"uri": image_uri, "name": "existing.png", "isDir": False},
            ],
        },
        content_map={
            nested_uri: "# 2026-06-05\n\nwrapped diary\n",
        },
    )
    monkeypatch.setattr(diary_tool, "_make_client", lambda: fake)

    result = json.loads(
        diary_tool.openviking_diary_build_tool(
            date="20260605",
            role_id="rosie",
            skip_if_exists=True,
            with_image=False,
        )
    )

    assert result["created"] is False
    assert result["reason"] == "already_exists_normalized"
    assert result["normalized_from_uri"] == nested_uri
    assert fake.delete_calls == [{"path": "/api/v1/fs", "params": {"uri": content_uri, "recursive": True}}]
    assert fake.writes and fake.writes[0]["uri"] == content_uri
    assert fake.writes[0]["mode"] == "create"
    assert fake._content_map[content_uri].startswith("# 2026-06-05")
    assert nested_uri not in fake._existing


def test_read_content_uses_diary_read_timeout():
    class ReadTimeoutCaptureClient(FakeClient):
        def __init__(self):
            super().__init__(content_map={"viking://resources/diary/rosie_hsu/20260609/content/content.md": "# ok\n"})
            self.read_calls = []

        def get(self, path, params=None, **kwargs):
            if path == "/api/v1/content/read":
                self.read_calls.append({"params": dict(params or {}), "kwargs": dict(kwargs)})
            return super().get(path, params, **kwargs)

    client = ReadTimeoutCaptureClient()
    uri = "viking://resources/diary/rosie_hsu/20260609/content/content.md"

    result = diary_tool._read_content(client, uri)

    assert result == "# ok\n"
    assert client.read_calls[0]["kwargs"]["timeout"] == diary_tool.DIARY_READ_TIMEOUT_SECONDS


def test_write_content_accepts_verified_timeout(monkeypatch):
    class TimeoutWriteClient(FakeClient):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.post_timeouts = []

        def post(self, path, payload=None, **kwargs):
            if path == "/api/v1/content/write":
                self.post_timeouts.append(kwargs.get("timeout"))
                assert payload is not None
                uri = payload["uri"]
                self._existing.add(uri)
                self._dir_uris.discard(uri)
                self._content_map[uri] = payload["content"]
                self.writes.append(payload)
                raise RuntimeError("timed out")
            return super().post(path, payload, **kwargs)

    content_uri = "viking://resources/diary/rosie_hsu/20260606/content/content.md"
    fake = TimeoutWriteClient(existing={"viking://resources/diary/rosie_hsu/20260606/content"})

    result = diary_tool._write_content(fake, content_uri, "# 2026-06-06\n\nverified\n", mode="replace")  # type: ignore[arg-type]

    assert result["uri"] == content_uri
    assert result["timed_out_but_verified"] is True
    assert result["verification_attempts"] == 1
    assert fake.post_timeouts == [diary_tool.DIARY_WRITE_TIMEOUT_SECONDS]
    assert fake.writes[0]["mode"] == "create"


def test_write_content_accepts_verified_timeout_after_retry(monkeypatch):
    class DelayedTimeoutWriteClient(FakeClient):
        def __init__(self, *, release_after_attempt=2, **kwargs):
            super().__init__(**kwargs)
            self._stat_calls = 0
            self._pending_uri = None
            self._pending_content = None
            self._release_after_attempt = release_after_attempt
            self.post_timeouts = []

        def get(self, path, params=None, **kwargs):
            params = params or {}
            if path == "/api/v1/fs/stat":
                uri = params.get("uri")
                if uri == self._pending_uri:
                    self._stat_calls += 1
                    if self._stat_calls >= self._release_after_attempt:
                        self._existing.add(uri)
                        self._dir_uris.discard(uri)
                        self._content_map[uri] = self._pending_content
                elif uri in self._existing:
                    self._stat_calls += 1
            return super().get(path, params, **kwargs)

        def post(self, path, payload=None, **kwargs):
            if path == "/api/v1/content/write":
                self.post_timeouts.append(kwargs.get("timeout"))
                assert payload is not None
                self.writes.append(payload)
                self._pending_uri = payload["uri"]
                self._pending_content = payload["content"]
                raise RuntimeError("timed out")
            return super().post(path, payload, **kwargs)

    monkeypatch.setattr(diary_tool.time, "sleep", lambda _seconds: None)
    content_uri = "viking://resources/diary/rosie_hsu/20260607/content/content.md"
    fake = DelayedTimeoutWriteClient(
        existing={"viking://resources/diary/rosie_hsu/20260607/content"},
        release_after_attempt=6,
    )

    result = diary_tool._write_content(fake, content_uri, "# 2026-06-07\n\nverified later\n", mode="replace")  # type: ignore[arg-type]

    assert result["uri"] == content_uri
    assert result["timed_out_but_verified"] is True
    assert result["verification_attempts"] == 6
    assert fake.post_timeouts == [diary_tool.DIARY_WRITE_TIMEOUT_SECONDS]
    assert fake._content_map[content_uri].startswith("# 2026-06-07")


def test_upload_image_uses_explicit_timeout_and_recovers_timeout(monkeypatch, tmp_path):
    class TimeoutImageUploadClient(FakeClient):
        def __init__(self, image_dir_uri):
            super().__init__(existing={image_dir_uri}, dir_uris={image_dir_uri}, recursive_entries={image_dir_uri: []})
            self.image_dir_uri = image_dir_uri
            self.upload_timeouts = []
            self.resource_timeouts = []
            self.temp_file_id = "temp_upload_123"
            self.wrapper_dir_uri = f"{image_dir_uri}/upload_abc123_png"
            self.nested_file_uri = f"{self.wrapper_dir_uri}/upload_abc123.png"

        def upload_temp_file(self, file_path, *, timeout=None):
            self.upload_timeouts.append(timeout)
            return self.temp_file_id

        def post(self, path, payload=None, **kwargs):
            if path == "/api/v1/resources":
                self.resource_timeouts.append(kwargs.get("timeout"))
                self._existing.update({self.wrapper_dir_uri, self.nested_file_uri})
                self._dir_uris.add(self.wrapper_dir_uri)
                self._content_map[self.nested_file_uri] = "binary-image-placeholder"
                self._recursive_entries[self.image_dir_uri] = [
                    {"uri": self.wrapper_dir_uri, "name": "upload_abc123_png", "isDir": True},
                    {"uri": self.nested_file_uri, "name": "upload_abc123.png", "isDir": False},
                ]
                raise RuntimeError("timed out")
            return super().post(path, payload, **kwargs)

    monkeypatch.setattr(diary_tool.time, "sleep", lambda _seconds: None)

    image_dir_uri = "viking://resources/diary/rosie_hsu/20260608/image"
    fake = TimeoutImageUploadClient(image_dir_uri)
    image_path = tmp_path / "diary.png"
    image_path.write_bytes(b"fakepng")

    final_uri = diary_tool._upload_image_to_openviking(fake, image_path=image_path, image_dir_uri=image_dir_uri)  # type: ignore[arg-type]

    assert final_uri == f"{image_dir_uri}/upload_abc123.png"
    assert fake.upload_timeouts == [diary_tool.IMAGE_UPLOAD_TIMEOUT_SECONDS]
    assert fake.resource_timeouts == [diary_tool.IMAGE_UPLOAD_TIMEOUT_SECONDS]
    assert fake.mv_calls == [{"from_uri": fake.nested_file_uri, "to_uri": final_uri}]
    assert final_uri in fake._existing


def test_build_returns_success_with_warning_when_readback_times_out_but_written_file_exists(monkeypatch):
    session_uri = "viking://session/20260611_000001_abcd"
    messages_uri = f"{session_uri}/messages.jsonl"
    content_uri = "viking://resources/diary/rosie_hsu/20260611/content/content.md"
    content_dir = "viking://resources/diary/rosie_hsu/20260611/content"

    fake = FakeClient(
        existing={content_dir},
        session_entries=[
            {"uri": session_uri, "name": "20260611_000001_abcd", "isDir": True},
        ],
        recursive_entries={
            session_uri: [
                {"uri": messages_uri, "name": "messages.jsonl", "isDir": False},
            ],
        },
        content_map={
            messages_uri: '{"role":"assistant","role_id":"rosie","content":"今天把 timeout 假失敗又追了一遍。"}\n',
        },
    )
    monkeypatch.setattr(diary_tool, "_make_client", lambda: fake)

    class DummyResponse:
        class Choice:
            class Message:
                content = "# 2026-06-11\n\n今天把 timeout 假失敗又追了一遍。"

            message = Message()

        choices = [Choice()]

    monkeypatch.setattr(diary_tool, "call_llm", lambda **kwargs: DummyResponse())
    monkeypatch.setattr(diary_tool, "extract_content_or_reasoning", lambda response: response.choices[0].message.content)

    def fake_write_content(client, uri, content, mode="replace"):
        fake._existing.add(uri)
        fake._dir_uris.discard(uri)
        fake._content_map[uri] = content + "\n"
        return {
            "uri": uri,
            "timed_out_but_verified": True,
            "verification_attempts": 3,
            "written_bytes": len(content),
        }

    monkeypatch.setattr(diary_tool, "_write_content", fake_write_content)

    original_read_content = diary_tool._read_content

    def flaky_read_content(client, uri, *, timeout=diary_tool.DIARY_READ_TIMEOUT_SECONDS):
        if uri == content_uri:
            raise RuntimeError("timed out")
        return original_read_content(client, uri, timeout=timeout)

    monkeypatch.setattr(diary_tool, "_read_content", flaky_read_content)

    result = json.loads(
        diary_tool.openviking_diary_build_tool(
            date="20260611",
            role_id="rosie",
            with_image=False,
            skip_if_exists=False,
        )
    )

    assert result["created"] is True
    assert result["content_uri"] == content_uri
    assert result["warning"] == "content_write_timeout_verified"
    assert result["warning_details"]["timed_out_but_verified"] is True
    assert result["warning_details"]["verification_attempts"] == 3
