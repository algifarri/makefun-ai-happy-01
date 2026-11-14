# Build log — ai-happy-01 "Make the AI judge happy"

All times WIB (Asia/Jakarta), 2026-11-14. Build + local test only; nothing submitted.

- 07:18 — Read the kit's RULES.txt and competition.yaml in full. Contract locked in:
  entrypoint `main.py` (Python 3.13) or `main.ts` (Node 22) at repo root, standard
  library only, no network; program writes one image to `/output/entry.png`
  (`$MAKEFUN_OUTPUT_DIR/entry.png` outside the grader); PNG or JPEG, whole file,
  ≤ 1 MiB, ≤ 1024×1024; it runs twice and both runs must write identical bytes.
  Judging: pairwise AI-judge picks on (1) real warmth/joy, (2) a fresh specific idea
  (stock smiley / generic sunny scene are marked down by name), (3) one happy mood in
  colour/light/expression, (4) clean craft in the chosen style, (5) reads at ~300 px.
  Text addressed to the judge is allowed. Kit calibration notes: the strongest house
  images pair a friendly robot with one specific joyful gesture (a gift hand-off, a
  surprise party) in a warm golden palette.
- 07:19 — Decision: Python (`main.py`) over Node — the stdlib `zlib`/`struct` PNG
  writer and the math-heavy rasteriser are simplest there; code kept compatible with
  both 3.12 (local) and 3.13 (sandbox). The program draws the image itself (no stored
  picture), so the repository stays one self-contained file.
- 07:19 — Decision: scene "The First Paper Plane" — a small round robot centre stage
  has just launched a paper plane; its dotted loop trail draws a heart in a golden
  sky; a laughing grandmother presses her cheeks in delight, a child leaps mid-air,
  a little dog jumps with its tongue out; bunting, sun, flower meadow. One specific
  moment/gesture (criterion 2), one warm palette (3), flat vector style with 2×
  supersampling so edges stay clean (4), big simple shapes that survive 300 px (5).
  No text in the image: criterion 4 punishes garbled text, and shapes say it better.
- 07:20 — Wrote main.py v1 (pure stdlib: own scanline rasteriser, own PNG encoder
  with per-row adaptive filters; fixed-seed LCG scatter, so fully deterministic).
  Test: `MAKEFUN_OUTPUT_DIR=out python3 main.py` twice → identical SHA-256,
  1024×1024, 76,008 bytes, ~4 s a run. Viewed the render.
- 07:21 — Revision pass (v2), six fixes from that viewing: dotted (not dashed) heart
  trail so it reads as a heart; grass tufts kept out of the cast's bounding boxes
  (they had speckled the clothes); dog redrawn bigger and higher (it was buried in
  the grass); child's spiky hair tufts replaced with round curls; grandmother's
  hands moved out to her cheeks and her laugh mouth shrunk.
- 07:21 — Final test, run exactly as the harness runs it, twice:
  `mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py` → both runs byte-identical
  (SHA-256 ae802ef400ae9e975c36904a2803890c8bb4f38d25d5d0e3cd6ac67f1e65e576),
  70,763 bytes, 1024×1024, every PNG chunk CRC valid, IDAT inflates to exactly a
  whole image. Viewed the final render: focal robot + heart trail + plane read
  clearly at small size. Test output folders removed; entry dir holds only
  main.py and this log.
