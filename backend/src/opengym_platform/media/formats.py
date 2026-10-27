"""Bounded header inspection, compatible with the existing seven media types."""

TYPES = {
    "image/jpeg": ("jpg", "image"),
    "image/png": ("png", "image"),
    "image/webp": ("webp", "image"),
    "image/gif": ("gif", "gif"),
    "video/mp4": ("mp4", "video"),
    "video/quicktime": ("mov", "video"),
    "video/webm": ("webm", "video"),
}
MP4_BRANDS = {
    b"isom",
    b"iso2",
    b"iso3",
    b"iso4",
    b"iso5",
    b"iso6",
    b"mp41",
    b"mp42",
    b"avc1",
    b"M4V ",
    b"M4VP",
    b"dash",
    b"mmp4",
    b"MSNV",
    b"3gp4",
    b"3gp5",
    b"3gp6",
    b"3g2a",
}


def vint(data, offset, *, marker=False):
    first = data[offset]
    if not first:
        raise ValueError
    length = 1
    while not first & (0x80 >> (length - 1)):
        length += 1
    if offset + length > len(data):
        raise ValueError
    value = int.from_bytes(data[offset : offset + length])
    return (value if marker else value & ((1 << (7 * length)) - 1)), length


def sniff(head):
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[4:8] == b"ftyp":
        if head[8:12] == b"qt  ":
            return "video/quicktime"
        if head[8:12] in MP4_BRANDS:
            return "video/mp4"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        try:
            size, length = vint(head, 4)
            offset, end = 4 + length, min(len(head), 4 + length + size)
            while offset < end:
                tag, length = vint(head, offset, marker=True)
                size, width = vint(head, offset + length)
                offset += length + width
                if tag == 0x4282:
                    if (
                        offset + size <= len(head)
                        and head[offset : offset + size].rstrip(b"\0") == b"webm"
                    ):
                        return "video/webm"
                    return None
                offset += size
        except (IndexError, ValueError):
            pass
    return None


def movie_duration(source, size):
    """Return duration (None for unknown); reject broken or excessive box headers."""
    count = 0

    def boxes(start, end):
        nonlocal count
        while start < end:
            count += 1
            if count > 10000 or end - start < 8:
                raise ValueError
            source.seek(start)
            header = source.read(min(16, end - start))
            length, width = int.from_bytes(header[:4]), 8
            if length == 1:
                if len(header) < 16:
                    raise ValueError
                length, width = int.from_bytes(header[8:16]), 16
                if length >= 9007199254740991:
                    raise ValueError
            elif length == 0:
                length = end - start
            if length < width or start + length > end:
                raise ValueError
            yield header[4:8], start + width, start + length
            start += length

    def read(start, end, limit):
        source.seek(start)
        return source.read(min(end - start, limit))

    def duration(value, wide):
        return None if value in (0, 9007199254740991 if wide else 0xFFFFFFFF) else value

    moov = None
    for index, (kind, start, end) in enumerate(boxes(0, size)):
        if index == 0 and (kind != b"ftyp" or end - start < 4):
            raise ValueError
        if kind == b"moov":
            if end - start + 8 > 8 * 1024 * 1024:
                raise ValueError
            moov = (start, end)
            break
    if moov is None:
        raise ValueError
    timescale, ticks, fragment, saw_header = 0, None, None, False
    for kind, start, end in boxes(*moov):
        if kind == b"mvhd" and not saw_header:
            data = read(start, end, 32)
            if len(data) < 20 or (data[0] == 1 and len(data) < 32):
                raise ValueError
            wide, saw_header = data[0] == 1, True
            offset = 20 if wide else 12
            timescale = int.from_bytes(data[offset : offset + 4])
            value = int.from_bytes(data[offset + 4 : offset + (12 if wide else 8)])
            ticks = duration(min(value, 9007199254740991), wide)
        elif kind == b"mvex":
            for tag, start2, end2 in boxes(start, end):
                if tag == b"mehd":
                    data = read(start2, end2, 12)
                    if len(data) >= 8:
                        wide = data[0] == 1 and len(data) >= 12
                        value = int.from_bytes(data[4 : 12 if wide else 8])
                        fragment = duration(min(value, 9007199254740991), wide)
    if not saw_header or not timescale:
        raise ValueError
    value = ticks if ticks is not None else fragment
    return None if value is None else int(value / timescale * 1000 + 0.5) / 1000
