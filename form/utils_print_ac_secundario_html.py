# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : form.utils_print_ac_secundario_html
# Created       : 28-09-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : HTML/WebView2 replacement for form.full_ac_templates
#                 (AC Secundário — PRIO/YINSON/YINSON ATLANTA), rendering
#                 templates/ac_secundario.html instead of filling
#                 TemplateAC_PRIO.xlsx/TemplateAC_YINSON.xlsx/
#                 TemplateAC_YINSON - ATLANTA.xlsx via Excel COM.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import os
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from form.full_ac_templates import _titulo_categoria, _adicionar_dia_util
from form.html_to_pdf import html_para_pdf
from form.utils_print_linearizacao_html import _TEMPLATE_DIR, _logo_base64

# Checklist item text is 100% static boilerplate in the original templates
# (never touched by `full_ac_templates.gerar_ac_completo` — see the audit in
# tasks/TAREFAS_migracao_html_ac_secundario_po.md) — kept here verbatim,
# transcribed cell-by-cell from TemplateAC_PRIO.xlsx / TemplateAC_YINSON.xlsx
# (rows 13-31). PRIO has its own wording; YINSON's is reused as-is by
# YINSON ATLANTA (its template's checklist text is identical to YINSON's).
_CHECKLIST_PRIO = [
    ("a) Identificação unívoca (Número do Certificado de Calibração).", "SIM"),
    ("b) Nome e endereço do Laboratório/Empresa.", "SIM"),
    ("c) Logotipo da RBC (para instrumento associado a sistemas de medição fiscal, apropriação, custódia, flare)", "SIM"),
    ("d) Nome e endereço do cliente.", "SIM"),
    ("e) Número de páginas e total de páginas.", "SIM"),
    ("f) Identificação do método/procedimento utilizado.", "SIM"),
    ("g) Registro das condições ambientais.", "SIM"),
    ("h) Descrição e identificação do item de calibração (ex.: nome, fabricante, tipo, modelo, número de série, etc).", "SIM"),
    ("i) A data do recebimento do(s) item(s) de calibração, se necessário.", "NA"),
    ("j) A data da realização da calibração.", "SIM"),
    ("k) Os resultados da calibração estão com as unidades de medida no SI, onde apropriado.", "SIM"),
    ("l) Evidências de que as medições são rastreáveis (Informações dos padrões utilizados).", "SIM"),
    ("m) Nome(s), função (ões) e assinatura (s) ou identificações equivalentes das pessoas autorizadas para emissão do certificado.", "SIM"),
    ("n) Declaração de que os resultados e incertezas se referem somente aos itens calibrados / inspecionados.", "SIM"),
    ("o) Nível de confiança e fator de abrangência.", "SIM"),
    ("p) Foi feita calibração de acordo com a faixa solicitada? ", "SIM"),
    ("q) Os erros máximos de medição (Erro sistemático remanescente + incerteza) são inferiores ao erro máximo admissível para o equipamento em questão?", "SIM"),
    ("r) O instrumento está aprovado para o uso no ponto de medição a que se destina de acordo com os critérios de aceitação informados pelo cliente?", "SIM"),
    ("s) No caso de ajuste no equipamento, estão informados os resultados das calibrações como encontrados (as found) e como deixados (as left)?", "NA"),
]

