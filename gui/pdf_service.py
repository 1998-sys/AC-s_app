import base64
import json
import os
import tempfile
import traceback
from pathlib import Path
from threading import Thread

from pdf.utils_parser import select_extract
from xml_model.xml_uc_generator import gerar_xml_uc
from xml_model.xml_cromato import xml_cromatografia

from gui.support import CHECKLIST_ALL, foto_instrumento


class PdfProcessingService:
    """Classifica o PDF/XML selecionado e decide o que fazer com ele:
    gerar um XML diretamente (cromatografia, incerteza) ou encaminhar para o
    Dispatcher/ProcessorFactory (secundário, placa de orifício, trecho reto).
    """

    def __init__(self, api):
        self.api = api
        self._cancelado = False

        # Tipos que geram XML diretamente a partir do PDF, sem passar pela tela
        # de revisão — diferente dos tipos despachados via Dispatcher/ProcessorFactory.
        # Adicionar um novo tipo aqui não exige editar _processar_pdf_thread.
        self._geradores_diretos = {
            "cromatografia": self._gerar_cromatografia,
            "ci": self._gerar_incerteza,
        }

    def escolher_arquivos_pdf(self):
        """Abre o diálogo de arquivo (permitindo selecionar um ou vários
        certificados) e retorna a lista de {caminho, nome} escolhidos, sem
        iniciar o processamento (fluxo de 2 passos: escolher arquivo(s) ->
        clicar em "Ler certificado")."""
        caminhos = self.api.escolher_arquivos(
            "Selecionar certificado(s)",
            ("PDF e XML (*.pdf;*.xml)", "PDF (*.pdf)", "XML (*.xml)"),
        )
        return [{"caminho": c, "nome": os.path.basename(c)} for c in caminhos]

    def receber_arquivos_soltos(self, arquivos):
        """Recebe arquivos soltos (drag-and-drop) na tela de seleção.

        O navegador não dá acesso ao caminho real do arquivo no disco por
        segurança (a API padrão de drag-and-drop só expõe o conteúdo) — o JS
        lê cada arquivo como base64 e manda aqui pra ser salvo numa pasta
        temporária, devolvendo a mesma estrutura {caminho, nome} de
        `escolher_arquivos_pdf`, pra reusar o fluxo existente sem duplicação.

        `arquivos` é uma lista de {"nome": str, "conteudo_base64": str}.
        """
        pasta = Path(tempfile.gettempdir()) / "certiflow_drop"
        pasta.mkdir(parents=True, exist_ok=True)

        resultado = []
        for arquivo in arquivos:
            nome = os.path.basename(arquivo["nome"])
            caminho = pasta / nome
            caminho.write_bytes(base64.b64decode(arquivo["conteudo_base64"]))
            resultado.append({"caminho": str(caminho), "nome": nome})
        return resultado

    def iniciar_leitura(self, itens):
        """Inicia em background o processamento da fila de arquivos já
        escolhidos (`itens` é sempre uma lista de {caminho, nome}, mesmo pra
        um único arquivo). O modo lote ativa automaticamente quando há mais
        de um item: a fila avança sozinha após cada arquivo (sucesso ou
        erro) até processar todos — ver `em_lote_ativo`/`avancar_fila`/
        `avancar_apos_sucesso_revisao`, acionados via
        `DialogBridge.voltar_para_selecao`/`RevisionService.confirmar_geracao`."""
        self._cancelado = False
        self.api.fila_processamento = list(itens)
        self.api.indice_fila = 0
        self.api.resultados_lote = []
        self.api.eventos_lote = []
        self._processar_item_da_fila()

    def _processar_item_da_fila(self):
        item = self.api.fila_processamento[self.api.indice_fila]
        caminho = item["caminho"]
        self.api.caminho_pdf_atual = caminho
        total = len(self.api.fila_processamento)
        if total > 1:
            self.api._js(f"App.setFilaProgresso({self.api.indice_fila + 1}, {total})")
        Thread(target=self._processar_pdf_thread, args=(caminho,), daemon=True).start()

    def cancelar_leitura(self):
        """Cancelamento cooperativo: não interrompe a extração do PDF já em
        andamento (bibliotecas de parsing não são interrompíveis com segurança),
        mas impede a thread de avançar pra tela de revisão/saída assim que o
        próximo ponto de checagem for alcançado. Também encerra a fila (um
        cancelamento explícito do usuário aborta o lote inteiro, não só o
        arquivo atual)."""
        self._cancelado = True
        self.api.fila_processamento = []
        self.api.indice_fila = 0

    # ---------- Fila / modo lote ----------
    # Dois pontos de entrada cobrem toda saída possível de um item da fila:
    # `avancar_fila` (via DialogBridge.voltar_para_selecao — erro, cancelamento
    # ou os tipos de geração direta como cromatografia/incerteza/linearização)
    # e `avancar_apos_sucesso_revisao` (via RevisionService.confirmar_geracao,
    # o caminho SEC/PO/TR que passa pela tela de revisão).

    def em_lote_ativo(self):
        return (
            len(self.api.fila_processamento) > 1
            and self.api.indice_fila < len(self.api.fila_processamento)
            and not self._cancelado
        )

    def registrar_evento_lote(self, titulo, mensagem, variant):
        """Chamado por DialogBridge.alert no lugar de exibir o alerta, quando
        em modo lote — evita que cada sucesso/erro pare a fila esperando o
        usuário clicar OK."""
        self.api.eventos_lote.append({
            "nome": os.path.basename(self.api.caminho_pdf_atual or ""),
            "titulo": titulo,
            "mensagem": mensagem,
            "ok": variant in ("success", "info"),
        })

    def avancar_fila(self):
        """Chamado por DialogBridge.voltar_para_selecao no lugar da navegação
        padrão. Retorna True se assumiu a navegação (avançou pro próximo item
        ou finalizou o lote exibindo a tela agregada); False se não havia
        lote ativo (fluxo de um único arquivo, comportamento inalterado)."""
        if not self.em_lote_ativo():
            return False

        self.api.indice_fila += 1
        total = len(self.api.fila_processamento)
        if self.api.indice_fila < total:
            self._processar_item_da_fila()
            return True

        if self.api.resultados_lote or self.api.eventos_lote:
            payload = self._finalizar_lote()
            self.api._js(f"App.showOutputLote({json.dumps(payload)})")
        else:
            self.api.fila_processamento = []
        return True

    def avancar_apos_sucesso_revisao(self, item_resultado):
        """Chamado por RevisionService.confirmar_geracao quando a AC de um
        item da fila é gerada com sucesso. Retorna o payload que
        confirmar_geracao deve devolver pro front: um marcador de avanço (se
        ainda há itens na fila) ou o payload agregado final."""
        self.api.resultados_lote.append(item_resultado)
        self.api.indice_fila += 1
        total = len(self.api.fila_processamento)
        if self.api.indice_fila < total and not self._cancelado:
            self._processar_item_da_fila()
            return {"avancando_lote": True, "item": item_resultado}
        return self._finalizar_lote()

    def _finalizar_lote(self):
        itens = self.api.resultados_lote
        eventos = self.api.eventos_lote
        total_arquivos = sum(len(it.get("files", [])) for it in itens)
        falhas = sum(1 for e in eventos if not e["ok"])

        partes_sub = [f"{len(itens)} instrumento{'s' if len(itens) != 1 else ''} processado{'s' if len(itens) != 1 else ''}"]
        if falhas:
            partes_sub.append(f"{falhas} falha{'s' if falhas != 1 else ''}")

        payload = {
            "lote": True,
            "itens": itens,
            "eventos": eventos,
            "sub": " · ".join(partes_sub) + " · atestados em PDF e XML da ANP",
            "total_arquivos": total_arquivos,
        }

        self.api.fila_processamento = []
        self.api.indice_fila = 0
        self.api.resultados_lote = []
        self.api.eventos_lote = []
        return payload

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
            self.api._voltar_para_selecao()
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
            if self._cancelado:
                self.api._voltar_para_selecao()
                return

            resumo = self._resumo_instrumento(dados_pdf)
            if resumo:
                self.api._js(f"App.showReadingInstrument({json.dumps(resumo)})")

            self.api._progress(35, "compare", ["extract"])

            gerador_direto = self._geradores_diretos.get(tipo)
            if gerador_direto:
                gerador_direto(caminho, dados_pdf)
                return

            self.api.dispatcher.dispatch(tipo, caminho, dados_pdf)

        except Exception as e:
            traceback.print_exc()
            self.api.alert("Erro no PDF", str(e), "error")
            self.api._voltar_para_selecao()

    def _resumo_instrumento(self, dados_pdf):
        """Monta o payload de resumo (foto/badge/campos) mostrado assim que o
        instrumento é identificado, ainda na tela de leitura — antes da
        revisão. Retorna None para tipos sem TAG de instrumento (ex.:
        cromatografia)."""
        tag = dados_pdf.get("tag")
        if not tag:
            return None

        min_range = dados_pdf.get("min_range")
        max_range = dados_pdf.get("max_range")
        faixa = f"{min_range} – {max_range}" if min_range is not None or max_range is not None else None

        return {
            "tag": tag,
            "badge": tag.split("-")[0],
            "photo": foto_instrumento(tag),
            "fields": [
                {"label": "TAG", "value": tag},
                {"label": "SN", "value": dados_pdf.get("sn_instrumento")},
                {"label": "Faixa calibrada", "value": faixa},
            ],
        }

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
                self.api.alert(
                    "XML não suportado",
                    "Este XML não é um certificado de calibração de medidor de vazão.\n"
                    "Tipo esperado: CERTIFICADO_CALIBRACAO_EXTERNA_MEDIDOR_VAZAO",
                    "error",
                )
                self.api._voltar_para_selecao()
                return

            dados = extrair_dados_ft(caminho)
            if self._cancelado:
                self.api._voltar_para_selecao()
                return
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
            self.api.alert("Erro no XML", str(e), "error")
            self.api._voltar_para_selecao()
