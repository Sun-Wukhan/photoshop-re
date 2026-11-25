# photoshop-re

We reverse engineered how Photoshop's core works, its PSD file
format and its layer and blend engine, and rebuilt it clean room
in Python. The result is `pslab`: a from scratch PSD parser, a
PSD writer, 26 blend modes, a layer compositor with masks and
opacity, and a small set of image adjustments, all covered by
tests whose expected values were computed by hand.

This is a learning and interoperability project. It is not
affiliated with Adobe, and it does not try to be a full photo
editor. It is the engine room, rebuilt and explained.

## Clean room statement

Everything in this repository is original code written by us.
The PSD parser and writer were implemented from the publicly
published file format documentation. The blend modes were
implemented from their well documented mathematical behaviour,
with each formula stated in plain words in its docstring. No
Adobe code, binaries, assets, icons or documentation text were
used, copied or decompiled. Photoshop is a trademark of Adobe
Inc.; this project is not endorsed by Adobe.

## What is inside

* **PSD parser** (`pslab/psd.py`): header, colour mode data,
  image resource blocks, layer records (name, bounds, channels,
  blend mode key, opacity, visibility) and the merged composite
  image, with raw and PackBits RLE decoding. Decodes the
  composite to a Pillow Image.
* **PSD writer** (`pslab/psd_writer.py`): writes minimal but
  valid PSD files with layer records and raw or RLE image data.
  It generates the fixtures our parser tests round trip against,
  so the whole loop is proven with files we created ourselves.
* **Blend modes** (`pslab/blends.py`): 26 modes on float RGB
  arrays: normal, darken, multiply, colour burn, linear burn,
  darker colour, lighten, screen, colour dodge, linear dodge,
  lighter colour, overlay, soft light, hard light, vivid light,
  linear light, pin light, hard mix, difference, exclusion,
  subtract, divide, hue, saturation, colour and luminosity.
  Dissolve is intentionally excluded: it is a randomised dither
  with no closed form formula, and `docs/FINDINGS.md` explains
  why faking it would be dishonest.
* **Compositor** (`pslab/composite.py`): blend then source over
  compositing with per layer opacity, blend mode and an optional
  greyscale layer mask.
* **Filters** (`pslab/filters.py`): gaussian blur, levels,
  brightness and contrast, hue and saturation, invert and
  grayscale (desaturate).
* **CLI** (`python -m pslab`): inspect a PSD as JSON, flatten it
  to PNG, or generate a demo composition with the engine itself.

## Quickstart

```bash
pip install -r requirements.txt
pip install -e .
python -m pytest tests/ -q

# Generate a synthetic composition with the blend engine
python -m pslab demo demo.png

# Write a PSD with our own writer, then inspect and flatten it
python - <<'PY'
from PIL import Image
from pslab.psd_writer import write_psd
base = Image.new("RGB", (64, 48), (70, 110, 170))
layer = Image.new("RGBA", (64, 48), (230, 180, 60, 255))
write_psd("sample.psd", base, [
    {"name": "Sky", "image": base.convert("RGBA")},
    {"name": "Sun tint", "image": layer,
     "blend_mode": "multiply", "opacity": 0.5},
])
PY
python -m pslab info sample.psd
python -m pslab flatten sample.psd sample.png
```

## Repository structure

```
pslab/
  psd.py         PSD parser
  psd_writer.py  minimal PSD writer (test fixture generator)
  packbits.py    PackBits RLE codec
  blends.py      26 blend modes plus the PSD key mapping
  composite.py   layer compositing with opacity and masks
  filters.py     basic adjustments
  cli.py         command line interface
tests/           pytest suite (parser round trips, blend maths,
                 compositing, filters)
docs/
  PSD-FORMAT.md  the format described in our own words
  FINDINGS.md    reverse engineering notes on blend behaviour
```

## Findings worth reading

`docs/FINDINGS.md` collects what the rebuild taught us: which
modes are separable and which treat a pixel as a whole colour,
the neutral colour of every mode (the fastest sanity check there
is), the division by zero edges in the burn and dodge family,
and why blending and alpha compositing must happen in that
order. `docs/PSD-FORMAT.md` documents the file layout, the layer
record structure and the RLE scheme as we implemented them.

## Licence

MIT, see `LICENSE`. Copyright (c) 2026 Navid Khan.
