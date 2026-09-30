# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : form.utils_print_linearizacao_html
# Created       : 25-09-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Generates the Linearização report as PDF from an HTML/Jinja2 template instead of the Excel/win32com pipeline (see form.utils_print_linearizacao) — computes in Python the values that used to be live Excel formulas. No XLSX is produced by this module (see tasks/TAREFAS_linearizacao_falha_presumida.md, "Migração — Linearização"): this is a report-only replacement, not a full parity migration yet — Falha Presumida and AC de Medidor Primário keep using the Excel pipeline and its XLSX for now.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import base64
import math
import os
from datetime import datetime
from functools import lru_cache

from jinja2 import Environment, FileSystemLoader, select_autoescape

from form.html_to_pdf import html_para_pdf
from form.utils_print_linearizacao import _data_br, identificar_cliente

# Applications with the tighter ±0.2% tolerance — same rule as the live
# formula in Template_Linearizacao.xlsx's "Status" column (see the CELLS
# comment in form/utils_print_linearizacao.py). Matched case-insensitively,
# with and without the accent, since the value comes from a free-form prompt
# answer (`PdfProcessingService._processar_xml_ft`'s "Aplicação" select).
_APLICACOES_TOLERANCIA_ESTREITA = {"FISCAL", "TRANSFERENCIA DE CUSTODIA", "TRANSFERÊNCIA DE CUSTÓDIA"}
_TOLERANCIA_ESTREITA_PCT = 0.2
_TOLERANCIA_PADRAO_PCT = 0.6

# Physical limit already enforced by the old Excel pipeline (Template_Linearizacao.xlsx
# only has 20 rows per table) — kept here so the report always fits a single printed
# page: see _estilo_tabela_pontos, tuned specifically for this worst case.
MAX_PONTOS = 20

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


@lru_cache(maxsize=None)
def _logo_base64(nome_arquivo: str) -> str:
    """Reads a PNG logo from the templates folder and returns it as a `data:` URI.

    Embedding the logos inline (instead of an `<img src="logo.png">` relative
    path) is required here: WebView2's `NavigateToString` (see
    `form.html_to_pdf`) has no base URL to resolve a relative path against,
    so a plain filename would silently fail to load. Cached since the same
    two files are read on every report generated in a session/batch.

    Args:
        nome_arquivo: logo's filename inside the `templates/` folder (e.g.
            "logo_ods_cabecalho.png").

    Returns:
        str: `data:image/png;base64,...` URI ready to use as an `<img src>`.
    """
    caminho = os.path.join(_TEMPLATE_DIR, nome_arquivo)
    with open(caminho, "rb") as f:
        conteudo = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{conteudo}"


def _casas_significativas(valor: float, digitos: int = 7) -> int:
    """Computes how many decimal places make `valor` display with `digitos` significant figures.

    Same rule as `form.utils_print_linearizacao._casas_significativas` (kept
    as its own copy here rather than imported, since that one returns an
    Excel number-format string's decimal count and this module only needs
    the plain integer for Python's own string formatting).

    Args:
        valor: value that will be rounded/displayed.
        digitos: number of significant figures to target (default: 7).

    Returns:
        int: number of decimal places (never negative). Falls back to
        `digitos - 1` when `valor` is zero/None (order of magnitude undefined).
    """
    if not valor:
        return digitos - 1
    ordem = math.floor(math.log10(abs(valor)))
    return max(0, digitos - 1 - ordem)


def _num_br(valor: float, casas: int) -> str:
    """Formats a number with a comma decimal separator and no thousands separator.

    Args:
        valor: value to format.
        casas: number of decimal places.

    Returns:
        str: e.g. `1234.5` with `casas=2` -> "1234,50" (no "." grouping the
        thousands digit — dropped per the user's explicit request).
    """
    return f"{valor:.{casas}f}".replace(".", ",")


_ESTILO_PONTOS_N_BASE = 8  # up to this many points, use the comfortable/default sizing
_ESTILO_PONTOS_FONTE_MAX = 9.5   # px — matches the document's own base font-size
_ESTILO_PONTOS_FONTE_MIN = 5.3   # px — at MAX_PONTOS, still legible when printed
_ESTILO_PONTOS_PAD_MAX = 0.7     # mm — matches the tables' original fixed padding
_ESTILO_PONTOS_PAD_MIN = 0.05    # mm


