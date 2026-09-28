# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : form.utils_print_ac_po_html
# Created       : 28-09-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : HTML/WebView2 replacement for form.utils_print_PRIO_PO and
#                 form.po_templates (AC Placa de Orifício — PRIO, YINSON,
#                 YINSON ATLANTA, ORIGEM), rendering templates/ac_po_prio.html
#                 and templates/ac_po_circulo.html instead of filling
#                 TemplateAC_PO_*.xlsx via Excel COM.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import os
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape

from form.html_to_pdf import html_para_pdf
from form.utils_print_linearizacao_html import _TEMPLATE_DIR, _logo_base64

# All checklist item text/marks below are 100% static boilerplate in the
# original templates (never touched by `utils_print_PRIO_PO.gerar_ac_prio_po`
# or `po_templates.gerar_ac_po` — see the audit in
# tasks/TAREFAS_migracao_html_ac_secundario_po.md), transcribed
# programmatically (not by hand) from each TemplateAC_PO_*.xlsx to avoid
# transcription errors given the item count (34+4 for PRIO, 20+3/4 for the
# others).

_CHECKLIST_PO_PRIO_1 = [
    ("a) Identificação unívoca (Número do Certificado de Calibração).", "SIM"),
    ("b) Nome e endereço do Laboratório/Empresa.", "SIM"),
    ("c) Logotipo da RBC (para instrumento associado a sistemas de medição fiscal, apropriação, custódia, flare)", "SIM"),
    ("d) Nome e endereço do cliente.", "SIM"),
    ("e) Número de páginas e total de páginas.", "SIM"),
    ("f) Identificação do método/procedimento utilizado.", "SIM"),
    ("g) Registro das condições ambientais.", "SIM"),
    ("h) Descrição e identificação do item de calibração (ex.: nome, fabricante, tipo, modelo, número de série, etc).", "SIM"),
    ("i) A data da realização da inspeção.", "SIM"),
    ("j) Os resultados da inspeção estão com as unidades de medida no SI, onde apropriado.", "SIM"),
    ("k) Evidências de que as medições são rastreáveis (Informações dos padrões utilizados).", "SIM"),
    ("l) Nome(s), função(ões) e assinatura(s) ou identificações equivalentes das pessoas autorizadas para emissão do certificado.", "SIM"),
    ("m) Declaração de que os resultados e incertezas se referem somente aos itens inspecionados.", "SIM"),
    ("n) Incertezas das medições de diâmetro.", "SIM"),
    ("o) Nível de confiança e fator de abrangência.", "SIM"),
    ("p) Norma de referência utilizada na inspeção.", "SIM"),
    ("q) Medida de diâmetro do orifício corrigido a 20º C (“dr”).", "SIM"),
    ("r) Medida de rugosidade a montante.", "SIM"),
    ("s) Medida de rugosidade a jusante (AGA 3).", "SIM"),
    ("t) Medida de espessura “E”.", "SIM"),
    ("u) Medida de espessura “e”.", "SIM"),
    ("v) Medida de planeza/planicidade.", "SIM"),
    ("w) Medida de ângulo do chanfro “α”.", "SIM"),
    ("x) O certificado informa da aprovação/reprovação da placa conforme a norma de referência?", "SIM"),
]

_CHECKLIST_PO_PRIO_2 = [
    ("a) Identificação unívoca ao respectivo Certificado de Inspeção.", "SIM"),
    ("b) Data da inspeção coincidente ao Certificado de Inspeção.", "SIM"),
    ("c) Diâmetro nas condições de referência.", "SIM"),
    ("d) CE/SAP da placa.", "SIM"),
]

