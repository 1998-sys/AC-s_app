# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : form.utils_print_linearizacao_xlsx
# Created       : 29-09-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Companion XLSX export for Linearização/Falha Presumida, filled via openpyxl only (no Excel COM/PDF export — that's the job of form.utils_print_linearizacao_html/form.utils_print_falha_presumida_html). Requested as a safety net so an engineer can open the filled Template_Linearizacao.xlsx directly to double-check or tweak a parameter, without redoing the HTML/PDF pipeline's math by hand.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from copy import copy
import math
import os
from datetime import datetime

import openpyxl
from openpyxl.styles import Border, Side

from form.utils_print_linearizacao import _data_br, identificar_cliente, parear_pontos_anterior

# ── CELL MAP ─────────────────────────────────────────────────────────
# Addresses confirmed by opening Template_Linearizacao.xlsx (sheet "Linearização").
# Frequência (E), Status (S), the 2nd table "Dados a Serem Configurados" (rows
# 56-75), KF médio (L76) and the alarm limits (J79/M79) are already FORMULAS in
# the template itself — all derived from the columns we fill here
# (C/G/I/K/M/Q). Do not write to them: Excel recalculates them on its own
# when the file is opened.
CELLS = {
    # Left header
    "cliente":         "D9",
    "instalacao":      "D10",
    "tag_sistema":     "D11",
    "aplicacao":       "D12",
    "sistema":         "D13",
    "data_calibracao": "D14",
    "tipo_medidor":    "D15",
    # Right header ("TAG" in M12 is formula "=D11", do not write)
    "num_certificado": "M9",
    "modelo":          "M10",
    "fabricante":      "M11",
    "num_serie":       "M13",
    "diametro":        "M14",
    "faixa_calibrada": "M15",
    # Nominal K-Factor
    "fator_k":         "D19",
    # KF médio (template formula "=AVERAGE(...)", in the 2nd table)
    "kf_medio":        "L76",
    # Calibration table (rows 22 to 41 — up to 20 points)
    "tabela_linha_ini": 22,
    "tabela_linha_fim": 41,
    "col_vazao":       "C",
    "col_vol_ref":     "G",
    "col_vol_med":     "I",
    "col_mf":          "K",
    "col_kfc":         "O",
    "col_erro":        "M",
    "col_incerteza":   "Q",
    # Column titles (the unit written in parentheses is dynamically
    # overwritten with the certificate's actual unit).
    "titulo_vazao":     "C21",
    "titulo_vol_ref":   "G21",
    "titulo_vol_med":   "I21",
    # Signature block (default names already come filled in the template;
    # only overwritten if the user chooses to change them in the prompt).
    "elaborado_nome": "F96",
    "elaborado_data": "F98",
    "verificado_nome": "N96",
    # verificado_data (N98) is formula "=F98" in the template — do not overwrite.
}

# Columns with a border in the calibration table (B = outer left border to
# T = outer right border). Row 30 is used as the reference for the "normal"
# (thin) border in the middle of the table.
_BORDA_COLS = ["B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"]
_LINHA_BORDA_REF = 30

# The "Dados a Serem Configurados" table (row + TABELA2_OFFSET) is narrower
# than the one above — it only uses H to M (N°/Vazão/Frequência/K-factor
# corrigido); C to G and N to T are always left without a border there.
_BORDA_COLS_TABELA2 = ["H", "I", "J", "K", "L", "M"]

# Row offset from table 1 (calibration) to the 2nd table ("Dados a Serem
# Configurados") — e.g. row 22 of table 1 mirrors row 56 of table 2.
TABELA2_OFFSET = 34

# ── "Falha Presumida" sheet ──────────────────────────────────────────────
SHEET_FALHA_PRESUMIDA = "Falha Presumida"
FP_CERT_ANTERIOR = "G85"          # previous certificate's number
FP_COL_MF_ANTERIOR = "G"          # previous certificate's meter factor, per row
FP_LINHA_INI = 87                 # mirrors Linearização's row 22 (offset 65)
FP_LINHA_FIM_MAX = 106            # mirrors Linearização's row 41 (up to 20 points)
FP_LINHA_BORDA_REF_CALCULO = 90   # a "middle" row of the Cálculo Falha Presumida table
FP_BORDA_COLS_CALCULO = ["E", "G", "I", "K", "L", "N"]

