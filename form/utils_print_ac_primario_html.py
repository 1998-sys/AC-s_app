# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : form.utils_print_ac_primario_html
# Created       : 28-09-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Generates the primary flow meter Critical Analysis (AC) report as PDF from an HTML/Jinja2 template instead of the Excel/win32com pipeline (see form.utils_print_ac_primario) — same HTML→PDF approach as the Linearização/Falha Presumida reports. No XLSX is produced. Unlike those two, this report is portrait and includes 3 line charts (rendered server-side with matplotlib, embedded as PNG data URIs) — see tasks/TAREFAS_ac_medidor_primario_prio.md, "Migração para HTML".
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import base64
import io
import os
from datetime import datetime

import matplotlib

matplotlib.use("Agg")  # headless — no GUI backend/display needed for a server-side render
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader, select_autoescape

from form.html_to_pdf import html_para_pdf
from form.utils_print_ac_primario import (
    CRITERIOS_ACEITACAO,
    INSTRUMENTO_PADRAO,
    UNIDADE_CERTIFICADO_PADRAO,
    _validade_padrao_texto,
)
from form.utils_print_linearizacao import _data_br, parear_pontos_anterior
from form.utils_print_linearizacao_html import _TEMPLATE_DIR, _logo_base64, _num_br

# Physical limit already enforced by the old Excel pipeline (10 rows per
# table in Template_AC_PRIM_PRIO.xlsx — TABELA_ERRO_LINHA_FIM_MAX -
# TABELA_ERRO_LINHA_INI + 1 in form.utils_print_ac_primario).
MAX_PONTOS = 10

_COR_INCERTEZA_ANTERIOR = "#2E8B57"
_COR_INCERTEZA_ATUAL = "#7030A0"
_COR_ERRO_ATUAL = "#00B0F0"
_COR_ERRO_ANTERIOR = "#1F4E78"
_COR_LIMITE = "#FF0000"
_COR_MF_ANTERIOR = "#1F77B4"
_COR_MF_ATUAL = "#FF7F0E"
_COR_REPETIBILIDADE_ANTERIOR = "#00B0F0"
_COR_REPETIBILIDADE_ATUAL = "#1F4E78"


def _grafico_base64(series, linhas_referencia=None, altura_pol=2.1):
    """Renders a line chart ("ANÁLISE PARAMÉTRICA") with matplotlib and returns it as a `data:` PNG URI.

    Runs entirely server-side (Agg backend, no display) — the resulting
    image is a static PNG embedded directly in the HTML, so there's no
    "wait for the chart to finish drawing" timing concern for
    `form.html_to_pdf.html_para_pdf` (unlike a client-side JS charting
    library would have against `PrintToPdfAsync`).

    Args:
        series: list of {"nome", "cor", "pontos": [(x, y), ...]} — one
            per plotted line.
        linhas_referencia: optional list of {"nome", "cor", "valor"} —
            horizontal reference lines (e.g. the acceptance threshold).
        altura_pol: figure height in inches (width is fixed to fit the
            report's portrait content area).

    Returns:
        str: `data:image/png;base64,...` URI ready to use as an `<img src>`.
    """
    fig, ax = plt.subplots(figsize=(6.8, altura_pol), dpi=150)

    for s in series:
        xs = [p[0] for p in s["pontos"]]
        ys = [p[1] for p in s["pontos"]]
        ax.plot(xs, ys, color=s["cor"], label=s["nome"], linewidth=1.2)

    for l in linhas_referencia or []:
        ax.axhline(l["valor"], color=l["cor"], linewidth=1.2, label=l["nome"])

    ax.set_title("ANÁLISE PARAMÉTRICA", fontsize=9, fontweight="bold", color="#1F4E78")
    ax.tick_params(labelsize=6.5)
    ax.grid(True, axis="y", linewidth=0.4, color="#cccccc")
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)
    ax.legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.18),
        ncol=3, fontsize=6, frameon=False,
    )
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"


