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
import math
import openpyxl
from openpyxl.styles import Border, Side
import win32com.client as win32
import os
from datetime import datetime


# ── MAPA DE CÉLULAS ─────────────────────────────────────────────────────────
# Endereços confirmados abrindo Template_Linearizacao.xlsx (aba "Linearização").
# Frequência (E), Status (S), a 2ª tabela "Dados a Serem Configurados" (linhas
# 56-75), KF médio (L76) e os limites de alarme (J79/M79) já são FÓRMULAS no
# próprio template — todas derivadas das colunas que preenchemos aqui
# (C/G/I/K/M/Q). Não escrever nelas: o Excel recalcula sozinho ao abrir/
# exportar (inclusive a cor aprovado/reprovado, que é formatação condicional
# nativa em S22:T41 — não precisa de PatternFill).
# K-factor corrigido (O) também é fórmula do template, mas o ROUND()/formato
# fixos em 5 casas do template só fecham 7 dígitos significativos quando o
# valor cai entre 10 e 100 — pra um K-Factor típico (perto de 1) isso rende
# só 6 dígitos. Por isso essa fórmula é reescrita por linha em
# gerar_linearizacao (casa decimal calculada a partir da ordem de grandeza,
# mesma regra do K-Factor nominal) em vez de deixada intacta como as demais.
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
    # KF médio (fórmula "=AVERAGE(...)" do template, na 2ª tabela)
    "kf_medio":        "L76",
    # Tabela de calibração (linhas 22 a 41 — até 20 pontos)
    "tabela_linha_ini": 22,
    "tabela_linha_fim": 41,
    "col_vazao":       "C",
    "col_vol_ref":     "G",
    "col_vol_med":     "I",
    "col_mf":          "K",
    "col_kfc":         "O",
    "col_erro":        "M",
    "col_incerteza":   "Q",
    # Títulos de coluna (unidade escrita entre parênteses é sobrescrita
    # dinamicamente com a unidade real do certificado — ver gerar_linearizacao).
    "titulo_vazao":     "C21",
    "titulo_vol_ref":   "G21",
    "titulo_vol_med":   "I21",
    # Bloco de assinatura (nomes padrão já vêm preenchidos no template; só
    # são sobrescritos se o usuário optar por alterar no prompt).
    "elaborado_nome": "F96",
    "elaborado_data": "F98",
    "verificado_nome": "N96",
    # verificado_data (N98) é fórmula "=F98" no template — não sobrescrever.
}

# Colunas com borda na tabela de calibração (B = borda externa esquerda até
# T = borda externa direita). Linha 30 é usada como referência de borda
# "normal" (fina) do meio da tabela — ver _ajustar_bordas_tabela.
_BORDA_COLS = ["B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"]
_LINHA_BORDA_REF = 30

# A tabela "Dados a Serem Configurados" (linha + TABELA2_OFFSET) é mais
# estreita que a de cima — só usa H a M (N°/Vazão/Frequência/K-factor
# corrigido); C a G e N a T ficam sempre sem borda ali. Aplicar o range de
# colunas da tabela 1 (B a T) nela sobra borda grossa nas colunas N a T da
# linha de fechamento, "vazando" pra fora da caixa real da tabela 2.
_BORDA_COLS_TABELA2 = ["H", "I", "J", "K", "L", "M"]

# Deslocamento de linha da tabela 1 (calibração) para a 2ª tabela ("Dados a
# Serem Configurados") — ex.: linha 22 da tabela 1 espelha na linha 56 da
# tabela 2. Usado tanto pra ocultar/mostrar linhas quanto pro formato do
# K-Factor Corrigido (col. L na tabela 2, que espelha a col. O da tabela 1).
TABELA2_OFFSET = 34


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


