# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : form.utils_print_linearizacao
# Created       : 31-07-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Fills the flow meter linearization Excel template with the calibration points and exports both XLSX and PDF.
#                 Preenche o template Excel de linearização de medidor de vazão com os pontos de calibração e exporta o XLSX e o PDF.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from copy import copy
import openpyxl
from openpyxl.styles import Border, Side
import win32com.client as win32
import os
from datetime import datetime


# ── MAPA DE CÉLULAS ─────────────────────────────────────────────────────────
# Endereços confirmados abrindo Template_Linearizacao.xlsx (aba "Linearização").
# Frequência (E), K-factor corrigido (O), Status (S), a 2ª tabela "Dados a
# Serem Configurados" (linhas 56-75), KF médio (L76) e os limites de alarme
# (J79/M79) já são FÓRMULAS no próprio template — todas derivadas das
# colunas que preenchemos aqui (C/G/I/K/M/Q). Não escrever nelas: o Excel
# recalcula sozinho ao abrir/exportar (inclusive a cor aprovado/reprovado,
# que é formatação condicional nativa em S22:T41 — não precisa de PatternFill).
CELLS = {
    # Cabeçalho esquerda
    "cliente":         "D9",
    "instalacao":      "D10",
    "tag_sistema":     "D11",
    "aplicacao":       "D12",
    "sistema":         "D13",
    "data_calibracao": "D14",
    "tipo_medidor":    "D15",
    # Cabeçalho direita ("TAG" em M12 é fórmula "=D11", não escrever)
    "num_certificado": "M9",
    "modelo":          "M10",
    "fabricante":      "M11",
    "num_serie":       "M13",
    "diametro":        "M14",
    "faixa_calibrada": "M15",
    # K-Factor nominal
    "fator_k":         "D19",
    # Tabela de calibração (linhas 22 a 41 — até 20 pontos)
    "tabela_linha_ini": 22,
    "tabela_linha_fim": 41,
    "col_vazao":       "C",
    "col_vol_ref":     "G",
    "col_vol_med":     "I",
    "col_mf":          "K",
    "col_erro":        "M",
    "col_incerteza":   "Q",
}

# Colunas com borda na tabela de calibração (B = borda externa esquerda até
# T = borda externa direita). Linha 30 é usada como referência de borda
# "normal" (fina) do meio da tabela — ver _ajustar_bordas_tabela.
_BORDA_COLS = ["B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"]
_LINHA_BORDA_REF = 30


def _data_br(data_iso: str) -> str:
    """Converts a date from ISO format (YYYY-MM-DD) to BR format (DD/MM/YYYY).

    Args:
        data_iso: Date in ISO format, e.g. "2026-04-25".

    Returns:
        str: Date in "DD/MM/YYYY" format, e.g. "25/04/2026"; returns
        `data_iso` unchanged if it cannot be parsed.
    """
    try:
        return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return data_iso


def _cliente_do_caminho(caminho: str) -> str:
    """Extracts the client name from the file path.

    Args:
        caminho: File path (e.g. ".../PRIO/...").

    Returns:
        str: Recognized client name (PRIO, YINSON, ORIGEM, SBM or
        PETROBRAS) found in some segment of the path, or an empty string
        if none is found.
    """
    partes = caminho.upper().replace("\\", "/").split("/")
    for p in partes:
        for cliente in ("PRIO", "YINSON", "ORIGEM", "SBM", "PETROBRAS"):
            if cliente in p:
                return cliente
    return ""


def contexto_db(tag: str):
    """Looks up application and system in the instrument registry by TAG.

    Used only as the pre-filled value for the prompt that asks the user for
    these two fields (see PdfProcessingService._processar_xml_ft); flow
    meters are usually not in this registry, so this tends to come back empty.

    Args:
        tag: Instrument TAG to look up.

    Returns:
        tuple: (aplicacao, sistema), each as a string (empty if not found
        or on a lookup error).
    """
    try:
        from data.utils_db import buscar_instrumento_por_tag
        inst = buscar_instrumento_por_tag(tag)
        if inst:
            return inst.get("aplicacao") or "", inst.get("sistema") or ""
    except Exception:
        pass
    return "", ""


