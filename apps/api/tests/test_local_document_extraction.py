from __future__ import annotations

import asyncio
from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject

from app.providers.document_extraction import DocumentExtractionRequest
from app.providers.local_document_extraction import LocalDocumentExtractionProvider


def text_pdf() -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = StreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 720 Td (Hello PDF) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)  # noqa: SLF001
    writer.write(output)
    return output.getvalue()


def test_local_provider_extracts_text_pdf_with_page_dimensions() -> None:
    result = asyncio.run(
        LocalDocumentExtractionProvider().extract(
            DocumentExtractionRequest("sample.pdf", text_pdf(), "application/pdf")
        )
    )

    assert "Hello PDF" in result.full_text
    assert len(result.pages) == 1
    assert result.pages[0].width == 612
    assert result.pages[0].blocks[0].char_end <= len(result.full_text)
