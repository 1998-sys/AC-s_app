"""Tests for pdf.utils_parser.select_extract (the parser dispatcher).

`select_extract` reads a PDF from disk via `extrair_texto` and then routes the
extracted text to the matching parser. To test the routing logic without a
real PDF, `pdf.utils_parser.extrair_texto` is monkeypatched to return the
already-extracted text of one of the four chromatography fixtures (see
tests/fixtures/cromato_*.txt and tasks/TAREFAS_testes_automatizados.md for
the rationale of using text fixtures instead of real PDFs).

Covers, for each of the 4 chromatography labs (GT Química, SGS, Origem
Energia Alagoas, GT Technology):
  1. The detected type is "cromatografia".
  2. The correct parser was chosen (no collision between the `identificar_*`
     functions of different labs, and a lab-specific field confirms the
     right extractor ran).
  3. `dados["_lab"] == "gt_quimica"` only for the GT Química fixture; the
     other three must not carry that marker (or must carry a different
     value).
"""

from pathlib import Path

import pytest

from pdf.parser_gt_quimica import identificar_gt_quimica
from pdf.parser_gt_technology import identificar_gt_technology
from pdf.parser_origem_cromato import identificar_origem_cromato
from pdf.parser_sgs import extrair_empresa
from pdf.utils_parser import select_extract

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _ler_fixture(nome):
    return (FIXTURES_DIR / nome).read_text(encoding="utf-8")


# One identificador per lab, each returning a plain bool, so they can be
# compared against each other to check for collisions. SGS has no dedicated
# `identificar_*` function; `select_extract` itself recognizes it via
# `extrair_empresa(texto) == "SGS"`, so that same check is reused here.
IDENTIFICADORES_POR_LAB = {
    "sgs": lambda texto: extrair_empresa(texto) == "SGS",
    "origem": identificar_origem_cromato,
    "gt_quimica": identificar_gt_quimica,
    "gt_technology": identificar_gt_technology,
}


def _assert_apenas_o_lab_esperado_identifica(texto, lab_esperado):
    """Confirms exactly one lab's `identificar_*` fires for `texto`.

    Guards against the regression this test exists to catch: an
    `identificar_*` written too loosely and matching another lab's report.
    """
    for lab, identificador in IDENTIFICADORES_POR_LAB.items():
        resultado = identificador(texto)
        if lab == lab_esperado:
            assert resultado is True, f"identificador de '{lab}' deveria reconhecer seu proprio texto"
        else:
            assert resultado is False, (
                f"identificador de '{lab}' nao deveria reconhecer o texto de '{lab_esperado}' "
                "(colisao entre identificar_* de labs diferentes)"
            )


@pytest.fixture
def mock_extrair_texto(monkeypatch):
    """Returns a helper that makes select_extract "read" the given text."""

    def _aplicar(texto):
        monkeypatch.setattr("pdf.utils_parser.extrair_texto", lambda caminho: texto)

    return _aplicar


class TestSelectExtractGtQuimica:
    TEXTO = _ler_fixture("cromato_gt_quimica.txt")

    def test_tipo_e_cromatografia(self, mock_extrair_texto):
        mock_extrair_texto(self.TEXTO)
        dados, tipo = select_extract("caminho_qualquer.pdf")
        assert tipo == "cromatografia"

    def test_parser_correto_sem_colisao(self):
        _assert_apenas_o_lab_esperado_identifica(self.TEXTO, "gt_quimica")

    def test_campos_do_parser_gt_quimica(self, mock_extrair_texto):
        mock_extrair_texto(self.TEXTO)
        dados, _ = select_extract("caminho_qualquer.pdf")
        # "composicao" only exists in GT Quimica's and SGS's dicts; combined
        # with the certificate number (unique per lab fixture) this confirms
        # the GT Quimica extractor ran, not SGS's or GT Technology's.
        assert "composicao" in dados
        assert dados["certificado"] == "CRO FRADE/26-29908"

    def test_marcador_lab_e_gt_quimica(self, mock_extrair_texto):
        mock_extrair_texto(self.TEXTO)
        dados, _ = select_extract("caminho_qualquer.pdf")
        assert dados["_lab"] == "gt_quimica"


