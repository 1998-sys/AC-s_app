"""Tests for pdf.parser_sgs.

Fixture `tests/fixtures/cromato_sgs.txt` is a SYNTHETIC text, built from the
layout expected by this parser's regexes (no real SGS chromatography report
was found saved in the project at the time these tests were written — see
the fixture file's header comment). It should be replaced with a real
extracted text when one becomes available. Using already-extracted text (not
a PDF) keeps "is the regex right" separate from "does pdfplumber read the PDF
right" — see tasks/TAREFAS_testes_automatizados.md for the rationale.
"""

from pathlib import Path

import pytest

from pdf.parser_sgs import (
    composicao,
    extrair_campos_cromato,
    extrair_empresa,
    propriedades_amostragem,
    propriedades_padrao,
)

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "cromato_sgs.txt"

# Expected composition labels, in fixture order (12 components).
ROTULOS_COMPOSICAO = [
    "N₂", "CO2", "C₁", "C₂", "C₃", "iC4", "nC4",
    "iC5", "nC5", "C₆", "C9+", "H2S",
]


@pytest.fixture
def texto_sgs():
    return FIXTURE_PATH.read_text(encoding="utf-8")


class TestExtrairEmpresa:
    def test_identifica_relatorio_sgs(self, texto_sgs):
        assert extrair_empresa(texto_sgs) == "SGS"

    def test_retorna_none_para_texto_vazio(self):
        assert extrair_empresa("") is None

    def test_retorna_none_para_texto_de_outro_laboratorio(self):
        assert extrair_empresa("Boletim de Resultado de Análise - gtquimica.com.br") is None


class TestComposicao:
    def test_retorna_lista_vazia_para_texto_vazio(self):
        assert composicao("") == {"composicao": []}

    def test_retorna_lista_vazia_quando_secao_nao_encontrada(self):
        assert composicao("texto sem a secao de composicao") == {"composicao": []}

    def test_tem_12_componentes_na_ordem_da_fixture(self, texto_sgs):
        lista = composicao(texto_sgs)["composicao"]
        assert len(lista) == 12
        assert [item["rotulo"] for item in lista] == ROTULOS_COMPOSICAO

    def test_cada_item_tem_os_quatro_campos(self, texto_sgs):
        lista = composicao(texto_sgs)["composicao"]
        for item in lista:
            assert set(item.keys()) == {"rotulo", "nome", "mol_pct", "incerteza"}

    def test_valores_especificos_nitrogenio(self, texto_sgs):
        lista = {item["rotulo"]: item for item in composicao(texto_sgs)["composicao"]}
        n2 = lista["N₂"]
        assert n2["nome"] == "Nitrogênio"
        assert n2["mol_pct"] == "0,850"
        assert n2["incerteza"] == "0,025"

    def test_valores_especificos_metano(self, texto_sgs):
        lista = {item["rotulo"]: item for item in composicao(texto_sgs)["composicao"]}
        c1 = lista["C₁"]
        assert c1["nome"] == "Metano"
        assert c1["mol_pct"] == "85,300"
        assert c1["incerteza"] == "0,150"

    def test_rotulo_co2_nao_recebe_subscrito(self, texto_sgs):
        lista = {item["rotulo"]: item for item in composicao(texto_sgs)["composicao"]}
        co2 = lista["CO2"]
        assert co2["nome"] == "Dióxido de Carbono"
        assert co2["mol_pct"] == "1,200"
        assert co2["incerteza"] == "0,035"

    def test_rotulo_c9_mais_permanece_identico(self, texto_sgs):
        lista = {item["rotulo"]: item for item in composicao(texto_sgs)["composicao"]}
        c9_mais = lista["C9+"]
        assert c9_mais["nome"] == "Nonanos e Superiores"
        assert c9_mais["mol_pct"] == "0,020"
        assert c9_mais["incerteza"] == "0,005"

    def test_rotulo_h2s_permanece_identico(self, texto_sgs):
        lista = {item["rotulo"]: item for item in composicao(texto_sgs)["composicao"]}
        h2s = lista["H2S"]
        assert h2s["nome"] == "Sulfeto de Hidrogênio"
        assert h2s["mol_pct"] == "0,250"
        assert h2s["incerteza"] == "0,020"

    def test_total_nao_e_contado_como_componente(self, texto_sgs):
        lista = composicao(texto_sgs)["composicao"]
        assert "Total" not in [item["rotulo"] for item in lista]