# Shared by YINSON PO and ORIGEM PO (identical text/marks in both templates).
_CHECKLIST_PO_CIRCULO_1 = [
    ("a) Identificação unívoca (Número do Certificado de Calibração).", "SIM"),
    ("b) Nome e endereço do Laboratório/Empresa.", "SIM"),
    ("c) Logotipo da RBC (para instrumento associado a sistemas de medição fiscal, apropriação, custódia, flare)", "SIM"),
    ("d) Nome e endereço do cliente.", "SIM"),
    ("e) Número de páginas e total de páginas.", "SIM"),
    ("f) Identificação do método/procedimento utilizado.", "SIM"),
    ("g) Registro das condições ambientais.", "SIM"),
    ("h) Descrição e identificação do item de calibração (ex.: nome, fabricante, tipo, modelo, número de série, outra identificação estabelecida pelo cliente).", "SIM"),
    ("i) A data da realização da inspeção.", "NA"),
    ("j) Os resultados da inspeção estão com as unidades de medida no SI, onde apropriado.", "SIM"),
    ("k)  Evidências de que as medições são rastreáveis (Informações dos padrões utilizados).", "SIM"),
    ("l) Nome(s), função(ões) e assinatura(s) ou identificações equivalentes das pessoas autorizadas para emissão do certificado.", "SIM"),
    ("m) Declaração de que os resultados e incertezas se referem somente aos itens inspecionados.", "SIM"),
    ("n)  Incertezas das medições de diâmetro.", "SIM"),
    ("o) Nível de confiança e fator de abrangência.", "SIM"),
    ("p) Norma de referência utilizada na inspeção", "SIM"),
    ("q) Medida de diâmetro do orifício corrigido a 20º C (“dr”)", "SIM"),
    ("r) Medida de rugosidade a montante", "SIM"),
    ("s) Medida de rugosidade a jusante", "NA"),
    ("t) Medida de espessura “E”", "NA"),
    ("u) Medida de espessura “e”", "NA"),
    ("v) Medida de planeza/planicidade", "NA"),
    ("w) Medida de ângulo do chanfro “φ”", "NA"),
    ("x) O certificado informa da aprovação/reprovação da placa conforme a norma de referência?", "NA"),
]

# YINSON ATLANTA PO's template has different default marks for items i and
# s-x (all "SIM" instead of "NÃO APLICÁVEL") — a genuine, deliberate content
# difference confirmed cell-by-cell against the base YINSON PO template, not
# a copy/paste artifact — kept as its own constant rather than reused.
_CHECKLIST_PO_CIRCULO_1_ATLANTA = [
    ("a) Identificação unívoca (Número do Certificado de Calibração).", "SIM"),
    ("b) Nome e endereço do Laboratório/Empresa.", "SIM"),
    ("c) Logotipo da RBC (para instrumento associado a sistemas de medição fiscal, apropriação, custódia, flare)", "SIM"),
    ("d) Nome e endereço do cliente.", "SIM"),
    ("e) Número de páginas e total de páginas.", "SIM"),
    ("f) Identificação do método/procedimento utilizado.", "SIM"),
    ("g) Registro das condições ambientais.", "SIM"),
    ("h) Descrição e identificação do item de calibração (ex.: nome, fabricante, tipo, modelo, número de série, outra identificação estabelecida pelo cliente).", "SIM"),
    ("i) A data da realização da inspeção.", "SIM"),
    ("j) Os resultados da inspeção estão com as unidades de medida no SI, onde apropriado.", "SIM"),
    ("k)  Evidências de que as medições são rastreáveis (Informações dos padrões utilizados).", "SIM"),
    ("l) Nome(s), função(ões) e assinatura(s) ou identificações equivalentes das pessoas autorizadas para emissão do certificado.", "SIM"),
    ("m) Declaração de que os resultados e incertezas se referem somente aos itens inspecionados.", "SIM"),
    ("n)  Incertezas das medições de diâmetro.", "SIM"),
    ("o) Nível de confiança e fator de abrangência.", "SIM"),
    ("p) Norma de referência utilizada na inspeção", "SIM"),
    ("q) Medida de diâmetro do orifício corrigido a 20º C (“dr”)", "SIM"),
    ("r) Medida de rugosidade a montante", "SIM"),
    ("s) Medida de rugosidade a jusante", "SIM"),
    ("t) Medida de espessura “E”", "SIM"),
    ("u) Medida de espessura “e”", "SIM"),
    ("v) Medida de planeza/planicidade", "SIM"),
    ("w) Medida de ângulo do chanfro “φ”", "SIM"),
    ("x) O certificado informa da aprovação/reprovação da placa conforme a norma de referência?", "SIM"),
]