# The calibration-table mirror (rows 22-41) has its own row visibility/border
# state on this sheet (Excel doesn't share hidden-row state between sheets),
# even though its cell values are 100% formula-mirrored from Linearização.
FP_MIRROR_LINHA_INI = 22
FP_MIRROR_LINHA_FIM_MAX = 41
FP_MIRROR_LINHA_BORDA_REF = 30
FP_MIRROR_BORDA_COLS = ["B", "C", "E", "G", "I", "K", "M", "O", "Q", "S", "T"]

MAX_PONTOS = CELLS["tabela_linha_fim"] - CELLS["tabela_linha_ini"] + 1


def _formato_decimal(casas: int) -> str:
    """Builds an Excel number format string with a fixed number of decimal places."""
    return f"0.{'0' * casas}" if casas > 0 else "0"


def _casas_significativas(valor: float, digitos: int) -> int:
    """Computes how many decimal places make `valor` display with `digitos` significant figures.

    Args:
        valor: value that will be rounded/displayed.
        digitos: number of significant figures to target — customizable per
            certificate (see `PdfProcessingService._processar_xml_ft`'s
            "Casas do Fator K" prompt field), since different flow computer
            models expect a different K-Factor precision.

    Returns:
        int: number of decimal places (never negative). Falls back to
        `digitos - 1` when `valor` is zero/None (order of magnitude undefined).
    """
    if not valor:
        return digitos - 1
    ordem = math.floor(math.log10(abs(valor)))
    return max(0, digitos - 1 - ordem)


def _formato_significativos(valor: float, digitos: int) -> str:
    """Builds an Excel number format string that always displays `digitos` significant figures."""
    return _formato_decimal(_casas_significativas(valor, digitos))


def _celula(col: str, linha: int) -> str:
    """Builds a cell address from column and row (e.g. "C", 22 -> "C22")."""
    return f"{col}{linha}"


def _ajustar_linhas_tabela(ws, linha_ini, linha_fim_max, n_pontos):
    """Shows only the table rows actually used and normalizes their borders/heights.

    Same normalization the old Excel pipeline did (see git history of this
    module) — kept here since it's still needed for a companion XLSX that
    looks right when opened directly, just without the win32com-only
    physical row deletion (that was purely cosmetic, to avoid Excel's own
    "hidden row" indicator — not worth reintroducing Excel COM for a
    reference file the engineer already knows to expect hidden rows on).

    Args:
        ws: openpyxl worksheet.
        linha_ini: First row of the calibration table.
        linha_fim_max: Last possible row of the table (maximum capacity).
        n_pontos: Number of calibration points for this certificate.
    """
    linha_fim_usada = linha_ini + n_pontos - 1 if n_pontos else linha_ini - 1

    for row in range(linha_ini, linha_fim_max + 1):
        usada = row <= linha_fim_usada
        ws.row_dimensions[row].hidden = not usada
        ws.row_dimensions[row + TABELA2_OFFSET].hidden = not usada
        ws[f"K{row + TABELA2_OFFSET}"].number_format = ws[f"E{row}"].number_format

        if not usada:
            # Rows 22-31 of the template ship with hardcoded SAMPLE
            # calibration values (not blank) — clearing them keeps KF
            # médio/tolerance-bound formulas (which span the full 20-row
            # range regardless of how many rows are shown) from reading
            # stale sample data for a certificate with fewer points.
            for col in (
                CELLS["col_vazao"], CELLS["col_vol_ref"], CELLS["col_vol_med"],
                CELLS["col_mf"], CELLS["col_erro"], CELLS["col_incerteza"],
            ):
                ws[f"{col}{row}"] = None
            continue

        if row == linha_ini:
            continue  # table header row: keeps the original border

        ws.row_dimensions[row].height = ws.row_dimensions[_LINHA_BORDA_REF].height
        ws.row_dimensions[row + TABELA2_OFFSET].height = ws.row_dimensions[
            _LINHA_BORDA_REF + TABELA2_OFFSET
        ].height

        for col in _BORDA_COLS:
            ws[f"{col}{row}"].border = copy(ws[f"{col}{_LINHA_BORDA_REF}"].border)
        for col in _BORDA_COLS_TABELA2:
            ws[f"{col}{row + TABELA2_OFFSET}"].border = copy(
                ws[f"{col}{_LINHA_BORDA_REF + TABELA2_OFFSET}"].border
            )

    if n_pontos:
        for col in _BORDA_COLS:
            atual = ws[f"{col}{linha_fim_usada}"].border
            ws[f"{col}{linha_fim_usada}"].border = Border(
                top=atual.top, left=atual.left, right=atual.right,
                bottom=Side(style="medium"),
            )
        for col in _BORDA_COLS_TABELA2:
            row_fim2 = linha_fim_usada + TABELA2_OFFSET
            atual = ws[f"{col}{row_fim2}"].border
            ws[f"{col}{row_fim2}"].border = Border(
                top=atual.top, left=atual.left, right=atual.right,
                bottom=Side(style="medium"),
            )


