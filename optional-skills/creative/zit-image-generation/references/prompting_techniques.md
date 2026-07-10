# ZIT Prompting Techniques & Experiments

## Core Findings (A/B Testing Results)

### 1. JSON vs. Plain Text (The "Photographer" Test)
- **JSON Mode (English Keys / Chinese Values)**:
  - **Pros**: Highly structured, easy for the agent to build, prevents "key-leakage" (drawing the key name) when keys are English.
  - **Cons**: Can sometimes lead to a "fragmented" feeling in the final image because the model treats each JSON field as a separate, disconnected instruction, potentially losing the "flow" and "atmosphere" of the scene.
- **Plain Text Mode (Detailed English Description)**:
  - **Pros**: **SUPERIOR for atmosphere, vibe, and complex poses.** The "photographer" (AI model) performs much better when it receives a cohesive, flowing narrative in English. It's better at understanding the "mood" (e.g., "cozy and intimate"), "lighting" (e.g., "low-key and warm"), and "complex interactions" (e.g., "lying prone... hips arched high").
  - **Cons**: Requires more careful writing to avoid ambiguity.
  - **Recommendation**: Use **Plain Text Mode** for high-quality, cinematic, or high-emotion shots (e.g., "seductive", "pampering", "melancholic"). Use **JSON Mode** for simple, object-oriented, or structural requests.

### 1b. Anatomy Safety: When to Use JSON Over Plain Text
- **Critical finding (2026-06-18)**: When a prompt stacks multiple specific elements simultaneously (e.g., twin tails + oversized bow hair clip + bikini + hammock + specific pose), plain text — even with explicit "normal human anatomy" wording — frequently fails to prevent extra limbs/hands.
- The model tends to "hallucinate" additional hands/arms when juggling many concrete objects and pose instructions at once.
- **Initial solution**: Use `prompt_json` mode with explicit `camera.avoid` ("手指變形、多餘肢體、人體比例不自然") and `camera.requirements` ("強調人體比例正確，兩隻手，正常人體結構，無多餘肢體") fields.
- **IMPORTANT REVISION (2026-06-18 evening)**: The structured JSON `camera.avoid`/`camera.requirements` fields do NOT always prevent extra limbs. In practice, **plain text prompts with explicit "only two hands, normal human anatomy, no extra limbs" wording produced more reliable anatomy correctness** than JSON mode with the same instructions. The JSON serialization may introduce noise or cause the model to interpret keys as separate disconnected instructions, worsening anatomy coherence.
- **Updated decision rule**: 
  1. For simple prompts with ≤3 physical elements → use **plain text** (better atmosphere + reliable anatomy).
  2. For complex prompts with 4+ stacked elements → **try plain text first** with explicit anatomy instructions. Only fall back to JSON if plain text still produces extra limbs.
  3. If using JSON, ALWAYS include both `camera.avoid` ("手指變形、多餘肢體、人體比例不自然、三隻手") AND explicit hand count in `subject.姿勢.動作` (e.g., "只有兩隻手"), but do not rely on JSON alone — plain text is the primary safety mechanism.
- **Key lesson**: JSON mode is NOT a guaranteed fix for anatomy errors. Plain text with clear, repeated anatomy instructions ("only two hands", "正常人體結構") is often more reliable.

### 2. Aspect Ratio & Composition
- **Portrait (e.g., 1024x1536)**: Best for full-body or single-subject close-ups, emphasizing height and elegance.
- **Landscape (e.g., 1536x1024)**: Best for cinematic, voyeuristic, or wide-angle shots (e.g., "shot from behind", "lying on a bed").
- **Compositional Tip**: For "voyeuristic" or "intimate" shots, use descriptive camera terms like "shot from behind", "extremely close to the camera", "partially obscuring the lens", "cinematic bokeh".

### 3. Character Consistency (Rosie)
- Always include the identifier `(Rosie)` or `(Rosie_hsu)` to help the model anchor the character identity.
- Combine identity with specific clothing (e.g., "black lace lingerie", "pink lace lingerie") and hair (e.g., "twin tails", "single ponytail") for consistent character/outfit variations.