_CHECKLIST_YINSON = [
    ("a) Identificação única do certificado (Número do Certificado de Calibração).", "SIM"),
    ("b) Razão social e endereço do Laboratório/Empresa responsável.", "SIM"),
    ("c) Presença do logotipo da RBC (quando aplicável a instrumentos associados a sistemas de medição fiscal, apropriação, custódia ou flare).", "SIM"),
    ("d) Identificação do cliente (nome e endereço).", "SIM"),
    ("e) Indicação do número de páginas e total de páginas do documento.", "SIM"),
    ("f) Identificação do método ou procedimento de calibração utilizado.", "SIM"),
    ("g) Registro das condições ambientais durante a calibração.", "SIM"),
    ("h) Descrição e identificação do item calibrado (ex.: nome, fabricante, tipo, modelo, número de série, entre outros).", "SIM"),
    ("i) Registro da data de recebimento do(s) item(ns) de calibração, quando aplicável.", "NA"),
    ("j) Indicação da data de realização da calibração.", "SIM"),
    ("k) Apresentação dos resultados da calibração nas unidades de medida do Sistema Internacional (SI), quando aplicável.", "SIM"),
    ("l) Evidências da rastreabilidade metrológica das medições (informações sobre os padrões utilizados).", "SIM"),
    ("m) Identificação das pessoas autorizadas para emissão do certificado, incluindo nome(s), função(ões) e assinatura(s) ou identificação equivalente.", "SIM"),
    ("n) Declaração de que os resultados e as incertezas apresentados referem-se exclusivamente aos itens calibrados e/ou inspecionados.", "SIM"),
    ("o) Indicação do nível de confiança e do fator de abrangência adotado.", "SIM"),
    ("p) Verificação se a calibração foi realizada de acordo com a faixa solicitada pelo cliente.", "SIM"),
    ("q) Confirmação de que os erros máximos de medição (erro sistemático remanescente somado à incerteza) são inferiores ao erro máximo admissível para o equipamento avaliado.", "SIM"),
    ("r)  O instrumento está aprovado para uso no ponto de medição ao qual se destina, conforme os critérios de aceitação definidos pelo cliente ?", "SIM"),
    ("s) Quando houver ajuste no equipamento, apresentação dos resultados de calibração nas condições “como encontrado” (as found) e “como deixado” (as left).", "NA"),
]

# Answers to 1.2/1.4/1.5 are also static and identical across all 3 clients
# (only the question wording changes — see `_PERGUNTAS_PRIO`/`_PERGUNTAS_YINSON`).
_RESPOSTA_1_2 = "( X )   Sim      (   ) Não"
_RESPOSTA_1_4 = "(   X   )  Sim       (      ) Não"
_RESPOSTA_1_5 = "(   X   )  Sim       (      ) Não*"

_PERGUNTAS_PRIO = {
    "titulo_checklist": "Descrição dos itens a serem verificados",
    "pergunta_1_2": "É recomendado que o relatório de análise contenha uma declaração especificando que o mesmo só deve ser reproduzido completo.  Reprodução de partes requer aprovação escrita do emitente. O relatório apresentado atende esta recomendação?",
    "pergunta_1_3": "Existe alguma informação no documento analisado que necessite ser atualizada em algum outro dispositivo (ex.: range de calibração no computador de vazão)?",
    "pergunta_1_4": "De acordo com a data do último ensaio / análise que foi realizada no equipamento / produto, observando a periodicidade estabelecida para realização do mesmo; a periodicidade de realização foi cumprida?",
    "pergunta_1_5": "Conclusão da análise crítica do relatório de calibração.\nO certificado está conforme requerimento do cliente e RTM?",
}

_PERGUNTAS_YINSON = {
    "titulo_checklist": "Descrição dos itens avaliados",
    "pergunta_1_2": "Recomenda-se que o relatório de análise contenha identificação adequada e informações claras sobre o emitente.\nO relatório apresentado está em conformidade com essa recomendação?",
    "pergunta_1_3": "Existe alguma informação no documento analisado que necessite complementação, correção ou esclarecimento para melhor compreensão do dispositivo\n(ex.: faixa de calibração no computador de vazão)?",
    "pergunta_1_4": "Com base na data do último ensaio ou análise registrada, bem como no critério de periodicidade definido para sua execução, a periodicidade estabelecida foi atendida?",
    "pergunta_1_5": "Conclusão da análise crítica do relatório de calibração\nO certificado está em conformidade com os requisitos do cliente e da RTM?",
}

