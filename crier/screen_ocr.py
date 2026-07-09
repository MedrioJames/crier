"""Recognize text in an image using Windows' built-in OCR engine (the same
one behind Snipping Tool's "Text Actions" / PowerToys Text Extractor) -
no model download, no external binary, and fast (tens of milliseconds)."""

import asyncio

from PySide6.QtCore import QBuffer, QByteArray, QIODevice


def pixmap_to_png_bytes(pixmap) -> bytes:
    buf = QByteArray()
    qbuf = QBuffer(buf)
    qbuf.open(QIODevice.WriteOnly)
    pixmap.save(qbuf, "PNG")
    qbuf.close()
    return bytes(buf)


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
    return result.text


def recognize_text(pixmap) -> str:
    """Blocking call - run this off the GUI thread. Raises on failure."""
    png_bytes = pixmap_to_png_bytes(pixmap)
    return asyncio.run(_recognize(png_bytes))