class TestPropriedadesPadrao:
    def test_retorna_lista_vazia_para_texto_vazio(self):
        assert propriedades_padrao("") == {"propriedades_padrao": []}

    def test_retorna_lista_vazia_quando_secao_nao_encontrada(self):
        assert propriedades_padrao("texto sem a secao de propriedades") == {"propriedades_padrao": []}

    def test_tem_4_propriedades(self, texto_sgs):
        lista = propriedades_padrao(texto_sgs)["propriedades_padrao"]
        assert len(lista) == 4

    def test_valores_com_referencia_iso(self, texto_sgs):
        lista = {p["propriedade"]: p for p in propriedades_padrao(texto_sgs)["propriedades_padrao"]}
        fator_z = lista["Fator de Compressibilidade"]
        assert fator_z["referencia"] == "ISO 12213"
        assert fator_z["valor"] == "0,9980"
        assert fator_z["incerteza"] == "0,0010"

        pcs = lista["Poder Calorífico Superior"]
        assert pcs["referencia"] == "ISO 6976"
        assert pcs["valor"] == "44500"
        assert pcs["incerteza"] == "90"

    def test_valor_sem_referencia_iso_fica_none(self, texto_sgs):
        lista = {p["propriedade"]: p for p in propriedades_padrao(texto_sgs)["propriedades_padrao"]}
        densidade = lista["Densidade Relativa"]
        assert densidade["referencia"] is None
        assert densidade["valor"] == "0,6530"
        assert densidade["incerteza"] == "0,0015"


class TestPropriedadesAmostragem:
    def test_retorna_lista_vazia_para_texto_vazio(self):
        assert propriedades_amostragem("") == {"propriedades_amostragem": []}

    def test_retorna_lista_vazia_quando_secao_nao_encontrada(self):
        assert propriedades_amostragem("texto sem a secao de amostragem") == {"propriedades_amostragem": []}

    def test_tem_4_propriedades(self, texto_sgs):
        lista = propriedades_amostragem(texto_sgs)["propriedades_amostragem"]
        assert len(lista) == 4

    def test_referencia_iso_tem_precedencia_sobre_a_nota(self, texto_sgs):
        lista = {p["propriedade"]: p for p in propriedades_amostragem(texto_sgs)["propriedades_amostragem"]}
        fator_z = lista["Fator de Compressibilidade"]
        # Line carries both a "(2)" note and an ISO reference; the ISO
        # reference wins (see propriedades_amostragem's docstring).
        assert fator_z["referencia"] == "ISO 12213"
        assert fator_z["valor"] == "0,9550"
        assert fator_z["incerteza"] == "0,0012"

    def test_nota_vira_referencia_quando_nao_ha_iso(self, texto_sgs):
        lista = {p["propriedade"]: p for p in propriedades_amostragem(texto_sgs)["propriedades_amostragem"]}
        densidade = lista["Densidade Relativa"]
        assert densidade["referencia"] == "(2)"
        assert densidade["valor"] == "0,6600"
        assert densidade["incerteza"] == "0,0016"

        temperatura = lista["Temperatura de Amostragem"]
        assert temperatura["referencia"] == "(2)"
        assert temperatura["valor"] == "25,0"
        assert temperatura["incerteza"] == "0,5"


class TestExtrairCamposCromato:
    @pytest.fixture
    def campos(self, texto_sgs):
        return extrair_campos_cromato(texto_sgs)

    def test_tem_as_cinco_chaves_esperadas(self, campos):
        assert set(campos.keys()) == {
            "empresa", "certificado", "composicao", "propriedades_pad", "propriedades_amost",
        }

    def test_composicao_embutida_bate_com_a_funcao_isolada(self, campos, texto_sgs):
        assert campos["composicao"] == composicao(texto_sgs)

    def test_propriedades_embutidas_batem_com_as_funcoes_isoladas(self, campos, texto_sgs):
        assert campos["propriedades_pad"] == propriedades_padrao(texto_sgs)
        assert campos["propriedades_amost"] == propriedades_amostragem(texto_sgs)