class TestSelectExtractSgs:
    TEXTO = _ler_fixture("cromato_sgs.txt")

    def test_tipo_e_cromatografia(self, mock_extrair_texto):
        mock_extrair_texto(self.TEXTO)
        dados, tipo = select_extract("caminho_qualquer.pdf")
        assert tipo == "cromatografia"

    def test_parser_correto_sem_colisao(self):
        _assert_apenas_o_lab_esperado_identifica(self.TEXTO, "sgs")

    def test_campos_do_parser_sgs(self, mock_extrair_texto):
        mock_extrair_texto(self.TEXTO)
        dados, _ = select_extract("caminho_qualquer.pdf")
        # SGS's own `composicao()` renders component labels with Unicode
        # subscripts (e.g. "N₂"), unlike GT Quimica's plain-ASCII labels
        # ("N2") — a field only SGS's extractor produces this way,
        # confirming the SGS parser (not GT Quimica's) actually ran.
        rotulos = [item["rotulo"] for item in dados["composicao"]["composicao"]]
        assert "N₂" in rotulos
        assert len(rotulos) == 12

    def test_sem_marcador_lab(self, mock_extrair_texto):
        mock_extrair_texto(self.TEXTO)
        dados, _ = select_extract("caminho_qualquer.pdf")
        assert dados.get("_lab") != "gt_quimica"
        assert "_lab" not in dados


class TestSelectExtractOrigem:
    TEXTO = _ler_fixture("cromato_origem.txt")

    def test_tipo_e_cromatografia(self, mock_extrair_texto):
        mock_extrair_texto(self.TEXTO)
        dados, tipo = select_extract("caminho_qualquer.pdf")
        assert tipo == "cromatografia"

    def test_parser_correto_sem_colisao(self):
        _assert_apenas_o_lab_esperado_identifica(self.TEXTO, "origem")

    def test_campos_do_parser_origem(self, mock_extrair_texto):
        mock_extrair_texto(self.TEXTO)
        dados, _ = select_extract("caminho_qualquer.pdf")
        assert dados["empresa"] == "Origem Energia Alagoas"
        assert dados["certificado"] == "15833/2026.0.A"
        assert "composicao" not in dados

    def test_sem_marcador_lab(self, mock_extrair_texto):
        mock_extrair_texto(self.TEXTO)
        dados, _ = select_extract("caminho_qualquer.pdf")
        assert dados.get("_lab") != "gt_quimica"
        assert "_lab" not in dados


class TestSelectExtractGtTechnology:
    TEXTO = _ler_fixture("cromato_gt_technology.txt")

    def test_tipo_e_cromatografia(self, mock_extrair_texto):
        mock_extrair_texto(self.TEXTO)
        dados, tipo = select_extract("caminho_qualquer.pdf")
        assert tipo == "cromatografia"

    def test_parser_correto_sem_colisao(self):
        _assert_apenas_o_lab_esperado_identifica(self.TEXTO, "gt_technology")

    def test_campos_do_parser_gt_technology(self, mock_extrair_texto):
        mock_extrair_texto(self.TEXTO)
        dados, _ = select_extract("caminho_qualquer.pdf")
        # Same client ("empresa") as the GT Quimica fixture on purpose: the
        # certificate number and the absence of "composicao" are what
        # actually distinguish the GT Technology extractor from GT Quimica's.
        assert dados["empresa"] == "PETRO RIO JAGUAR PETRÓLEO S.A"
        assert dados["certificado"] == "CRO FRADE/26-30112"
        assert "composicao" not in dados

    def test_sem_marcador_lab(self, mock_extrair_texto):
        mock_extrair_texto(self.TEXTO)
        dados, _ = select_extract("caminho_qualquer.pdf")
        assert dados.get("_lab") != "gt_quimica"
        assert "_lab" not in dados
