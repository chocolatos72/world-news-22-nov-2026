# Berita 22 — The World in One Day

A single 1024x1024 newspaper page summing up Sunday 22 November 2026:
35 stories, 7 regions, 11 pictured cards + 24 more in the list, a world map
with 11 numbered dots, a date-check box and a UTC strip.

Entry for the make.fun bounty `news-image-20261122`.

## Run

```
python3 main.py            # writes entry-v4.png next to main.py
python3 main.py out.png    # writes to the given path
```

Stdlib only — a hand-rolled PNG encoder and a 5x7 bitmap font, because the
make.fun sandbox has no Pillow or Matplotlib. Deterministic: two runs
produce byte-identical output, with zero pure-black pixels.

## Contents

- `main.py` — the whole entry: canvas + PNG encoder, bitmap font, the 35
  stories, 11 hand-drawn scenes, the map, and the page layout.

## The 35 stories

13 pictured cards (COP31 collapses with no deal; the Sparta II burning off
Finland; Bahrain seeking UN action; the Kyiv drone strike; Sunday strikes in
Gaza; Hong Kong voting at 97% turnout; the Seoul minister quitting over AI;
Verstappen winning in Las Vegas; India 720/9 in Wellington; the record
Florida flood; Hamas seeking emergency talks) and 24 more in the list, each
tagged with the day it happened ([SUN], [SAT] or [FRI]).

The DATE CHECK box states the rule: every story happened or was first
reported on Sunday 22 November 2026 (UTC), to press time 01:00 UTC — and
lists the stories left out on purpose because they happened on an earlier
day (Paris, Rutte, Kryvyi Rih, GTA VI, US stocks, Riemann).
