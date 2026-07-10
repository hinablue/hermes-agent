# Music-video storyboard pipeline from ZIT stills

Use this when a user wants more than isolated image generation — e.g. a full MV planning pack built from lyrics and AI storyboard stills.

## Trigger
- User provides song lyrics and wants a complete MV storyboard.
- User wants timecoded scenes plus multiple concept stills per scene.
- User plans to turn the stills into downstream video clips in Kling, LTX, Runway, Veo, etc.

## Working pattern
1. **Build scene-level structure first**
   - Create a scene table with `scene_id`, title, section, lyrics covered, emotional function, visual motif, and camera language.
   - For songs without exact audio yet, start with a working-duration storyboard and note that it will be re-timed later.

2. **Generate 4 still prompts per scene**
   - One wide / establishing frame
   - One medium or emotional performance frame
   - One detail or object frame
   - One alternate angle / transition-support frame

3. **Store outputs in a project folder**
   Recommended layout:
   - `docs/storyboard.md`
   - `docs/storyboard.csv`
   - `docs/storyboard_data.json`
   - `images/<scene_id>/<image_id>.png`
   - `manifests/generation_manifest.json`
   - `manifests/final_manifest.json`

4. **When audio arrives, retime everything to the real duration**
   - Measure exact runtime with ffprobe.
   - Re-scale scene durations rather than leaving rounded working timings.
   - Update scene files and image manifests so all downstream artifacts share the same timecodes.

5. **Add two downstream delivery layers**
   - `docs/shot_timeline.*` — shot-level timing for each generated still
   - `docs/lyric_cues.*` — line-level timing for subtitle / lyric sync

6. **Then derive model-specific video prompt sheets**
   - General `video_prompt_sheet.*` for portable use
   - `kling_prompt_sheet.*` with concise prompt, negative prompt, continuity note, recommended fixed clip length
   - `ltx23_prompt_sheet.*` with shorter prompt, conservative motion, and short test-clip guidance (e.g. 4s/5s/6s)

## Useful duration strategy
- If the user only knows an approximate runtime, make a **working version** centered in the stated range.
  - Example: if the song is around 5:16–5:24, use 5:20 as the working storyboard.
- Once the real file is provided, retime to exact duration and propagate the update everywhere.

## LTX-2.3-specific note
For first-pass LTX experiments, prefer:
- short clips (4s / 5s / 6s)
- low to medium motion only
- identity stability over aggressive movement
- source-image composition lock
- edit-side retiming instead of asking the model to solve long exact timings

## Kling-specific note
Kling sheets are easier to use when each row includes:
- source image path
- target duration
- recommended fixed clip duration bucket (5s / 8s / 10s)
- concise prompt
- concise negative prompt
- continuity note
- edit note explaining trim / retime after generation

## Subtitle outputs
If lyric cues are already timecoded, export both:
- `lyrics.srt`
- `lyrics.vtt`

This keeps the same cue sheet usable for NLEs, lyric videos, and web players.

## Pitfalls
- Do not leave scene timings in a rough draft once the actual audio file exists.
- Do not generate stills without a stable `scene_id` / `image_id` scheme; downstream manifests become painful.
- Do not make LTX prompts as long as general-purpose video prompts; LTX experiments benefit from shorter, steadier instructions.
- Do not collapse all downstream prompt sheets into one generic file; model-specific sheets reduce operator friction.
- Keep the generated still prompts and the video prompts linked by the same IDs, or continuity review becomes messy.