def estilo_tabela_pontos(n_pontos: int) -> dict:
    """Computes a font-size/padding for the calibration-point tables that shrinks as the
    certificate has more points, so the report always fits a single printed page
    regardless of point count (1 to `MAX_PONTOS`).

    Only the two point-tables ("Valores do Certificado de Calibração" and "Dados a
    Serem Configurados no Computador de Vazão") scale — they're the only sections whose
    height actually grows with the certificate; the header, Fórmulas, Limites de
    Alarme, Observações and signature block stay full-size regardless, so a
    certificate with few points isn't shrunk for no reason. This mirrors what the old
    Excel pipeline did with a single *fixed* 42% print zoom on the whole sheet (tuned
    for its own worst case of 20 points, confirmed via `ws.page_setup.scale` on
    `Template_Linearizacao.xlsx`) — here it's computed per certificate instead of
    fixed, so a certificate with few points isn't shrunk for no reason.

    Args:
        n_pontos: number of calibration points on this certificate.

    Returns:
        dict: `fonte_px` and `padding_mm`, meant to be set as the `--pontos-fonte`/
        `--pontos-pad` inline CSS custom properties on `table.pontos`/`table.config`
        (see `templates/_report_style.html`) — full-size below
        `_ESTILO_PONTOS_N_BASE` points, linearly interpolated down to the minimum at
        `MAX_PONTOS`.
    """
    n = min(max(n_pontos, 1), MAX_PONTOS)
    if n <= _ESTILO_PONTOS_N_BASE:
        return {"fonte_px": _ESTILO_PONTOS_FONTE_MAX, "padding_mm": _ESTILO_PONTOS_PAD_MAX}

    fracao = (n - _ESTILO_PONTOS_N_BASE) / (MAX_PONTOS - _ESTILO_PONTOS_N_BASE)
    fonte = _ESTILO_PONTOS_FONTE_MAX - fracao * (_ESTILO_PONTOS_FONTE_MAX - _ESTILO_PONTOS_FONTE_MIN)
    padding = _ESTILO_PONTOS_PAD_MAX - fracao * (_ESTILO_PONTOS_PAD_MAX - _ESTILO_PONTOS_PAD_MIN)
    return {"fonte_px": round(fonte, 2), "padding_mm": round(padding, 2)}


def _limite_erro_pct(aplicacao: str) -> float:
    """Returns the maximum admissible |erro%| for this "Aplicação", same rule as the Excel template's Status formula."""
    aplicacao_norm = (aplicacao or "").strip().upper()
    return _TOLERANCIA_ESTREITA_PCT if aplicacao_norm in _APLICACOES_TOLERANCIA_ESTREITA else _TOLERANCIA_PADRAO_PCT


def status_ponto(erro_pct: float, aplicacao: str) -> str:
    """Classifies a calibration point as APROVADO/REPROVADO from its % error and the certificate's Aplicação.

    Args:
        erro_pct: point's percentage error (`DESVIO_MEDIO`/`erro_pct` from
            `xml_extractor_FT.extrair_dados_ft`).
        aplicacao: certificate's "Aplicação" field (drives the tolerance).

    Returns:
        str: "REPROVADO" if `abs(erro_pct)` exceeds the tolerance for this
        Aplicação (±0.2% for Fiscal/Transferência de Custódia, ±0.6%
        otherwise), "APROVADO" otherwise.
    """
    return "REPROVADO" if abs(erro_pct) > _limite_erro_pct(aplicacao) else "APROVADO"


