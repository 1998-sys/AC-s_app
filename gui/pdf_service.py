# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : gui.pdf_service
# Created       : 24-08-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Orchestrates the certificate reading queue, classifying each PDF/XML and routing it to direct XML generation or to the Dispatcher.
#                 Orquestra a fila de leitura de certificados, classificando cada PDF/XML e encaminhando para geração direta de XML ou para o Dispatcher.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import base64
import json
import os
import time
import traceback
from threading import Thread

from pdf.utils_parser import select_extract
from xml_model.xml_uc_generator import gerar_xml_uc
from xml_model.xml_cromato import xml_cromatografia

from data.utils_fs import pasta_documentos
from gui.support import CHECKLIST_ALL, PASTA_CERTIFICADOS_SOLTOS, foto_instrumento, limpar_certificado_solto


class PdfProcessingService:
    """Classifica o PDF/XML selecionado e decide o que fazer com ele:
    gerar um XML diretamente (cromatografia, incerteza) ou encaminhar para o
    Dispatcher/ProcessorFactory (secundário, placa de orifício, trecho reto).
    """

    # Tempo mínimo (segundos) que cada certificado do lote fica visível na
    # tela de leitura antes de trocar pro próximo — dá sensação de progresso
    # contínuo em vez de um flash entre telas quando a extração é rápida.
    TEMPO_MINIMO_POR_ITEM = 2.0

    def __init__(self, api):
        """Initializes cancellation state, the session's "Related Items" cache, and the map of types with direct XML generation."""
        self.api = api
        self._cancelado = False
        self._inicio_item_ts = None

        # Cache de "Itens Relacionados" da Origem (ex.: LDN-030.pdf) pra essa
        # sessão de leitura — ver dados_origem_automaticos. Resetado a cada
        # iniciar_leitura pra não vazar de uma sessão de leitura pra outra.
        self._itens_relacionados_cache = {}
        self._itens_relacionados_perguntado = False

        # Tipos que geram XML diretamente a partir do PDF, sem passar pela tela
        # de revisão — diferente dos tipos despachados via Dispatcher/ProcessorFactory.
        # Adicionar um novo tipo aqui não exige editar _processar_pdf_thread.
        # ("cromatografia" tem checklist/saída próprios — interceptado antes
        # desse dict em _processar_pdf_thread, ver _gerar_cromatografia.)
        self._geradores_diretos = {
            "ci": self._gerar_incerteza,
        }

    def escolher_arquivos_pdf(self):
        """Opens the file dialog to choose one or more certificates, without starting processing.

        Returns:
            List of `{"caminho": str, "nome": str}` dicts in the chosen order
            (empty if the user cancelled).

        Notes:
            2-step flow: choose file(s) -> click "Ler certificado" (which
            calls `iniciar_leitura`).
        """
        caminhos = self.api.escolher_arquivos(
            "Selecionar certificado(s)",
            ("PDF e XML (*.pdf;*.xml)", "PDF (*.pdf)", "XML (*.xml)"),
        )
        return [{"caminho": c, "nome": os.path.basename(c)} for c in caminhos]

    def receber_arquivos_soltos(self, arquivos):
        """Saves loose (drag-and-drop) files from the selection screen to disk and returns their paths.

        Args:
            arquivos: list of `{"nome": str, "conteudo_base64": str}` coming from the JS side.

        Returns:
            List of `{"caminho": str, "nome": str}` dicts, in the same
            structure as `escolher_arquivos_pdf`, to reuse the existing
            flow without duplication.

        Notes:
            The browser doesn't give access to the file's real path on disk
            for security reasons (the standard drag-and-drop API only
            exposes the content) — so the JS reads each file as base64 and
            sends it here to be saved to disk. It saves to the Documents
            folder (`PASTA_CERTIFICADOS_SOLTOS`), not a temp folder: the
            generated report/XML always goes to the same folder as the
            source certificate (`obter_caminho_ac`), so using a temp folder
            here would make the generated files land there too — a place
            Windows can clean up on its own and that nobody would think to
            look for them in.
        """
        pasta = pasta_documentos(PASTA_CERTIFICADOS_SOLTOS)

        resultado = []
        for arquivo in arquivos:
            nome = os.path.basename(arquivo["nome"])
            caminho = pasta / nome
            caminho.write_bytes(base64.b64decode(arquivo["conteudo_base64"]))
            resultado.append({"caminho": str(caminho), "nome": nome})
        return resultado

    def iniciar_leitura(self, itens):
        """Resets the queue state and dispatches the first file's processing in the background.

        Args:
            itens: list of `{"caminho": str, "nome": str}` already chosen,
                even for a single file.

        Notes:
            Batch mode activates automatically when there's more than one
            item: the queue advances on its own after each file (success or
            error) until all are processed — see `em_lote_ativo`/
            `avancar_fila`, triggered via `DialogBridge.voltar_para_selecao`/
            `RevisionService.confirmar_geracao`.
        """
        self._cancelado = False
        self.api.fila_processamento = list(itens)
        self.api.indice_fila = 0
        self.api.resultados_lote = []
        self.api.eventos_lote = []
        self.api.instrumentos_lote = []
        self._itens_relacionados_cache = {}
        self._itens_relacionados_perguntado = False
        self._processar_item_da_fila()

    def _processar_item_da_fila(self):
        """Marks the start of processing for the current queue item, updates the UI progress, and dispatches the reading thread."""
        self._inicio_item_ts = time.time()
        item = self.api.fila_processamento[self.api.indice_fila]
        caminho = item["caminho"]
        self.api.caminho_pdf_atual = caminho
        total = len(self.api.fila_processamento)
        if total > 1:
            nome = json.dumps(item.get("nome") or os.path.basename(caminho))
            self.api._js(f"App.setFilaProgresso({self.api.indice_fila + 1}, {total}, {nome})")
        Thread(target=self._processar_pdf_thread, args=(caminho,), daemon=True).start()

    def _aguardar_tempo_minimo_item(self):
        """Sleeps for the remaining time until `TEMPO_MINIMO_POR_ITEM` has elapsed, so the item doesn't switch screens too fast for the user to notice."""
        inicio = self._inicio_item_ts
        if inicio is None:
            return
        faltam = self.TEMPO_MINIMO_POR_ITEM - (time.time() - inicio)
        if faltam > 0:
            time.sleep(faltam)

    def cancelar_leitura(self):
        """Signals cooperative cancellation of the reading and ends the whole queue.

        Notes:
            Doesn't interrupt the PDF extraction already in progress
            (parsing libraries can't be safely interrupted), but prevents
            the thread from advancing to the review/output screen once the
            next checkpoint is reached. It also ends the queue (an explicit
            user cancellation aborts the whole batch, not just the current
            file).
        """
        self._cancelado = True
        self.api.fila_processamento = []
        self.api.indice_fila = 0
        self.api.instrumentos_lote = []

    # ---------- Fila / modo lote ----------
    # Todo item da fila termina de um jeito só: `avancar_fila`, chamado via
    # DialogBridge.voltar_para_selecao — seja por erro/cancelamento, pelos
    # tipos de geração direta (cromatografia/incerteza/linearização), ou pela
    # coleta de revisão da Fase 6 (RevisionService.coletar_revisao_lote), que
    # nunca gera nada por item — só quando a fila esgota é que se decide
    # mostrar a revisão agregada, gerar tudo, ou ir direto pra saída.

    def em_lote_ativo(self):
        """Indicates whether there's a queue of more than one item in progress (not cancelled and still with a pending item).

        Returns:
            True if batch mode is active.
        """
        return (
            len(self.api.fila_processamento) > 1
            and self.api.indice_fila < len(self.api.fila_processamento)
            and not self._cancelado
        )

    def registrar_evento_lote(self, titulo, mensagem, variant, nome=None):
        """Appends an event (success/error) to the list shown on the batch output screen, instead of showing a blocking alert.

        Args:
            titulo: event title.
            mensagem: detailed event message.
            variant: "success"/"info" count as success; any other value
                counts as a failure (see `ok` in the resulting dict).
            nome: name of the file associated with the event. If omitted,
                uses `caminho_pdf_atual` (correct during reading, when that
                really is the item being processed); `gerar_lote` passes
                the explicit name, since at that point `caminho_pdf_atual`
                no longer reflects the loop's current item (all reading has
                already finished before generating any of them).

        Notes:
            Called by `DialogBridge.alert` instead of showing the alert,
            when in batch mode — prevents each success/error from stopping
            the queue waiting for the user to click OK.
        """
        self.api.eventos_lote.append({
            "nome": nome or os.path.basename(self.api.caminho_pdf_atual or ""),
            "titulo": titulo,
            "mensagem": mensagem,
            "ok": variant in ("success", "info"),
        })

    def avancar_fila(self):
        """Advances to the next item in the batch queue, or ends the queue if all items have already been processed.

        Returns:
            True if it took over navigation (advanced to the next item or
            ended the queue); False if there was no active batch
            (single-file flow, unchanged behavior — called by
            `DialogBridge.voltar_para_selecao` in place of the default
            navigation).
        """
        if not self.em_lote_ativo():
            return False

        self._aguardar_tempo_minimo_item()
        self.api.indice_fila += 1
        total = len(self.api.fila_processamento)
        if self.api.indice_fila < total:
            self._processar_item_da_fila()
            return True

        self._ao_fila_esgotada()
        return True

    def _ao_fila_esgotada(self):
        """Decides what to show after the queue has finished reading all items.

        Notes:
            - Some instrument collected (Phase 6) with a pending divergence
              -> aggregated divergences screen.
            - Instruments collected but none pending -> generates everything
              directly.
            - Nothing collected (only direct-generation/error events) ->
              output screen with whatever there is.
        """
        api = self.api
        if api.instrumentos_lote:
            tem_pendencia = any(
                any(not getattr(i, "resolved", False) for i in inst["issues"].values())
                for inst in api.instrumentos_lote
            )
            if tem_pendencia:
                payload = api._revision_service._montar_payload_divergencias_lote()
                api._js(f"App.showDivergenciasLote({json.dumps(payload)})")
            else:
                api._revision_service.gerar_lote()
            return

        if api.resultados_lote or api.eventos_lote:
            payload = self._finalizar_lote()
            api._js(f"App.showOutputLote({json.dumps(payload)})")
        else:
            api.fila_processamento = []

    def finalizar_lote_manualmente(self):
        """Public wrapper around `_finalizar_lote`.

        Notes:
            Called by `RevisionService.gerar_lote` after generating
            everything, outside the normal `avancar_fila` flow (which would
            call this on its own if the queue were still "active", but at
            this point it has already been exhausted).
        """
        return self._finalizar_lote()

    def _finalizar_lote(self):
        """Builds the batch output screen's payload (generated items, events, and summary) and clears the queue state.

        Returns:
            Dict with `lote`, `itens`, `eventos`, `sub` (text summary), and
            `total_arquivos`.
        """
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

    def dados_origem_automaticos(self, tag):
        """Looks up Location/AC No. for the TAG in an Origem "Related Items" document (e.g. LDN-030.pdf), asking the user for the file the first time.

        Args:
            tag: TAG of the instrument to look up in the document.

        Returns:
            Tuple `(n_ac, localizacao)`, or `(None, None)` if the user
            declines to use the document, cancels the selection, or the
            TAG isn't in it — `processors.utils.fluxo_origem` falls back to
            the manual prompt in that case.

        Notes:
            Asks the user, only the first time in this reading session
            (reset in `iniciar_leitura`), whether they want to include this
            document; if so, opens the file selection and builds the cache
            for the whole session (one document covers several TAGs).
        """
        if not self._itens_relacionados_perguntado:
            self._itens_relacionados_perguntado = True
            if self.api.confirm(
                "Dados complementares automáticos",
                "Deseja incluir automaticamente Localização e Nº AC a partir "
                "de um documento de Itens Relacionados (ex.: LDN)?",
            ):
                caminho = self.api.escolher_arquivo(
                    "Selecione o documento de Itens Relacionados",
                    ("PDF (*.pdf)",),
                )
                if caminho:
                    from pdf.extrator import extrair_texto
                    from pdf.parser_certificados import extrair_itens_relacionados
                    texto = extrair_texto(caminho)
                    self._itens_relacionados_cache = extrair_itens_relacionados(texto)

        from pdf.parser_certificados import buscar_item_relacionado
        return buscar_item_relacionado(self._itens_relacionados_cache, tag)

    def solicitar_dados_origem(self, dados_pdf, callback):
        """Asks the user for Location/AC No. via a prompt and continues the flow in `callback` with `dados_pdf` filled in.

        Args:
            dados_pdf: dict of data extracted from the certificate, updated
                in-place with `localizacao`/`n_ac`.
            callback: function called with `dados_pdf` after it's filled
                in; not called if the user cancels the prompt.

        Notes:
            Called when `dados_origem_automaticos` didn't find
            Location/AC No. (user didn't include the document, or the TAG
            wasn't in it).
        """
        valores = self.api.prompt(
            "Dados complementares",
            "Preencha as informações adicionais exigidas para certificados ORIGEM.",
            [
                {"name": "localizacao", "label": "Localização", "required": True},
                {"name": "n_ac", "label": "Nº AC", "required": False},
            ],
        )
        if not valores:
            self.api._voltar_para_selecao()
            return
        dados_pdf["localizacao"] = valores.get("localizacao", "")
        dados_pdf["n_ac"] = valores.get("n_ac", "")
        callback(dados_pdf)

    def _processar_pdf_thread(self, caminho):
        """Extracts and classifies the certificate (running in the background) and routes it to direct XML generation, chromatography, or the Dispatcher.

        Args:
            caminho: path of the file (PDF or XML) to process.
        """
        if caminho.lower().endswith(".xml"):
            self._processar_xml_ft(caminho)
            return

        try:
            self.api._progress(15, "extract", [])
            dados_pdf, tipo = select_extract(caminho)
            if self._cancelado:
                self.api._voltar_para_selecao()
                return

            if tipo == "cromatografia":
                # Sem comparação com cadastro nem validação de regras da ANP
                # (não há instrumento/divergência aqui) — checklist e fluxo
                # de saída próprios, ver _gerar_cromatografia.
                self._gerar_cromatografia(caminho, dados_pdf)
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
        """Builds the summary payload (photo/badge/fields) shown as soon as the instrument is identified, still on the reading screen — before review.

        Returns:
            Dict with `tag`, `badge`, `photo`, and `fields`, or None for
            types without an instrument TAG (e.g. chromatography).
        """
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
        """Generates the chromatography XML from the PDF, showing step-by-step progress, and forwards the result to output (batch or single)."""
        api = self.api
        api._js("App.setChecklistTipo('cromatografia')")
        api._progress(50, "extract", [])

        # Dá tempo do usuário ver "Extraindo texto" ativo antes de já pular
        # pro "Montando XML de cromatografia" — sem isso os dois passos
        # completam rápido demais pra perceber (mesmo motivo do sleep em
        # RevisionService.coletar_revisao_lote).
        time.sleep(2)
        if self._cancelado:
            api._voltar_para_selecao()
            return

        api._progress(75, "build", ["extract"])

        xml_path = xml_cromatografia(caminho, dados_pdf)
        limpar_certificado_solto(caminho)

        api._progress(100, "build", ["extract", "build"])
        resultado = self._montar_resultado_cromatografia(xml_path, dados_pdf)

        if self.em_lote_ativo():
            api.resultados_lote.append(resultado)
            api._voltar_para_selecao()
        else:
            payload = {"sub": resultado["sub"], "files": resultado["files"]}
            api._js(f"App.showOutput({json.dumps(payload)})")

    def _montar_resultado_cromatografia(self, xml_path, dados_pdf):
        """Builds the result dict (output card) for a generated chromatography XML.

        Returns:
            Dict with `tag`, `badge`, `sub`, `avisos`, and `files`.
        """
        tamanho = os.path.getsize(xml_path) // 1024
        titulo = dados_pdf.get("certificado") or dados_pdf.get("empresa") or "Cromatografia"
        return {
            "tag": titulo,
            "badge": "XML",
            "sub": f"{titulo} · XML de cromatografia",
            "avisos": 0,
            "files": [{
                "kind": "XML",
                "name": os.path.basename(xml_path),
                "meta": f"{tamanho} KB",
                "path": xml_path,
            }],
        }

    def _gerar_incerteza(self, caminho, dados_pdf):
        """Generates the Uncertainty (CI) XML directly from the certificate, in the same folder as the PDF, and returns to the selection screen."""
        numero_ci = dados_pdf.get("numero_ci", "NI")
        xml_path = os.path.splitext(caminho)[0] + ".xml"
        gerar_xml_uc(numero_ci, dados_pdf, xml_path)
        limpar_certificado_solto(caminho)
        self.api._progress(100, "build", CHECKLIST_ALL)
        self.api.alert("Sucesso", f"XML de Incerteza gerado:\n{xml_path}", "success")
        self.api._voltar_para_selecao()

    def _processar_xml_ft(self, caminho):
        """Validates a flow meter external calibration certificate XML, asks the user for Application/System, and generates the Linearization spreadsheet.

        Args:
            caminho: path of the XML file (CERTIFICADO_CALIBRACAO_EXTERNA_MEDIDOR_VAZAO).

        Notes:
            Application/System don't exist in the instrument registry for
            flow meters (that's only for secondary instruments) — and
            Application feeds the template's Status formula (±0.2%
            tolerance for Fiscal/Custody Transfer, ±0.6% for the rest), so
            they need to be asked from the user instead of left blank.
        """
        try:
            from xml_model.xml_extractor_FT import is_certificado_ft, extrair_dados_ft
            from form.utils_print_linearizacao import gerar_linearizacao, contexto_db

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

            # Aplicação/Sistema não existem no cadastro de instrumentos pra
            # medidor de vazão (isso é só pra instrumentos secundários) — e
            # Aplicação alimenta a fórmula de Status do template (tolerância
            # ±0,2% pra Fiscal/Transferência de Custódia, ±0,6% pros demais),
            # então precisa ser pedida ao usuário em vez de deixar em branco.
            aplicacao_padrao, sistema_padrao = contexto_db(dados.get("tag", ""))
            valores = self.api.prompt(
                "Aplicação e sistema",
                "Preencha os dados abaixo para gerar a Linearização.",
                [
                    {
                        "name": "aplicacao",
                        "label": "Aplicação",
                        "required": True,
                        "type": "select",
                        "options": ["Fiscal", "Apropriação", "Transferência de Custódia"],
                        "value": aplicacao_padrao,
                    },
                    {
                        "name": "sistema",
                        "label": "Sistema",
                        "required": False,
                        "value": sistema_padrao,
                    },
                ],
            )
            if not valores:
                self.api._voltar_para_selecao()
                return
            dados["aplicacao"] = valores.get("aplicacao", "")
            dados["sistema"] = valores.get("sistema", "")

            if self._cancelado:
                self.api._voltar_para_selecao()
                return
            self.api._progress(70, "build", ["extract", "compare", "validate"])
            caminho_saida = gerar_linearizacao(dados, caminho)
            limpar_certificado_solto(caminho)
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