# Shared by YINSON PO and YINSON ATLANTA PO (identical, confirmed cell-by-cell).
_CHECKLIST_ETIQUETA_YINSON = [
    ("a) Identificação unívoca ao respectivo Certificado de Inspeção.", "SIM"),
    ("b) Data da inspeção coincidente ao Certificado de Inspeção.", "SIM"),
    ("c) Diâmetro nas condições de referência", "SIM"),
]

_CHECKLIST_ETIQUETA_ORIGEM = [
    ("a) Identificação unívoca ao respectivo Certificado de Inspeção.", "SIM"),
    ("b) Data da inspeção coincidente ao Certificado de Inspeção.", "SIM"),
    ("c) Diâmetro nas condições de referência", "SIM"),
    ("d) CE/SAP da placa", "SIM"),
]

# The "OUTRAS INFORMAÇÕES" instrument-type checkboxes are also static in all
# 3 circle-style PO templates (PDT checked, everything else unchecked) —
# unlike the AC Secundário family, none of `po_templates.gerar_ac_po`'s
# per-client configs ever touch these cells.
_MARCADO = "[ ✔ ]"
_DESMARCADO = "[ ]"


def _sanitizar_nome_arquivo(texto: str) -> str:
    """Replaces characters invalid for a file name with a hyphen (same rule as `utils_print_PRIO_PO.gerar_ac_prio_po`'s local `sanitize`)."""
    return re.sub(r'[<>:"/\\|?*]+', "-", str(texto or "")).strip()


def _limpar_nome_arquivo(texto: str) -> str:
    """Removes invalid filename characters and turns spaces into underscores (same rule as `po_templates.limpar_nome_arquivo`)."""
    if not texto:
        return ""
    texto = re.sub(r'[\\/*?:"<>|]', "", texto)
    texto = re.sub(r"\s+", "_", texto)
    return texto.strip()


def montar_contexto_ac_po_prio(dados: dict) -> dict:
    """Builds the Jinja2 context for `templates/ac_po_prio.html` from the certificate fields.

    Args:
        dados: Certificate fields, same shape `utils_print_PRIO_PO.gerar_ac_prio_po`
            already expected (`local`, `data_calibracao`, `sn_inst`,
            `certificado`, `report_date`, `tag`).

    Returns:
        dict: context ready to pass to the Jinja2 template.
    """
    return {
        "logo_principal": _logo_base64("logo_prio_cabecalho.png"),
        "local": dados.get("local", ""),
        "sn_inst": dados.get("sn_inst", ""),
        "certificado": dados.get("certificado", ""),
        "data_calibracao": dados.get("data_calibracao", ""),
        "empresa_certificadora": "ODS Metering Systems",
        "checklist_1": [{"texto": t, "resposta": r} for t, r in _CHECKLIST_PO_PRIO_1],
        "checklist_2": [{"texto": t, "resposta": r} for t, r in _CHECKLIST_PO_PRIO_2],
        # No date-adjustment rule here — `utils_print_PRIO_PO.gerar_ac_prio_po`
        # writes `report_date` straight into the cell, unlike the other AC
        # families (no +1 day, no weekend push).
        "data_entrega": dados.get("report_date", ""),
    }


def gerar_ac_prio_po_pdf(dados: dict, caminho_pdf_original: str, sessao=None) -> str:
    """Renders `templates/ac_po_prio.html` and exports it to PDF.

    HTML/WebView2 replacement for `form.utils_print_PRIO_PO.gerar_ac_prio_po`
    (Excel COM) — same output filename convention (`{certificado}_{tag}_AC.pdf`).

    Args:
        dados: Certificate fields (see `montar_contexto_ac_po_prio`).
        caminho_pdf_original: Path of the source PDF, used to determine the
            output folder.
        sessao: Optional already-open `SessaoHtmlParaPdf` to reuse. `None`
            falls back to a throwaway one-off session.

    Returns:
        str: absolute path of the generated PDF.
    """
    contexto = montar_contexto_ac_po_prio(dados)

    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("ac_po_prio.html").render(**contexto)

    pasta_saida = os.path.dirname(os.path.abspath(caminho_pdf_original))
    certificado = _sanitizar_nome_arquivo(dados.get("certificado")).replace(" ", "")
    tag = _sanitizar_nome_arquivo(dados.get("tag")).replace(" ", "")
    caminho_pdf = os.path.join(pasta_saida, f"{certificado}_{tag}_AC.pdf".strip("_"))

    if os.path.exists(caminho_pdf):
        os.remove(caminho_pdf)

    if sessao is not None:
        sessao.exportar(html, caminho_pdf)
    else:
        html_para_pdf(html, caminho_pdf)

    return caminho_pdf


