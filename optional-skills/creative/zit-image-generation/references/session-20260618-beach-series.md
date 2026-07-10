# Session 2026-06-18: Beach Water Splash Series

## Session Context
Iterative generation of beach photos with progressive pose escalation, using `zit_image_generate` tool with `prompt_json` direct input.

## Final Configuration (what converged)
- **Size**: 1024x1536 (portrait, full-body)
- **Subject**: Rosie Hsu, twin tails, oversized bow hair clip, large black-rim glasses, sheer transparent bikini
- **Scene**: tropical beach, boyfriend POV, bending down to scoop water at feet, water splashing onto camera lens
- **Key prompt_json fields**:
  - `camera.avoid`: "手指變形、多餘肢體、人體比例不自然、背景過度模糊"
  - `camera.requirements`: "強調人體比例正確，兩隻手，正常人體結構，無多餘肢體，第一人稱視角，鏡頭上有大量水花飛濺"
  - `camera.composition`: "POV 男友視角，從正面平視，人物極度彎腰面向鏡頭，水花大量濺到鏡頭上"
  - `shooting`: "廣角鏡頭，自然光，動態捕捉，高速快門凝結水花"

## Pose Escalation Path
1. Standing, being hit by waves (蹲姿被海浪打)
2. Bending forward to splash water (彎腰潑水)
3. Bending more, hands scooping water (大幅度彎腰潑水)
4. Extreme bend, upper body near ground, water splashing onto lens (極度彎腰捧水 + 水花波到鏡頭)

## Lessons
- `zit_image_generate` tool accepts `prompt_json` directly — no need for plain text conversion
- **REVISED (evening 2026-06-18)**: JSON `camera.avoid`/`camera.requirements` do NOT reliably prevent extra limbs. Plain text with explicit "only two hands, normal human anatomy, no extra limbs" wording is MORE reliable for anatomy correctness.
- Anatomy safety requires BOTH explicit instructions in pose/action AND clear "only two hands" wording
- Water-on-lens effect requires explicit mention in BOTH `camera.composition` AND `props_and_scene.主要道具`
- High-speed shutter phrasing "高速快門凝結水花" in `shooting` helps freeze water droplets
- Multiple generations with progressive pose changes work well when keeping all other elements constant
- When user says "攝影師拍壞了" (photographer messed up / extra hand), switching to plain text prompt is often more effective than retrying with JSON

## Rainbow Selfie (evening 2026-06-18)
- Scene: Rosie taking selfie with large rainbow in the sky after rain
- Outfit: white thin-strap sundress → light floral sundress (evening change), big black-rim glasses
- Background: post-rain sky, large rainbow, white clouds, green mountains
- Pose: one hand holding phone for selfie, other hand making "YA" gesture, surprised happy expression
- Camera: wide-angle selfie, natural light, golden hour backlight
- Key lesson: Plain text prompt produced better anatomy correctness than JSON for this multi-element scene (rainbow + dress + glasses + pose + gesture)
