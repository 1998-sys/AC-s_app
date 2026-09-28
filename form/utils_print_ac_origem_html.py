# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : form.utils_print_ac_origem_html
# Created       : 28-09-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : HTML/WebView2 replacement for form.utils_print_ORIGEM
#                 (AC Secundário ORIGEM), rendering templates/ac_origem.html
#                 instead of filling TemplateAC_ORIGEM.xlsx via Excel COM.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import os
from datetime import datetime, timedelta

from jinja2 import Environment, FileSystemLoader, select_autoescape

from form.html_to_pdf import html_para_pdf
from form.utils_print_linearizacao_html import _TEMPLATE_DIR, _logo_base64

# Checklist item text is 100% static boilerplate in the original template
# (never touched by `utils_print_ORIGEM.gerar_ac_origem` — see the audit in
# tasks/TAREFAS_migracao_html_ac_secundario_po.md) — transcribed cell-by-cell
# from TemplateAC_ORIGEM.xlsx (rows 17-35, columns A/F/G/H).
_CHECKLIST_ORIGEM = [
    ("a) Identificação unívoca (Número do Certificado de Calibração).", "SIM"),
    ("b) Nome e endereço do Laboratório/Empresa.", "SIM"),
    ("c) Logotipo da RBC (para instrumento associado a sistemas de medição fiscal, apropriação, custódia, flare)", "SIM"),
    ("d) Nome e endereço do cliente.", "SIM"),
    ("e) Número de páginas e total de páginas.", "SIM"),
    ("f) Identificação do método/procedimento utilizado.", "SIM"),
    ("g) Registro das condições ambientais.", "SIM"),
    ("h) Descrição e identificação do item de calibração (ex.: nome, fabricante, tipo, modelo, número de série, outra identificação estabelecida pelo cliente).", "SIM"),
    ("i) A data do recebimento do(s) item(s) de calibração, se necessário.", "NA"),
    ("j) A data da realização da calibração.", "SIM"),
    ("k) Os resultados da calibração estão com as unidades de medida no SI, onde apropriado.", "SIM"),
    ("l) Evidências de que as medições são rastreáveis (Informações dos padrões utilizados).", "SIM"),
    ("m) Nome(s), função (ões) e assinatura (s) ou identificações equivalentes das pessoas autorizadas para emissão do certificado.", "SIM"),
    ("n) Declaração de que os resultados e incertezas se referem somente aos itens calibrados / inspecionados.", "SIM"),
    ("o) Nível de confiança e fator de abrangência.", "SIM"),
    ("p) Foi feita calibração de acordo com a faixa solicitada?", "SIM"),
    ("q) Os erros máximos de medição (Erro sistemático remanescente + incerteza) são inferiores ao erro máximo admissível para o equipamento em questão?", "SIM"),
    ("r) O instrumento está aprovado para o uso no ponto de medição a que se destina de acordo com os critérios de aceitação informados pelo cliente?", "SIM"),
    # Item "s" (as found/as left) is NOT static — see `_resolver_item_s` below.
]

_CATEGORIAS_TERMORRESISTENCIA = (
    "TERMORRESISTÊNCIA PT-100 - 2 FIOS",
    "TERMORRESISTÊNCIA PT-100 - 3 FIOS",
    "TERMORRESISTÊNCIA PT-100 - 4 FIOS",
)
_CATEGORIAS_TEMPERATURA = (
    "TRANSMISSOR DE TEMPERATURA COM SAÍDA EM UNIDADE ELÉTRICA",
    "TRANSMISSOR DE TEMPERATURA",
    "TERMÔMETRO ANALÓGICO",
    "TERMÔMETRO DIGITAL",
)
_CATEGORIAS_PRESSAO = (
    "TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA",
    "TRANSMISSOR DE PRESSÃO ABSOLUTA COM SAÍDA EM UNIDADE ELÉTRICA",
    "MANOMETRO DIGITAL",
    "MANOMETRO ANALÓGICO",
    "MANOMETRO DIGITAL ABSOLUTO",
)
_CATEGORIAS_PRESSAO_DIFERENCIAL = (
    "MANOMETRO DIFERENCIAL DIGITAL",
    "MANOMETRO DIFERENCIAL ANALÓGICO",
)

_MARCADO = "[ ✔ ]"
_DESMARCADO = "[ ]"


def _marcas_tipo_instrumento(dados: dict) -> dict:
    """Resolves the PT/PDT/TT/TE checkbox marks from the certificate's category.

    Same 4-branch rule as the original `gerar_ac_origem` (never touched a
    5th, unmatched category — that leaves the raw template's own leftover
    defaults untouched; here it just leaves everything unchecked, since
    every category actually used by the app already falls in one of the 4
    branches).

    Args:
        dados: Certificate fields — reads `categoria`, `sn_sensor`, `max_range`.

    Returns:
        dict: `marca_pt`/`marca_pdt`/`marca_tt`/`marca_te`, each `"[ ✔ ]"` or `"[ ]"`.
    """
    categoria = (dados.get("categoria") or "").upper()
    marcas = {"marca_pt": _DESMARCADO, "marca_pdt": _DESMARCADO, "marca_tt": _DESMARCADO, "marca_te": _DESMARCADO}

    if categoria in _CATEGORIAS_TERMORRESISTENCIA:
        marcas["marca_te"] = _MARCADO

    elif categoria in _CATEGORIAS_TEMPERATURA:
        marcas["marca_tt"] = _MARCADO
        if (dados.get("sn_sensor") or "").upper():
            marcas["marca_te"] = _MARCADO

    elif categoria in _CATEGORIAS_PRESSAO:
        try:
            max_range_float = float(dados.get("max_range"))
        except (TypeError, ValueError):
            max_range_float = None
        if categoria == "TRANSMISSOR DE PRESSÃO COM SAÍDA EM UNIDADE ELÉTRICA" and max_range_float is not None and max_range_float <= 250:
            marcas["marca_pdt"] = _MARCADO
        else:
            marcas["marca_pt"] = _MARCADO

    elif categoria in _CATEGORIAS_PRESSAO_DIFERENCIAL:
        marcas["marca_pdt"] = _MARCADO

    return marcas