# Client configuration for the circle-style PO family — mirrors
# `po_templates.CONFIG_ORIGEM_PO`/`CONFIG_YINSON_PO`/`CONFIG_YINSON_ATLANTA_PO`
# (same cell/field semantics), plus what's only meaningful for HTML
# rendering (logos, static header text, checklist family, per-client labels).
CONFIG_YINSON_PO = {
    "estilo": "simples",
    "titulo": "ANÁLISE CRÍTICA\n DE INSPEÇÃO DE\nPLACA DE ORIFÍCIO",
    "logo_principal": "logo_yinson_cabecalho.png",
    "logo_extra": None,
    "linha5_rotulo1": "Cliente", "linha5_valor_campo1": None, "linha5_valor_fixo1": "Yinson",
    "linha5_rotulo2": "Localização", "linha5_valor_campo2": "local",
    "linha5_rotulo3": "NS", "linha5_valor_campo3": "sn_inst",
    "rotulo_data_calibracao": "Data da Inspeção",
    "mostrar_data_instalacao": False,
    "campo_certificado": "certificado",
    "campo_data_calibracao": "data_calibracao",
    "checklist_1": _CHECKLIST_PO_CIRCULO_1,
    "checklist_2": _CHECKLIST_ETIQUETA_YINSON,
    "nome_arquivo_campo": "certificado",
}

CONFIG_YINSON_ATLANTA_PO = {
    **CONFIG_YINSON_PO,
    "logo_extra": "logo_brava_cabecalho.png",
    "checklist_1": _CHECKLIST_PO_CIRCULO_1_ATLANTA,
}

CONFIG_ORIGEM_PO = {
    "estilo": "doc",
    "titulo": "REGISTRO DE ANÁLISE CRÍTICA\nDO CERTIFICADO DE INSPEÇÃO DE\nPLACA DE ORIFÍCIO",
    "logo_principal": "logo_origem_cabecalho.png",
    "logo_extra": None,
    "linha5_rotulo1": "TAG", "linha5_valor_campo1": "sn_inst",
    "linha5_rotulo2": "Localização", "linha5_valor_campo2": "localizacao",
    "linha5_rotulo3": "Identificação", "linha5_valor_campo3": "n_ac",
    "rotulo_data_calibracao": "Data da Calibração",
    "mostrar_data_instalacao": True,
    "campo_certificado": "certificado",
    "campo_data_calibracao": "data_calibracao",
    "checklist_1": _CHECKLIST_PO_CIRCULO_1,
    "checklist_2": _CHECKLIST_ETIQUETA_ORIGEM,
    "nome_arquivo_campo": "n_ac",
}