def montar_contexto_ac_primario(dados_atual: dict, dados_anterior: dict, aplicacao: str, caminho_xml: str) -> dict:
    """Builds the full Jinja2 context for `templates/ac_primario.html`.

    Ports, to Python, the exact formulas confirmed cell-by-cell in
    `Template_AC_PRIM_PRIO.xlsx` (see tasks/TAREFAS_ac_medidor_primario_prio.md):
    the Erro table's "RESULTADO" compares the *current uncertainty*
    against the Erro Máximo Admissível (not the measured error itself);
    the Meter Factor table's "Critério" is the Validação MF limit divided
    by 100 (a fraction) and its "Resultado" compares that against the
    *absolute* MF difference; the Repetibilidade table compares the
    current repeatability directly against its own limit.

    Args:
        dados_atual: current certificate's data (`xml_extractor_FT.extrair_dados_ft`
            output on the current XML).
        dados_anterior: previous certificate's data (same function's
            output on the previous XML).
        aplicacao: one of `CRITERIOS_ACEITACAO`'s keys.
        caminho_xml: path of the current XML — unused here beyond being
            threaded through for interface consistency with the other
            reports (this report has no path-based fallback field).

    Returns:
        dict: context ready to pass to the Jinja2 template.

    Raises:
        KeyError: if `aplicacao` isn't one of `CRITERIOS_ACEITACAO`'s keys.
        ValueError: if the certificate has more calibration points than
            `MAX_PONTOS`, or if `dados_anterior` has no points to pair
            against (see `parear_pontos_anterior`).
    """
    criterios = CRITERIOS_ACEITACAO[aplicacao]
    erro_maximo = criterios["erro_maximo"]
    repetibilidade_limite = criterios["repetibilidade"]
    validacao_mf = criterios["validacao_mf"]
    criterio_mf_fracao = (validacao_mf or 0) / 100

    pontos_atual = dados_atual.get("pontos", [])
    if len(pontos_atual) > MAX_PONTOS:
        raise ValueError(
            f"AC de Medidor Primário suporta no máximo {MAX_PONTOS} pontos "
            f"de calibração (certificado tem {len(pontos_atual)})."
        )

    pontos_pareados = parear_pontos_anterior(pontos_atual, dados_anterior.get("pontos", []))

    pontos_erro, pontos_mf, pontos_rep = [], [], []
    eixo_x = []
    serie_incerteza_anterior, serie_incerteza_atual = [], []
    serie_erro_anterior, serie_erro_atual = [], []
    serie_mf_anterior, serie_mf_atual = [], []
    serie_rep_anterior, serie_rep_atual = [], []

    for p_atual, p_anterior in zip(pontos_atual, pontos_pareados):
        vazao = p_atual["vazao"]
        vazao_fmt = _num_br(vazao, p_atual.get("vazao_casas", 0))
        eixo_x.append(vazao)

        # ── 2.1 Erro de Medição ───────────────────────────────────────
        incerteza_atual = p_atual["incerteza"]
        incerteza_anterior = p_anterior["incerteza"]
        erro_atual = p_atual["erro_pct"]
        erro_anterior = p_anterior["erro_pct"]
        status_erro = "APROVADO" if incerteza_atual <= erro_maximo else "REPROVADO"
        pontos_erro.append({
            "vazao_fmt": vazao_fmt,
            "erro_anterior_fmt": _num_br(erro_anterior, 2),
            "erro_atual_fmt": _num_br(erro_atual, 2),
            "incerteza_anterior_fmt": _num_br(incerteza_anterior, 2),
            "incerteza_atual_fmt": _num_br(incerteza_atual, 2),
            "metrica_fmt": _num_br(erro_maximo, 2),
            "status": status_erro,
        })
        serie_incerteza_anterior.append((vazao, incerteza_anterior))
        serie_incerteza_atual.append((vazao, incerteza_atual))
        serie_erro_anterior.append((vazao, erro_anterior))
        serie_erro_atual.append((vazao, erro_atual))

        # ── 2.2 Análise do Meter Factor ───────────────────────────────
        mf_anterior = p_anterior["meter_factor"]
        mf_atual = p_atual["meter_factor"]
        diferenca = abs(mf_anterior - mf_atual)
        pct_diff = (mf_atual - mf_anterior) / mf_anterior if mf_anterior else 0.0
        status_mf = "APROVADO" if criterio_mf_fracao <= 0 or diferenca <= criterio_mf_fracao else "REPROVADO"
        pontos_mf.append({
            "vazao_fmt": vazao_fmt,
            "mf_anterior_fmt": _num_br(mf_anterior, 5),
            "mf_atual_fmt": _num_br(mf_atual, 5),
            "diferenca_fmt": _num_br(diferenca, 3),
            "criterio_fmt": f"{_num_br(criterio_mf_fracao * 100, 2)}%",
            "resultado_pct_fmt": f"{_num_br(pct_diff * 100, 2)}%",
            "status": status_mf,
        })
        serie_mf_anterior.append((vazao, mf_anterior))
        serie_mf_atual.append((vazao, mf_atual))

        # ── 2.3 Análise da Repetibilidade ─────────────────────────────
        rep_anterior = p_anterior["repetibilidade"]
        rep_atual = p_atual["repetibilidade"]
        status_rep = "APROVADO" if rep_atual <= repetibilidade_limite else "REPROVADO"
        pontos_rep.append({
            "vazao_fmt": vazao_fmt,
            "repetibilidade_anterior_fmt": _num_br(rep_anterior, 2),
            "repetibilidade_atual_fmt": _num_br(rep_atual, 2),
            "criterio_fmt": _num_br(repetibilidade_limite, 3),
            "status": status_rep,
        })
        serie_rep_anterior.append((vazao, rep_anterior))
        serie_rep_atual.append((vazao, rep_atual))

    grafico_erro = _grafico_base64(
        series=[
            {"nome": "Incerteza de Medição Anterior", "cor": _COR_INCERTEZA_ANTERIOR, "pontos": serie_incerteza_anterior},
            {"nome": "Incerteza de Medição Atual", "cor": _COR_INCERTEZA_ATUAL, "pontos": serie_incerteza_atual},
            {"nome": "Erro Medição Atual", "cor": _COR_ERRO_ATUAL, "pontos": serie_erro_atual},
            {"nome": "Erro Medição Anterior", "cor": _COR_ERRO_ANTERIOR, "pontos": serie_erro_anterior},
        ],
        linhas_referencia=[{"nome": "Incerteza máxima admissível", "cor": _COR_LIMITE, "valor": erro_maximo}],
    )
    grafico_mf = _grafico_base64(
        series=[
            {"nome": "MF Anterior", "cor": _COR_MF_ANTERIOR, "pontos": serie_mf_anterior},
            {"nome": "MF Atual", "cor": _COR_MF_ATUAL, "pontos": serie_mf_atual},
        ],
    )
    grafico_repetibilidade = _grafico_base64(
        series=[
            {"nome": "Repetibilidade Anterior", "cor": _COR_REPETIBILIDADE_ANTERIOR, "pontos": serie_rep_anterior},
            {"nome": "Repetibilidade Atual", "cor": _COR_REPETIBILIDADE_ATUAL, "pontos": serie_rep_atual},
        ],
        linhas_referencia=[{"nome": "Critério", "cor": _COR_LIMITE, "valor": repetibilidade_limite}],
    )

    pressao_calibracao = dados_atual.get("pressao_calibracao")
    pressao_fmt = (
        f"{_num_br(pressao_calibracao, 1)} {dados_atual.get('pressao_calibracao_unidade', '')}".strip()
        if pressao_calibracao else ""
    )
    faixa_calibrada = dados_atual.get("faixa_calibrada", "")
    faixa_calibrada_completa = f"{faixa_calibrada} {UNIDADE_CERTIFICADO_PADRAO}        {pressao_fmt}".strip()

    return {
        "cabecalho": {
            "tipo_equipamento": dados_atual.get("tipo", ""),
            "tag": dados_atual.get("tag", ""),
            "instrumento": INSTRUMENTO_PADRAO,
            "fabricante": dados_atual.get("fabricante", ""),
            "modelo": dados_atual.get("modelo", ""),
            "num_serie": dados_atual.get("num_serie", ""),
            "faixa_medicao": faixa_calibrada,
            "pressao_calibracao": pressao_fmt,
            "dn": dados_atual.get("diametro", ""),
            "unidade_certificado": UNIDADE_CERTIFICADO_PADRAO,
            "certificado_anterior": dados_anterior.get("numero_certificado", ""),
            "laboratorio_anterior": dados_anterior.get("laboratorio", ""),
            "data_cal_anterior": _data_br(dados_anterior.get("data_calibracao", "")),
            "certificado_atual": dados_atual.get("numero_certificado", ""),
            "laboratorio_atual": dados_atual.get("laboratorio", ""),
            "data_cal_atual": _data_br(dados_atual.get("data_calibracao", "")),
            "validade_padrao": _validade_padrao_texto(dados_atual.get("padroes")),
            "faixa_calibrada_completa": faixa_calibrada_completa,
        },
        "criterios": {
            "erro_maximo_fmt": _num_br(erro_maximo, 2),
            "repetibilidade_fmt": _num_br(repetibilidade_limite, 2),
            "validacao_mf_fmt": _num_br(validacao_mf, 2) if validacao_mf is not None else "N.A.",
        },
        "logos": {"prio": _logo_base64("logo_prio_cabecalho.png")},
        "pontos_erro": pontos_erro,
        "pontos_mf": pontos_mf,
        "pontos_rep": pontos_rep,
        "graficos": {
            "erro": grafico_erro,
            "mf": grafico_mf,
            "repetibilidade": grafico_repetibilidade,
        },
        "situacao_badge": "NECESSITA DE ANÁLISE",
        "observacoes": "Medidor aprovado para instalação",
        "data_analise": datetime.now().strftime("%d/%m/%Y"),
    }