def _calcular_ponto(p: dict, fator_k: float, aplicacao: str, digitos: int = 7) -> dict:
    """Computes the derived, display-ready fields of a single calibration point.

    Ports to Python what used to be live Excel formulas (Frequência, K-Factor
    Corrigido, Status) plus BR-formatted strings for every column, so the
    Jinja2 template only interpolates ready-to-print text.

    Args:
        p: one entry of `dados["pontos"]` (see `xml_extractor_FT.extrair_dados_ft`).
        fator_k: certificate's nominal K-Factor (`dados["fator_k"]`).
        aplicacao: certificate's "Aplicação" field.
        digitos: number of significant figures for the K-Factor Corrigido
            column — customizable per certificate (see `montar_contexto`).

    Returns:
        dict: all of `p`'s original keys plus `frequencia_hz`, `kfc` (raw
        floats) and every `*_fmt` string used directly by the template.
    """
    meter_factor = p["meter_factor"]
    frequencia_hz = fator_k * p["vazao"] / 3600
    try:
        kfc = fator_k / meter_factor
    except ZeroDivisionError:
        kfc = 0.0
    casas_kfc = _casas_significativas(kfc, digitos)

    return {
        **p,
        "frequencia_hz": frequencia_hz,
        "kfc": round(kfc, casas_kfc),
        "status": status_ponto(p["erro_pct"], aplicacao),
        "vazao_fmt": _num_br(p["vazao"], p.get("vazao_casas", 0)),
        "vol_ref_fmt": _num_br(p["vol_referencia"], p.get("vol_referencia_casas", 0)),
        "vol_med_fmt": _num_br(p["vol_medidor"], p.get("vol_medidor_casas", 0)),
        "frequencia_fmt": _num_br(frequencia_hz, 0),
        "meter_factor_fmt": _num_br(meter_factor, 5),
        "kfc_fmt": _num_br(kfc, casas_kfc),
        "erro_fmt": _num_br(p["erro_pct"], 2),
        "incerteza_fmt": _num_br(p["incerteza"], 2),
    }


def montar_contexto(dados: dict, caminho_xml: str) -> dict:
    """Builds the full Jinja2 context for `templates/linearizacao.html` from the extracted certificate data.

    Args:
        dados: data extracted by `xml_model.xml_extractor_FT.extrair_dados_ft`,
            with `aplicacao`/`sistema`/`cliente`/`elaborado_por`/`verificado_por`
            already filled in by the prompt in
            `PdfProcessingService._processar_xml_ft` (same as
            `form.utils_print_linearizacao.gerar_linearizacao` expects).
        caminho_xml: path of the input XML — used only as a fallback to
            resolve "Cliente" from the folder name when `dados["cliente"]`
            isn't already set (see `identificar_cliente`).

    Returns:
        dict: context ready to pass to the Jinja2 template — `cabecalho`,
        `unidades`, `pontos` (each already carrying its `*_fmt` display
        strings and `status`), `resumo` (KF médio + alarm limits) and
        `assinaturas`.
    """
    cliente = dados.get("cliente") or identificar_cliente(dados.get("cliente_xml", ""), caminho_xml)
    aplicacao = dados.get("aplicacao", "")
    fator_k = dados.get("fator_k", 0.0)
    # Significant figures for the K-Factor Corrigido column only — it's the
    # value actually programmed into the flow computer, so its precision
    # depends on that specific CV, not on the meter/certificate (see
    # `PdfProcessingService._processar_xml_ft`'s "Casas do Fator K" prompt
    # field). The nominal K-Factor (certificate's own reported value) and
    # KF médio keep the fixed 7-significant-figure rule regardless.
    digitos_kfc = int(dados.get("casas_fator_k") or 7)

    pontos = [_calcular_ponto(p, fator_k, aplicacao, digitos_kfc) for p in dados.get("pontos", [])]

    if pontos:
        kf_medio = sum(p["kfc"] for p in pontos) / len(pontos)
        casas_kf_medio = _casas_significativas(kf_medio, 7)
    else:
        kf_medio = 0.0
        casas_kf_medio = 0

    agora = datetime.now()
    data_assinatura = dados.get("_data_assinatura") or agora.strftime("%d/%m/%Y")

    return {
        "gerado_em": agora.strftime("%d/%m/%Y %H:%M"),
        "cabecalho": {
            "cliente": cliente,
            "instalacao": dados.get("unidade_operacional", ""),
            "tag_sistema": dados.get("tag", ""),
            "aplicacao": aplicacao,
            "sistema": dados.get("sistema", ""),
            "data_calibracao": _data_br(dados.get("data_calibracao", "")),
            "tipo_medidor": dados.get("tipo", ""),
            "num_certificado": dados.get("numero_certificado", ""),
            "modelo": dados.get("modelo", ""),
            "fabricante": dados.get("fabricante", ""),
            "num_serie": dados.get("num_serie", ""),
            "diametro": dados.get("diametro", ""),
            "faixa_calibrada": dados.get("faixa_calibrada", ""),
            "fator_k": _num_br(fator_k, _casas_significativas(fator_k, 7)),
        },
        "unidades": {
            "vazao": dados.get("vazao_unidade") or "m³/h",
            "vol_ref": dados.get("vol_referencia_unidade") or "L",
            "vol_med": dados.get("vol_medidor_unidade") or "L",
        },
        "pontos": pontos,
        "estilo_pontos": estilo_tabela_pontos(len(pontos)),
        "resumo": {
            "kf_medio_fmt": _num_br(kf_medio, casas_kf_medio),
            "alarme_baixo_fmt": dados.get("faixa_min", ""),
            "alarme_alto_fmt": dados.get("faixa_max", ""),
        },
        "assinaturas": {
            "elaborado_nome": dados.get("elaborado_por") or "",
            "elaborado_data": data_assinatura,
            "verificado_nome": dados.get("verificado_por") or "",
            "verificado_data": data_assinatura,
        },
        "logos": {
            "ods": _logo_base64("logo_ods_cabecalho.png"),
            "mascote": _logo_base64("logo_mascote.png"),
        },
    }


