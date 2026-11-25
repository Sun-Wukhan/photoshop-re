"""PackBits run length encoding, written from scratch.

PackBits is a simple byte oriented RLE scheme. Each packet starts
with a signed header byte n:

* 0 to 127: copy the next n + 1 bytes literally.
* -127 to -1: repeat the next single byte 1 - n times.
* -128: no operation (padding).
"""

from __future__ import annotations


def packbits_decode(data: bytes, expected_length: int) -> bytes:
    """Decode PackBits data until expected_length bytes are produced."""
    out = bytearray()
    i = 0
    n = len(data)
    while i < n and len(out) < expected_length:
        header = data[i]
        i += 1
        if header > 127:
            header -= 256
        if 0 <= header <= 127:
            count = header + 1
            out.extend(data[i:i + count])
            i += count
        elif -127 <= header <= -1:
            if i >= n:
                break
            out.extend([data[i]] * (1 - header))
            i += 1
        # header == -128 is a no op
    return bytes(out[:expected_length])


def packbits_encode(data: bytes) -> bytes:
    """Encode bytes with PackBits. Simple greedy encoder."""
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        # Look for a run of at least 3 identical bytes.
        run = 1
        while i + run < n and data[i + run] == data[i] and run < 128:
            run += 1
        if run >= 3:
            out.append(257 - run)  # encodes as negative header
            out.append(data[i])
            i += run
            continue
        # Literal packet: gather until a run of 3 starts or 128 bytes.
        start = i
        i += 1
        while i < n and (i - start) < 128:
            run = 1
            while i + run < n and data[i + run] == data[i] and run < 128:
                run += 1
            if run >= 3:
                break
            i += 1
        literal = data[start:i]
        out.append(len(literal) - 1)
        out.extend(literal)
    return bytes(out)
