import openpyxl
from openpyxl.styles import PatternFill, Alignment
import win32com.client as win32
import os
from datetime import datetime


# ── MAPA DE CÉLULAS ─────────────────────────────────────────────────────────
# Confirmar endereços abrindo Template_Linearizacao.xlsx e clicando nas células
CELLS = {
    # Cabeçalho esquerda (col B = rótulo, col C = valor)
    "cliente":         "C9",
    "instalacao":      "C10",
    "tag_sistema":     "C11",
    "aplicacao":       "C12",
    "sistema":         "C13",
    "data_calibracao": "C14",
    "tipo_medidor":    "C15",
    # Cabeçalho direita (col K = rótulo, col L = valor)
    "num_certificado": "L9",
    "modelo":          "L10",
    "fabricante":      "L11",
    "tag":             "L12",
    "num_serie":       "L13",
    "diametro":        "L14",
    "faixa_calibrada": "L15",
    # K-Factor nominal
    "fator_k":         "D19",
    # Tabela de calibração — colunas (escrever na top-left da célula mesclada)
    "tabela_linha_ini": 22,
    "col_vazao":       "B",
    "col_freq":        "D",
    "col_vol_ref":     "F",
    "col_vol_med":     "H",
    "col_mf":          "J",
    "col_erro":        "L",
    "col_kfc":         "N",
    "col_incerteza":   "O",
    "col_status":      "R",
    # Segunda tabela "Dados à Serem Configurados"
    "tab2_linha_ini":  53,   # TODO: confirmar linha
    "col2_num":        "C",
    "col2_vazao":      "D",
    "col2_freq":       "F",
    "col2_kfc":        "H",  # TODO: confirmar coluna
    # KF médio e alarmes
    "kf_medio":        "H64",  # TODO: confirmar
    "alarme_baixo":    "D68",  # TODO: confirmar
    "alarme_alto":     "H68",  # TODO: confirmar
}

_FILL_APROVADO  = PatternFill("solid", fgColor="00B050")
_FILL_REPROVADO = PatternFill("solid", fgColor="D81F3C")
_ALIGN_CENTER   = Alignment(horizontal="center", vertical="center")


def _data_br(data_iso: str) -> str:
    """'2026-04-25' → '25/04/2026'"""
    try:
        return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return data_iso


def _cliente_do_caminho(caminho: str) -> str:
    """Extrai o nome do cliente do path do arquivo (ex: .../PRIO/... → 'PRIO')."""
    partes = caminho.upper().replace("\\", "/").split("/")
    for p in partes:
        for cliente in ("PRIO", "YINSON", "ORIGEM", "SBM", "PETROBRAS"):
            if cliente in p:
                return cliente
    return ""


def _contexto_db(tag: str):
    """Busca aplicacao e sistema no banco de dados pelo TAG."""
    try:
        from data.utils_db import buscar_instrumento_por_tag
        inst = buscar_instrumento_por_tag(tag)
        if inst:
            return inst.get("aplicacao") or "", inst.get("sistema") or ""
    except Exception:
        pass
    return "", ""


def _celula(col: str, linha: int) -> str:
    return f"{col}{linha}"


def gerar_linearizacao(dados: dict, caminho_xml: str) -> str:
    """
    Preenche Template_Linearizacao.xlsx com os dados do medidor de vazão e
    exporta XLSX + PDF na mesma pasta do XML de entrada.
    Retorna o caminho do XLSX gerado.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    caminho_template = os.path.join(base_dir, "Template_Linearizacao.xlsx")

    wb = openpyxl.load_workbook(caminho_template)
    ws = wb.active

    C = CELLS  # atalho

    # ── Cabeçalho esquerda ────────────────────────────────────────────────
    cliente = _cliente_do_caminho(caminho_xml)
    aplicacao, sistema = _contexto_db(dados.get("tag", ""))

    ws[C["cliente"]]         = cliente
    ws[C["instalacao"]]      = dados.get("unidade_operacional", "")
    ws[C["tag_sistema"]]     = dados.get("tag", "")
    ws[C["aplicacao"]]       = aplicacao
    ws[C["sistema"]]         = sistema
    ws[C["data_calibracao"]] = _data_br(dados.get("data_calibracao", ""))
    ws[C["tipo_medidor"]]    = dados.get("tipo", "")

    # ── Cabeçalho direita ─────────────────────────────────────────────────
    ws[C["num_certificado"]] = dados.get("numero_certificado", "")
    ws[C["modelo"]]          = dados.get("modelo", "")
    ws[C["fabricante"]]      = dados.get("fabricante", "")
    ws[C["tag"]]             = dados.get("tag", "")
    ws[C["num_serie"]]       = dados.get("num_serie", "")
    ws[C["diametro"]]        = dados.get("diametro", "")
    ws[C["faixa_calibrada"]] = dados.get("faixa_calibrada", "")

    # ── K-Factor nominal ──────────────────────────────────────────────────
    ws[C["fator_k"]] = dados.get("fator_k", "")

    # ── Tabela de calibração (10 pontos) ──────────────────────────────────
    pontos = dados.get("pontos", [])
    linha_ini = C["tabela_linha_ini"]

    for i, p in enumerate(pontos):
        row = linha_ini + i

        ws[_celula(C["col_vazao"],    row)] = p["vazao"]
        ws[_celula(C["col_freq"],     row)] = p["frequencia"]
        ws[_celula(C["col_vol_ref"],  row)] = p["vol_referencia_l"]
        ws[_celula(C["col_vol_med"],  row)] = p["vol_medidor_l"]
        ws[_celula(C["col_mf"],       row)] = p["meter_factor"]
        ws[_celula(C["col_erro"],     row)] = p["erro_pct"]
        ws[_celula(C["col_kfc"],      row)] = p["kfc"]
        ws[_celula(C["col_incerteza"],row)] = p["incerteza"]

        status_cell = ws[_celula(C["col_status"], row)]
        status_cell.value     = p["status"]
        status_cell.fill      = _FILL_APROVADO if p["status"] == "APROVADO" else _FILL_REPROVADO
        status_cell.alignment = _ALIGN_CENTER

    # ── Segunda tabela "Dados à Serem Configurados" ───────────────────────
    linha2 = C["tab2_linha_ini"]

    for i, p in enumerate(pontos):
        row = linha2 + i
        ws[_celula(C["col2_num"],   row)] = i + 1
        ws[_celula(C["col2_vazao"], row)] = p["vazao"]
        ws[_celula(C["col2_freq"],  row)] = p["frequencia"]
        ws[_celula(C["col2_kfc"],   row)] = p["kfc"]

    # KF médio
    ws[C["kf_medio"]] = dados.get("kf_medio", "")

    # ── Limites de alarme (faixa nominal = limites de alarme) ─────────────
    ws[C["alarme_baixo"]] = dados.get("faixa_min", "")
    ws[C["alarme_alto"]]  = dados.get("faixa_max", "")

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
        wb_excel.ExportAsFixedFormat(0, caminho_pdf)
        wb_excel.Close(SaveChanges=False)
    finally:
        excel.Quit()

    return caminho_xlsx