# Client configuration: mirrors `full_ac_templates.CONFIG_PRIO`/`CONFIG_YINSON`/
# `CONFIG_YINSON_ATLANTA` (same header-cell semantics), plus the bits only
# meaningful for HTML rendering (logos, static header text, checklist family).
CONFIG_PRIO = {
    "estilo": "prio",
    "logo_principal": "logo_prio_cabecalho.png",
    "logo_extra": None,
    "linha7_rotulo": "Unidade:",
    "linha8_rotulo": "Localização:",
    "cliente_fixo": None,  # linha7_valor comes from `dados["local"]`, not a fixed client name
    "checklist": _CHECKLIST_PRIO,
    "perguntas": _PERGUNTAS_PRIO,
    "nome_responsavel": "Carolina Bastos",
    "permitir_split_pt_pdt": True,
    "prefixo_saida": "AC",
}

CONFIG_YINSON = {
    "estilo": "yinson",
    "logo_principal": "logo_yinson_cabecalho.png",
    "logo_extra": None,
    "linha7_rotulo": "Cliente:",
    "linha8_rotulo": "Localização:",
    "cliente_fixo": "YINSON",
    "checklist": _CHECKLIST_YINSON,
    "perguntas": _PERGUNTAS_YINSON,
    "nome_responsavel": "",
    "permitir_split_pt_pdt": False,
    "prefixo_saida": "AC",
}

CONFIG_YINSON_ATLANTA = {
    **CONFIG_YINSON,
    "logo_extra": "logo_brava_cabecalho.png",
}


def _resolver_observacao_1_3(dados: dict) -> tuple[str, str]:
    """Resolves the 1.3 answer line + bold observation text from the update flags.

    Same 3-way rule as the original `gerar_ac_completo` (range updated / SN
    updated / neither), now returning plain strings instead of an
    `openpyxl` `CellRichText` object.

    Args:
        dados: Certificate fields — reads `range_atualizado`/`sn_atualizado`.

    Returns:
        tuple[str, str]: `(resposta_1_3, observacao_1_3)` — the second item
        is `""` when neither flag is set (no bold observation line).
    """
    if dados.get("range_atualizado", False):
        return "( X ) Sim (  ) Não", "Novo range e alarmes alterados no computador de vazão"
    if dados.get("sn_atualizado", False):
        return "( X ) Sim (  ) Não", "Novo NS alterado no computador de vazão / XML / SFP"
    return "(  ) Sim ( X ) Não", ""


def montar_contexto_ac_secundario(config: dict, dados: dict) -> dict:
    """Builds the Jinja2 context for `templates/ac_secundario.html` from one client's config + certificate fields.

    Args:
        config: One of `CONFIG_PRIO`/`CONFIG_YINSON`/`CONFIG_YINSON_ATLANTA`.
        dados: Certificate fields, same shape `full_ac_templates.gerar_ac_completo`
            already expected (`tag`, `certificado`, `data`, `sistema`, `local`,
            `categoria`, `max_range`, `report_date`, `range_atualizado`,
            `sn_atualizado`).

    Returns:
        dict: context ready to pass to the Jinja2 template.
    """
    local = (dados.get("local") or "").strip()
    linha7_valor = config["cliente_fixo"] if config["cliente_fixo"] is not None else local
    linha8_valor = dados.get("sistema") if config["cliente_fixo"] is None else local

    categoria = (dados.get("categoria") or "").upper()
    titulo = _titulo_categoria(categoria, config["permitir_split_pt_pdt"], dados.get("max_range")) or ""

    data_entrega = ""
    if dados.get("report_date"):
        dt = datetime.strptime(dados["report_date"], "%d/%m/%Y")
        data_entrega = _adicionar_dia_util(dt).strftime("%d/%m/%Y")

    resposta_1_3, observacao_1_3 = _resolver_observacao_1_3(dados)

    checklist = [
        {"texto": texto, "resposta": resposta}
        for texto, resposta in config["checklist"]
    ]

    return {
        "estilo": config["estilo"],
        "logo_principal": _logo_base64(config["logo_principal"]),
        "logo_extra": _logo_base64(config["logo_extra"]) if config["logo_extra"] else None,
        "titulo": titulo,
        "linha7_rotulo": config["linha7_rotulo"],
        "linha7_valor": linha7_valor,
        "linha8_rotulo": config["linha8_rotulo"],
        "linha8_valor": linha8_valor,
        "tag": dados.get("tag", ""),
        "certificado": dados.get("certificado", ""),
        "data_calibracao": dados.get("data", ""),
        "empresa_certificadora": "ODS Metering Systems",
        "titulo_checklist": config["perguntas"]["titulo_checklist"],
        "checklist": checklist,
        "pergunta_1_2": config["perguntas"]["pergunta_1_2"],
        "resposta_1_2": _RESPOSTA_1_2,
        "pergunta_1_3": config["perguntas"]["pergunta_1_3"],
        "resposta_1_3": resposta_1_3,
        "observacao_1_3": observacao_1_3,
        "pergunta_1_4": config["perguntas"]["pergunta_1_4"],
        "resposta_1_4": _RESPOSTA_1_4,
        "pergunta_1_5": config["perguntas"]["pergunta_1_5"],
        "resposta_1_5": _RESPOSTA_1_5,
        "nome_responsavel": config["nome_responsavel"],
        "data_entrega": data_entrega,
    }