def _celula(col: str, linha: int) -> str:
    """Builds a cell address from column and row (e.g. "C", 22 -> "C22")."""
    return f"{col}{linha}"


def _ajustar_linhas_tabela(ws, linha_ini, linha_fim_max, n_pontos):
    """Shows only the table rows actually used and normalizes their borders.

    Displays exactly the `n_pontos` used rows (from `linha_ini` to
    `linha_ini + n_pontos - 1`), hiding the rest even if they were
    originally visible, normalizes each row's border against row
    `_LINHA_BORDA_REF` (a "middle" row of the table, with a thin border) and
    closes the last used row with a thick border at the bottom.

    Args:
        ws: openpyxl worksheet.
        linha_ini: First row of the calibration table.
        linha_fim_max: Last possible row of the table (maximum capacity).
        n_pontos: Number of calibration points for this certificate.

    Notes:
        Without this normalization, re-shown rows (originally hidden, when
        there are fewer than 10 points) come out with a thicker outline, and
        the old last row (31), once it stops being the last one due to
        extra points, would be left with the thick border "leftover" in the
        middle of the table. The "Dados a Serem Configurados" table mirrors,
        on row N + `TABELA2_OFFSET` (34), row N of this table (e.g. row 22 ->
        row 56), so each hidden/shown row is also replicated there.
    """
    TABELA2_OFFSET = 34
    linha_fim_usada = linha_ini + n_pontos - 1 if n_pontos else linha_ini - 1

    for row in range(linha_ini, linha_fim_max + 1):
        usada = row <= linha_fim_usada
        ws.row_dimensions[row].hidden = not usada
        ws.row_dimensions[row + TABELA2_OFFSET].hidden = not usada

        if not usada or row == linha_ini:
            continue  # linha de cabeçalho da tabela: mantém a borda original

        for col in _BORDA_COLS:
            ws[f"{col}{row}"].border = copy(ws[f"{col}{_LINHA_BORDA_REF}"].border)

    if n_pontos:
        for col in _BORDA_COLS:
            atual = ws[f"{col}{linha_fim_usada}"].border
            ws[f"{col}{linha_fim_usada}"].border = Border(
                top=atual.top, left=atual.left, right=atual.right,
                bottom=Side(style="medium"),
            )


