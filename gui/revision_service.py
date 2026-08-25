import os
import json
import time
import traceback
import win32com.client as win32
from pathlib import Path

from xml_model.xml_generator import normalizar_certificado, tag_te, chave_par_te
from data.utils_db import buscar_instrumento_por_tag, buscar_por_sn_instrumento
from xml_model.xml_extractor_PO import extrair_valores_medidos
from form.utils_print import gerar_ac_escolha, obter_caminho_ac
from validation.engine import ValidationEngine
from validation.context import ValidationContext

from gui.support import CHECKLIST_ALL, extrair_tag_base, foto_instrumento, limpar_certificado_solto


class RevisionService:
    """Orquestra a tela de revisão: roda a ValidationEngine sobre o certificado,
    mantém as divergências pendentes e gera a Análise Crítica quando o usuário
    confirma. Também resolve a listagem/abertura dos arquivos gerados.
    """

    def __init__(self, api):
        self.api = api

    def iniciar_revisao(self, dados_pdf):
        api = self.api
        # Fase 6 (lote): em vez de pausar mostrando a revisão desse item, só
        # coleta os dados/divergências e segue lendo os próximos — a revisão
        # de todos junto acontece só no final, na tela agregada. Fora do
        # lote (um único certificado), o fluxo é o de sempre, inalterado.
        if api._pdf_service.em_lote_ativo():
            return self.coletar_revisao_lote(dados_pdf)

        if not dados_pdf:
            api.alert("Erro interno", "Dados do certificado estão vazios.", "error")
            api._voltar_para_selecao()
            return

        try:
            dados_revisao = self._montar_dados_revisao(dados_pdf)
            if dados_revisao is None:
                return
            issues, registro = dados_revisao

            api._issues_pendentes = {issue.key: issue for issue in issues}
            api._dados_pdf_review = dados_pdf
            api._registro_review = registro

            api._progress(90, "validate", ["extract", "compare"])

            payload = self._montar_resumo_instrumento(dados_pdf)
            payload["issues"] = self.serializar_issues()
            api._js(f"App.showReview({json.dumps(payload)})")
        except Exception as e:
            traceback.print_exc()
            api.alert("Erro na revisão", str(e), "error")
            api._voltar_para_selecao()

    def coletar_revisao_lote(self, dados_pdf):
        """Versão em lote de iniciar_revisao: roda a mesma validação, mas só
        guarda o resultado (dados/registro/divergências) em
        `api.instrumentos_lote` e segue pro próximo certificado da fila —
        nunca mostra a tela de revisão por item. `pontos_calibracao` etc.
        são atributos de sessão únicos na Api que cada novo certificado
        sobrescreve; por isso são copiados aqui pra dentro do registro do
        instrumento, senão na hora de gerar tudo no final só os valores do
        ÚLTIMO certificado lido sobreviveriam. O certificado do TE (pra
        vincular no TT/TIT correspondente) NÃO é copiado aqui — é buscado
        de `certificados_te_por_par` só na hora de gerar (ver
        `_gerar_e_montar_resultado`), já que nesse ponto a leitura de TODOS
        os itens do lote já terminou, então não importa se o TT foi lido
        antes do seu TE na fila."""
        api = self.api
        if not dados_pdf:
            api._pdf_service.registrar_evento_lote(
                "Certificado pulado", "Dados do certificado estão vazios.", "error"
            )
            api._voltar_para_selecao()
            return

        try:
            dados_revisao = self._montar_dados_revisao(dados_pdf)
            if dados_revisao is None:
                return
            issues, registro = dados_revisao

            api._progress(70, "validate", ["extract", "compare"])
            # Dá tempo do usuário ver "Validando regras da ANP" ativo antes
            # de já pular pro "Montando relatório e XML" — sem isso os dois
            # passos completam juntos rápido demais pra perceber.
            time.sleep(2)

            api.instrumentos_lote.append({
                "tag": dados_pdf.get("tag") or "",
                "dados_pdf": dados_pdf,
                "registro": registro,
                "issues": {issue.key: issue for issue in issues},
                "caminho_pdf": api.caminho_pdf_atual,
                "pontos_calibracao": api.pontos_calibracao,
                "pontos_calibracao_petro": api.pontos_calibracao_petro,
                "dados_report": api.dados_report_atual,
                "dados_dim_tr": api.dados_dim_tr,
            })

            # "build" aqui significa "coleta concluída pra esse item" — a
            # geração de verdade só acontece depois, em gerar_lote, mas
            # completar visualmente o checklist antes de avançar pro
            # próximo certificado dá a mesma sensação de progresso contínuo
            # que os tipos de geração direta já mostram.
            api._progress(100, "build", CHECKLIST_ALL)

            api._voltar_para_selecao()
        except Exception as e:
            traceback.print_exc()
            api._pdf_service.registrar_evento_lote(
                dados_pdf.get("tag") or "certificado", f"Erro na revisão: {e}", "error"
            )
            api._voltar_para_selecao()

    def _montar_dados_revisao(self, dados_pdf):
        """Parte comum de iniciar_revisao/coletar_revisao_lote: valida a TAG,
        busca o cadastro e roda a ValidationEngine. Retorna (issues, registro)
        ou None se já tratou um erro (TAG ausente) e não deve continuar —
        quem chama decide o que fazer no caso de erro antes de chegar aqui,
        já que os dois fluxos reportam esse erro de formas diferentes
        (alert direto vs. evento de lote)."""
        api = self.api
        is_placa = dados_pdf.get("instrumento") == "Placa de Orificio"
        tipo_instrumento = "PO" if is_placa else "SEC"
        tag = dados_pdf.get("tag")

        if not is_placa:
            if not tag:
                em_lote = api._pdf_service.em_lote_ativo()
                if em_lote:
                    api._pdf_service.registrar_evento_lote(
                        "Certificado pulado", "TAG não encontrada no certificado.", "error"
                    )
                else:
                    api.alert("Erro", "TAG não encontrada no certificado.", "error")
                api._voltar_para_selecao()
                return None
            tag = tag.upper()
            dados_pdf["tag"] = tag
        elif tag:
            dados_pdf["tag"] = tag.upper()

        registro = None
        reg_sn = None
        if not is_placa:
            registro = buscar_instrumento_por_tag(tag)
            reg_sn = buscar_por_sn_instrumento(dados_pdf.get("sn_instrumento"))

        if tag_te(dados_pdf.get("tag")):
            chave = chave_par_te(dados_pdf.get("tag"))
            if chave:
                api.certificados_te_por_par[chave] = normalizar_certificado(dados_pdf.get("certificado"))

        ctx = ValidationContext(
            dados_pdf=dados_pdf,
            registro=registro,
            reg_sn=reg_sn,
            tag_base_pdf=extrair_tag_base(tag) if tag else None,
            tag_base_sn=extrair_tag_base(registro.get("tag")) if registro else None,
            pontos=api.pontos_calibracao,
            tipo_instrumento=tipo_instrumento,
            dados_report=api.dados_report_atual,
            valores_medidos=extrair_valores_medidos(api.caminho_pdf_atual),
        )

        engine = ValidationEngine()
        issues = engine.run(ctx)
        for issue in issues:
            issue.resolved = False

        return issues, registro

    def _montar_resumo_instrumento(self, dados_pdf):
        badge = (dados_pdf.get("tag") or "").split("-")[0] if dados_pdf.get("tag") else ""
        return {
            "tag": dados_pdf.get("tag") or "—",
            "sub": f"Certificado {normalizar_certificado(dados_pdf.get('certificado')) or '—'} · {dados_pdf.get('local') or ''}",
            "badge": badge,
            "photo": foto_instrumento(dados_pdf.get("tag")),
            "fields": [
                {"label": "TAG", "value": dados_pdf.get("tag")},
                {"label": "SN", "value": dados_pdf.get("sn_instrumento")},
                {"label": "Faixa calibrada", "value": f"{dados_pdf.get('min_range')} – {dados_pdf.get('max_range')}"},
            ],
        }

    def serializar_issues(self):
        return self._serializar_issues_dict(self.api._issues_pendentes)

    def _serializar_issues_dict(self, issues_dict):
        return [
            {
                "key": issue.key,
                "title": issue.title,
                "message": issue.message,
                "blocking": issue.blocking,
                "has_action": issue.action is not None,
                "resolved": getattr(issue, "resolved", False),
                # Qual opção foi escolhida ao resolver (True = usou o
                # certificado/aplicou a ação; False = manteve o cadastro sem
                # rodar a ação). None enquanto pendente. Permite a UI
                # distinguir "divergência de fato corrigida" de "divergência
                # mantida conscientemente" — ver renderIssueCard em app.js.
                "aplicado": getattr(issue, "aplicado", None),
                "opcoes": getattr(issue, "opcoes", None),
            }
            for issue in issues_dict.values()
        ]

    def resolver_divergencia(self, key, aplicar):
        api = self.api
        issue = api._issues_pendentes.get(key)
        if issue:
            if aplicar and issue.action:
                issue.action()
                if api._dados_pdf_review is not None:
                    api._dados_pdf_review["_novo_instrumento_inserido"] = True
            issue.resolved = True
            issue.aplicado = aplicar
        return self.serializar_issues()

    def desfazer_divergencia(self, key):
        """Volta uma divergência resolvida pra pendente, permitindo escolher de
        novo. Não reverte a escrita no banco de uma ação já aplicada (ex.:
        inserir_instrumento/atualizar_sn já executados) — as regras de
        validação não carregam uma "ação reversa"; se o valor gravado estiver
        errado, o ajuste é feito na tela Editar instrumento."""
        issue = self.api._issues_pendentes.get(key)
        if issue:
            issue.resolved = False
        return self.serializar_issues()

    def voltar_da_revisao(self):
        """Abandona a revisão atual sem gerar nada (botão "←" da tela de
        revisão) — inclui os casos sem nenhuma saída possível, como uma
        divergência bloqueante sem ação nenhuma (ex.: "Incerteza abaixo da
        CMC"). Essa tela só aparece fora do lote (Fase 6: em lote a revisão
        é agregada, ver coletar_revisao_lote), então só limpa o estado; a
        navegação de volta pra seleção fica a cargo do JS."""
        self.api._issues_pendentes = {}
        self.api._dados_pdf_review = None
        self.api._registro_review = None
        return {"em_lote": False}

    def confirmar_geracao(self):
        """Gera a AC de um único certificado (fluxo fora do lote — em lote
        quem gera é gerar_lote, a partir da tela de divergências agregada)."""
        api = self.api
        dados_pdf = api._dados_pdf_review
        if not dados_pdf:
            api.alert("Erro", "Nenhum certificado em revisão.", "error")
            return None

        pendentes = [i for i in api._issues_pendentes.values() if i.blocking and not getattr(i, "resolved", False)]
        if pendentes:
            api.alert("Erro", "Existem divergências bloqueantes não resolvidas.", "error")
            return None

        # Divergências resolvidas via "Manter o cadastro" (aplicar=False): o
        # AC gerado sempre reflete os dados do certificado — a diferença é só
        # se o cadastro interno foi atualizado ou não — mas ainda assim é uma
        # divergência que não foi corrigida no cadastro, então pede
        # confirmação explícita antes de gerar em vez de seguir direto.
        mantidas = [
            i for i in api._issues_pendentes.values()
            if getattr(i, "resolved", False) and i.opcoes and getattr(i, "aplicado", None) is False
        ]
        if mantidas:
            titulos = "\n".join(f"- {i.title}" for i in mantidas)
            if not api.confirm(
                "Certificado não corrigido",
                f"As divergências abaixo foram mantidas sem corrigir o cadastro:\n\n{titulos}\n\n"
                "Deseja gerar o relatório e o XML mesmo assim?",
            ):
                api.alert(
                    "Certificado não gerado",
                    "Geração cancelada — divergência mantida sem confirmar.",
                    "error",
                )
                return None

        if not api.caminho_pdf_atual:
            api.alert("Erro", "Caminho do PDF não encontrado.", "error")
            return None

        caminho_ac = obter_caminho_ac(dados_pdf, api.caminho_pdf_atual)
        if os.path.exists(caminho_ac):
            if not api.confirm(
                "Arquivo já existe",
                f"O arquivo abaixo já existe:\n\n{os.path.basename(caminho_ac)}\n\nDeseja sobrescrever?",
            ):
                api.alert("Operação cancelada", "A Análise Crítica não foi sobrescrita.", "info")
                return None

        try:
            return self._gerar_e_montar_resultado(
                dados_pdf,
                api.caminho_pdf_atual,
                api.pontos_calibracao,
                api.pontos_calibracao_petro,
                api.dados_report_atual,
                api.dados_dim_tr,
                api._issues_pendentes.values(),
            )
        except Exception as e:
            traceback.print_exc()
            api.alert("Erro", f"Erro na geração: {e}", "error")
            return None
        finally:
            api.dados_report_atual = None
            api.dados_dim_tr = None

    def _gerar_e_montar_resultado(
        self, dados_pdf, caminho_pdf, pontos_calibracao,
        pontos_calibracao_petro, dados_report, dados_dim_tr, issues, excel=None,
    ):
        """Gera a AC/XML de um certificado e monta o dict de resultado usado
        tanto pela tela de saída de um único arquivo quanto pelos cards da
        saída agregada em lote. Compartilhado entre confirmar_geracao
        (fluxo de um único arquivo) e gerar_lote (Fase 6).

        O certificado do TE (pra vincular no TT/TIT) é buscado aqui mesmo,
        por TAG (`certificados_te_por_par`), na hora de gerar — não antes —
        pra funcionar independente da ordem em que TE e TT foram lidos.

        `excel`: instância COM do Excel já aberta, reaproveitada pelo
        gerar_lote em vez de abrir um processo novo por certificado."""
        certificado_te = self.api.certificados_te_por_par.get(chave_par_te(dados_pdf.get("tag")))
        caminho_gerado = gerar_ac_escolha(
            dados_pdf, caminho_pdf, pontos_calibracao, certificado_te,
            pontos_calibracao_petro, dados_report, dados_dim_tr=dados_dim_tr, excel=excel,
        )

        avisos = sum(1 for i in issues if not i.blocking)
        badge = (dados_pdf.get("tag") or "").split("-")[0] if dados_pdf.get("tag") else ""
        arquivos = self._listar_arquivos_gerados(caminho_gerado, caminho_pdf)
        limpar_certificado_solto(caminho_pdf)

        return {
            "tag": dados_pdf.get("tag") or "",
            "sub": f"{dados_pdf.get('tag') or ''} · atestado e XML da ANP",
            "pdf_name": os.path.basename(caminho_gerado) if caminho_gerado else None,
            "badge": badge,
            "avisos": avisos,
            "files": arquivos,
        }

    # ---------- Fase 6: revisão agregada em lote ----------

    def _achar_instrumento_lote(self, tag):
        return next((i for i in self.api.instrumentos_lote if i["tag"] == tag), None)

    def _montar_payload_divergencias_lote(self):
        grupos = []
        for inst in self.api.instrumentos_lote:
            if not inst["issues"]:
                continue
            grupo = self._montar_resumo_instrumento(inst["dados_pdf"])
            grupo["issues"] = self._serializar_issues_dict(inst["issues"])
            grupos.append(grupo)
        return {"grupos": grupos}

    def resolver_divergencia_lote(self, tag, key, aplicar):
        inst = self._achar_instrumento_lote(tag)
        if not inst:
            return self._montar_payload_divergencias_lote()

        issue = inst["issues"].get(key)
        if not issue:
            return self._montar_payload_divergencias_lote()

        if not aplicar and issue.opcoes:
            # Divergência de duas opções (ex.: SN/range "usar o certificado"
            # x "pular certificado"): manter o cadastro sem corrigir geraria
            # uma AC com dado divergente do cadastro — em vez de deixar
            # "mantido" e permitir gerar mesmo assim, pula o certificado
            # inteiro (os demais do lote seguem normalmente).
            return self.pular_instrumento_lote(tag, motivo=f"{issue.title}: {issue.message}")

        if aplicar and issue.action:
            issue.action()
            inst["dados_pdf"]["_novo_instrumento_inserido"] = True
        issue.resolved = True
        issue.aplicado = aplicar
        return self._montar_payload_divergencias_lote()

    def desfazer_divergencia_lote(self, tag, key):
        inst = self._achar_instrumento_lote(tag)
        if inst:
            issue = inst["issues"].get(key)
            if issue:
                issue.resolved = False
        return self._montar_payload_divergencias_lote()

    def pular_instrumento_lote(self, tag, motivo=None):
        """Remove um instrumento inteiro da revisão agregada sem gerar nada
        pra ele — usado quando ele tem uma divergência bloqueante sem
        nenhuma ação possível (ex.: "Incerteza abaixo da CMC"), ou quando o
        usuário escolhe não corrigir uma divergência de duas opções (ver
        resolver_divergencia_lote)."""
        api = self.api
        inst = self._achar_instrumento_lote(tag)
        if inst:
            api.instrumentos_lote.remove(inst)
            if motivo is None:
                pendentes = [
                    i.title for i in inst["issues"].values()
                    if i.blocking and not getattr(i, "resolved", False)
                ]
                motivo = "; ".join(pendentes) if pendentes else "Certificado pulado pelo usuário"
            nome = os.path.basename(inst["caminho_pdf"])
            api._pdf_service.registrar_evento_lote(tag or "certificado", motivo, "error", nome=nome)
        return self._montar_payload_divergencias_lote()

    def confirmar_geracao_lote(self):
        """Chamado pelo botão "Gerar relatórios" da tela de divergências
        agregada. Uma divergência de duas opções não corrigida ("Pular
        certificado") já removeu o instrumento de instrumentos_lote em
        resolver_divergencia_lote — não sobra "mantido sem corrigir" pra
        confirmar aqui, só bloqueantes pendentes."""
        api = self.api
        pendentes = [
            i for inst in api.instrumentos_lote for i in inst["issues"].values()
            if i.blocking and not getattr(i, "resolved", False)
        ]
        if pendentes:
            api.alert("Erro", "Existem divergências bloqueantes não resolvidas.", "error")
            return None

        return self.gerar_lote()

    def gerar_lote(self):
        """Gera a AC/XML de cada instrumento coletado que estiver pronto (sem
        divergência, ou com tudo resolvido/ignorado) e finaliza o lote.
        Chamado automaticamente quando a leitura contínua termina sem
        nenhuma pendência, e também por confirmar_geracao_lote.

        Abre uma única instância do Excel COM e reaproveita ela em todos os
        certificados do lote — abrir/fechar o Excel por certificado era a
        maior parte do delay percebido na transição revisão → saída."""
        api = self.api
        instrumentos = api.instrumentos_lote
        api.instrumentos_lote = []

        excel = None
        if instrumentos:
            excel = win32.DispatchEx("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            excel.ScreenUpdating = False
            excel.Interactive = False

        try:
            for inst in instrumentos:
                nome = os.path.basename(inst["caminho_pdf"])
                pendentes = [i for i in inst["issues"].values() if i.blocking and not getattr(i, "resolved", False)]
                if pendentes:
                    api._pdf_service.registrar_evento_lote(
                        inst["tag"] or "certificado", "Divergências bloqueantes não resolvidas.", "error", nome=nome
                    )
                    continue

                dados_pdf = inst["dados_pdf"]
                try:
                    caminho_ac = obter_caminho_ac(dados_pdf, inst["caminho_pdf"])
                    if os.path.exists(caminho_ac):
                        # Em lote não dá pra perguntar "sobrescrever?" a cada item
                        # sem virar uma sequência de confirms — sobrescreve direto
                        # e deixa registrado que aconteceu.
                        api._pdf_service.registrar_evento_lote(
                            inst["tag"] or "certificado",
                            f"Arquivo já existia e foi sobrescrito: {os.path.basename(caminho_ac)}",
                            "success",
                            nome=nome,
                        )

                    resultado = self._gerar_e_montar_resultado(
                        dados_pdf, inst["caminho_pdf"], inst["pontos_calibracao"],
                        inst["pontos_calibracao_petro"],
                        inst["dados_report"], inst["dados_dim_tr"], inst["issues"].values(),
                        excel=excel,
                    )
                    api.resultados_lote.append(resultado)
                except Exception as e:
                    traceback.print_exc()
                    api._pdf_service.registrar_evento_lote(
                        inst["tag"] or "certificado", f"Erro na geração: {e}", "error", nome=nome
                    )
        finally:
            if excel:
                try:
                    excel.Quit()
                except Exception:
                    pass

        payload = api._pdf_service.finalizar_lote_manualmente()
        api._js(f"App.showOutputLote({json.dumps(payload)})")
        return payload

    def _listar_arquivos_gerados(self, caminho_pdf_gerado, caminho_pdf_original):
        arquivos = []
        if caminho_pdf_gerado and os.path.exists(caminho_pdf_gerado):
            tamanho = os.path.getsize(caminho_pdf_gerado) // 1024
            arquivos.append({
                "kind": "PDF",
                "name": os.path.basename(caminho_pdf_gerado),
                "meta": f"Atestado de calibração · {tamanho} KB",
                "path": caminho_pdf_gerado,
            })

        candidatos_xml = [Path(caminho_pdf_original).with_suffix(".xml")]
        stem = Path(caminho_pdf_original).stem
        candidatos_xml.append(Path(caminho_pdf_original).with_name(f"{stem}_petro.xml"))

        for candidato in candidatos_xml:
            if candidato.exists():
                tamanho = candidato.stat().st_size // 1024
                arquivos.append({
                    "kind": "XML",
                    "name": candidato.name,
                    "meta": f"Validado contra o schema · {tamanho} KB",
                    "path": str(candidato),
                })
        return arquivos

    def abrir_arquivo(self, caminho):
        try:
            os.startfile(caminho)
        except Exception as e:
            self.api.alert("Erro", f"Não foi possível abrir o arquivo: {e}", "error")