def ler_nomes_assinatura():
    """Reads the default "Elaborado por"/"Verificado por" names baked into Template_Linearizacao.xlsx.

    Used only to pre-fill the rename prompt shown to the user before
    generating the report (see PdfProcessingService._processar_xml_ft) —
    the template ships with a fixed pair of names that most reports reuse
    as-is.

    Returns:
        tuple: (elaborado, verificado), each as a string (empty if the
        corresponding template cell has no value).
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    caminho_template = os.path.join(base_dir, "templates", "Template_Linearizacao.xlsx")
    wb = openpyxl.load_workbook(caminho_template, read_only=True)
    try:
        ws = wb["Linearização"]
        return ws[CELLS["elaborado_nome"]].value or "", ws[CELLS["verificado_nome"]].value or ""
    finally:
        wb.close()


def _formato_decimal(casas: int) -> str:
    """Builds an Excel number format string with a fixed number of decimal places.

    Args:
        casas: number of decimal places (0 means an integer format).

    Returns:
        str: Excel number format, e.g. "0.000" for `casas=3`, or "0" for `casas=0`.
    """
    return f"0.{'0' * casas}" if casas > 0 else "0"


def _casas_significativas(valor: float, digitos: int = 7) -> int:
    """Computes how many decimal places make `valor` display with `digitos` significant figures.

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


