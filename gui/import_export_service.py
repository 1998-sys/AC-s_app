# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : gui.import_export_service
# Created       : 24-08-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Handles bulk import/export of the instrument database through XLSX spreadsheets.
#                 Cuida da importação/exportação em massa da base de instrumentos via planilhas XLSX.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from collections import defaultdict

from importer.importador import ler_xlsx, executar
from importer.relatorio import gerar as gerar_relatorio
from importer.exportador import exportar as exportar_xlsx_db


class ImportExportService:
    """Importação/exportação da base de instrumentos via planilha XLSX."""

    def __init__(self, api):
        """Stores the Api reference for dialogs and access to other services."""
        self.api = api

    def importar_xlsx(self):
        """Imports an instrument XLSX spreadsheet into the database, asking the user how to resolve conflicts before writing.

        Notes:
            Two kinds of conflict require manual confirmation before
            `executar`: an NS that diverges from the one already registered
            for the same TAG (asks whether to overwrite it), and an NS
            repeated across multiple rows that are candidates for the same
            MVS (asks whether the rows belong to the same MVS and legitimately
            share the NS, or whether they should be blocked). At the end, it
            generates a .txt report and shows a summary with the counts of
            inserted/overwritten/kept/problems.
        """
        api = self.api
        caminho = api.escolher_arquivo("Selecionar planilha de instrumentos", ("Excel (*.xlsx)",))
        if not caminho:
            return

        try:
            resultado = ler_xlsx(caminho)
        except ValueError as e:
            api.alert("Erro na planilha", str(e), "error")
            return

        sobrescrever = []
        pulados = []
        for item in resultado["divergente"]:
            resposta = api.confirm(
                "NS divergente",
                f"TAG: {item['tag']}\n\n"
                f"NS no banco : {item['sn_banco']}\n"
                f"NS no xlsx  : {item['sn']}\n\n"
                "Deseja sobrescrever o NS no banco?",
            )
            if resposta:
                sobrescrever.append(item)
            else:
                pulados.append(item)

        grupos_mvs = defaultdict(list)
        for item in resultado["mvs_candidato"]:
            grupos_mvs[item["sn"]].append(item)

        for sn, itens in grupos_mvs.items():
            tag_existente = itens[0]["tag_existente"]
            lista_tags = "\n".join(f"  • Linha {i['linha']} — {i['tag']}" for i in itens)
            resposta = api.confirm(
                "Instrumento MVS?",
                f"O NS '{sn}' já está cadastrado com a TAG '{tag_existente}'.\n\n"
                f"Os seguintes instrumentos do xlsx também usam esse NS:\n{lista_tags}\n\n"
                "Eles pertencem ao mesmo MVS e compartilham o NS?\n\n"
                "SIM → todos serão inseridos normalmente\n"
                "NÃO → todos serão registrados como bloqueados",
            )
            for item in itens:
                if resposta:
                    resultado["inserir"].append(item)
                else:
                    item["motivo"] = f"NS já cadastrado com TAG '{tag_existente}' — não confirmado como MVS"
                    resultado["bloqueado"].append(item)

        executar(resultado, sobrescrever)
        caminho_txt = gerar_relatorio(resultado, pulados, caminho)

        total_ins = len(resultado["inserir"])
        total_sob = len(sobrescrever)
        total_mant = len(resultado["mantido"])
        total_prob = len(resultado["bloqueado"]) + len(resultado["aviso"]) + len(pulados)

        msg = (
            f"Importação concluída.\n\n"
            f"Inseridos   : {total_ins}\n"
            f"Sobrescritos: {total_sob}\n"
            f"Mantidos    : {total_mant}\n"
            f"Problemas   : {total_prob}"
        )
        if caminho_txt:
            msg += f"\n\nRelatório gerado em:\n{caminho_txt}"

        api.alert("Importação", msg, "success")

    def exportar_xlsx(self):
        """Exports the entire instrument database to an XLSX spreadsheet and reports the generated path."""
        api = self.api
        try:
            caminho = exportar_xlsx_db()
            api.alert("Exportação concluída", f"Base de dados exportada com sucesso.\n\n{caminho}", "success")
        except Exception as e:
            api.alert("Erro na exportação", str(e), "error")
