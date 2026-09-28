# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : form.utils_print_falha_presumida_html
# Created       : 27-09-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Generates the Falha Presumida report as PDF from an HTML/Jinja2 template instead of the Excel/win32com pipeline (see form.utils_print_linearizacao.gerar_falha_presumida) — same HTML→PDF approach as form.utils_print_linearizacao_html. No XLSX is produced (this report no longer depends on the Linearização workbook the old pipeline reopened).
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import os

from jinja2 import Environment, FileSystemLoader, select_autoescape

from form.html_to_pdf import html_para_pdf
from form.utils_print_linearizacao import parear_pontos_anterior
from form.utils_print_linearizacao_html import _APLICACOES_TOLERANCIA_ESTREITA, _TEMPLATE_DIR, _num_br, montar_contexto

# Applications with the tighter ±0.25% tolerance on Diff MF — same rule as
# the live formula in Template_Linearizacao.xlsx's "Falha Presumida" sheet
# (see tasks/TAREFAS_linearizacao_falha_presumida.md, "Atualização —
# mapeamento real da aba 'Falha Presumida'"). Diff MF itself is a fraction
# (e.g. 0.0023 for 0.23%), so the thresholds here are fractions too, not
# percentages.
_TOLERANCIA_ESTREITA_FP = 0.0025
_TOLERANCIA_PADRAO_FP = 0.02


def _limite_diff_mf(aplicacao: str) -> float:
    """Returns the maximum admissible |Diff MF| (as a fraction) for this "Aplicação"."""
    aplicacao_norm = (aplicacao or "").strip().upper()
    return _TOLERANCIA_ESTREITA_FP if aplicacao_norm in _APLICACOES_TOLERANCIA_ESTREITA else _TOLERANCIA_PADRAO_FP


def status_falha_presumida(diff_mf: float, aplicacao: str) -> str:
    """Classifies a paired point as APROVADO/REPROVADO from its Diff MF and the certificate's Aplicação.

    Args:
        diff_mf: `(mf_atual - mf_anterior) / mf_anterior`, as a fraction
            (not a percentage).
        aplicacao: certificate's "Aplicação" field (drives the tolerance).

    Returns:
        str: "REPROVADO" if `abs(diff_mf)` exceeds the tolerance for this
        Aplicação (±0,25% for Fiscal/Transferência de Custódia, ±2%
        otherwise), "APROVADO" otherwise.
    """
    return "REPROVADO" if abs(diff_mf) > _limite_diff_mf(aplicacao) else "APROVADO"


def _calcular_ponto_falha_presumida(vazao_fmt: str, mf_atual: float, mf_anterior: float, aplicacao: str) -> dict:
    """Computes the derived, display-ready fields of a single Falha Presumida comparison point.

    Args:
        vazao_fmt: current point's already-formatted flow rate (reused as-is
            from `montar_contexto`'s "Valores do Certificado" table).
        mf_atual: current certificate's meter factor for this point.
        mf_anterior: previous certificate's meter factor, already paired to
            this point by nearest flow rate (see `parear_pontos_anterior`).
        aplicacao: certificate's "Aplicação" field.

    Returns:
        dict: `vazao_fmt`, `mf_atual_fmt`, `mf_anterior_fmt`, `diff_mf_fmt`
        (percentage with "%" appended, 2 decimals — the template's `K86`
        column header is just "Diff MF", with the unit carried by the
        cell's own percentage format instead, same as replicated here),
        `fci_fmt` ("Fator de Correção", 5 decimals, or "-" when the point
        is APROVADO — same rule as the template's `L87` formula) and
        `status`.
    """
    diff_mf = (mf_atual - mf_anterior) / mf_anterior if mf_anterior else 0.0
    status = status_falha_presumida(diff_mf, aplicacao)
    fci_fmt = _num_br(mf_atual / mf_anterior, 5) if status == "REPROVADO" and mf_anterior else "-"

    return {
        "vazao_fmt": vazao_fmt,
        "mf_atual_fmt": _num_br(mf_atual, 5),
        "mf_anterior_fmt": _num_br(mf_anterior, 5),
        "diff_mf_fmt": f"{_num_br(diff_mf * 100, 2)}%",
        "fci_fmt": fci_fmt,
        "status": status,
    }


