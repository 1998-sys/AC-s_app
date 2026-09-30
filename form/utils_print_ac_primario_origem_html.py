# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : form.utils_print_ac_primario_origem_html
# Created       : 29-09-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Generates the ORIGEM "Medidor Linear" (primary meter) Critical Analysis report as PDF from an HTML/Jinja2 template — see templates/ac_primario_origem.html. Source: FO-COR-GER-CPROD-031_0_1.xlsx (a blank template, never filled — see tasks/TAREFAS_ac_primario_yinson_origem.md). Unlike PRIO's AC Primário (point-by-point comparison + charts) or YINSON's (threshold table with live formulas), this is a plain a-r checklist, same visual family as the already-migrated AC Secundário/PO ORIGEM reports — and, same as those, every item defaults to SIM (confirmed with the user: the source template ships with no marks at all, so there is nothing certificate-specific to derive per item).
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import os
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from form.html_to_pdf import html_para_pdf
from form.utils_print_linearizacao import _data_br
from form.utils_print_linearizacao_html import _TEMPLATE_DIR, _logo_base64

# Checklist item text transcribed from FO-COR-GER-CPROD-031_0_1.xlsx, rows
# 15-32 (column A) — every item ships with no mark at all in the source
# template (a genuinely blank form, never used for a real certificate), so
# there is no per-item default to replicate faithfully like the other AC
# families had; every item defaults to SIM per explicit user instruction.
_CHECKLIST_ORIGEM_PRIMARIO = [
    "a) Identificação unívoca (Número do Certificado de Calibração).",
    "b) Nome e endereço do Laboratório/Empresa.",
    "c) Logotipo da RBC (para instrumento associado a sistemas de medição fiscal, apropriação, custódia, flare)",
    "d) Nome e endereço do cliente.",
    "e) Número de páginas e total de páginas.",
    "f) Identificação do método utilizado (Master meter/Prover/Tanque serafim).",
    "g) A descrição e identificação do item de calibração (ex.: nome, fabricante, tipo, modelo, número de série, outra identificação estabelecida pelo cliente).",
    "h) Condição do item sob análise (ex.: K-Factor nominal).",
    "i) A data da realização da calibração",
    "j) Os resultados da calibração estão com as unidades de medida no SI, onde apropriado.",
    "k) Evidências de que as medições são rastreáveis (Identificação dos padrões utilizados).",
    "l) Nome(s), função(ões) e assinatura (s) ou identificações equivalentes das pessoas autorizadas para emissão do certificado.",
    "m) Declaração de que os resultados e incertezas se referem somente aos itens calibrados.",
    "n) Incerteza da calibração",
    "o) Nível de confiança e fator de abrangência.",
    "p) Informações de número de corridas efetuadas",
    "q) Fator do medidor (Meter Factor)",
    "r) Identificação do fluido utilizado na calibração",
]

# t_lista_medidor_vazao (PetrobrasSchemaV3.0.0.xsd) — only these 3 have a
# checkbox in the source template; a certificate with another type (ex.:
# "V-CONE", "DESLOCAMENTO POSITIVO") leaves all 3 unmarked, same as the
# blank template itself would.
_TIPOS_SENSOR = {
    "CORIOLIS": "marca_coriolis",
    "TURBINA": "marca_turbina",
    "ULTRASSÔNICO": "marca_ultrassonico",
    "ULTRASSONICO": "marca_ultrassonico",  # tolerate the XML without the accent
}

_MARCADO = "[ ✔ ]"
_DESMARCADO = "[ ]"


def montar_contexto_ac_primario_origem(dados: dict) -> dict:
    """Builds the Jinja2 context for `templates/ac_primario_origem.html`.

    Args:
        dados: current certificate's data (`xml_extractor_FT.extrair_dados_ft`
            output), with `cliente`/`n_ac` already filled in by the prompt
            in `PdfProcessingService._processar_ac_primario` (`n_ac` is
            optional — ORIGEM's "Identificação (CE)" field has no source in
            the flow meter XML, same gap `n_ac` already has for the
            secondary-instrument ORIGEM reports).

    Returns:
        dict: context ready to pass to the Jinja2 template.
    """
    tipo = (dados.get("tipo") or "").strip().upper()
    marcas = {"marca_coriolis": _DESMARCADO, "marca_turbina": _DESMARCADO, "marca_ultrassonico": _DESMARCADO}
    campo_marcado = _TIPOS_SENSOR.get(tipo)
    if campo_marcado:
        marcas[campo_marcado] = _MARCADO

    checklist = [{"texto": texto, "resposta": "SIM"} for texto in _CHECKLIST_ORIGEM_PRIMARIO]

    contexto = {
        "logo_origem": _logo_base64("logo_origem_cabecalho.png"),
        "tag": dados.get("tag", ""),
        "localizacao": dados.get("unidade_operacional", ""),
        "identificacao": f"CE: {dados.get('n_ac', '')}",
        "certificado": dados.get("numero_certificado", ""),
        "data_calibracao": _data_br(dados.get("data_calibracao", "")),
        "empresa_certificadora": "ODS Lab",
        "checklist": checklist,
        "observacao": "",
        "data_entrega": datetime.now().strftime("%d/%m/%Y"),
    }
    contexto.update(marcas)
    return contexto


def gerar_ac_primario_origem_pdf(dados: dict, caminho_xml: str, sessao=None) -> str:
    """Renders `templates/ac_primario_origem.html` and exports it to PDF.

    Args:
        dados: current certificate's data (see `montar_contexto_ac_primario_origem`).
        caminho_xml: path of the input XML; used to determine the output folder.
        sessao: optional already-open `SessaoHtmlParaPdf` to reuse. `None`
            falls back to a throwaway one-off session.

    Returns:
        str: absolute path of the generated PDF.
    """
    contexto = montar_contexto_ac_primario_origem(dados)

    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("ac_primario_origem.html").render(**contexto)

    pasta_saida = os.path.dirname(os.path.abspath(caminho_xml))
    cert_limpo = (dados.get("numero_certificado") or "").replace(" ", "")
    tag_limpa = (dados.get("tag") or "").replace(" ", "")
    caminho_pdf = os.path.join(pasta_saida, f"{cert_limpo}_{tag_limpa}_AC_MEDIDOR_PRIMARIO.pdf")

    if os.path.exists(caminho_pdf):
        os.remove(caminho_pdf)

    if sessao is not None:
        sessao.exportar(html, caminho_pdf)
    else:
        html_para_pdf(html, caminho_pdf)

    return caminho_pdf