def _resolver_item_s_e_observacao(dados: dict, dados_xml_petro: dict) -> tuple[str, str]:
    """Resolves item "s" (as found/as left) and the OBSERVAÇÕES text.

    Same if/elif/elif/else precedence as the original `gerar_ac_origem`:
    a range/SN update takes over the OBSERVAÇÕES box AND leaves item "s" at
    its static "NÃO APLICÁVEL" default (the original code's own behavior —
    it only sets item "s" from `dados_xml_petro`'s AS FOUND/AS LEFT in the
    remaining, neither-updated case).

    Args:
        dados: Certificate fields — reads `range_atualizado`/`sn_atualizado`.
        dados_xml_petro: Petrobras XML data — reads `tabela2` ("AS LEFT" vs
            anything else, treated as AS FOUND).

    Returns:
        tuple[str, str]: `(resposta_item_s, observacao)` — `resposta_item_s`
        is one of `"SIM"`/`"NA"`; `observacao` is `""` when neither flag is set.
    """
    if dados.get("range_atualizado"):
        return "NA", "Novo range e alarmes alterados no computador de vazão"
    if dados.get("sn_atualizado"):
        return "NA", "Novo NS alterado no computador de vazão / XML / SFP"
    if dados_xml_petro and dados_xml_petro.get("tabela2") == "AS LEFT":
        return "SIM", ""
    return "NA", ""


def montar_contexto_ac_origem(dados: dict, dados_xml_petro: dict) -> dict:
    """Builds the Jinja2 context for `templates/ac_origem.html` from the certificate fields.

    Args:
        dados: Certificate fields, same shape `utils_print_ORIGEM.gerar_ac_origem`
            already expected (`tag`, `localizacao`, `n_ac`, `certificado`,
            `data`, `categoria`, `sn_sensor`, `max_range`, `report_date`,
            `range_atualizado`, `sn_atualizado`).
        dados_xml_petro: Petrobras XML data (reads `tabela2`).

    Returns:
        dict: context ready to pass to the Jinja2 template.
    """
    resposta_s, observacao = _resolver_item_s_e_observacao(dados, dados_xml_petro)
    checklist = [
        {"texto": texto, "resposta": resposta}
        for texto, resposta in _CHECKLIST_ORIGEM
    ] + [{"texto": "s) No caso de ajuste no equipamento, estão informados os resultados das calibrações como encontrados (as found) e como deixados (as left)?", "resposta": resposta_s}]

    data_entrega = ""
    if dados.get("report_date"):
        dt = datetime.strptime(dados["report_date"], "%d/%m/%Y")
        if dt.weekday() == 5:  # Saturday
            dt += timedelta(days=2)
        elif dt.weekday() == 6:  # Sunday
            dt += timedelta(days=1)
        data_entrega = dt.strftime("%d/%m/%Y")

    contexto = {
        "logo_origem": _logo_base64("logo_origem_cabecalho.png"),
        "tag": dados.get("tag", ""),
        "localizacao": dados.get("localizacao", ""),
        "identificacao": f"CE: {dados.get('n_ac', '')}",
        "certificado": dados.get("certificado", ""),
        "data_calibracao": dados.get("data", ""),
        "empresa_certificadora": "ODS Lab",
        "checklist": checklist,
        "observacao": observacao,
        "data_entrega": data_entrega,
    }
    contexto.update(_marcas_tipo_instrumento(dados))
    return contexto


def gerar_ac_origem_pdf(dados: dict, caminho_pdf_original: str, dados_xml_petro: dict, sessao=None) -> str:
    """Renders `templates/ac_origem.html` and exports it to PDF.

    HTML/WebView2 replacement for `form.utils_print_ORIGEM.gerar_ac_origem`
    (Excel COM) — same output filename convention (`{n_ac}_AC.pdf`,
    alongside the source PDF).

    Args:
        dados: Certificate fields (see `montar_contexto_ac_origem`).
        caminho_pdf_original: Path of the source PDF, used to determine the
            output folder.
        dados_xml_petro: Petrobras XML data; used to determine whether the
            calibration is AS LEFT (otherwise assumes AS FOUND).
        sessao: Optional already-open `SessaoHtmlParaPdf` to reuse (see
            `form.html_to_pdf`). `None` falls back to a throwaway one-off
            session.

    Returns:
        str: absolute path of the generated PDF.

    Raises:
        HtmlParaPdfError: if the WebView2 export itself fails.
    """
    contexto = montar_contexto_ac_origem(dados, dados_xml_petro)

    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("ac_origem.html").render(**contexto)

    pasta_saida = os.path.dirname(os.path.abspath(caminho_pdf_original))
    n_ac = (dados.get("n_ac") or "").replace(" ", "")
    caminho_pdf = os.path.join(pasta_saida, f"{n_ac}_AC.pdf")

    if os.path.exists(caminho_pdf):
        os.remove(caminho_pdf)

    if sessao is not None:
        sessao.exportar(html, caminho_pdf)
    else:
        html_para_pdf(html, caminho_pdf)

    return caminho_pdf
