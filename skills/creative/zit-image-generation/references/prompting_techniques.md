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

### 2. Aspect Ratio & Composition
- **Portrait (e.g., 1024x1536)**: Best for full-body or single-subject close-ups, emphasizing height and elegance.
- **Landscape (e.g., 1536x1024)**: Best for cinematic, voyeuristic, or wide-angle shots (e.g., "shot from behind", "lying on a bed").
- **Compositional Tip**: For "voyeuristic" or "intimate" shots, use descriptive camera terms like "shot from behind", "extremely close to the camera", "partially obscuring the lens", "cinematic bokeh".

### 3. Character Consistency (Rosie)
- Always include the identifier `(Rosie)` or `(Rosie_hsu)` to help the model anchor the character identity.
- Combine identity with specific clothing (e.g., "black lace lingerie", "pink lace lingerie") and hair (e.g., "twin tails", "single ponytail") for consistent character/outfit variations.

### 4. Pose & Movement
- Use descriptive, action-oriented English for complex poses (e.g., "lying prone", "hips and buttocks are arched high towards the camera", "upper body flat against the bed").
- For "seductive" or "pampering" moods, combine physical pose with facial expression instructions (e.g., "enchanting and alluring gaze", "subtle, seductive smile").
