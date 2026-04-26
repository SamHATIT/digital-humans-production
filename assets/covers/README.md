# Studio editorial covers

Generated images live here, one JPEG per cover, named after the brief id.

- Source briefs: `tools/cover_briefs.yaml`
- Generator: `tools/generate_studio_covers.py`
- Operator guide: `docs/COVERS_GENERATION.md`

## Layout

```
assets/covers/
├── README.md                 (this file)
├── .generation.log           (run history, gitignored)
├── logifleet.jpg             (gallery)
├── pharma.jpg                (gallery)
├── ...                       (4 more gallery covers)
├── manifesto-trust-apex.jpg  (article)
├── craft-triggers-flows.jpg  (article)
└── ...                       (6 more article covers)
```

The JPEGs are intentionally **not** committed by default — they are large binary
artefacts produced by Gemini API calls and the cost of regeneration is low.
Sam decides per-batch whether to commit them or pin them by reference (URL on
the public assets bucket).

## Marker file

`.gitkeep` keeps the directory tracked even when empty, so the relative paths in
the mockup HTML and in `tools/generate_studio_covers.py` stay valid in fresh
clones.
