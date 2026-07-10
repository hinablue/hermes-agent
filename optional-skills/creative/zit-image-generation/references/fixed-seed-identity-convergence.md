# Fixed-seed identity convergence for Rosie MV / storyboard batches

Use this when a large Rosie batch already exists but the face drifts too much across scenes and the user wants a stronger first-pass character lock.

## When this helps

- The batch is already structurally good (prompts / framing / scene logic are usable)
- The main complaint is **五官差異過大 / identity drift**
- The user explicitly wants to test whether a **single shared seed** improves convergence before doing heavier reference-conditioning work

This is a good **first stabilization pass**, not a final guarantee of perfect identity.

## Proven pattern

### 1) Re-run the whole managed batch with one fixed seed
For storyboard-style Rosie jobs, regenerate every manifest-tracked image with the **same seed** instead of per-image random seeds.

In the successful session that motivated this note, regenerating all images with one fixed seed produced a noticeably tighter first-pass face/shape cluster than the previous mixed-seed batch.

### 2) Keep prompts and framing, change only seed first
Do not immediately rewrite all prompts.
First test the cheapest variable:
- keep the same prompt text
- keep the same dimensions
- keep the same file layout / image IDs
- replace per-image seeds with one shared seed

This isolates whether the drift is mostly seed-driven.

### 3) Treat this as a manifest-driven migration
If the batch already has manifests, do not freehand rerun images one by one.
Create a deterministic pass that:
- reads all existing manifests
- preserves `image_id`, `scene_id`, output paths, and ordering
- records the original seed
- writes the new fixed seed into regenerated result records
- updates the managed manifests only after success

### 4) Back up manifests before rewriting them
Before the convergence pass, create one backup copy for each manifest you will rewrite.
Use a stable suffix such as:
- `final_manifest.before_fixed_seed_backup.json`
- `extra_final_manifest.before_fixed_seed_backup.json`
- `hero_transition_expansion_results.before_fixed_seed_backup.json`

### 5) Save a combined regeneration manifest and result log
Keep at least three artifacts:
- a combined manifest of every item selected for regeneration
- a progress JSON for long-running jobs
- a final results JSON with prompt_id / output / updated seed metadata

This makes the pass resumable and auditable.

## Recommended verification

After the full pass:
- verify total regenerated count matches expected count
- verify all updated manifests now contain the fixed seed only
- verify all referenced output files exist
- create a small **identity contact sheet** from 6–8 representative scenes
- do a human or vision-model review focused on:
  - face shape consistency
  - eye / nose / mouth proportion consistency
  - which scenes still read as different people

## Interpretation guideline

A shared seed can improve convergence enough for a **first-round character-consistent batch**, but it does not eliminate all drift.
If a few scenes still look like different people, the next escalation is usually:
- stronger shared face wording in prompt skeletons
- scene-family prompt normalization
- selecting the most stable results into a curated first-pass pack
- only after that, heavier reference / identity locking methods

## Good user-facing framing

Say it as:
- this is a **收斂測試 / first stabilization pass**
- the result may be good enough for a first-round pack
- if some scenes still drift, move to a targeted second pass instead of rerunning everything blindly

## Pitfall to avoid

Do not describe the result as "identity solved" just because all images share one seed.
The right claim is narrower: **fixed-seed regeneration can materially reduce drift and make the batch more coherent, but it still needs contact-sheet review and possibly a targeted second pass.**