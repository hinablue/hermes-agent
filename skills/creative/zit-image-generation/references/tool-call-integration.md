# Tool-call integration notes for ZIT Image Generation

This reference captures how to turn the `zit-image-generation` skill workflow into a Hermes tool-call surface without violating the immutable workflow-assets policy.

## Recommended shape

Prefer a dedicated tool named `zit_image_generate` before replacing or overloading Hermes' built-in `image_generate` tool.

Suggested tool arguments:

```json
{
  "prompt": "string",
  "workflow": "auto | rosie | general",
  "width": 1024,
  "height": 1024,
  "seed": 123456789
}
```

Why a dedicated tool first:
- Preserves precise `workflow`, `width`, `height`, and `seed` controls.
- Avoids changing the global `image_generate(prompt, aspect_ratio)` contract.
- Keeps ZIT-specific Rosie/general routing explicit.
- Reduces risk to non-ZIT image generation providers.

## Alternative: image_gen provider plugin

A more official integration can be implemented as an image-generation provider plugin under:

```text
plugins/image_gen/zit/
  plugin.yaml
  __init__.py
```

The provider would implement Hermes' `ImageGenProvider` interface and register via `PluginContext.register_image_gen_provider()` so existing `image_generate` calls route through the configured `image_gen.provider: zit` backend.

Trade-off: the built-in `image_generate` schema is primarily `prompt + aspect_ratio`, so exact width/height/seed and workflow selection either need schema expansion or provider-side conventions.

## Core handler responsibilities

A `zit_image_generate` handler should:

1. Accept prompt, workflow selection, dimensions, and seed.
2. Resolve `workflow=auto` to `rosie` or `general` using the same rules as SKILL.md.
3. Locate the selected bundled workflow assets from the active Hermes profile, not a hard-coded home directory.
4. Validate required files exist.
5. Generate an explicit random seed when none is provided.
6. Build runtime `--args` only.
7. Invoke the existing ComfyUI `run_workflow.py` against Comfy Cloud.
8. Copy the final image to an allowed Hermes media cache location.
9. Return a JSON result with `success`, `image`, `workflow`, `prompt_id`, `seed`, `width`, and `height`.

## In-repo tool implementation pattern

When adding this as a first-class Hermes runtime tool, use a dedicated module such as:

```text
tools/zit_image_generation_tool.py
tests/tools/test_zit_image_generation_tool.py
```

Registration pattern:
- export a `tool_definition()` for the schema
- export a `handle_zit_image_generate(args)` / handler function that performs validation and execution
- add `zit_image_generate` to `_HERMES_CORE_TOOLS`
- add `zit_image_generate` to `TOOLSETS["image_gen"]`

Safety pattern:
- locate the profile with `get_hermes_home()`; do not hard-code `~/.hermes/skills` or `/home/hina/.hermes/skills`
- build subprocess arguments as a list with `shell=False`
- pass only `workflow.json`, `schema.json`, cloud host, API key, output dir, websocket flag, and runtime args
- reject explicit prompts/requests that ask the tool to modify, patch, regenerate, rename, move, or delete workflow assets before any subprocess starts

Regression tests should cover:
- `auto` workflow routing for Rosie vs general prompts
- correct prompt key mapping: `rosie -> user_prompt`, `general -> prompt`
- Comfy Cloud command construction without `shell=True`
- output image copy into Hermes media cache
- immutable-assets mutation requests are rejected before runner invocation

## Immutable assets enforcement

The tool handler must enforce the immutable-assets policy in code, not just rely on the skill prompt.

Allowed operations on `assets/`:
- read files
- verify file existence
- pass paths as inputs to `run_workflow.py`

Forbidden operations on `assets/`:
- write
- patch
- format
- regenerate
- delete
- move
- rename
- migrate

Do not expose any tool argument that edits, updates, replaces, or syncs workflow assets.

## User-facing delivery

Tool results should return an image path that is safe for Hermes media delivery. Final replies may include `MEDIA:<path>`, but natural-language text should not reveal local output/cache paths.