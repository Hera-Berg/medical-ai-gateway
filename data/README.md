# Seed data

- `authoritative/` — published clinical literature (NICE NG28 PDF, selected
  PubMed abstracts, WHO/NHS guidance). The seed script fetches/loads these. Check
  each source's licence before committing the file vs fetching at seed time.
- `personal/` — a single SYNTHETIC patient record. Never real PHI.

The two folders mirror the app's trust boundary: authoritative (curated,
admin-managed by design) vs personal (user-supplied, ephemeral).
