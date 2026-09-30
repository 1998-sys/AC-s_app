# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : form.utils_print_ac_primario_yinson_html
# Created       : 29-09-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Generates the YINSON primary meter Critical Analysis report as PDF from an HTML/Jinja2 template — see templates/ac_primario_yinson.html. Source: FC-5 - 20FT9001C - 20260607_AC (2).xlsx, a real filled example (not a blank template) — see tasks/TAREFAS_ac_primario_yinson_origem.md.
#
#                 THIS IS A LAYOUT-ONLY PASS: `montar_contexto_ac_primario_yinson`
#                 wires the fields that are already fully resolved (reusing
#                 established patterns — same certificate header fields
#                 Linearização/PRIO's AC already use, same
#                 `CRITERIOS_ACEITACAO`/`parear_pontos_anterior` used
#                 elsewhere), but everything that depends on a still-open
#                 decision (periodicidade, período de emissão, incerteza
#                 admitida, diferença de temperatura/pressão vs. padrão —
#                 not extracted by `extrair_dados_ft` yet — diferença de
#                 pressão "conforme histórico", e as 3 conferências manuais
#                 do documento) is left as an explicit empty placeholder
#                 in `_CAMPOS_PENDENTES` below, not computed. See the task
#                 file's "O que não está no XML nem no banco" section
#                 before wiring any of those for real.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import os
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from form.html_to_pdf import html_para_pdf
from form.utils_print_ac_primario import CRITERIOS_ACEITACAO
from form.utils_print_linearizacao import _data_br, parear_pontos_anterior
from form.utils_print_linearizacao_html import _TEMPLATE_DIR, _logo_base64

# "Dados Obrigatórios" reference list — transcribed from
# FC-5 - 20FT9001C - 20260607_AC (2).xlsx, rows 38-56 (column B). Purely a
# static legend in the source file (no SIM/NÃO column of its own, unlike
# the other AC families' checklists) — item 35 in the evaluation table
# ("Os dados obrigatórios listadodos abaixo estão presentes?") is the
# single yes/no answer that covers this whole list.
_DADOS_OBRIGATORIOS = [
    "a. Logotipo de acreditação do laboratório",
    "b. Identificação do aprovador",
    "c. Identificação do cliente",
    "d. Identificação dos padrões utilizados",
    "e. Condições ambientais durante calibração",
    "f. Numeração das paginas",
    "g. Registros de pressão e temperatura do medidor",
    "h. Identificação do fluido utilizado",
    "i. Número de corridas e resultado de cada uma",
    "j. Data e hora de alinhamento do medidor para calibração",
    "k. Data e hora de início das corridas",
    "l. Data e hora de finalização das corridas",
    "m. Data e hora de elaboração do relatório",
    "n. Valores medidos (volumes, pressões, temperaturas, níveis) no início e no fim da calibração",
    "o. Fatores de calibração correntes (fator do medidor e k-factor);",
    "p. Fatores de calibração encontrados após calibração (fator do medidor e k-factor)",
    "q. Desvio entre fatores de calibração corrente e encontrado após calibração",
    "r. Número de corridas de calibração",
    "s. Histórico do fator do medidor encontrado nas calibrações anteriores, para o mesmo instrumento",
]


def _maior(pontos: list, chave: str) -> float:
    """Returns the largest absolute value of `chave` across `pontos`, or 0.0 if `pontos` is empty."""
    valores = [abs(p[chave]) for p in pontos]
    return max(valores) if valores else 0.0


def _maior_desvio_mf(pontos_atual: list, pontos_anterior: list) -> float:
    """Largest |Diff MF| between each current point and its nearest-flow-rate previous point.

    Same pairing rule Falha Presumida already uses (`parear_pontos_anterior`)
    — reused here instead of duplicating it, since this AC's "Maior desvio
    em relação à calibração anterior" is the same comparison, just reduced
    to its worst-case point instead of shown per-point.
    """
    if not pontos_atual or not pontos_anterior:
        return 0.0
    pareados = parear_pontos_anterior(pontos_atual, pontos_anterior)
    diffs = [
        abs(p_atual["meter_factor"] - p_ant["meter_factor"]) / p_ant["meter_factor"]
        for p_atual, p_ant in zip(pontos_atual, pareados)
        if p_ant["meter_factor"]
    ]
    return max(diffs) if diffs else 0.0


