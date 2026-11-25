"""pslab: a clean room reimplementation of a PSD parser and a
Photoshop style layer and blend engine.

Everything in this package was written from scratch from published
file format documentation and from well known blend mode behaviour.
It contains no Adobe code, binaries, or assets.
"""

__version__ = "0.1.0"

from .psd import parse_psd, decode_composite_image

__all__ = ["parse_psd", "decode_composite_image", "__version__"]
