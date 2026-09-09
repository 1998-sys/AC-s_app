# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : gui.revision_service
# Created       : 24-08-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Orchestrates the divergence review screen and generates the Critical Analysis, both for single certificates and batches.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

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
    """Orchestrates the review screen: runs the ValidationEngine over the certificate,
    keeps track of the pending divergences and generates the Critical Analysis when the user
    confirms. Also handles listing/opening the generated files.
    """

    def __init__(self, api):
        """Stores the reference to the Api to access session state and the other services."""
        self.api = api

    def iniciar_revisao(self, dados_pdf):
        """Runs certificate validation and shows the divergence review screen (outside batch mode).

        Args:
            dados_pdf: data extracted from the certificate to review.

        Notes:
            In batch mode (Phase 6), delegates to `coletar_revisao_lote`: instead
            of pausing to show this item's review, it only collects the
            data/divergences and moves on to reading the next ones — the review
            of everything together only happens at the end, on the aggregated
            screen. Outside batch mode (a single certificate), the flow is the
            usual one, unchanged.
        """
        api = self.api
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
        """Batch version of `iniciar_revisao`: runs the same validation, but only stores the result and keeps reading the next certificate in the queue, without pausing.

        Args:
            dados_pdf: data extracted from the certificate to validate.

        Notes:
            Stores the result (data/record/divergences) in
            `api.instrumentos_lote` and never shows the per-item review screen.
            `pontos_calibracao` etc. are unique session attributes on the Api
            that each new certificate overwrites; that's why they are copied
            here into the instrument's record, otherwise when generating
            everything at the end only the values of the LAST certificate read
            would survive. The TE certificate (to link into the corresponding
            TT/TIT) is NOT copied here — it is looked up from
            `certificados_te_por_par` only at generation time (see
            `_gerar_e_montar_resultado`), since by that point reading of ALL
            batch items has already finished, so it doesn't matter whether the
            TT was read before its TE in the queue.
        """
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
            # Gives the user time to see "Validando regras da ANP" active before already
            # jumping to "Montando relatório e XML" — without this the two
            # steps complete together too fast to notice.
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

            # "build" here means "collection completed for this item" — the
            # actual generation only happens later, in gerar_lote, but
            # visually completing the checklist before advancing to the
            # next certificate gives the same sense of continuous progress
            # that the direct-generation types already show.
            api._progress(100, "build", CHECKLIST_ALL)

            api._voltar_para_selecao()
        except Exception as e:
            traceback.print_exc()
            api._pdf_service.registrar_evento_lote(
                dados_pdf.get("tag") or "certificado", f"Erro na revisão: {e}", "error"
            )
            api._voltar_para_selecao()

    def _montar_dados_revisao(self, dados_pdf):
        """Common part of `iniciar_revisao`/`coletar_revisao_lote`: validates the TAG, looks up the registered record and runs the ValidationEngine.

        Args:
            dados_pdf: data extracted from the certificate.

        Returns:
            Tuple `(issues, registro)`, or None if an error (missing TAG)
            was already handled and processing should not continue — the
            caller decides what to do in the error case before reaching
            here, since the two flows report that error differently (direct
            alert vs. batch event).
        """
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
        """Builds the summary payload (tag/badge/photo/fields) shown at the top of the review screen.

        Returns:
            Dict with `tag`, `sub`, `badge`, `photo` and `fields`.
        """
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
        """Serializes the pending divergences of the review in progress (outside batch mode) to send to the UI.

        Returns:
            List of dicts, one per divergence (see `_serializar_issues_dict`).
        """
        return self._serializar_issues_dict(self.api._issues_pendentes)

    def _serializar_issues_dict(self, issues_dict):
        """Converts a dict of issues (key -> Issue object) into the list of serializable dicts consumed by the UI.

        Returns:
            List of dicts with `key`, `title`, `message`, `blocking`,
            `has_action`, `resolved`, `aplicado` and `opcoes`.
        """
        return [
            {
                "key": issue.key,
                "title": issue.title,
                "message": issue.message,
                "blocking": issue.blocking,
                "has_action": issue.action is not None,
                "resolved": getattr(issue, "resolved", False),
                # Which option was chosen when resolving (True = used the
                # certificate/ran the action; False = kept the registered record without
                # running the action). None while pending. Lets the UI
                # distinguish a "divergence actually fixed" from a "divergence
                # knowingly kept" — see renderIssueCard in app.js.
                "aplicado": getattr(issue, "aplicado", None),
                "opcoes": getattr(issue, "opcoes", None),
            }
            for issue in issues_dict.values()
        ]

    def resolver_divergencia(self, key, aplicar):
        """Marks a pending divergence (outside batch mode) as resolved, running its action if the user chose to apply it.

        Args:
            key: key of the issue to resolve.
            aplicar: True to run `issue.action` (use the certificate);
                False to keep the registered record unchanged.

        Returns:
            Serialized list of divergences (see `serializar_issues`).
        """
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
        """Reverts a resolved divergence (outside batch mode) back to pending, allowing the choice to be made again.

        Args:
            key: key of the issue to undo.

        Returns:
            Serialized list of divergences (see `serializar_issues`).

        Notes:
            Does not revert the database write of an action already applied
            (e.g., inserir_instrumento/atualizar_sn already executed) —
            validation rules don't carry a "reverse action"; if the recorded
            value is wrong, the fix is made on the Edit instrument screen.
        """
        issue = self.api._issues_pendentes.get(key)
        if issue:
            issue.resolved = False
        return self.serializar_issues()

    def voltar_da_revisao(self):
        """Abandons the current review without generating anything (the "←" button on the review screen), clearing the session state.

        Returns:
            Dict `{"em_lote": False}`.

        Notes:
            Covers cases with no possible way out, such as a blocking
            divergence with no action at all (e.g., "Uncertainty below the
            CMC"). This screen only appears outside batch mode (Phase 6: in
            batch mode the review is aggregated, see `coletar_revisao_lote`),
            so it only clears the state; navigation back to selection is
            handled by the JS side.
        """
        self.api._issues_pendentes = {}
        self.api._dados_pdf_review = None
        self.api._registro_review = None
        return {"em_lote": False}

    def confirmar_geracao(self):
        """Validates the pending divergences and generates the AC/XML for a single certificate (non-batch flow).

        Returns:
            Result dict (see `_gerar_e_montar_resultado`), or None if there
            are unresolved blocking divergences, the user declines to
            confirm a divergence kept without fixing it, declines to
            overwrite an existing file, or an error occurs during generation
            (in those cases the alert has already been shown).

        Notes:
            In batch mode, generation is done by `gerar_lote`, from the
            aggregated divergences screen.
        """
        api = self.api
        dados_pdf = api._dados_pdf_review
        if not dados_pdf:
            api.alert("Erro", "Nenhum certificado em revisão.", "error")
            return None

        pendentes = [i for i in api._issues_pendentes.values() if i.blocking and not getattr(i, "resolved", False)]
        if pendentes:
            api.alert("Erro", "Existem divergências bloqueantes não resolvidas.", "error")
            return None

        # Divergences resolved via "Keep the registered record" (aplicar=False): the
        # generated AC always reflects the certificate's data — the only difference is
        # whether the internal record was updated or not — but it's still a
        # divergence that wasn't fixed in the record, so it asks for
        # explicit confirmation before generating instead of proceeding directly.
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
        """Generates the AC/XML for a certificate and builds the result dict (output card), used both for a single file and for the batch.

        Args:
            excel: Excel COM instance already open, reused by `gerar_lote`
                instead of opening a new process per certificate. If None,
                `gerar_ac_escolha` opens its own.

        Returns:
            Dict with `tag`, `sub`, `pdf_name`, `badge`, `avisos` and `files`.

        Notes:
            Shared between `confirmar_geracao` (single-file flow) and
            `gerar_lote` (Phase 6). The TE certificate (to link into the
            TT/TIT) is looked up right here, by TAG
            (`certificados_te_por_par`), at generation time — not earlier —
            so it works regardless of the order in which TE and TT were read.
        """
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

    # ---------- Phase 6: aggregated batch review ----------

    def _achar_instrumento_lote(self, tag):
        """Looks up in `api.instrumentos_lote` the collected item with this TAG.

        Returns:
            The instrument's dict, or None if not found.
        """
        return next((i for i in self.api.instrumentos_lote if i["tag"] == tag), None)

    def _montar_payload_divergencias_lote(self):
        """Builds the aggregated divergences screen's payload, one group per collected instrument that still has some issue.

        Returns:
            Dict `{"grupos": [...]}`, each group in the format of
            `_montar_resumo_instrumento` plus serialized `issues`.
        """
        grupos = []
        for inst in self.api.instrumentos_lote:
            if not inst["issues"]:
                continue
            grupo = self._montar_resumo_instrumento(inst["dados_pdf"])
            grupo["issues"] = self._serializar_issues_dict(inst["issues"])
            grupos.append(grupo)
        return {"grupos": grupos}

    def resolver_divergencia_lote(self, tag, key, aplicar):
        """Resolves a divergence of an instrument in the aggregated batch review, running the action if applicable.

        Args:
            tag: instrument's TAG (key in `instrumentos_lote`).
            key: key of the issue to resolve.
            aplicar: True to run `issue.action`; False to keep the
                registered record unchanged.

        Returns:
            Updated payload of the aggregated divergences screen (see
            `_montar_payload_divergencias_lote`).

        Notes:
            A two-option divergence (e.g., SN/range "use the certificate" vs.
            "skip certificate") not applied: keeping the registered record
            without fixing it would generate an AC with data diverging from
            the record — instead of leaving it "kept" and allowing generation
            anyway, it skips the whole certificate (the rest of the batch
            proceeds normally).
        """
        inst = self._achar_instrumento_lote(tag)
        if not inst:
            return self._montar_payload_divergencias_lote()

        issue = inst["issues"].get(key)
        if not issue:
            return self._montar_payload_divergencias_lote()

        if not aplicar and issue.opcoes:
            return self.pular_instrumento_lote(tag, motivo=f"{issue.title}: {issue.message}")

        if aplicar and issue.action:
            issue.action()
            inst["dados_pdf"]["_novo_instrumento_inserido"] = True
        issue.resolved = True
        issue.aplicado = aplicar
        return self._montar_payload_divergencias_lote()

    def desfazer_divergencia_lote(self, tag, key):
        """Reverts a resolved divergence of a batch instrument back to pending.

        Returns:
            Updated payload of the aggregated divergences screen (see
            `_montar_payload_divergencias_lote`).
        """
        inst = self._achar_instrumento_lote(tag)
        if inst:
            issue = inst["issues"].get(key)
            if issue:
                issue.resolved = False
        return self._montar_payload_divergencias_lote()

    def pular_instrumento_lote(self, tag, motivo=None):
        """Removes an entire instrument from the aggregated review without generating anything for it — used when it has a blocking divergence with no possible action (e.g., "Uncertainty below the CMC"), or when the user chooses not to fix a two-option divergence (see resolver_divergencia_lote)."""
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
        """Called by the "Generate reports" button on the aggregated divergences screen. An unfixed two-option divergence ("Skip certificate") has already removed the instrument from instrumentos_lote in resolver_divergencia_lote — there's no "kept without fixing" left to confirm here, only pending blocking ones."""
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
        """Generates the AC/XML for each collected instrument that is ready (no divergence, or with everything resolved/ignored) and finalizes the batch. Called automatically when continuous reading finishes with no pending items, and also by confirmar_geracao_lote.

        Opens a single Excel COM instance and reuses it for every certificate
        in the batch — opening/closing Excel per certificate was the biggest
        part of the delay perceived in the review -> output transition."""
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
                        # In batch mode there's no way to ask "overwrite?" for every item
                        # without turning it into a sequence of confirms — it overwrites directly
                        # and logs that it happened.
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
        """Builds the list of generated files (AC PDF and associated XML(s)) to display on the output card.

        Args:
            caminho_pdf_gerado: path of the already generated Critical
                Analysis PDF (can be None or no longer exist on disk).
            caminho_pdf_original: path of the source certificate, used to
                look for the XMLs generated next to it (same name and, for
                Petrobras, with the "_petro" suffix).

        Returns:
            List of dicts `{"kind", "name", "meta", "path"}`, one per file
            found (PDF and/or XML), in PDF -> XML order.
        """
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
        """Opens a generated file (PDF or XML) in the system's default application, showing an alert if it fails.

        Args:
            caminho: path of the file to open.
        """
        try:
            os.startfile(caminho)
        except Exception as e:
            self.api.alert("Erro", f"Não foi possível abrir o arquivo: {e}", "error")