def _formato_significativos(valor: float, digitos: int = 7) -> str:
    """Builds an Excel number format string that always displays `digitos` significant figures.

    Unlike `_formato_decimal` (fixed decimal places, used when the output
    must mirror the certificate's own precision), this pads with trailing
    zeros when the source value naturally has fewer significant digits —
    required for K-Factor, which must always show 7 digits regardless of
    its order of magnitude.

    Args:
        valor: value that will be written to the cell.
        digitos: number of significant figures to display (default: 7).

    Returns:
        str: Excel number format, e.g. "0.000000" for a value between 1 and
        9.999999, or "0.00000000" for a value between 0.01 and 0.09999999.
    """
    return _formato_decimal(_casas_significativas(valor, digitos))


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
        middle of the table. The template's row HEIGHT is also inconsistent
        between blocks (some rows are None/default, others a fixed 15.0,
        15.75 or 14.45) — normalized here too, or a re-shown/last row comes
        out visibly taller/shorter than the rest even with a correct border.
        The "Dados a Serem Configurados" table mirrors, on row N +
        `TABELA2_OFFSET` (34), row N of this table (e.g. row 22 -> row 56) —
        visibility, border AND height normalization below are all applied to
        both tables; missing the second one leaves its old 10-point closing
        border stuck in the middle when there are more points, plus stray
        thick verticals and inconsistent heights on the re-shown rows.

        The mirror table's Frequência column (K) has the same kind of
        template inconsistency: rows 56-65 (points 1-10) carry the "0"
        format (no decimals, matching column E on table 1), but rows 66-75
        (points 11-20) come as "General" — which displays the raw,
        un-rounded value (e.g. "677,7777778") instead of the rounded
        display ("678") table 1 shows for the same point. Synced below on
        every row regardless of `usada`, since it's cheap and this is a
        display-only fix (no border/height implication).
    """
    linha_fim_usada = linha_ini + n_pontos - 1 if n_pontos else linha_ini - 1

    for row in range(linha_ini, linha_fim_max + 1):
        usada = row <= linha_fim_usada
        ws.row_dimensions[row].hidden = not usada
        ws.row_dimensions[row + TABELA2_OFFSET].hidden = not usada
        ws[f"K{row + TABELA2_OFFSET}"].number_format = ws[f"E{row}"].number_format

        if not usada or row == linha_ini:
            continue  # linha de cabeçalho da tabela: mantém a borda original

        # A altura das linhas do template original também é inconsistente
        # entre blocos (algumas ficam com altura padrão/None, outras com um
        # valor fixo tipo 15.0/15.75/14.45) — sem normalizar isso, uma linha
        # reexibida ou a última linha usada saem com altura diferente das
        # demais, mesmo com a borda já uniformizada.
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
    caminho_template = os.path.join(base_dir, "templates", "Template_Linearizacao.xlsx")

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
    # Sempre 7 dígitos significativos (completa com zeros se o certificado
    # tiver menos) — K-Factor não tem uma casa decimal fixa como os demais
    # campos, é significância que importa, não posição decimal.
    fator_k = dados.get("fator_k", 0.0)
    ws[C["fator_k"]] = fator_k
    ws[C["fator_k"]].number_format = _formato_significativos(fator_k)

    # ── Títulos de coluna (unidade real do certificado, sem conversão) ────
    ws[C["titulo_vazao"]]   = f"Vazão da Calibração ({dados.get('vazao_unidade') or 'm³/h'})"
    ws[C["titulo_vol_ref"]] = f"Volume de Referência ({dados.get('vol_referencia_unidade') or 'L'})"
    ws[C["titulo_vol_med"]] = f"Volume do Medidor ({dados.get('vol_medidor_unidade') or 'L'})"

    # ── Tabela de calibração ────────────────────────────────────────────
    # Frequência (E) e Status (S) são fórmulas do template — calculadas a
    # partir do que escrevemos aqui, não tocar. K-Factor Corrigido (O) também
    # é fórmula, mas tem o ROUND()/formato reescritos por linha logo abaixo
    # (ver comentário junto à escrita da coluna O).
    pontos = dados.get("pontos", [])
    linha_ini = C["tabela_linha_ini"]
    max_pontos = C["tabela_linha_fim"] - linha_ini + 1
    if len(pontos) > max_pontos:
        raise ValueError(
            f"Template de linearização suporta no máximo {max_pontos} pontos "
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

        # K-Factor Corrigido (O) = fator_k / meter_factor — mesmos operandos
        # da fórmula do template, só recalculados aqui pra saber com quantas
        # casas arredondar (regra dos 7 dígitos significativos). Mantém como
        # fórmula (não como valor estático) pra continuar recalculando sozinho
        # se o usuário editar D19/K{row} manualmente no Excel depois.
        meter_factor = p["meter_factor"]
        try:
            kfc_estimado = fator_k / meter_factor
        except ZeroDivisionError:
            kfc_estimado = 0
        casas_kfc = _casas_significativas(kfc_estimado)
        col_kfc = C["col_kfc"]
        col_mf = C["col_mf"]

        cel_kfc = ws[_celula(col_kfc, row)]
        cel_kfc.value = f'=IFERROR(ROUND($D$19/{col_mf}{row},{casas_kfc}),"")'
        cel_kfc.number_format = _formato_decimal(casas_kfc)
        kfc_estimados.append(round(kfc_estimado, casas_kfc))

        # Espelho na tabela "Dados a Serem Configurados" (col. L = "=IF(O.."):
        # mesma fórmula/valor, só precisa do formato acompanhando o de cima.
        ws[f"L{row + TABELA2_OFFSET}"].number_format = _formato_decimal(casas_kfc)

    # KF médio (L76, "=AVERAGE(...)" do template) tinha formato fixo em 5
    # casas — pra um K-Factor de ordem de grandeza maior (ex.: Coriolis
    # ~20000 pulsos/m³) isso estourava bem além de 7 dígitos (ex.:
    # "19970,57000"). Só o formato é ajustado aqui (valor continua a fórmula
    # do template) — a média em Python usa os mesmos K-Factor Corrigidos já
    # escritos na coluna O, então tem a mesma ordem de grandeza do resultado real.
    if kfc_estimados:
        media_kfc = sum(kfc_estimados) / len(kfc_estimados)
        ws[C["kf_medio"]].number_format = _formato_significativos(media_kfc)

    # O template só vem com as 10 primeiras linhas de cada tabela visíveis e
    # com borda "normal" (linhas 22-31 e seu espelho 56-65 em "Dados a Serem
    # Configurados"); as próximas 10 (32-41 / 66-75) ficam ocultas por
    # padrão — reexibe/oculta conforme o nº de pontos deste certificado e
    # uniformiza a borda (senão as linhas reexibidas saem com um contorno
    # mais grosso, herdado do estilo delas quando ocultas).
    _ajustar_linhas_tabela(ws, C["tabela_linha_ini"], C["tabela_linha_fim"], len(pontos))

    # ── Assinaturas (Elaborado por / Verificado por) ───────────────────────
    # Data sempre atualizada para hoje (o template vem com uma data de
    # exemplo fixa); a data de "Verificado por" (N98) já é a fórmula "=F98"
    # no próprio template, então acompanha sozinha — não escrever nela.
    # Os nomes só são sobrescritos se o usuário optou por alterar no prompt
    # (PdfProcessingService._processar_xml_ft); senão ficam com o padrão já
    # preenchido no template (ver ler_nomes_assinatura).
    ws[C["elaborado_data"]] = datetime.now()
    if dados.get("elaborado_por"):
        ws[C["elaborado_nome"]] = dados["elaborado_por"]
    if dados.get("verificado_por"):
        ws[C["verificado_nome"]] = dados["verificado_por"]

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