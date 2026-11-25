# The PSD file format, in our own words

This document describes the PSD layout as we implemented it in
`pslab/psd.py` and `pslab/psd_writer.py`. It is an original summary
written from our own parser work and from the publicly available
format documentation. No vendor documentation text is reproduced.

## Overall structure

A PSD file is a sequence of five parts, all integers big endian:

1. A fixed size file header (26 bytes).
2. Colour mode data (length prefixed).
3. Image resources (length prefixed).
4. Layer and mask information (length prefixed).
5. Image data: the merged, flattened picture.

The length prefixed sections can be empty (length zero), which is
common for colour mode data in RGB files.

## File header

| Offset | Size | Meaning |
| ------ | ---- | ------- |
| 0 | 4 | Signature, always the ASCII text `8BPS` |
| 4 | 2 | Version, 1 for PSD (2 is the large document PSB variant) |
| 6 | 6 | Reserved, must be zero |
| 12 | 2 | Number of channels, 1 to 56 (3 for RGB, 4 for RGB plus alpha) |
| 14 | 4 | Height in pixels (rows) |
| 18 | 4 | Width in pixels (columns) |
| 22 | 2 | Depth, bits per channel (we decode 8; 1, 16 and 32 also exist) |
| 24 | 2 | Colour mode: 0 Bitmap, 1 Grayscale, 2 Indexed, 3 RGB, 4 CMYK, 7 Multichannel, 8 Duotone, 9 Lab |

## Colour mode data

A 4 byte length followed by that many bytes. For Indexed and
Duotone files this holds the colour table or duotone spec. For
RGB files it is normally empty.

## Image resources

A 4 byte length followed by a sequence of resource blocks. Each
block starts with a signature (usually `8BIM`), a 2 byte unique
identifier, a Pascal string name padded to an even size, and a
4 byte data size followed by the data, also padded to even. Our
parser identifies and lists these blocks without interpreting
their payloads.

## Layer and mask information

A 4 byte length wraps the whole section. Inside it:

* A 4 byte length for the layer info sub section.
* A signed 2 byte layer count. A negative count means the first
  alpha channel holds the transparency data of the merged image,
  and the absolute value is the real layer count.
* One layer record per layer, stored top layer first.
* The channel image data for every layer, in the same order.
* A global layer mask block and any additional tagged blocks,
  which our parser skips.

### Layer record

| Field | Size | Notes |
| ----- | ---- | ----- |
| Bounds | 16 | Top, left, bottom, right as signed 4 byte values. Bottom and right are exclusive in effect: height is bottom minus top |
| Channel count | 2 | Number of channel entries that follow |
| Channel entries | 6 each | Signed 2 byte channel id, then a 4 byte length of that channel's image data, compression tag included |
| Blend signature | 4 | Always `8BIM` |
| Blend mode key | 4 | Four character code, see the table below |
| Opacity | 1 | 0 to 255 |
| Clipping | 1 | 0 base, 1 non base |
| Flags | 1 | Bit 1 (value 2) set means the layer is hidden |
| Filler | 1 | Zero |
| Extra data length | 4 | Covers everything after this field in the record |
| Layer mask data | varies | Length prefixed, often empty |
| Blending ranges | varies | Length prefixed, often empty in simple files |
| Layer name | varies | Pascal string padded so the whole field is a multiple of 4 bytes |

Channel ids 0, 1, 2 are the colour channels (red, green, blue in
an RGB file). Id -1 is the transparency mask, id -2 is a user
layer mask, id -3 is the real user mask.

### Layer channel image data

Each channel starts with a 2 byte compression tag. Tag 0 means
the plane follows as raw bytes, row by row. Tag 1 means PackBits
RLE: first come one 2 byte byte count per row of the layer (for
that channel), then the compressed rows in order.

## Image data (the merged picture)

The final section stores the flattened image in the same two
encodings. It starts with a 2 byte compression tag. Raw data is
stored plane by plane: all rows of channel 0, then all rows of
channel 1, and so on. RLE data starts with the byte counts for
every row of every channel (channels times height counts), then
the compressed rows, again plane by plane.

## PackBits in one paragraph

PackBits works on a stream of packets. A signed header byte from
0 to 127 means copy that many plus one literal bytes. A header
from -127 to -1 means repeat the next byte one minus the header
times. A header of -128 does nothing. Rows are compressed
independently, so a decoder can use the per row byte counts to
jump through the stream.

## Blend mode keys

| Key | Mode | Key | Mode |
| --- | ---- | --- | ---- |
| `norm` | Normal | `dark` | Darken |
| `mul ` | Multiply | `idiv` | Colour Burn |
| `lbrn` | Linear Burn | `dkCl` | Darker Colour |
| `lite` | Lighten | `scrn` | Screen |
| `div ` | Colour Dodge | `lddg` | Linear Dodge (Add) |
| `ltCl` | Lighter Colour | `over` | Overlay |
| `sLit` | Soft Light | `hLit` | Hard Light |
| `vLit` | Vivid Light | `lLit` | Linear Light |
| `pLit` | Pin Light | `hMix` | Hard Mix |
| `diff` | Difference | `smud` | Exclusion |
| `fsub` | Subtract | `fdiv` | Divide |
| `hue ` | Hue | `sat ` | Saturation |
| `colr` | Colour | `lum ` | Luminosity |

Note the trailing spaces in several keys: they are significant,
every key is exactly four bytes.
