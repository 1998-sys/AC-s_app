"""Tests for pdf.parser_origem_cromato.

Fixture `tests/fixtures/cromato_origem.txt` is a SYNTHETIC text, built from
the layout expected by this module's regexes (no real Origem Energia Alagoas
report was available in the project at the time these tests were written —
see the comment at the top of the fixture file). Using already-extracted
text (not a PDF) keeps "is the regex right" separate from "does pdfplumber
read the PDF right" — see tasks/TAREFAS_testes_automatizados.md for the
rationale.
"""

from pathlib import Path

import pytest

from pdf.parser_origem_cromato import (
    extrair_campos_cromato_origem,
    identificar_origem_cromato,
)

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "cromato_origem.txt"


@pytest.fixture
def texto_origem():
    return FIXTURE_PATH.read_text(encoding="utf-8")


class TestIdentificarOrigemCromato:
    def test_identifica_relatorio_origem(self, texto_origem):
        assert identificar_origem_cromato(texto_origem) is True

    def test_rejeita_texto_vazio(self):
        assert identificar_origem_cromato("") is False

    def test_rejeita_texto_de_outro_laboratorio(self):
        assert identificar_origem_cromato("Boletim de Análise - SGS do Brasil Ltda.") is False


class TestExtrairCamposCromatoOrigem:
    @pytest.fixture
    def campos(self, texto_origem):
        return extrair_campos_cromato_origem(texto_origem)

    def test_empresa_e_certificado(self, campos):
        # "empresa" here is the lab itself (header "Laboratório Cromatografia
        # - Origem Energia Alagoas"), not an external client company — see
        # extrair_empresa_origem's docstring.
        assert campos["empresa"] == "Origem Energia Alagoas"
        # The longest variant of the report number must win over the shorter
        # one found in the supplementary properties section ("15833/2026.0").
        assert campos["certificado"] == "15833/2026.0.A"

    def test_propriedades_padrao_tem_2_itens_na_ordem_esperada(self, campos):
        propriedades_padrao = campos["propriedades_pad"]["propriedades_padrao"]
        assert len(propriedades_padrao) == 2
        assert [p["propriedade"] for p in propriedades_padrao] == [
            "Massa Molar",
            "Densidade Absoluta",
        ]

    def test_propriedades_padrao_valores_especificos(self, campos):
        propriedades_padrao = {
            p["propriedade"]: p for p in campos["propriedades_pad"]["propriedades_padrao"]
        }

        massa_molar = propriedades_padrao["Massa Molar"]
        assert massa_molar["valor"] == "20,2104"
        assert massa_molar["incerteza"] == "0,045"

        # Regression check: the "Densidade Absoluta" row must be picked, not
        # the unrelated "Densidade Absoluta - CL" (sampling condition) row
        # that precedes it in the report — see _linha_propriedade's
        # docstring for why a naive prefix match would get this wrong.
        densidade_absoluta = propriedades_padrao["Densidade Absoluta"]
        assert densidade_absoluta["valor"] == "0,8587"
        assert densidade_absoluta["incerteza"] == "0,0019"

    def test_propriedades_amostragem_tem_3_itens_na_ordem_esperada(self, campos):
        propriedades_amostragem = campos["propriedades_amost"]["propriedades_amostragem"]
        assert len(propriedades_amostragem) == 3
        assert [p["propriedade"] for p in propriedades_amostragem] == [
            "Fator de compressibilidade - CL",
            "Viscosidade do gás - CL",
            "Coeficiente Isentrópico - CL",
        ]

    def test_propriedades_amostragem_valores_especificos(self, campos):
        propriedades_amostragem = {
            p["propriedade"]: p for p in campos["propriedades_amost"]["propriedades_amostragem"]
        }

        fator_compressibilidade = propriedades_amostragem["Fator de compressibilidade - CL"]
        assert fator_compressibilidade["valor"] == "0,9447"
        assert fator_compressibilidade["incerteza"] == "0,00094"

        viscosidade = propriedades_amostragem["Viscosidade do gás - CL"]
        assert viscosidade["valor"] == "0,0111"
        assert viscosidade["incerteza"] == "0,0000077"

        coeficiente_isentropico = propriedades_amostragem["Coeficiente Isentrópico - CL"]
        assert coeficiente_isentropico["valor"] == "1,2383"
        assert coeficiente_isentropico["incerteza"] == "0,0036"

    def test_referencia_sempre_none(self, campos):
        todas = (
            campos["propriedades_pad"]["propriedades_padrao"]
            + campos["propriedades_amost"]["propriedades_amostragem"]
        )
        assert all(p["referencia"] is None for p in todas)
