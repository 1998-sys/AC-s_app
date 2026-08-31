# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : importer.importador
# Created       : 04-05-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Reads an xlsx spreadsheet, categorizes each row against the instrument registry, and persists the accepted rows to the database.
#                 Lê uma planilha xlsx, categoriza cada linha em relação ao cadastro de instrumentos e grava no banco as linhas aceitas.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import openpyxl
from collections import defaultdict
from importer.validador import validar_linha
from data.utils_db import (
    inserir_instrumento, inserir_placa,
    atualizar_sn, atualizar_sn_sensor, atualizar_range, atualizar_sn_placa,
    atualizar_campos_extras,
)

COLUNAS_OBRIGATORIAS = {"tag", "sn_instrumento", "tipo"}

_SUFIXOS_PRESSAO = {"PT", "DPT", "PDT"}
_SUFIXOS_TEMP    = {"TT"}


def _segmentos(tag):
    return {s.upper() for s in tag.split("-")}


def _e_grupo_mvs(tags):
    todos = set()
    for t in tags:
        todos |= _segmentos(t)
    return bool(todos & _SUFIXOS_PRESSAO) and bool(todos & _SUFIXOS_TEMP)


def _resolver_mvs(resultado):
    """
    Analisa mvs_candidato e resolve automaticamente os grupos onde o padrão de
    sufixo de TAG indica um MVS (pressão + temperatura no mesmo NS).
    Os demais permanecem em mvs_candidato para confirmação manual.
    """
    grupos = defaultdict(list)
    for item in resultado["mvs_candidato"]:
        grupos[item["sn"]].append(item)

    nao_auto = []
    for sn, itens in grupos.items():
        todas_tags = {i["tag"] for i in itens} | {i["tag_existente"] for i in itens}
        if _e_grupo_mvs(todas_tags):
            for item in itens:
                item["tipo"] = "MVS"
                resultado["inserir"].append(item)
        else:
            nao_auto.extend(itens)

    resultado["mvs_candidato"] = nao_auto


def ler_xlsx(caminho_xlsx):
    """
    Lê o xlsx e retorna o resultado categorizado sem escrever no banco.

    Returns:
        dict com listas: inserir, mantido, divergente, bloqueado, aviso, mvs_candidato
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

    resultado = {"inserir": [], "mantido": [], "divergente": [], "bloqueado": [], "aviso": [], "mvs_candidato": []}

    for n, row in enumerate(ws.iter_rows(min_row=3), start=3):
        if all(c.value is None for c in row):
            continue

        tag  = (get(row, "tag") or "").upper()
        sn   = get(row, "sn_instrumento")
        tipo = (get(row, "tipo") or "").upper()
        sn_sensor = get(row, "sn_sensor")
        min_raw   = get(row, "min_range")
        max_raw   = get(row, "max_range")
        sistema   = get(row, "sistema")
        aplicacao = get(row, "aplicação") or get(row, "aplicacao")
        ativo     = get(row, "ativo")

        categoria, payload = validar_linha(
            n, tag, sn, tipo, sn_sensor, min_raw, max_raw,
            sistema, aplicacao, ativo,
        )
        resultado[categoria].append(payload)

    _resolver_mvs(resultado)
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
            inserir_placa(
                item["tag"], item["sn"],
                item.get("sistema"), item.get("aplicacao"), item.get("ativo"),
            )
        else:
            inserir_instrumento(
                item["tag"], item["sn"],
                item.get("sn_sensor"),
                item.get("min_range"),
                item.get("max_range"),
                item.get("sistema"),
                item.get("aplicacao"),
                item.get("ativo"),
                tipo=item["tipo"],
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
        atualizar_campos_extras(
            item["tag"],
            item.get("sistema"), item.get("aplicacao"), item.get("ativo"),
        )