def gerar_linearizacao(dados: dict, caminho_xml: str) -> str:
    """Fills Template_Linearizacao.xlsx with the flow meter data and exports XLSX + PDF.

    The output files are saved in the same folder as the input XML.

    Args:
        dados: Flow meter and calibration data (header and list of points
            under "pontos").
        caminho_xml: Path of the input XML; used only to determine the
            output folder and, from the path, the client.

    Returns:
        str: Path of the generated XLSX (the PDF is generated alongside it,
        with the same base name).

    Raises:
        ValueError: If the certificate has more calibration points than
            the template supports.
        PermissionError: If the output PDF already exists and is open (it
            cannot be overwritten).
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    caminho_template = os.path.join(base_dir, "Template_Linearizacao.xlsx")

    wb = openpyxl.load_workbook(caminho_template)
    ws = wb["Linearização"]

    C = CELLS  # atalho

    # ── Cabeçalho esquerda ────────────────────────────────────────────────
    # aplicacao/sistema vêm do prompt pedido ao usuário ao soltar o XML
    # (PdfProcessingService._processar_xml_ft) — não existem no cadastro de
    # instrumentos pra medidor de vazão.
    cliente = _cliente_do_caminho(caminho_xml)

    ws[C["cliente"]]         = cliente
    ws[C["instalacao"]]      = dados.get("unidade_operacional", "")
    ws[C["tag_sistema"]]     = dados.get("tag", "")
    ws[C["aplicacao"]]       = dados.get("aplicacao", "")
    ws[C["sistema"]]         = dados.get("sistema", "")
    ws[C["data_calibracao"]] = _data_br(dados.get("data_calibracao", ""))
    ws[C["tipo_medidor"]]    = dados.get("tipo", "")

    # ── Cabeçalho direita ─────────────────────────────────────────────────
    ws[C["num_certificado"]] = dados.get("numero_certificado", "")
    ws[C["modelo"]]          = dados.get("modelo", "")
    ws[C["fabricante"]]      = dados.get("fabricante", "")
    ws[C["num_serie"]]       = dados.get("num_serie", "")
    ws[C["diametro"]]        = dados.get("diametro", "")
    ws[C["faixa_calibrada"]] = dados.get("faixa_calibrada", "")

    # ── K-Factor nominal ──────────────────────────────────────────────────
    ws[C["fator_k"]] = dados.get("fator_k", "")

    # ── Tabela de calibração ────────────────────────────────────────────
    # Frequência (E), K-factor corrigido (O) e Status (S) são fórmulas do
    # template — calculadas a partir do que escrevemos aqui, não tocar.
    pontos = dados.get("pontos", [])
    linha_ini = C["tabela_linha_ini"]
    max_pontos = C["tabela_linha_fim"] - linha_ini + 1
    if len(pontos) > max_pontos:
        raise ValueError(
            f"Template de linearização suporta no máximo {max_pontos} pontos "
            f"de calibração (certificado tem {len(pontos)})."
        )

    for i, p in enumerate(pontos):
        row = linha_ini + i

        ws[_celula(C["col_vazao"],     row)] = p["vazao"]
        ws[_celula(C["col_vol_ref"],   row)] = p["vol_referencia_l"]
        ws[_celula(C["col_vol_med"],   row)] = p["vol_medidor_l"]
        ws[_celula(C["col_mf"],        row)] = p["meter_factor"]
        ws[_celula(C["col_erro"],      row)] = p["erro_pct"]
        ws[_celula(C["col_incerteza"], row)] = p["incerteza"]

    # O template só vem com as 10 primeiras linhas de cada tabela visíveis e
    # com borda "normal" (linhas 22-31 e seu espelho 56-65 em "Dados a Serem
    # Configurados"); as próximas 10 (32-41 / 66-75) ficam ocultas por
    # padrão — reexibe/oculta conforme o nº de pontos deste certificado e
    # uniformiza a borda (senão as linhas reexibidas saem com um contorno
    # mais grosso, herdado do estilo delas quando ocultas).
    _ajustar_linhas_tabela(ws, C["tabela_linha_ini"], C["tabela_linha_fim"], len(pontos))

    # ── Salvar XLSX de saída ──────────────────────────────────────────────
    pasta_saida   = os.path.dirname(os.path.abspath(caminho_xml))
    cert_limpo    = dados.get("numero_certificado", "").replace(" ", "")
    tag_limpa     = dados.get("tag", "").replace(" ", "")
    nome_xlsx     = f"{cert_limpo}_{tag_limpa}_LINEARIZACAO.xlsx"
    caminho_xlsx  = os.path.join(pasta_saida, nome_xlsx)

    wb.save(caminho_xlsx)

    # ── Exportar PDF via Excel COM ────────────────────────────────────────
    nome_pdf    = f"{cert_limpo}_{tag_limpa}_LINEARIZACAO.pdf"
    caminho_pdf = os.path.join(pasta_saida, nome_pdf)

    if os.path.exists(caminho_pdf):
        try:
            os.remove(caminho_pdf)
        except PermissionError:
            raise PermissionError(
                f"O arquivo PDF está aberto e não pode ser sobrescrito:\n{caminho_pdf}"
            )

    excel = win32.DispatchEx("Excel.Application")
    excel.Visible        = False
    excel.DisplayAlerts  = False
    excel.ScreenUpdating = False
    excel.Interactive    = False

    try:
        wb_excel = excel.Workbooks.Open(os.path.abspath(caminho_xlsx))
        # Frequência/KFc/Status/2ª tabela/KF médio/alarmes são fórmulas —
        # força o recálculo antes de exportar pra não sair em branco no PDF.
        excel.Calculate()
        # Exporta só a aba "Linearização" — ExportAsFixedFormat no Workbook
        # (em vez da Worksheet) incluiria também "Falha Presumida" (ainda
        # não implementada) com os dados de exemplo do template.
        ws_excel = wb_excel.Worksheets("Linearização")
        ws_excel.ExportAsFixedFormat(0, caminho_pdf)
        wb_excel.Close(SaveChanges=False)
    finally:
        excel.Quit()

    return caminho_xlsx