def montar_contexto_ac_po_circulo(config: dict, dados: dict) -> dict:
    """Builds the Jinja2 context for `templates/ac_po_circulo.html` from one client's config + certificate fields.

    Args:
        config: One of `CONFIG_YINSON_PO`/`CONFIG_YINSON_ATLANTA_PO`/`CONFIG_ORIGEM_PO`.
        dados: Certificate fields, same shape `po_templates.gerar_ac_po`
            already expected — which keys are read depends on `config`
            (see each `CONFIG_*`'s `linha5_valor_campo*`/`campo_*`).

    Returns:
        dict: context ready to pass to the Jinja2 template.
    """
    def valor(campo_key, fixo_key):
        fixo = config.get(fixo_key)
        if fixo is not None:
            return fixo
        campo = config[campo_key]
        return dados.get(campo, "") if campo else ""

    return {
        "estilo": config["estilo"],
        "titulo": config["titulo"],
        "logo_principal": _logo_base64(config["logo_principal"]),
        "logo_extra": _logo_base64(config["logo_extra"]) if config["logo_extra"] else None,
        "linha5_rotulo1": config["linha5_rotulo1"],
        "linha5_valor1": valor("linha5_valor_campo1", "linha5_valor_fixo1"),
        "linha5_rotulo2": config["linha5_rotulo2"],
        "linha5_valor2": valor("linha5_valor_campo2", "linha5_valor_fixo2"),
        "linha5_rotulo3": config["linha5_rotulo3"],
        "linha5_valor3": valor("linha5_valor_campo3", "linha5_valor_fixo3"),
        "marca_pt": _DESMARCADO,
        "marca_pdt": _MARCADO,
        "marca_tt": _DESMARCADO,
        "marca_te": _DESMARCADO,
        "rotulo_data_calibracao": config["rotulo_data_calibracao"],
        "mostrar_data_instalacao": config["mostrar_data_instalacao"],
        "certificado": dados.get(config["campo_certificado"], ""),
        "data_calibracao": dados.get(config["campo_data_calibracao"], ""),
        "empresa_certificadora": "ODS Lab",
        "checklist_1": [{"texto": t, "resposta": r} for t, r in config["checklist_1"]],
        "checklist_2": [{"texto": t, "resposta": r} for t, r in config["checklist_2"]],
        # No date-adjustment rule here either — `po_templates.gerar_ac_po`
        # writes `report_date` straight into "Data: {report_date}".
        "data_entrega": dados.get("report_date", ""),
    }


def gerar_ac_po_circulo_pdf(config: dict, dados: dict, caminho_pdf_original: str, sessao=None) -> str:
    """Renders `templates/ac_po_circulo.html` for one client config and exports it to PDF.

    HTML/WebView2 replacement for `form.po_templates.gerar_ac_po` (Excel COM)
    — same output filename convention (`{nome_arquivo_campo}_AC.pdf`).

    Args:
        config: One of `CONFIG_YINSON_PO`/`CONFIG_YINSON_ATLANTA_PO`/`CONFIG_ORIGEM_PO`.
        dados: Certificate fields (see `montar_contexto_ac_po_circulo`).
        caminho_pdf_original: Path of the source PDF, used to determine the
            output folder.
        sessao: Optional already-open `SessaoHtmlParaPdf` to reuse. `None`
            falls back to a throwaway one-off session.

    Returns:
        str: absolute path of the generated PDF.
    """
    contexto = montar_contexto_ac_po_circulo(config, dados)

    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("ac_po_circulo.html").render(**contexto)

    pasta_saida = os.path.dirname(os.path.abspath(caminho_pdf_original))
    nome_base = _limpar_nome_arquivo(dados.get(config["nome_arquivo_campo"], ""))
    caminho_pdf = os.path.join(pasta_saida, f"{nome_base}_AC.pdf")

    if os.path.exists(caminho_pdf):
        os.remove(caminho_pdf)

    if sessao is not None:
        sessao.exportar(html, caminho_pdf)
    else:
        html_para_pdf(html, caminho_pdf)

    return caminho_pdf


def gerar_ac_yinson_po_pdf(dados: dict, caminho_pdf_original: str, sessao=None) -> str:
    """Renders the AC PO YINSON report as HTML/PDF (see `gerar_ac_po_circulo_pdf`)."""
    return gerar_ac_po_circulo_pdf(CONFIG_YINSON_PO, dados, caminho_pdf_original, sessao=sessao)


def gerar_ac_yinson_atlanta_po_pdf(dados: dict, caminho_pdf_original: str, sessao=None) -> str:
    """Renders the AC PO YINSON ATLANTA report as HTML/PDF (see `gerar_ac_po_circulo_pdf`)."""
    return gerar_ac_po_circulo_pdf(CONFIG_YINSON_ATLANTA_PO, dados, caminho_pdf_original, sessao=sessao)


def gerar_ac_origem_po_pdf(dados: dict, caminho_pdf_original: str, sessao=None) -> str:
    """Renders the AC PO ORIGEM report as HTML/PDF (see `gerar_ac_po_circulo_pdf`)."""
    return gerar_ac_po_circulo_pdf(CONFIG_ORIGEM_PO, dados, caminho_pdf_original, sessao=sessao)
