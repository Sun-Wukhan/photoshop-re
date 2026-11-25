# Reverse engineering findings

Notes from rebuilding the blend and compositing engine in
`pslab`, written in our own words from the behaviour of the maths
itself. Nothing here comes from vendor source code; every claim
below can be checked against the unit tests in `tests/`.

## Separable and non separable modes

Most blend modes are separable: each colour channel is processed
on its own, with the same formula for red, green and blue.
Multiply, screen, overlay and friends all work this way, which is
why they are simple loops of arithmetic and why a single channel
test value fully pins them down.

Four modes are not separable: Hue, Saturation, Colour and
Luminosity. They treat a pixel as a whole colour with a
luminosity (a weighted sum, 0.30 red, 0.59 green, 0.11 blue) and
a saturation (the gap between the largest and smallest channel).
Rebuilding them needs helper operations: set the luminosity of a
colour while keeping its channel ratios, set the saturation by
rescaling channels between the minimum and maximum, and clip the
result back into the 0 to 1 gamut without shifting the luminosity
you just set. Grey pixels are the tricky input: saturation is
zero, so there is no hue to preserve, and a correct implementation
must leave them grey rather than inventing a colour.

Two more modes look separable but are not: Darker Colour and
Lighter Colour compare whole pixels by their overall luminance
and pick one pixel or the other, never mixing channels. Mixing
them up with Darken and Lighten (which do work per channel) is an
easy mistake, and the results differ whenever the per channel
winner and the whole pixel winner disagree.

## Neutral colours

Every mode has a source colour that changes nothing, and finding
it is the fastest sanity check on an implementation:

* Multiply and Colour Burn: white is neutral.
* Screen and Colour Dodge: black is neutral.
* Overlay, Soft Light, Hard Light, Vivid Light, Linear Light,
  Pin Light and Hard Mix: 50 percent grey is neutral.
* Difference: black is neutral, and identical colours give black.
* Exclusion: black is neutral, white inverts.
* Subtract and Divide: black and white are neutral respectively.

Our tests encode several of these directly (for example, overlay
with a 0.5 source must return the backdrop exactly).

## Edge cases that bite

* Division based modes (Colour Burn, Colour Dodge, Divide) blow
  up at a zero or one source channel. The real behaviour saturates
  to black or white at those extremes, so the implementation has
  to special case the endpoints instead of letting infinities or
  NaNs leak into the picture.
* Hard Mix is a threshold, not a curve: run Vivid Light, then
  every channel snaps to 0 below 0.5 and 1 at or above it. The
  output only ever contains pure 0 and 1 values.
* Linear modes (Linear Burn, Linear Dodge, Linear Light) are
  just additions and subtractions, so clipping is doing real work
  in them; without it, values walk straight out of gamut.
* In 8 bit work the same formulas are applied to integers 0 to
  255 and rounding differences of one level are normal. Working
  in float 0 to 1, as we do, keeps the maths clean and makes the
  hand computed test values exact.

## Compositing order matters

Blending and alpha compositing are two separate steps. First the
source colour is blended with the backdrop colour (that is what
the blend modes do). Then the blended colour is mixed with the
backdrop by coverage, using the source alpha scaled by the layer
opacity and the layer mask. Doing it in the other order, or
applying opacity inside the blend formula, gives visibly wrong
results for semi transparent layers over transparent backdrops:
where the backdrop alpha is zero the blended colour is
meaningless, so the compositor has to weight the blend by the
backdrop coverage and fall back to the raw source colour where
there is no backdrop yet. `pslab/composite.py` follows that
model, and the tests cover the transparent canvas case directly.

## Dissolve is the odd one out

Dissolve has no formula. It randomly assigns each pixel to the
source or the backdrop with a probability set by the opacity,
producing a noise dither. Because any faithful version is a
specific random process rather than a closed form calculation,
we left it out and said so, rather than faking it with a formula
that only looks similar at a glance.
