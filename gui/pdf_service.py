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
        lê cada arquivo como base64 e manda aqui pra ser salvo em disco,
        devolvendo a mesma estrutura {caminho, nome} de
        `escolher_arquivos_pdf`, pra reusar o fluxo existente sem duplicação.

        Salva em Documentos (não numa pasta temporária): o relatório/XML
        gerado sempre vai pra mesma pasta do certificado de origem
        (`obter_caminho_ac`), então usar uma pasta temporária aqui faria os
        arquivos gerados também caírem lá — um lugar que o Windows pode
        limpar sozinho e que ninguém pensaria em procurar.

        `arquivos` é uma lista de {"nome": str, "conteudo_base64": str}.
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
        self.api.instrumentos_lote = []
        self._itens_relacionados_cache = {}
        self._itens_relacionados_perguntado = False
        self._processar_item_da_fila()

    def _processar_item_da_fila(self):
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
        inicio = self._inicio_item_ts
        if inicio is None:
            return
        faltam = self.TEMPO_MINIMO_POR_ITEM - (time.time() - inicio)
        if faltam > 0:
            time.sleep(faltam)

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
        self.api.instrumentos_lote = []

    # ---------- Fila / modo lote ----------
    # Todo item da fila termina de um jeito só: `avancar_fila`, chamado via
    # DialogBridge.voltar_para_selecao — seja por erro/cancelamento, pelos
    # tipos de geração direta (cromatografia/incerteza/linearização), ou pela
    # coleta de revisão da Fase 6 (RevisionService.coletar_revisao_lote), que
    # nunca gera nada por item — só quando a fila esgota é que se decide
    # mostrar a revisão agregada, gerar tudo, ou ir direto pra saída.

    def em_lote_ativo(self):
        return (
            len(self.api.fila_processamento) > 1
            and self.api.indice_fila < len(self.api.fila_processamento)
            and not self._cancelado
        )

    def registrar_evento_lote(self, titulo, mensagem, variant, nome=None):
        """Chamado por DialogBridge.alert no lugar de exibir o alerta, quando
        em modo lote — evita que cada sucesso/erro pare a fila esperando o
        usuário clicar OK. `nome` é opcional: por padrão usa
        `caminho_pdf_atual` (correto durante a leitura, quando esse é
        realmente o item em processamento); `gerar_lote` passa o nome
        explícito, já que ali `caminho_pdf_atual` não reflete mais o item
        do laço (a leitura de todos já terminou antes de gerar qualquer
        um)."""
        self.api.eventos_lote.append({
            "nome": nome or os.path.basename(self.api.caminho_pdf_atual or ""),
            "titulo": titulo,
            "mensagem": mensagem,
            "ok": variant in ("success", "info"),
        })

    def avancar_fila(self):
        """Chamado por DialogBridge.voltar_para_selecao no lugar da navegação
        padrão. Retorna True se assumiu a navegação (avançou pro próximo item
        ou encerrou a fila); False se não havia lote ativo (fluxo de um
        único arquivo, comportamento inalterado)."""
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
        """A fila terminou de ler todos os itens. Decide o que mostrar:
        - Algum instrumento coletado (Fase 6) com divergência pendente →
          tela de divergências agregada.
        - Instrumentos coletados mas todos sem pendência → gera tudo direto.
        - Nada coletado (só eventos de geração direta / erro) → tela de
          saída com o que tiver."""
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
        """Wrapper público de _finalizar_lote — chamado por
        RevisionService.gerar_lote depois de gerar tudo, fora do fluxo normal
        de avancar_fila (que já chamaria isso sozinho se a fila ainda
        estivesse "ativa", mas nesse ponto ela já foi esgotada)."""
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

    def dados_origem_automaticos(self, tag):
        """Retorna (n_ac, localizacao) pra essa TAG a partir de um documento
        "Itens Relacionados" da Origem (ex.: LDN-030.pdf) — pergunta ao
        usuário, só na primeira vez nesta sessão de leitura (reset em
        iniciar_leitura), se ele quer incluir esse documento; se sim, abre
        a seleção de arquivo e monta o cache pra essa sessão inteira (um
        documento cobre várias TAGs). Devolve (None, None) se o usuário
        recusar, cancelar a seleção, ou a TAG não estiver no documento —
        processors.utils.fluxo_origem cai pro prompt manual nesse caso."""
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
        # Chamado quando dados_origem_automaticos não achou Localização/Nº AC
        # (usuário não incluiu o documento, ou a TAG não estava nele).
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
        numero_ci = dados_pdf.get("numero_ci", "NI")
        xml_path = os.path.splitext(caminho)[0] + ".xml"
        gerar_xml_uc(numero_ci, dados_pdf, xml_path)
        limpar_certificado_solto(caminho)
        self.api._progress(100, "build", CHECKLIST_ALL)
        self.api.alert("Sucesso", f"XML de Incerteza gerado:\n{xml_path}", "success")
        self.api._voltar_para_selecao()

    def _processar_xml_ft(self, caminho):
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
