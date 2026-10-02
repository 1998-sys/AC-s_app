# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : xml_model.xml_cromato
# Created       : 25-02-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Builds the reduced chromatography certificate XML with only the properties used in the flow calculation.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import unicodedata
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement

from xml_model.xml_common import salvar_xml_bonito


def _normalizar(texto):
    """Normalizes text for comparison: uppercase and without accents/diacritics.

    Args:
        texto: text to normalize (accepts None, treated as an empty string).

    Returns:
        str: uppercase text, without accentuation marks.
    """
    texto = (texto or "").upper()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def _buscar_propriedade(lista, incluir_todos=(), incluir_algum=(), excluir=()):
    """Finds the first property in the list whose name matches the given filters.

    Searches a list of extracted properties (propriedades_padrao or
    propriedades_amostragem) for the first item whose `propriedade` field
    contains all the terms in `incluir_todos`, at least one of
    `incluir_algum` (if provided) and none of `excluir` — all compared
    without accents/case.

    Args:
        lista: list of property dicts extracted from the PDF, each with
            keys "propriedade", "valor" and "incerteza".
        incluir_todos: terms that must ALL appear in the property name.
        incluir_algum: terms of which AT LEAST ONE must appear, if provided.
        excluir: terms that must NOT appear in the property name.

    Returns:
        tuple: (valor, incerteza) of the first matching item, or (None, None)
        if no item satisfies the filters.
    """
    for item in lista:
        nome = _normalizar(item.get("propriedade"))
        if not all(t in nome for t in incluir_todos):
            continue
        if incluir_algum and not any(t in nome for t in incluir_algum):
            continue
        if any(t in nome for t in excluir):
            continue
        return item.get("valor"), item.get("incerteza")
    return None, None


