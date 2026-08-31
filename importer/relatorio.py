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
    """
    Gera o arquivo .txt de relatório em Documentos/AC's Generator/Relatórios/.
    Inclui apenas os itens que precisam de atenção: bloqueados, avisos e pulados.

    Returns:
        str: caminho absoluto do .txt gerado, ou None se não houver nada a reportar
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