def gerar_linearizacao_pdf(dados: dict, caminho_xml: str, sessao=None) -> str:
    """Renders the Linearização report straight to PDF from `templates/linearizacao.html` — no XLSX is produced.

    Output file is saved in the same folder as the input XML, named the same
    way as the Excel pipeline's PDF (`<CERT>_<TAG>_LINEARIZACAO.pdf`) so it
    drops into the existing output-card/"open file" UI without changes there.

    Args:
        dados: same shape `form.utils_print_linearizacao.gerar_linearizacao`
            expects (`xml_extractor_FT.extrair_dados_ft`'s output, plus
            `aplicacao`/`sistema`/`cliente`/`elaborado_por`/`verificado_por`
            from the prompt).
        caminho_xml: path of the input XML; used to determine the output
            folder and as `identificar_cliente`'s path fallback.
        sessao: optional `form.html_to_pdf.SessaoHtmlParaPdf` already
            started — reuses its warm WebView2 environment instead of
            spinning up a brand-new one just for this report. Pass the
            same session shared with `gerar_falha_presumida_pdf`/
            `gerar_ac_primario_pdf` when generating more than one report
            for the same certificate — opening a fresh session per report
            multiplies a real, measured ~cold-start cost for no benefit
            (see `SessaoHtmlParaPdf`'s docstring). `None` falls back to a
            throwaway one-off session (fine for standalone/single calls).

    Returns:
        str: path of the generated PDF.

    Raises:
        ValueError: if the certificate has more calibration points than
            `MAX_PONTOS` — the layout (see `estilo_tabela_pontos`) is only
            tuned to shrink down to that many points while still fitting a
            single printed page.
        HtmlParaPdfError: if the WebView2 export itself fails (see
            `form.html_to_pdf.html_para_pdf`).
        PermissionError: if the output PDF already exists and is open.
    """
    n_pontos = len(dados.get("pontos", []))
    if n_pontos > MAX_PONTOS:
        raise ValueError(
            f"Relatório de Linearização suporta no máximo {MAX_PONTOS} pontos "
            f"de calibração (certificado tem {n_pontos})."
        )

    contexto = montar_contexto(dados, caminho_xml)

    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("linearizacao.html").render(**contexto)

    pasta_saida = os.path.dirname(os.path.abspath(caminho_xml))
    cert_limpo = dados.get("numero_certificado", "").replace(" ", "")
    tag_limpa = dados.get("tag", "").replace(" ", "")
    caminho_pdf = os.path.join(pasta_saida, f"{cert_limpo}_{tag_limpa}_LINEARIZACAO.pdf")

    if sessao is not None:
        sessao.exportar(html, caminho_pdf)
    else:
        html_para_pdf(html, caminho_pdf)
    return caminho_pdf
