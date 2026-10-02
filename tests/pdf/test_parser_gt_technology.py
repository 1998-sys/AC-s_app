"""Tests for pdf.parser_gt_technology.

Fixture `tests/fixtures/cromato_gt_technology.txt` is a SYNTHETIC text,
built from the layout expected by this module's regexes (no real GT
Technology report was available in the project at the time these tests
were written — see the comment at the top of the fixture file). Using
already-extracted text (not a PDF) keeps "is the regex right" separate
from "does pdfplumber read the PDF right" — see
tasks/TAREFAS_testes_automatizados.md for the rationale.
"""

from pathlib import Path

import pytest

from pdf.parser_gt_technology import (
    extrair_campos_cromato_gt_technology,
    identificar_gt_technology,
)

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "cromato_gt_technology.txt"


@pytest.fixture
def texto_gt_technology():
    return FIXTURE_PATH.read_text(encoding="utf-8")


class TestIdentificarGtTechnology:
    def test_identifica_relatorio_gt_technology(self, texto_gt_technology):
        assert identificar_gt_technology(texto_gt_technology) is True

    def test_rejeita_texto_vazio(self):
        assert identificar_gt_technology("") is False

    def test_rejeita_texto_de_outro_laboratorio(self):
        assert identificar_gt_technology("Boletim de Análise - SGS do Brasil Ltda.") is False


class TestExtrairCamposCromatoGtTechnology:
    @pytest.fixture
    def campos(self, texto_gt_technology):
        return extrair_campos_cromato_gt_technology(texto_gt_technology)

    def test_empresa_e_certificado(self, campos):
        assert campos["empresa"] == "PETRO RIO JAGUAR PETRÓLEO S.A"
        assert campos["certificado"] == "CRO FRADE/26-30112"

    def test_propriedades_padrao_tem_2_itens(self, campos):
        propriedades_padrao = campos["propriedades_pad"]["propriedades_padrao"]
        assert len(propriedades_padrao) == 2

    def test_propriedades_padrao_valores_especificos(self, campos):
        propriedades_padrao = {
            p["propriedade"]: p for p in campos["propriedades_pad"]["propriedades_padrao"]
        }

        peso_molecular = propriedades_padrao["Peso Molecular Médio"]
        assert peso_molecular["valor"] == "20,8300"
        assert peso_molecular["incerteza"] == "0,048"

        # "Densidade Absoluta (Padrão)" is renamed to "Densidade Absoluta"
        # (see pdf.parser_gt_technology._CAMPOS) so xml_cromato.py's
        # keyword search finds it the same way it does for every other
        # lab's report.
        assert "Densidade Absoluta (Padrão)" not in propriedades_padrao
        densidade_absoluta = propriedades_padrao["Densidade Absoluta"]
        assert densidade_absoluta["valor"] == "0,8700"
        assert densidade_absoluta["incerteza"] == "0,0021"

    def test_propriedades_amostragem_tem_3_itens(self, campos):
        propriedades_amostragem = campos["propriedades_amost"]["propriedades_amostragem"]
        assert len(propriedades_amostragem) == 3

    def test_propriedades_amostragem_fator_z_renomeado_e_valores(self, campos):
        propriedades_amostragem = {
            p["propriedade"]: p for p in campos["propriedades_amost"]["propriedades_amostragem"]
        }

        # "Fator Z (Operação)" is renamed to "Fator de Compressibilidade"
        # (see pdf.parser_gt_technology._CAMPOS).
        assert "Fator Z (Operação)" not in propriedades_amostragem
        fator_compressibilidade = propriedades_amostragem["Fator de Compressibilidade"]
        assert fator_compressibilidade["valor"] == "0,9512"
        assert fator_compressibilidade["incerteza"] == "0,00088"

        viscosidade = propriedades_amostragem["Viscosidade (Operação)"]
        assert viscosidade["valor"] == "0,0109"
        assert viscosidade["incerteza"] == "0,0000079"

        coef_isentropico = propriedades_amostragem["Coeficiente Isentrópico (Operação)"]
        assert coef_isentropico["valor"] == "1,2460"
        assert coef_isentropico["incerteza"] == "0,0033"

    def test_referencia_e_sempre_none(self, campos):
        todas = (
            campos["propriedades_pad"]["propriedades_padrao"]
            + campos["propriedades_amost"]["propriedades_amostragem"]
        )
        assert all(p["referencia"] is None for p in todas)

    def test_campos_vazios_para_texto_vazio(self):
        campos = extrair_campos_cromato_gt_technology("")
        assert campos["empresa"] is None
        assert campos["certificado"] is None
        assert campos["propriedades_pad"]["propriedades_padrao"] == []
        assert campos["propriedades_amost"]["propriedades_amostragem"] == []
