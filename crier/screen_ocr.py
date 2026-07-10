"""Recognize text in an image using Windows' built-in OCR engine (the same
one behind Snipping Tool's "Text Actions" / PowerToys Text Extractor) -
no model download, no external binary, and fast (tens of milliseconds)."""

import asyncio

from PySide6.QtCore import QBuffer, QByteArray, QIODevice

# A paragraph/title break inserts noticeably more vertical space than a
# plain wrapped line within the same paragraph does (typically under one
# line-height for a wrap, a full extra line-height or more for a real
# break) - this ratio is how "noticeably more" is judged.
_BREAK_HEIGHT_RATIO = 0.8


def pixmap_to_png_bytes(pixmap) -> bytes:
    buf = QByteArray()
    qbuf = QBuffer(buf)
    qbuf.open(QIODevice.WriteOnly)
    pixmap.save(qbuf, "PNG")
    qbuf.close()
    return bytes(buf)


def _reconstruct_text(ocr_result) -> str:
    """OcrResult.text joins every detected line with a plain space, so a
    title runs straight into the body paragraph with no way to tell them
    apart afterwards. Rebuild the text from the line-level word geometry
    instead: a line whose gap from the previous one is notably taller than
    either line's own height is a real paragraph/title break (-> newline);
    a normal wrapped continuation (-> just a space) otherwise."""
    lines = []
    for line in ocr_result.lines:
        words = list(line.words)
        if not words:
            continue
        text = line.text.strip()
        if not text:
            continue
        top = min(w.bounding_rect.y for w in words)
        bottom = max(w.bounding_rect.y + w.bounding_rect.height for w in words)
        lines.append((text, top, bottom))

    if not lines:
        return ocr_result.text or ""

    parts = [lines[0][0]]
    for i in range(1, len(lines)):
        text, top, _ = lines[i]
        _, _, prev_bottom = lines[i - 1]
        prev_height = lines[i - 1][2] - lines[i - 1][1]
        height = lines[i][2] - lines[i][1]
        gap = top - prev_bottom
        is_break = gap > _BREAK_HEIGHT_RATIO * max(prev_height, height, 1)
        parts.append("\n" if is_break else " ")
        parts.append(text)
    return "".join(parts)


async def _recognize(png_bytes: bytes) -> str:
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream.get_output_stream_at(0))
    writer.write_bytes(png_bytes)
    await writer.store_async()
    await writer.flush_async()
    stream.seek(0)

    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()

    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise RuntimeError("No OCR language available (install one under Windows Settings > Time & Language > Language)")

    result = await engine.recognize_async(bitmap)
    return _reconstruct_text(result)


def recognize_text(pixmap) -> str:
    """Blocking call - run this off the GUI thread. Raises on failure."""
    png_bytes = pixmap_to_png_bytes(pixmap)
    return asyncio.run(_recognize(png_bytes))
