# EssayCards — Images

Split out of `CLAUDE.md` (reference detail; load when working on this area).

## Images
Images enter two ways — a **server-side staging folder** and **in-browser upload**
(paste / drop / pick, Images view only). Both run the identical processing core
(`backend.import_images.process_image_bytes`): decode → `exif_transpose` → Lanczos
downscale to a 2000 px longest edge → metadata-stripped re-encode → slug →
`source_sha256` idempotency → per-file transaction (write `/app/images/<slug>.<ext>`,
INSERT the `essaycards.images` row, commit). Accepted: `.jpg` `.jpeg` `.png` `.gif`
`.webp` — SVG is rejected (stored-XSS vector). Per-file problems (not an image, format
mismatch, oversized GIF, still-too-large after re-encode) are reported as `skipped` /
`400` and never abort a batch.

Idempotency spans both paths: `source_sha256` (SHA-256 of the original bytes) is the
key, so uploading bytes already imported via staging — or vice versa — returns
`unchanged` with no second row and no rewrite.

**Staging path**
1. Drop files into `${DATA_ROOT}/essaycards/staging` (mounted read-only at
   `/app/staging`) — scp, a file share, Syncthing, etc.
2. Import: CLI `docker exec atlas-essaycards python -m backend.import_images`, or the
   **Images** view → **Scan staging folder**.

**Browser upload path** (`POST /api/essaycards/images/upload`)
- On the Images view: paste (Ctrl/Cmd-V), drop onto the drop zone, or pick a file.
- Hard 12 MiB request-body cap, enforced while reading.
- The **raw uploaded bytes** are archived to `${DATA_ROOT}/essaycards/images/originals/`
  (`/app/images/originals/<source_sha256>.<ext>`, created by the code) *before* the
  import — this is the upload path's equivalent of a retained staging original. There
  is no reprocess-from-`originals/` tool yet; to rebuild an uploaded image today, copy
  its original into staging and rescan.

Use **Copy Markdown** in the Images view to copy `![](/api/essaycards/images/<slug>)`
into essay or card text.

The slug is derived from the original filename (lowercased, non-alphanumeric runs
collapsed to `-`; an unnamed clipboard paste becomes `pasted-image`), with a `-<6 hex>`
suffix appended only on a collision with a different image.

**You must retain your own copies — nothing under `/app/images` is backed up
automatically.** The daily `pg_dump` covers the `essaycards.images` rows only, never the
files. `/app/images/<slug>.<ext>` (processed, web-served) and `/app/images/originals/`
(raw upload archive) are both outside it and nothing else backs them up. After a database
restore the rows are back but `GET /images/{slug}` returns 404 until the bytes are
restored:
- **Staged images:** re-run the scan against the retained staging folder.
- **Uploaded images:** the raw bytes live in `originals/<source_sha256>.<ext>`; today,
  recovery is manual (copy an original into staging and rescan).

If you lose `/app/images` *and* both your staging originals and the `originals/` archive,
the affected images are unrecoverable.