def _sim_nao(condicao) -> str:
    """Formats a boolean as "SIM"/"NÃO", or "" when `condicao` is None (value not available yet)."""
    if condicao is None:
        return ""
    return "SIM" if condicao else "NÃO"


def montar_contexto_ac_primario_yinson(dados_atual: dict, dados_anterior: dict = None) -> dict:
    """Builds the Jinja2 context for `templates/ac_primario_yinson.html`.

    Args:
        dados_atual: current certificate's data (`xml_extractor_FT.extrair_dados_ft`
            output), with `cliente`/`aplicacao` already filled in by the
            Linearização prompt.
        dados_anterior: previous certificate's data, if the user opted into
            Falha Presumida (this report's "Maior desvio em relação à
            calibração anterior" needs it, same as Falha Presumida itself).

    Returns:
        dict: context ready to pass to the Jinja2 template. Rows whose
        source is still an open decision (see the module docstring) come
        back with `valor=""` rather than a guessed number.
    """
    dados_anterior = dados_anterior or {}
    pontos_atual = dados_atual.get("pontos", [])
    pontos_anterior = dados_anterior.get("pontos", [])
    aplicacao = dados_atual.get("aplicacao", "")
    criterios = CRITERIOS_ACEITACAO.get(aplicacao, {})

    maior_repetibilidade = _maior(pontos_atual, "repetibilidade") if pontos_atual else None
    repetibilidade_admitida = criterios.get("repetibilidade")
    maior_desvio = _maior_desvio_mf(pontos_atual, pontos_anterior) if pontos_anterior else None
    desvio_admitido = criterios.get("validacao_mf")
    maior_incerteza = _maior(pontos_atual, "incerteza") if pontos_atual else None

    # Not resolved yet — see the module docstring and
    # tasks/TAREFAS_ac_primario_yinson_origem.md before filling these in.
    periodicidade_dias = None
    periodo_emissao_dias = None
    incerteza_admitida = None
    maior_diff_temperatura = None
    maior_diff_pressao = None
    diff_pressao_admitida = None
    range_correto = None
    certificado_assinado = None
    dados_obrigatorios_presentes = None

    avaliacao = [
        {"label": "Data da calibração anterior", "valor": _data_br(dados_anterior.get("data_calibracao", ""))},
        {"label": "Periodicidade (dias)", "valor": periodicidade_dias if periodicidade_dias is not None else ""},
        {"label": "A periodicidade foi atendida?", "valor": _sim_nao(None)},
        {"label": "Data de emissão", "valor": _data_br(dados_atual.get("data_emissao", ""))},
        {"label": "Período para emissão (dias)", "valor": periodo_emissao_dias if periodo_emissao_dias is not None else ""},
        {"label": "O período para emissão foi atendido?", "valor": _sim_nao(None)},
        {"label": "Maior repetibilidade obtida na calibração (%)", "valor": f"{maior_repetibilidade:.3f}".replace(".", ",") if maior_repetibilidade is not None else ""},
        {"label": "Repetibilidade máxima admitida (%)", "valor": f"{repetibilidade_admitida:.2f}".replace(".", ",") if repetibilidade_admitida is not None else ""},
        {"label": "A repetibilidade foi atendida?", "valor": _sim_nao(maior_repetibilidade <= repetibilidade_admitida if maior_repetibilidade is not None and repetibilidade_admitida is not None else None)},
        {"label": "Maior desvio em relação à calibração anterior (%)", "valor": f"{maior_desvio * 100:.3f}".replace(".", ",") if maior_desvio is not None else ""},
        {"label": "Desvio máximo admitido em relação à calibração anterior (%)", "valor": f"{desvio_admitido:.2f}".replace(".", ",") if desvio_admitido is not None else ""},
        {"label": "O desvio em relação à calibração anterior foi atendido?", "valor": _sim_nao((maior_desvio * 100) <= desvio_admitido if maior_desvio is not None and desvio_admitido is not None else None)},
        {"label": "Maior incerteza da calibração", "valor": f"{maior_incerteza:.1E}".replace(".", ",") if maior_incerteza is not None else ""},
        {"label": "Incerteza admitida", "valor": incerteza_admitida if incerteza_admitida is not None else ""},
        {"label": "O critério de incerteza foi atendido?", "valor": _sim_nao(None)},
        {"label": "Maior diferença da temperatura médida medidor calibrado em relação ao padrão (°C)", "valor": maior_diff_temperatura if maior_diff_temperatura is not None else ""},
        {"label": "A diferença de temperatura atende o limite de 5°C ?", "valor": _sim_nao(None)},
        {"label": "Maior diferença da pressão medida do medidor calibrado em relação ao padrão (kPa)", "valor": maior_diff_pressao if maior_diff_pressao is not None else ""},
        {"label": "Diferença admitida conforme histórico (kPa)", "valor": diff_pressao_admitida if diff_pressao_admitida is not None else ""},
        {"label": "A diferença de pressão atende o limite histórico?", "valor": _sim_nao(None)},
        {"label": "O range está correto?", "valor": _sim_nao(range_correto)},
        {"label": "O certificado está assinado?", "valor": _sim_nao(certificado_assinado)},
        {"label": "Os dados obrigatórios listadodos abaixo estão presentes?", "valor": _sim_nao(dados_obrigatorios_presentes)},
        {"label": "O medidor está apto e atende a todos os ítens avaliados? ", "valor": "", "destaque": True},
    ]

    return {
        "logo_yinson": _logo_base64("logo_yinson_cabecalho.png"),
        "cliente": dados_atual.get("cliente", ""),
        "tag": dados_atual.get("tag", ""),
        "localizacao": dados_atual.get("unidade_operacional", ""),
        "certificado": dados_atual.get("numero_certificado", ""),
        "data_calibracao": _data_br(dados_atual.get("data_calibracao", "")),
        "classificacao": aplicacao,
        "avaliacao": avaliacao,
        "dados_obrigatorios": _DADOS_OBRIGATORIOS,
        "data_entrega": datetime.now().strftime("%d/%m/%Y"),
    }