def montar_contexto_falha_presumida(dados_atual: dict, dados_anterior: dict, caminho_xml: str) -> dict:
    """Builds the full Jinja2 context for `templates/falha_presumida.html`.

    Reuses `form.utils_print_linearizacao_html.montar_contexto` for the
    header/calibration-table/signature fields (100% mirrored from the
    Linearização report in the old Excel pipeline, via formula) and adds the
    "Cálculo Falha Presumida" section under the `falha_presumida` key.

    Args:
        dados_atual: current certificate's data (`xml_extractor_FT.extrair_dados_ft`
            output, with `aplicacao`/`sistema`/`cliente`/`elaborado_por`/
            `verificado_por` already filled in — same as
            `gerar_linearizacao_pdf` expects).
        dados_anterior: previous certificate's data, from `extrair_dados_ft`
            on the previous calibration's XML.
        caminho_xml: path of the current certificate's XML — passed through
            to `montar_contexto` (Cliente path fallback).

    Returns:
        dict: `montar_contexto`'s own keys, plus `falha_presumida`
        (`certificado_anterior` and `pontos`, one entry per current
        calibration point, paired to the nearest-flow-rate previous point).

    Raises:
        ValueError: if `dados_anterior` has no calibration points (raised
            by `parear_pontos_anterior`).
    """
    contexto = montar_contexto(dados_atual, caminho_xml)

    aplicacao = dados_atual.get("aplicacao", "")
    pontos_anterior_pareados = parear_pontos_anterior(
        dados_atual.get("pontos", []), dados_anterior.get("pontos", [])
    )

    pontos_fp = [
        _calcular_ponto_falha_presumida(
            p_atual["vazao_fmt"], p_atual["meter_factor"], p_pareado["meter_factor"], aplicacao
        )
        for p_atual, p_pareado in zip(contexto["pontos"], pontos_anterior_pareados)
    ]

    contexto["falha_presumida"] = {
        "certificado_anterior": dados_anterior.get("numero_certificado", ""),
        "pontos": pontos_fp,
    }
    return contexto


def gerar_falha_presumida_pdf(dados_atual: dict, dados_anterior: dict, caminho_xml: str, sessao=None) -> str:
    """Renders the Falha Presumida report straight to PDF from `templates/falha_presumida.html` — no XLSX is produced.

    Output file is saved in the same folder as the input XML, named the same
    way as the Excel pipeline's PDF (`<CERT_ATUAL>_<TAG>_FALHA_PRESUMIDA.pdf`).

    Args:
        dados_atual: current certificate's data (see `montar_contexto_falha_presumida`).
        dados_anterior: previous certificate's data.
        caminho_xml: path of the current certificate's XML; used to
            determine the output folder.
        sessao: optional `form.html_to_pdf.SessaoHtmlParaPdf` already
            started, shared with `gerar_linearizacao_pdf`/
            `gerar_ac_primario_pdf` — see that function's docstring for why.

    Returns:
        str: path of the generated PDF.

    Raises:
        ValueError: if the previous certificate has no calibration points.
        HtmlParaPdfError: if the WebView2 export itself fails.
        PermissionError: if the output PDF already exists and is open.
    """
    contexto = montar_contexto_falha_presumida(dados_atual, dados_anterior, caminho_xml)

    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("falha_presumida.html").render(**contexto)

    pasta_saida = os.path.dirname(os.path.abspath(caminho_xml))
    cert_limpo = dados_atual.get("numero_certificado", "").replace(" ", "")
    tag_limpa = dados_atual.get("tag", "").replace(" ", "")
    caminho_pdf = os.path.join(pasta_saida, f"{cert_limpo}_{tag_limpa}_FALHA_PRESUMIDA.pdf")

    if sessao is not None:
        sessao.exportar(html, caminho_pdf)
    else:
        html_para_pdf(html, caminho_pdf)
    return caminho_pdf
