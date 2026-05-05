import openpyxl
from importer.validador import validar_linha
from data.utils_db import (
    inserir_instrumento, inserir_placa,
    atualizar_sn, atualizar_sn_sensor, atualizar_range, atualizar_sn_placa,
)

COLUNAS_OBRIGATORIAS = {"tag", "sn_instrumento", "tipo"}


def ler_xlsx(caminho_xlsx):
    """
    Lê o xlsx e retorna o resultado categorizado sem escrever no banco.

    Returns:
        dict com listas: inserir, mantido, divergente, bloqueado, aviso
    """
    try:
        wb = openpyxl.load_workbook(caminho_xlsx, data_only=True)
        ws = wb.active
    except Exception as e:
        raise ValueError(f"Erro ao abrir o arquivo: {e}")

    headers = [str(c.value).strip().lower() if c.value else "" for c in ws[1]]
    faltando = COLUNAS_OBRIGATORIAS - set(headers)
    if faltando:
        raise ValueError(f"Colunas obrigatórias ausentes no xlsx: {', '.join(sorted(faltando))}")

    idx = {h: i for i, h in enumerate(headers)}

    def get(row, col):
        i = idx.get(col)
        if i is None:
            return None
        v = row[i].value
        return str(v).strip() if v is not None else None

    resultado = {"inserir": [], "mantido": [], "divergente": [], "bloqueado": [], "aviso": []}

    for n, row in enumerate(ws.iter_rows(min_row=3), start=3):
        if all(c.value is None for c in row):
            continue

        tag  = (get(row, "tag") or "").upper()
        sn   = get(row, "sn_instrumento")
        tipo = (get(row, "tipo") or "").upper()
        sn_sensor = get(row, "sn_sensor")
        min_raw   = get(row, "min_range")
        max_raw   = get(row, "max_range")

        categoria, payload = validar_linha(n, tag, sn, tipo, sn_sensor, min_raw, max_raw)
        resultado[categoria].append(payload)

    return resultado


def executar(resultado, sobrescrever):
    """
    Persiste no banco os registros válidos.

    Args:
        resultado   : dict retornado por ler_xlsx
        sobrescrever: lista de itens de resultado['divergente'] confirmados pelo usuário
    """
    for item in resultado["inserir"]:
        if item["tipo"] == "PO":
            inserir_placa(item["tag"], item["sn"])
        else:
            inserir_instrumento(
                item["tag"], item["sn"],
                item.get("sn_sensor"),
                item.get("min_range"),
                item.get("max_range"),
            )

    for item in sobrescrever:
        if item["tipo"] == "PO":
            atualizar_sn_placa(item["tag"], item["sn"])
        else:
            atualizar_sn(item["tag"], item["sn"])
            if item.get("sn_sensor") is not None:
                atualizar_sn_sensor(item["tag"], item["sn_sensor"])
            if item.get("min_range") is not None and item.get("max_range") is not None:
                atualizar_range(item["tag"], item["min_range"], item["max_range"])