def gerar_ac_primario_yinson_pdf(dados_atual: dict, dados_anterior: dict, caminho_xml: str, sessao=None) -> str:
    """Renders `templates/ac_primario_yinson.html` and exports it to PDF.

    Args:
        dados_atual: current certificate's data (see `montar_contexto_ac_primario_yinson`).
        dados_anterior: previous certificate's data, if available.
        caminho_xml: path of the input XML; used to determine the output folder.
        sessao: optional already-open `SessaoHtmlParaPdf` to reuse. `None`
            falls back to a throwaway one-off session.

    Returns:
        str: absolute path of the generated PDF.
    """
    contexto = montar_contexto_ac_primario_yinson(dados_atual, dados_anterior)

    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("ac_primario_yinson.html").render(**contexto)

    pasta_saida = os.path.dirname(os.path.abspath(caminho_xml))
    cert_limpo = (dados_atual.get("numero_certificado") or "").replace(" ", "")
    tag_limpa = (dados_atual.get("tag") or "").replace(" ", "")
    caminho_pdf = os.path.join(pasta_saida, f"{cert_limpo}_{tag_limpa}_AC_MEDIDOR_PRIMARIO.pdf")

    if os.path.exists(caminho_pdf):
        os.remove(caminho_pdf)

    if sessao is not None:
        sessao.exportar(html, caminho_pdf)
    else:
        html_para_pdf(html, caminho_pdf)

    return caminho_pdf
