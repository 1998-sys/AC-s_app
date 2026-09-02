# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : importer.relatorio
# Created       : 04-05-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Generates a text report listing the rows from a bulk import that were blocked, warned or skipped.
#                 Gera um relatório em texto listando as linhas de uma importação em massa que foram bloqueadas, geraram aviso ou foram puladas.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import os
from datetime import datetime

from data.utils_fs import pasta_documentos


def gerar(resultado, pulados, caminho_xlsx):
    """Generates the import report .txt file under Documents/AC's Generator/Relatórios/.

    Includes only the items that need attention: blocked, warnings and skipped. If there
    is nothing to report, no file is created.

    Args:
        resultado: dict returned by `ler_xlsx`, with the keys "bloqueado" and "aviso".
        pulados: list of items with divergent SN that were kept in the database (not overwritten).
        caminho_xlsx: path of the original xlsx, used to name the report file.

    Returns:
        str: absolute path of the generated .txt, or None if there is nothing to report.
    """
    bloqueados = resultado["bloqueado"]
    avisos     = resultado["aviso"]

    if not bloqueados and not avisos and not pulados:
        return None

    pasta = pasta_documentos("AC's Generator/Relatórios")
    nome  = os.path.splitext(os.path.basename(caminho_xlsx))[0]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho_txt = str(pasta / f"{nome}_relatorio_{stamp}.txt")

    linhas = [
        "=== RELATÓRIO DE IMPORTAÇÃO ===",
        f"Arquivo : {os.path.basename(caminho_xlsx)}",
        f"Data    : {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
    ]

    def secao(titulo, itens, fmt):
        """Appends to `linhas` a "[titulo]" block with one line formatted by `fmt` per item; does nothing if `itens` is empty."""
        if not itens:
            return
        linhas.append(f"[{titulo}]")
        for item in itens:
            linhas.append(fmt(item))
        linhas.append("")

    secao(
        "BLOQUEADOS",
        bloqueados,
        lambda i: f"  Linha {i['linha']:>4} | TAG: {i['tag']:<20} | NS: {i['sn']:<25} | {i['motivo']}",
    )
    secao(
        "LINHAS IGNORADAS",
        avisos,
        lambda i: f"  Linha {i['linha']:>4} | TAG: {i['tag']:<20} | NS: {i['sn']:<25} | {i['motivo']}",
    )
    secao(
        "PULADOS (NS divergente mantido no banco)",
        pulados,
        lambda i: f"  Linha {i['linha']:>4} | TAG: {i['tag']:<20} | NS banco: {i['sn_banco']:<20} | NS xlsx ignorado: {i['sn']}",
    )

    with open(caminho_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))

    return caminho_txt
