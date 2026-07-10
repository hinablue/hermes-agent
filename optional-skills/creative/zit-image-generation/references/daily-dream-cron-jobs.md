# Daily Dream Cron Jobs

Use this note for scheduled Rosie image jobs that first require a fixed-format text artifact and then a matching dream-image render.

## What this session taught

A daily 07:00 dream job is not just “generate an image.” It is a two-part content pipeline:
1. write a finished dream paragraph with an exact character count,
2. then convert that exact text into visual anchors for the Rosie workflow.

If those two parts drift apart, the final delivery feels fake even when the image itself looks good.

## Recommended workflow

1. Draft the dream text first.
2. Verify the exact character count programmatically.
3. Freeze that text before touching the image prompt.
4. Extract concrete visual anchors from the text:
   - wardrobe/accessories
   - room state
   - key props
   - city / weather cues
   - emotional temperature
   - traces of the previous day’s work
5. Build the Rosie prompt from those anchors, not from a looser paraphrase.
6. Run image generation.
7. QA the result for both image quality and text-image alignment.
8. If needed, do one targeted second pass instead of accepting a “mostly right” first image.

## Converting prior-day events into image anchors

When the job says to include what happened yesterday, convert the day’s events into objects and scene traces rather than literal exposition.

Examples:
- dialogue/style curation work → scattered notes, marked-up pages, paper slips
- indexing/reindexing or summary work → scripts on paper, folded sheets, abstracted technical traces
- late-night coding/admin work → coffee cup, terminal glow, desk clutter, half-finished notes
- messaging / silence / unread tension → phone on table, paused chat feeling, saved note, unsent or "goodnight" mood

This keeps the dream image grounded in the real session without dumping technical prose into the prompt.

## When to do a targeted second pass

Do a second pass before delivery if QA says any of these happened:
- a required prop is weak or missing
- the scene mood is right but a major anchor is absent
- the result drifted slightly more sensual than intended for a quiet daily-life photo
- the room became too clean / generic and lost the previous-day trace

## Good second-pass moves

Keep the same emotional core and workflow, but tighten specifics:
- make the required prop explicitly visible (e.g. beanbag / paper boat / coffee cup)
- upgrade weak environmental cues into explicit scene requirements
- reduce exposed skin with neutral wardrobe constraints (blanket, long socks, oversized knit, longer framing)
- strengthen `avoid` guidance for over-sexualization, stray text, anatomy drift, or age ambiguity
- preserve adult wording explicitly

## Delivery checklist

- final text already locked
- exact character count verified in code
- prompt visibly inherits the text’s anchors
- output file verified to exist and match expected format/size
- temp run directory cleaned after cached deliverable is verified
- final reply includes the exact text plus image metadata
