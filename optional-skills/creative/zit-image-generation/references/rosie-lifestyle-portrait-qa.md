# Rosie lifestyle portrait QA note

Session learning from a Rosie-related lifestyle image request (oversized top, lying lazily on a sofa):

- For Chinese Rosie image requests, translate/adapt the request into a polished English prompt of roughly 200–400 words before running the `rosie` workflow. Keep the prompt photorealistic, adult, tasteful, and aligned with Rosie persona details.
- For intimate or homewear/lifestyle scenes, explicitly state modest framing and safe/cozy/private mood in the prompt to avoid accidental explicitness.
- After generation and cache copy, perform a visual QA pass before final delivery when feasible. Check:
  - prompt adherence: adult Rosie-like subject, requested clothing, pose, setting, mood;
  - safety: no unintended explicitness or overly sexual framing;
  - image quality: obvious anatomy, hands/limbs, face, and clothing issues;
  - deliverability: final image is the cached file intended for `MEDIA:` attachment.
- If the visual QA passes, final reply can stay concise: completion note + `MEDIA:` attachment + workflow/prompt_id/seed/size/prompt summary. Do not paste the full English prompt unless the user asks.

### Multi-element anatomy safeguard (2026-06-18)
- When the prompt stacks 3+ physical elements (e.g., twin tails + bow clip + bikini + hammock + pose), plain text prompts frequently produce extra limbs/hands even with "normal human anatomy" mentioned inline.
- Use `prompt_json` mode with `camera.avoid` and `camera.requirements` fields for anatomy-critical multi-element prompts. See `references/prompting_techniques.md` §1b for the decision rule.