def _normalizar_linhas_tabela_generico(ws, linha_ini, linha_fim_max, n_pontos, linha_borda_ref, colunas_borda):
    """Same show/hide + border/height normalization as `_ajustar_linhas_tabela`, generalized to a single table (no 2nd-table mirroring) — reused for the "Falha Presumida" sheet's two tables."""
    linha_fim_usada = linha_ini + n_pontos - 1 if n_pontos else linha_ini - 1

    for row in range(linha_ini, linha_fim_max + 1):
        usada = row <= linha_fim_usada
        ws.row_dimensions[row].hidden = not usada

        if not usada or row == linha_ini:
            continue  # table header row: keeps the original border

        ws.row_dimensions[row].height = ws.row_dimensions[linha_borda_ref].height
        for col in colunas_borda:
            ws[f"{col}{row}"].border = copy(ws[f"{col}{linha_borda_ref}"].border)

    if n_pontos:
        for col in colunas_borda:
            atual = ws[f"{col}{linha_fim_usada}"].border
            ws[f"{col}{linha_fim_usada}"].border = Border(
                top=atual.top, left=atual.left, right=atual.right,
                bottom=Side(style="medium"),
            )


def gerar_linearizacao_xlsx(dados: dict, caminho_xml: str, casas_fator_k: int = 7) -> str:
    """Fills Template_Linearizacao.xlsx's "Linearização" sheet and saves it — no PDF export, that's `form.utils_print_linearizacao_html.gerar_linearizacao_pdf`'s job.

    Companion artifact to the PDF: same output folder/base name as the old
    Excel pipeline's XLSX, so an engineer can open it directly to
    double-check a parameter or tweak something the PDF doesn't expose
    (e.g. re-running a formula by hand).

    Args:
        dados: same shape `form.utils_print_linearizacao_html.gerar_linearizacao_pdf`
            expects, plus optional `casas_fator_k` (falls back to the
            `casas_fator_k` parameter below if absent from `dados`).
        caminho_xml: path of the input XML; used to determine the output folder.
        casas_fator_k: number of significant figures for the K-Factor
            Corrigido column (per point) — customizable per certificate
            since it's the value actually programmed into the flow
            computer, and different flow computer models expect a
            different precision (see `PdfProcessingService._processar_xml_ft`'s
            "Casas do Fator K" prompt). The nominal K-Factor and KF médio
            keep the fixed 7-significant-figure rule regardless.

    Returns:
        str: path of the generated XLSX.

    Raises:
        ValueError: if the certificate has more calibration points than the
            template supports (20).
    """
    # Significant figures for the K-Factor Corrigido column only — see
    # form.utils_print_linearizacao_html.montar_contexto's comment on why
    # the nominal K-Factor and KF médio keep the fixed 7-figure rule.
    digitos_kfc = int(dados.get("casas_fator_k") or casas_fator_k)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    caminho_template = os.path.join(base_dir, "templates", "Template_Linearizacao.xlsx")

    wb = openpyxl.load_workbook(caminho_template)
    ws = wb["Linearização"]

    C = CELLS  # shortcut

    cliente = dados.get("cliente") or identificar_cliente(dados.get("cliente_xml", ""), caminho_xml)

    ws[C["cliente"]]         = cliente
    ws[C["instalacao"]]      = dados.get("unidade_operacional", "")
    ws[C["tag_sistema"]]     = dados.get("tag", "")
    ws[C["aplicacao"]]       = dados.get("aplicacao", "")
    ws[C["sistema"]]         = dados.get("sistema", "")
    ws[C["data_calibracao"]] = _data_br(dados.get("data_calibracao", ""))
    ws[C["tipo_medidor"]]    = dados.get("tipo", "")

    ws[C["num_certificado"]] = dados.get("numero_certificado", "")
    ws[C["modelo"]]          = dados.get("modelo", "")
    ws[C["fabricante"]]      = dados.get("fabricante", "")
    ws[C["num_serie"]]       = dados.get("num_serie", "")
    ws[C["diametro"]]        = dados.get("diametro", "")
    ws[C["faixa_calibrada"]] = dados.get("faixa_calibrada", "")

    fator_k = dados.get("fator_k", 0.0)
    ws[C["fator_k"]] = fator_k
    ws[C["fator_k"]].number_format = _formato_significativos(fator_k, 7)

    ws[C["titulo_vazao"]]   = f"Vazão da Calibração ({dados.get('vazao_unidade') or 'm³/h'})"
    ws[C["titulo_vol_ref"]] = f"Volume de Referência ({dados.get('vol_referencia_unidade') or 'L'})"
    ws[C["titulo_vol_med"]] = f"Volume do Medidor ({dados.get('vol_medidor_unidade') or 'L'})"

    pontos = dados.get("pontos", [])
    linha_ini = C["tabela_linha_ini"]
    if len(pontos) > MAX_PONTOS:
        raise ValueError(
            f"Template de linearização suporta no máximo {MAX_PONTOS} pontos "
            f"de calibração (certificado tem {len(pontos)})."
        )

    kfc_estimados = []
    for i, p in enumerate(pontos):
        row = linha_ini + i

        cel_vazao = ws[_celula(C["col_vazao"], row)]
        cel_vazao.value = p["vazao"]
        cel_vazao.number_format = _formato_decimal(p.get("vazao_casas", 0))

        cel_vol_ref = ws[_celula(C["col_vol_ref"], row)]
        cel_vol_ref.value = p["vol_referencia"]
        cel_vol_ref.number_format = _formato_decimal(p.get("vol_referencia_casas", 0))

        cel_vol_med = ws[_celula(C["col_vol_med"], row)]
        cel_vol_med.value = p["vol_medidor"]
        cel_vol_med.number_format = _formato_decimal(p.get("vol_medidor_casas", 0))

        ws[_celula(C["col_mf"],        row)] = p["meter_factor"]
        ws[_celula(C["col_erro"],      row)] = p["erro_pct"]
        ws[_celula(C["col_incerteza"], row)] = p["incerteza"]

        meter_factor = p["meter_factor"]
        try:
            kfc_estimado = fator_k / meter_factor
        except ZeroDivisionError:
            kfc_estimado = 0
        casas_kfc = _casas_significativas(kfc_estimado, digitos_kfc)
        col_kfc = C["col_kfc"]
        col_mf = C["col_mf"]

        cel_kfc = ws[_celula(col_kfc, row)]
        cel_kfc.value = f'=IFERROR(ROUND($D$19/{col_mf}{row},{casas_kfc}),"")'
        cel_kfc.number_format = _formato_decimal(casas_kfc)
        kfc_estimados.append(round(kfc_estimado, casas_kfc))

        ws[f"L{row + TABELA2_OFFSET}"].number_format = _formato_decimal(casas_kfc)

    if kfc_estimados:
        media_kfc = sum(kfc_estimados) / len(kfc_estimados)
        ws[C["kf_medio"]].number_format = _formato_significativos(media_kfc, 7)

    _ajustar_linhas_tabela(ws, C["tabela_linha_ini"], C["tabela_linha_fim"], len(pontos))

    ws[C["elaborado_data"]] = datetime.now()
    if dados.get("elaborado_por"):
        ws[C["elaborado_nome"]] = dados["elaborado_por"]
    if dados.get("verificado_por"):
        ws[C["verificado_nome"]] = dados["verificado_por"]

    pasta_saida   = os.path.dirname(os.path.abspath(caminho_xml))
    cert_limpo    = dados.get("numero_certificado", "").replace(" ", "")
    tag_limpa     = dados.get("tag", "").replace(" ", "")
    caminho_xlsx  = os.path.join(pasta_saida, f"{cert_limpo}_{tag_limpa}_LINEARIZACAO.xlsx")

    wb.save(caminho_xlsx)
    return caminho_xlsx