def xml_cromatografia(pdf_path: str, dados: dict, caminho_saida_xml: str | None = None) -> str:
    """Generates the reduced chromatography XML used in the flow calculation.

    Includes the certificate identification and only the 5 parameters used
    in the flow calculation (molar mass, absolute density — at
    standard/base condition — and compressibility factor, viscosity and
    isentropic coefficient at line/sampling conditions, "_CL" suffix).

    Args:
        pdf_path: path of the source PDF (used only to validate its
            existence and, if `caminho_saida_xml` is not provided, to derive
            the output XML name).
        dados: dictionary with the data extracted from the PDF (empresa,
            certificado, propriedades_pad, propriedades_amost).
        caminho_saida_xml: path of the output XML; if None, uses the same
            name as the PDF replacing the extension with .xml.

    Returns:
        str: absolute path of the generated XML file.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")

    if caminho_saida_xml is None:
        caminho_saida_xml = pdf_path.with_suffix(".xml")
    caminho_saida_xml = Path(caminho_saida_xml)

    root = Element("CROMATOGRAFIA")

    empresa = dados.get("empresa")
    certificado = dados.get("certificado")
    if empresa is not None:
        SubElement(root, "EMPRESA").text = str(empresa)
    if certificado is not None:
        SubElement(root, "CERTIFICADO").text = str(certificado)

    padrao = (dados.get("propriedades_pad") or {}).get("propriedades_padrao", []) or []
    amostragem = (dados.get("propriedades_amost") or {}).get("propriedades_amostragem", []) or []

    # Viscosity (note (2) of the SGS report) comes from a reference
    # correlation, not a direct measurement — that's why the reduced XML
    # has no uncertainty field for it, only value (see approved example).
    campos = [
        ("MASSA_MOLAR", padrao, {"incluir_algum": ("MOLECULAR", "MOLAR")}, True),
        ("DENSIDADE_ABSOLUTA", padrao, {"incluir_todos": ("DENSIDADE",), "excluir": ("RELATIVA",)}, True),
        ("FATOR_COMPRESSIBILIDADE_CL", amostragem, {"incluir_todos": ("COMPRESSIBILIDADE",)}, True),
        ("VISCOSIDADE_GAS_CL", amostragem, {"incluir_todos": ("VISCOSIDADE",)}, False),
        ("COEFICIENTE_ISENTROPICO_CL", amostragem, {"incluir_todos": ("COEFICIENTE",), "incluir_algum": ("ADIABATIC", "ISENTROP")}, True),
    ]

    for tag, lista, filtro, com_incerteza in campos:
        valor, incerteza = _buscar_propriedade(lista, **filtro)
        if valor is not None:
            SubElement(root, tag).text = str(valor)
        if com_incerteza and incerteza is not None:
            SubElement(root, f"{tag}_INCERTEZA").text = str(incerteza)

    return salvar_xml_bonito(root, caminho_saida_xml)


def xml_cromatografia_completa(pdf_path: str, dados: dict, caminho_saida_xml: str | None = None) -> str:
    """Generates the full chromatography XML — certificate header, full gas
    composition (one COMPONENTE per element) and every property reported at
    both standard condition and sampling condition, each with its own
    uncertainty.

    This is the original schema used before the 2026-08-25 reduction to
    just the 5 flow-calculation parameters (see `xml_cromatografia`) —
    restored here for labs/flows that need the complete certificate
    content instead of the reduced one (currently: GT Química, see
    `gui.pdf_service._gerar_cromatografia`). Any section/field missing from
    `dados` is simply omitted, not an error — e.g. a parser that doesn't
    extract gas composition yet just produces an empty `COMPOSICAOGASES`.

    Args:
        pdf_path: path of the source PDF (used only to validate its
            existence and, if `caminho_saida_xml` is not provided, to derive
            the output XML name).
        dados: dictionary with the data extracted from the PDF — same shape
            `pdf.parser_sgs.extrair_campos_cromato` returns (empresa,
            certificado, composicao, propriedades_pad, propriedades_amost).
        caminho_saida_xml: path of the output XML; if None, uses the same
            name as the PDF replacing the extension with .xml.

    Returns:
        str: absolute path of the generated XML file.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")

    if caminho_saida_xml is None:
        caminho_saida_xml = pdf_path.with_suffix(".xml")
    caminho_saida_xml = Path(caminho_saida_xml)

    root = Element("CROMATOGRAFIA")

    cab = SubElement(root, "CABECALHO")
    empresa = dados.get("empresa")
    certificado = dados.get("certificado")
    if empresa is not None:
        SubElement(cab, "EMPRESA").text = str(empresa)
    if certificado is not None:
        SubElement(cab, "CERTIFICADO").text = str(certificado)

    comp_wrap = SubElement(root, "COMPOSICAOGASES")
    comp_list = (dados.get("composicao") or {}).get("composicao", []) or []
    for item in comp_list:
        rot = item.get("rotulo")
        nome = item.get("nome")
        mol = item.get("mol_pct")
        inc = item.get("incerteza")

        comp_el = SubElement(comp_wrap, "COMPONENTE")
        if rot is not None:
            comp_el.set("rotulo", str(rot))
        if nome is not None:
            SubElement(comp_el, "NOME").text = str(nome)
        if mol is not None:
            SubElement(comp_el, "MOLPCT").text = str(mol)
        if inc is not None:
            SubElement(comp_el, "INCERTEZA").text = str(inc)

    def _propriedades(chave_dados, chave_lista, nome_tag):
        wrap = SubElement(root, nome_tag)
        lista = (dados.get(chave_dados) or {}).get(chave_lista, []) or []
        for p in lista:
            prop_el = SubElement(wrap, "PROPRIEDADE")
            ref = p.get("referencia")
            if ref:
                prop_el.set("referencia", str(ref))
            if p.get("propriedade") is not None:
                SubElement(prop_el, "NOME").text = str(p["propriedade"])
            if p.get("valor") is not None:
                SubElement(prop_el, "VALOR").text = str(p["valor"])
            if p.get("incerteza") is not None:
                SubElement(prop_el, "INCERTEZA").text = str(p["incerteza"])

    _propriedades("propriedades_pad", "propriedades_padrao", "PROPRIEDADESCONDICAOPADRAO")
    _propriedades("propriedades_amost", "propriedades_amostragem", "PROPRIEDADESCONDICOESAMOSTRAGEM")

    return salvar_xml_bonito(root, caminho_saida_xml)
