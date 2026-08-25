import unicodedata
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement

from xml_model.xml_common import salvar_xml_bonito


def _normalizar(texto):
    texto = (texto or "").upper()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def _buscar_propriedade(lista, incluir_todos=(), incluir_algum=(), excluir=()):
    """Procura, numa lista de propriedades extraídas (propriedades_padrao ou
    propriedades_amostragem), a primeira cuja `propriedade` contenha todos
    os termos de `incluir_todos`, ao menos um de `incluir_algum` (se
    informado) e nenhum de `excluir` — tudo comparado sem acento/maiúsculas.
    Retorna (valor, incerteza) ou (None, None) se não encontrar."""
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
    """Gera o XML reduzido de cromatografia: identificação do certificado e
    só os 5 parâmetros usados no cálculo de vazão (massa molar, densidade
    absoluta — em condição padrão/base — e fator de compressibilidade,
    viscosidade e coeficiente isentrópico em condições de linha/amostragem,
    sufixo "_CL")."""
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

    # A viscosidade (nota (2) do relatório SGS) vem de uma correlação de
    # referência, não de uma medição direta — por isso o XML reduzido não
    # tem campo de incerteza pra ela, só valor (ver exemplo aprovado).
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