def gerar_falha_presumida_xlsx(caminho_xlsx: str, dados_atual: dict, dados_anterior: dict) -> str:
    """Fills the "Falha Presumida" sheet of an already-generated Linearização workbook and re-saves it — no PDF export.

    Only two things are written here: the previous certificate's number and
    its meter factor per point (paired by nearest flow rate). Everything
    else on this sheet (header, calibration table, Diff MF, Fator de
    Correção, Status) is a template formula mirroring the "Linearização"
    sheet of the same workbook, already filled by `gerar_linearizacao_xlsx`.

    Args:
        caminho_xlsx: path of the workbook already produced by
            `gerar_linearizacao_xlsx` for the current certificate (reopened
            and updated in place, since both sheets live in it).
        dados_atual: current certificate's data (`dados_atual["pontos"]`
            gives the row order/count already written to the Linearização
            table).
        dados_anterior: previous certificate's data.

    Returns:
        str: path of the updated XLSX (same as `caminho_xlsx`).

    Raises:
        ValueError: if the previous certificate has no calibration points.
    """
    wb = openpyxl.load_workbook(caminho_xlsx)
    ws = wb[SHEET_FALHA_PRESUMIDA]

    pontos_atual = dados_atual.get("pontos", [])
    mf_anteriores = [
        p["meter_factor"]
        for p in parear_pontos_anterior(pontos_atual, dados_anterior.get("pontos", []))
    ]

    ws[FP_CERT_ANTERIOR] = dados_anterior.get("numero_certificado", "")
    for i, mf in enumerate(mf_anteriores):
        ws[f"{FP_COL_MF_ANTERIOR}{FP_LINHA_INI + i}"] = mf

    # Rows 87-96 of the template ship with hardcoded SAMPLE "MF Calibração
    # anterior" values (not blank) — clearing the unused ones keeps a
    # certificate with fewer points from showing a bogus Diff MF/Status for
    # a "phantom" point.
    for row in range(FP_LINHA_INI + len(mf_anteriores), FP_LINHA_FIM_MAX + 1):
        ws[f"{FP_COL_MF_ANTERIOR}{row}"] = None

    _normalizar_linhas_tabela_generico(
        ws, FP_MIRROR_LINHA_INI, FP_MIRROR_LINHA_FIM_MAX, len(pontos_atual),
        FP_MIRROR_LINHA_BORDA_REF, FP_MIRROR_BORDA_COLS,
    )
    _normalizar_linhas_tabela_generico(
        ws, FP_LINHA_INI, FP_LINHA_FIM_MAX, len(pontos_atual),
        FP_LINHA_BORDA_REF_CALCULO, FP_BORDA_COLS_CALCULO,
    )

    wb.save(caminho_xlsx)
    return caminho_xlsx
