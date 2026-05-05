import os
from datetime import datetime


def gerar(resultado, pulados, caminho_xlsx):
    """
    Gera o arquivo .txt de relatório na mesma pasta do xlsx.
    Inclui apenas os itens que precisam de atenção: bloqueados, avisos e pulados.

    Args:
        resultado   : dict retornado por importador.ler_xlsx
        pulados     : itens de divergente que o usuário optou por pular
        caminho_xlsx: caminho do arquivo de origem

    Returns:
        str: caminho absoluto do .txt gerado, ou None se não houver nada a reportar
    """
    bloqueados = resultado["bloqueado"]
    avisos     = resultado["aviso"]

    if not bloqueados and not avisos and not pulados:
        return None

    pasta = os.path.dirname(os.path.abspath(caminho_xlsx))
    nome  = os.path.splitext(os.path.basename(caminho_xlsx))[0]
    caminho_txt = os.path.join(pasta, f"{nome}_relatorio_importacao.txt")

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
