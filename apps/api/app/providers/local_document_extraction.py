from __future__ import annotations

import zipfile
from io import BytesIO
from xml.etree import ElementTree

from PIL import Image
from pypdf import PdfReader

from app.providers.document_extraction import (
    DocumentExtractionProvider,
    DocumentExtractionRequest,
    ExtractedDocument,
    ExtractedPage,
    TextBlock,
)
from app.providers.errors import ProviderError


class LocalDocumentExtractionProvider(DocumentExtractionProvider):
    """Local text extraction and image preview provider; it performs no OCR."""

    async def extract(self, request: DocumentExtractionRequest) -> ExtractedDocument:
        try:
            if request.content_type == "application/pdf":
                pages = self._pdf_pages(request.content)
            elif request.content_type.endswith("wordprocessingml.document"):
                pages = self._text_pages(self._docx_text(request.content))
            elif request.content_type == "text/plain":
                pages = self._text_pages(request.content.decode("utf-8"))
            elif request.content_type.startswith("image/"):
                pages = self._image_pages(request.content)
            else:
                raise ProviderError("Unsupported extraction content type.")
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("Local document extraction failed.") from exc

        full_text = "\f".join(page.text for page in pages)
        offset = 0
        normalized_pages: list[ExtractedPage] = []
        for page in pages:
            blocks = tuple(
                TextBlock(
                    page_number=page.page_number,
                    text=block.text,
                    reading_order=block.reading_order,
                    char_start=block.char_start + offset,
                    char_end=block.char_end + offset,
                    polygon=block.polygon,
                    confidence=block.confidence,
                )
                for block in page.blocks
            )
            normalized_pages.append(
                ExtractedPage(
                    page_number=page.page_number,
                    text=page.text,
                    blocks=blocks,
                    width=page.width,
                    height=page.height,
                    preview_content=page.preview_content,
                    preview_content_type=page.preview_content_type,
                )
            )
            offset += len(page.text) + 1
        return ExtractedDocument(
            full_text=full_text,
            pages=tuple(normalized_pages),
            provider="local",
            provider_version="1",
        )

    def _text_pages(self, text: str) -> list[ExtractedPage]:
        pages: list[ExtractedPage] = []
        for page_number, page_text in enumerate(text.split("\f"), 1):
            blocks: list[TextBlock] = []
            offset = 0
            for order, line in enumerate(page_text.splitlines(keepends=True)):
                value = line.rstrip("\r\n")
                blocks.append(
                    TextBlock(
                        page_number, value, order, offset, offset + len(value), confidence=1.0
                    )
                )
                offset += len(line)
            pages.append(ExtractedPage(page_number, page_text, tuple(blocks), 612, 792))
        return pages

    def _pdf_pages(self, content: bytes) -> list[ExtractedPage]:
        reader = PdfReader(BytesIO(content))
        pages: list[ExtractedPage] = []
        for page_number, pdf_page in enumerate(reader.pages, 1):
            text = pdf_page.extract_text() or ""
            page = self._text_pages(text)[0]
            pages.append(
                ExtractedPage(
                    page_number,
                    text,
                    tuple(
                        TextBlock(
                            page_number,
                            b.text,
                            b.reading_order,
                            b.char_start,
                            b.char_end,
                            confidence=1.0,
                        )
                        for b in page.blocks
                    ),
                    float(pdf_page.mediabox.width),
                    float(pdf_page.mediabox.height),
                )
            )
        return pages

    def _docx_text(self, content: bytes) -> str:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs: list[str] = []
        for paragraph in root.iter(f"{namespace}p"):
            paragraphs.append("".join(node.text or "" for node in paragraph.iter(f"{namespace}t")))
        return "\n".join(paragraphs)

    def _image_pages(self, content: bytes) -> list[ExtractedPage]:
        image = Image.open(BytesIO(content))
        pages: list[ExtractedPage] = []
        frame_count = getattr(image, "n_frames", 1)
        for page_number in range(1, frame_count + 1):
            image.seek(page_number - 1)
            output = BytesIO()
            image.convert("RGB").save(output, format="PNG")
            pages.append(
                ExtractedPage(
                    page_number,
                    "",
                    (),
                    float(image.width),
                    float(image.height),
                    output.getvalue(),
                    "image/png",
                )
            )
        return pages