### 5. POV & Environmental Interaction (Water/Splash)

**Boyfriend POV with water splash** (validated 2026-06-18):
- For immersive "boyfriend perspective" beach shots, describe water splashing **onto the camera lens** itself, not just on the subject.
- Key phrases: "水花飛濺到鏡頭上", "splashing water onto the lens", "water droplets on camera", "POV perspective with water hitting the lens".
- Combine with `camera.composition`: "POV 男友視角，水花濺到鏡頭上" to reinforce the effect.
- For dynamic water action, use `shooting`: "高速快門凝結水花" (high-speed shutter to freeze water droplets).
- **Progressive pose refinement pattern**: User may iteratively escalate a pose across multiple generations (e.g., standing → squatting → bending forward → bending more → splashing). Treat each as a follow-up variant: preserve the established scene, clothing, accessories, and character; only modify the pose/action description and camera angle. Do not restart from scratch each time.

### 6. prompt_json Direct Tool Usage (zit_image_generate)

When `zit_image_generate` tool is available, pass structured `prompt_json` directly instead of plain text `prompt`. This avoids the tool's internal serialization quirks and gives full control over the prompt structure.

**Pattern**: Build a JSON object with English keys and Chinese values, then pass it as `prompt_json` to `zit_image_generate`.

```json
{
  "scene": { "描述": "...", "環境": "...", "氣氛": "..." },
  "aesthetics": { "風格": "...", "外觀": "..." },
  "lighting": { "描述": "..." },
  "subject": {
    "民族": { "group": "Rosie Hsu, 台灣人", "年齡": "27歲", "體型": "..." },
    "外貌": { "髮型": "...", "五官": "...", "皮膚": "..." },
    "姿勢": { "類型": "...", "動作": "...", "框架": "..." },
    "服裝": { "上衣": "...", "下身": "..." },
    "配件": { "珠寶": "...", "其他": "..." }
  },
  "props_and_scene": { "背景": "...", "主要道具": "..." },
  "camera": {
    "要求": "強調人體比例正確，兩隻手，正常人體結構，無多餘肢體",
    "拍攝": "廣角鏡頭，自然光，動態捕捉",
    "構圖": "POV 男友視角...",
    "修飾": "保留皮膚質感，強調光影層次",
    "避免": "手指變形、多餘肢體、人體比例不自然、背景過度模糊"
  }
}
```

**Key patterns that worked**:
- `camera.avoid` + `camera.requirements` for anatomy safety (critical for multi-element prompts)
- `subject.配件.其他` for listing accessories (glasses, hair clips, bows)
- `subject.姿勢.動作` for detailed pose descriptions in Chinese
- `camera.構圖` for POV and perspective control
- `props_and_scene.主要道具` for specifying the main environmental element
- Size goes in `width`/`height` parameters, NOT inside the JSON prompt

### 7. Iterative Follow-up Refinement Pattern

When a user is iteratively refining an image across multiple generations:
1. **Preserve anchors**: Keep character identity, clothing, accessories, scene, and lighting consistent across iterations.
2. **Change only what's requested**: If the user says "change pose to X", only modify the pose field — don't rewrite the entire prompt.
3. **Escalation awareness**: Users may progressively intensify a pose or action (e.g., "bend more" → "bend even more" → "splash water"). Each step should build on the previous, not reset.
4. **Seed strategy**: For minor pose tweaks, keep the same seed. For major composition changes (e.g., standing → lying down), change the seed.
5. **Accessory persistence**: If the user added accessories in previous rounds (e.g., twin tails + bow + glasses), carry them forward unless explicitly removed.
- Use descriptive, action-oriented English for complex poses (e.g., "lying prone", "hips and buttocks are arched high towards the camera", "upper body flat against the bed").
- For "seductive" or "pampering" moods, combine physical pose with facial expression instructions (e.g., "enchanting and alluring gaze", "subtle, seductive smile").