def gerar_ac_primario_pdf(dados_atual: dict, dados_anterior: dict, aplicacao: str, caminho_xml: str, sessao=None) -> str:
    """Renders the primary flow meter Critical Analysis (AC) report straight to PDF from `templates/ac_primario.html` — no XLSX is produced.

    Output file is saved in the same folder as the input XML, named the
    same way as the Excel pipeline's PDF (`<CERT>_<TAG>_AC_MEDIDOR_PRIMARIO.pdf`).

    Args:
        dados_atual: current certificate's data.
        dados_anterior: previous certificate's data.
        aplicacao: one of `CRITERIOS_ACEITACAO`'s keys.
        caminho_xml: path of the current XML; used to determine the
            output folder.
        sessao: optional `form.html_to_pdf.SessaoHtmlParaPdf` already
            started, shared with `gerar_linearizacao_pdf`/
            `gerar_falha_presumida_pdf` — see that function's docstring
            for why.

    Returns:
        str: path of the generated PDF.

    Raises:
        KeyError: if `aplicacao` isn't one of `CRITERIOS_ACEITACAO`'s keys.
        ValueError: if the certificate has more calibration points than
            `MAX_PONTOS`, or if `dados_anterior` has no points to pair against.
        HtmlParaPdfError: if the WebView2 export itself fails.
        PermissionError: if the output PDF already exists and is open.
    """
    contexto = montar_contexto_ac_primario(dados_atual, dados_anterior, aplicacao, caminho_xml)

    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("ac_primario.html").render(**contexto)

    pasta_saida = os.path.dirname(os.path.abspath(caminho_xml))
    cert_limpo = dados_atual.get("numero_certificado", "").replace(" ", "")
    tag_limpa = dados_atual.get("tag", "").replace(" ", "")
    caminho_pdf = os.path.join(pasta_saida, f"{cert_limpo}_{tag_limpa}_AC_MEDIDOR_PRIMARIO.pdf")

    if sessao is not None:
        sessao.exportar(html, caminho_pdf)
    else:
        html_para_pdf(html, caminho_pdf)
    return caminho_pdf
