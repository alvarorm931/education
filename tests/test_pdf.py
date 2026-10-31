"""Texto de los PDF de boletines con los límites de pypdf ampliados (motor/pdf.py)."""
import io

import pytest

from motor.pdf import limites_boletin, paginas


def pdf_con_muchas_operaciones(n: int) -> bytes:
    """Una página con un texto y n operaciones de dibujo («0 0 m»), como un plano vectorial en un boletín."""
    contenido = b"BT /F1 12 Tf 72 720 Td (Texto del anuncio) Tj ET\n" + b"0 0 m\n" * n
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(contenido) + contenido + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    salida = io.BytesIO()
    salida.write(b"%PDF-1.4\n")
    posiciones = []
    for i, o in enumerate(objetos, 1):
        posiciones.append(salida.tell())
        salida.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
    xref = salida.tell()
    salida.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1))
    for p in posiciones:
        salida.write(b"%010d 00000 n \n" % p)
    salida.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objetos) + 1, xref))
    return salida.getvalue()


def test_texto_de_un_pdf_corriente():
    assert paginas(pdf_con_muchas_operaciones(10))[0].strip() == "Texto del anuncio"
    assert "Texto del anuncio" in paginas(pdf_con_muchas_operaciones(10), layout=True)[0]


def test_pagina_que_pasa_el_limite_de_pypdf():
    pypdf = pytest.importorskip("pypdf")
    if not hasattr(pypdf, "apply_configuration") or not hasattr(pypdf.get_configuration(), "stream_parsing_work_maximum_count"):
        pytest.skip("pypdf sin límite de trabajo por página")
    from pypdf import PdfReader
    pdf = pdf_con_muchas_operaciones(2000)
    # El límite real es de 2 millones (BOP de Las Palmas, 30/10/2026); aquí se baja para que la prueba sea rápida
    with pypdf.apply_configuration(stream_parsing_work_maximum_count=1000):
        with pytest.raises(Exception, match="maximum number of tokens"):
            PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
        assert paginas(pdf)[0].strip() == "Texto del anuncio"
        with limites_boletin():
            assert pypdf.get_configuration().stream_parsing_work_maximum_count == 30_000_000
        assert pypdf.get_configuration().stream_parsing_work_maximum_count == 1000