def gerar_ac_secundario_pdf(config: dict, dados: dict, caminho_pdf_original: str, sessao=None) -> str:
    """Renders `templates/ac_secundario.html` for one client config and exports it to PDF.

    HTML/WebView2 replacement for `form.full_ac_templates.gerar_ac_completo`
    (Excel COM) — same output filename convention
    (`{certificado}_{tag}_AC.pdf`, alongside the source PDF).

    Args:
        config: One of `CONFIG_PRIO`/`CONFIG_YINSON`/`CONFIG_YINSON_ATLANTA`.
        dados: Certificate fields (see `montar_contexto_ac_secundario`).
        caminho_pdf_original: Path of the source PDF, used to determine the
            output folder.
        sessao: Optional already-open `SessaoHtmlParaPdf` to reuse (see
            `form.html_to_pdf`) — avoids paying WebView2's cold-start cost
            again when generating multiple reports for the same certificate.
            `None` falls back to a throwaway one-off session.

    Returns:
        str: absolute path of the generated PDF.

    Raises:
        HtmlParaPdfError: if the WebView2 export itself fails.
        PermissionError: if the output PDF already exists and is open.
    """
    contexto = montar_contexto_ac_secundario(config, dados)

    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("ac_secundario.html").render(**contexto)

    pasta_saida = os.path.dirname(os.path.abspath(caminho_pdf_original))
    certificado = (dados.get("certificado") or "").replace(" ", "")
    tag_limpa = (dados.get("tag") or "").replace(" ", "")
    caminho_pdf = os.path.join(pasta_saida, f"{certificado}_{tag_limpa}_AC.pdf")

    if os.path.exists(caminho_pdf):
        try:
            os.remove(caminho_pdf)
        except PermissionError:
            raise PermissionError(
                f"⚠ O arquivo PDF está aberto e não pode ser sobrescrito:\n{caminho_pdf}"
            )

    if sessao is not None:
        sessao.exportar(html, caminho_pdf)
    else:
        html_para_pdf(html, caminho_pdf)

    return caminho_pdf


def gerar_ac_prio_pdf(dados: dict, caminho_pdf_original: str, sessao=None) -> str:
    """Renders the AC PRIO report as HTML/PDF (see `gerar_ac_secundario_pdf`)."""
    return gerar_ac_secundario_pdf(CONFIG_PRIO, dados, caminho_pdf_original, sessao=sessao)


def gerar_ac_yinson_pdf(dados: dict, caminho_pdf_original: str, sessao=None) -> str:
    """Renders the AC YINSON report as HTML/PDF (see `gerar_ac_secundario_pdf`)."""
    return gerar_ac_secundario_pdf(CONFIG_YINSON, dados, caminho_pdf_original, sessao=sessao)


def gerar_ac_yinson_atlanta_pdf(dados: dict, caminho_pdf_original: str, sessao=None) -> str:
    """Renders the AC YINSON ATLANTA report as HTML/PDF (see `gerar_ac_secundario_pdf`)."""
    return gerar_ac_secundario_pdf(CONFIG_YINSON_ATLANTA, dados, caminho_pdf_original, sessao=sessao)
