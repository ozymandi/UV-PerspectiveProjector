"""Minimal EXIF reader for the focal length (JPEG and TIFF), no third-party modules."""

from __future__ import annotations

import struct

TAG_EXIF_IFD = 0x8769
TAG_FOCAL_LENGTH = 0x920A
TAG_FOCAL_35MM = 0xA405
TAG_FOCAL_PLANE_XRES = 0xA20E
TAG_FOCAL_PLANE_UNIT = 0xA210
TAG_PIXEL_X = 0xA002

_TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8, 11: 4, 12: 8}


def _read_tiff_block(path):
    with open(path, "rb") as fh:
        head = fh.read(4)
        fh.seek(0)
        if head[:2] in (b"II", b"MM"):
            return fh.read()
        if head[:2] != b"\xff\xd8":
            return None
        fh.read(2)
        while True:
            marker = fh.read(2)
            if len(marker) < 2 or marker[0] != 0xFF:
                return None
            if marker[1] in (0xD9, 0xDA):  # end of image / start of scan
                return None
            size = struct.unpack(">H", fh.read(2))[0]
            data = fh.read(size - 2)
            if marker[1] == 0xE1 and data[:6] == b"Exif\x00\x00":
                return data[6:]


def _parse_ifd(buf, offset, endian):
    tags = {}
    if offset + 2 > len(buf):
        return tags, 0
    count = struct.unpack(endian + "H", buf[offset:offset + 2])[0]
    for i in range(count):
        e = offset + 2 + i * 12
        if e + 12 > len(buf):
            break
        tag, typ, n = struct.unpack(endian + "HHI", buf[e:e + 8])
        size = _TYPE_SIZES.get(typ, 1) * n
        if size <= 4:
            raw = buf[e + 8:e + 8 + size]
        else:
            ptr = struct.unpack(endian + "I", buf[e + 8:e + 12])[0]
            raw = buf[ptr:ptr + size]
        tags[tag] = _decode(typ, n, raw, endian)
    nxt_pos = offset + 2 + count * 12
    nxt = struct.unpack(endian + "I", buf[nxt_pos:nxt_pos + 4])[0] if nxt_pos + 4 <= len(buf) else 0
    return tags, nxt


def _decode(typ, n, raw, endian):
    try:
        if typ == 3:
            return struct.unpack(endian + "H" * n, raw)[0]
        if typ == 4:
            return struct.unpack(endian + "I" * n, raw)[0]
        if typ in (5, 10):
            num, den = struct.unpack(endian + ("II" if typ == 5 else "ii"), raw[:8])
            return num / den if den else None
        if typ == 11:
            return struct.unpack(endian + "f", raw[:4])[0]
        if typ == 12:
            return struct.unpack(endian + "d", raw[:8])[0]
    except struct.error:
        return None
    return None


def read_exif_tags(path):
    """Return the merged IFD0 + Exif IFD tags we care about, or {} when absent."""
    try:
        buf = _read_tiff_block(path)
    except OSError:
        return {}
    if not buf or len(buf) < 8:
        return {}
    endian = "<" if buf[:2] == b"II" else ">"
    first = struct.unpack(endian + "I", buf[4:8])[0]
    tags, _ = _parse_ifd(buf, first, endian)
    exif_ptr = tags.get(TAG_EXIF_IFD)
    if isinstance(exif_ptr, int):
        exif_tags, _ = _parse_ifd(buf, exif_ptr, endian)
        tags.update(exif_tags)
    return tags


def focal_px_from_exif(path, width: int, height: int):
    """Focal length in pixels from EXIF FocalLengthIn35mmFilm, or None.

    The physical FocalLength + FocalPlaneXResolution route is deliberately not used: some cameras
    write a FocalPlaneXResolution that does not match the sensor (a Fujifilm X100T test photo gave
    13.9 mm instead of its 35 mm equivalent), and a silently wrong focal is worse than asking the
    user for one. Returns ``(focal_px, description)``.
    """
    from .solve import focal_from_35mm

    tags = read_exif_tags(path)
    f35 = tags.get(TAG_FOCAL_35MM)
    if isinstance(f35, (int, float)) and f35 > 0:
        return focal_from_35mm(float(f35), width, height), f"EXIF {f35:g} mm (35 mm equiv.)"
    return None
