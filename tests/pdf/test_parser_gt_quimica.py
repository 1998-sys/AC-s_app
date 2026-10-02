"""Tests for pdf.parser_gt_quimica.

Fixture `tests/fixtures/cromato_gt_quimica.txt` holds the real text already
extracted from a GT Química chromatography report ("Boletim de Resultado de
Análise"), used to validate this parser's extraction in a previous session.
Using the already-extracted text (not a PDF) keeps "is the regex right"
separate from "does pdfplumber read the PDF right" — see
tasks/TAREFAS_testes_automatizados.md for the rationale.
"""

from pathlib import Path

import pytest

from pdf.parser_gt_quimica import (
    extrair_campos_cromato_gt,
    extrair_certificado_gt,
    extrair_cliente_gt,
    identificar_gt_quimica,
)

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "cromato_gt_quimica.txt"

# Expected composition labels, in report order (14 components).
ROTULOS_COMPOSICAO = [
    "N2", "C1", "CO2", "C2", "C3", "iC4", "nC4",
    "iC5", "nC5", "C6", "C7", "C8", "C9+", "H2S",
]


@pytest.fixture
def texto_gt():
    return FIXTURE_PATH.read_text(encoding="utf-8")


class TestIdentificarGtQuimica:
    def test_identifica_relatorio_gt_quimica(self, texto_gt):
        assert identificar_gt_quimica(texto_gt) is True

    def test_rejeita_texto_vazio(self):
        assert identificar_gt_quimica("") is False

    def test_rejeita_texto_de_outro_laboratorio(self):
        assert identificar_gt_quimica("Boletim de Análise - SGS do Brasil Ltda.") is False


class TestExtrairClienteGt:
    def test_extrai_razao_social_do_cliente(self, texto_gt):
        assert extrair_cliente_gt(texto_gt) == "PETRO RIO JAGUAR PETRÓLEO S.A"

    def test_retorna_none_para_texto_vazio(self):
        assert extrair_cliente_gt("") is None


class TestExtrairCertificadoGt:
    def test_extrai_numero_do_boletim(self, texto_gt):
        assert extrair_certificado_gt(texto_gt) == "CRO FRADE/26-29908"

    def test_retorna_none_para_texto_vazio(self):
        assert extrair_certificado_gt("") is None


class TestExtrairCamposCromatoGt:
    @pytest.fixture
    def campos(self, texto_gt):
        return extrair_campos_cromato_gt(texto_gt)

    def test_empresa_e_certificado(self, campos):
        assert campos["empresa"] == "PETRO RIO JAGUAR PETRÓLEO S.A"
        assert campos["certificado"] == "CRO FRADE/26-29908"

    def test_composicao_tem_14_componentes_na_ordem_do_boletim(self, campos):
        composicao = campos["composicao"]["composicao"]
        assert len(composicao) == 14
        assert [item["rotulo"] for item in composicao] == ROTULOS_COMPOSICAO

    def test_composicao_valores_especificos(self, campos):
        composicao = {item["rotulo"]: item for item in campos["composicao"]["composicao"]}

        n2 = composicao["N2"]
        assert n2["nome"] == "Nitrogênio"
        assert n2["mol_pct"] == "0,865"
        assert n2["incerteza"] == "0,039"

        c9_mais = composicao["C9+"]
        assert c9_mais["nome"] == "Nonanos"
        assert c9_mais["mol_pct"] == "0,003"
        assert c9_mais["incerteza"] == "0,00085"

    def test_propriedades_padrao_tem_9_itens(self, campos):
        propriedades_padrao = campos["propriedades_pad"]["propriedades_padrao"]
        assert len(propriedades_padrao) == 9

    def test_propriedades_padrao_valores_especificos(self, campos):
        propriedades_padrao = {
            p["propriedade"]: p for p in campos["propriedades_pad"]["propriedades_padrao"]
        }

        peso_molecular = propriedades_padrao["Peso Molecular Médio (kg/kmol)"]
        assert peso_molecular["valor"] == "20,5907"
        assert peso_molecular["incerteza"] == "0,045"

        densidade_absoluta = propriedades_padrao["Densidade Absoluta (kg/m³)"]
        assert densidade_absoluta["valor"] == "0,8587"
        assert densidade_absoluta["incerteza"] == "0,0019"

    def test_propriedades_amostragem_tem_4_itens(self, campos):
        propriedades_amostragem = campos["propriedades_amost"]["propriedades_amostragem"]
        assert len(propriedades_amostragem) == 4

    def test_propriedades_amostragem_fator_z_renomeado_e_valores(self, campos):
        propriedades_amostragem = {
            p["propriedade"]: p for p in campos["propriedades_amost"]["propriedades_amostragem"]
        }

        # "Fator Z" is renamed to "Fator de Compressibilidade" (see
        # pdf.parser_gt_quimica._RENOMEAR) so xml_cromato.py's keyword
        # search for "compressibilidade" finds it like it does for every
        # other lab's report.
        assert "Fator Z" not in propriedades_amostragem
        fator_compressibilidade = propriedades_amostragem["Fator de Compressibilidade"]
        assert fator_compressibilidade["valor"] == "0,9447"
        assert fator_compressibilidade["incerteza"] == "0,00094"

        densidade_absoluta = propriedades_amostragem["Densidade Absoluta (kg/m³)"]
        assert densidade_absoluta["valor"] == "26,6108"
        assert densidade_absoluta["incerteza"] == "0,2"
