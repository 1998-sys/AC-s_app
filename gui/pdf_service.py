import os
import traceback
from threading import Thread

from pdf.utils_parser import select_extract
from xml_model.xml_uc_generator import gerar_xml_uc
from xml_model.xml_cromato import xml_cromatografia

from gui.support import CHECKLIST_ALL


class PdfProcessingService:
    """Classifica o PDF/XML selecionado e decide o que fazer com ele:
    gerar um XML diretamente (cromatografia, incerteza) ou encaminhar para o
    Dispatcher/ProcessorFactory (secundário, placa de orifício, trecho reto).
    """

    def __init__(self, api):
        self.api = api

        # Tipos que geram XML diretamente a partir do PDF, sem passar pela tela
        # de revisão — diferente dos tipos despachados via Dispatcher/ProcessorFactory.
        # Adicionar um novo tipo aqui não exige editar _processar_pdf_thread.
        self._geradores_diretos = {
            "cromatografia": self._gerar_cromatografia,
            "ci": self._gerar_incerteza,
        }

    def selecionar_pdf(self):
        caminho = self.api.escolher_arquivo(
            "Selecionar certificado",
            ("PDF e XML (*.pdf;*.xml)", "PDF (*.pdf)", "XML (*.xml)"),
        )
        if not caminho:
            return None
        self.api.caminho_pdf_atual = caminho
        Thread(target=self._processar_pdf_thread, args=(caminho,), daemon=True).start()
        return os.path.basename(caminho)

    def solicitar_dados_origem(self, dados_pdf, callback):
        valores = self.api.prompt(
            "Dados complementares",
            "Preencha as informações adicionais exigidas para certificados ORIGEM.",
            [
                {"name": "localizacao", "label": "Localização", "required": True},
                {"name": "sap", "label": "SAP", "required": False},
                {"name": "n_ac", "label": "Nº AC", "required": False},
            ],
        )
        if not valores:
            return
        dados_pdf["localizacao"] = valores.get("localizacao", "")
        dados_pdf["sap"] = valores.get("sap", "")
        dados_pdf["n_ac"] = valores.get("n_ac", "")
        callback(dados_pdf)

    def _processar_pdf_thread(self, caminho):
        if caminho.lower().endswith(".xml"):
            self._processar_xml_ft(caminho)
            return

        try:
            self.api._progress(15, "extract", [])
            dados_pdf, tipo = select_extract(caminho)
            self.api._progress(35, "compare", ["extract"])

            gerador_direto = self._geradores_diretos.get(tipo)
            if gerador_direto:
                gerador_direto(caminho, dados_pdf)
                return

            self.api.dispatcher.dispatch(tipo, caminho, dados_pdf)

        except Exception as e:
            traceback.print_exc()
            self.api._voltar_para_selecao()
            self.api.alert("Erro no PDF", str(e), "error")

    def _gerar_cromatografia(self, caminho, dados_pdf):
        xml_path = xml_cromatografia(caminho, dados_pdf)
        self.api._progress(100, "build", CHECKLIST_ALL)
        self.api.alert("Sucesso", f"XML de Cromatografia gerado:\n{xml_path}", "success")
        self.api._voltar_para_selecao()

    def _gerar_incerteza(self, caminho, dados_pdf):
        numero_ci = dados_pdf.get("numero_ci", "NI")
        xml_path = os.path.splitext(caminho)[0] + ".xml"
        gerar_xml_uc(numero_ci, dados_pdf, xml_path)
        self.api._progress(100, "build", CHECKLIST_ALL)
        self.api.alert("Sucesso", f"XML de Incerteza gerado:\n{xml_path}", "success")
        self.api._voltar_para_selecao()

    def _processar_xml_ft(self, caminho):
        try:
            from xml_model.xml_extractor_FT import is_certificado_ft, extrair_dados_ft
            from form.utils_print_linearizacao import gerar_linearizacao

            self.api._progress(30, "extract", [])
            if not is_certificado_ft(caminho):
                self.api._voltar_para_selecao()
                self.api.alert(
                    "XML não suportado",
                    "Este XML não é um certificado de calibração de medidor de vazão.\n"
                    "Tipo esperado: CERTIFICADO_CALIBRACAO_EXTERNA_MEDIDOR_VAZAO",
                    "error",
                )
                return

            dados = extrair_dados_ft(caminho)
            self.api._progress(70, "build", ["extract", "compare", "validate"])
            caminho_saida = gerar_linearizacao(dados, caminho)
            self.api._progress(100, "build", CHECKLIST_ALL)

            self.api.alert(
                "Linearização gerada",
                f"Planilha gerada com sucesso:\n{os.path.basename(caminho_saida)}",
                "success",
            )
            self.api._voltar_para_selecao()

        except Exception as e:
            traceback.print_exc()
            self.api._voltar_para_selecao()
            self.api.alert("Erro no XML", str(e), "error")
