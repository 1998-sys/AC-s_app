import os
import json
import traceback
from pathlib import Path

from xml_model.xml_generator import normalizar_certificado, tag_te
from data.utils_db import buscar_instrumento_por_tag, buscar_por_sn_instrumento
from xml_model.xml_extractor_PO import extrair_valores_medidos
from form.utils_print import gerar_ac_escolha, obter_caminho_ac
from validation.engine import ValidationEngine
from validation.context import ValidationContext

from gui.support import extrair_tag_base, foto_instrumento


class RevisionService:
    """Orquestra a tela de revisão: roda a ValidationEngine sobre o certificado,
    mantém as divergências pendentes e gera a Análise Crítica quando o usuário
    confirma. Também resolve a listagem/abertura dos arquivos gerados.
    """

    def __init__(self, api):
        self.api = api

    def iniciar_revisao(self, dados_pdf):
        api = self.api
        if not dados_pdf:
            api.alert("Erro interno", "Dados do certificado estão vazios.", "error")
            api._voltar_para_selecao()
            return

        try:
            is_placa = dados_pdf.get("instrumento") == "Placa de Orificio"
            tipo_instrumento = "PO" if is_placa else "SEC"
            tag = dados_pdf.get("tag")

            if not is_placa:
                if not tag:
                    api.alert("Erro", "TAG não encontrada no certificado.", "error")
                    api._voltar_para_selecao()
                    return
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
                api.certificado_te_atual = normalizar_certificado(dados_pdf.get("certificado"))

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

            api._issues_pendentes = {issue.key: issue for issue in issues}
            api._dados_pdf_review = dados_pdf
            api._registro_review = registro

            api._progress(90, "validate", ["extract", "compare"])

            badge = (dados_pdf.get("tag") or "").split("-")[0] if dados_pdf.get("tag") else ""
            payload = {
                "tag": dados_pdf.get("tag") or "—",
                "sub": f"Certificado {normalizar_certificado(dados_pdf.get('certificado')) or '—'} · {dados_pdf.get('local') or ''}",
                "badge": badge,
                "photo": foto_instrumento(dados_pdf.get("tag")),
                "fields": [
                    {"label": "TAG", "value": dados_pdf.get("tag")},
                    {"label": "SN", "value": dados_pdf.get("sn_instrumento")},
                    {"label": "Faixa calibrada", "value": f"{dados_pdf.get('min_range')} – {dados_pdf.get('max_range')}"},
                ],
                "issues": self.serializar_issues(),
            }
            api._js(f"App.showReview({json.dumps(payload)})")
        except Exception as e:
            traceback.print_exc()
            api._voltar_para_selecao()
            api.alert("Erro na revisão", str(e), "error")

    def serializar_issues(self):
        return [
            {
                "key": issue.key,
                "title": issue.title,
                "message": issue.message,
                "blocking": issue.blocking,
                "has_action": issue.action is not None,
                "resolved": getattr(issue, "resolved", False),
            }
            for issue in self.api._issues_pendentes.values()
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
        return self.serializar_issues()

    def confirmar_geracao(self):
        api = self.api
        dados_pdf = api._dados_pdf_review
        if not dados_pdf:
            api.alert("Erro", "Nenhum certificado em revisão.", "error")
            return None

        pendentes = [i for i in api._issues_pendentes.values() if i.blocking and not getattr(i, "resolved", False)]
        if pendentes:
            api.alert("Erro", "Existem divergências bloqueantes não resolvidas.", "error")
            return None

        try:
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

            caminho_gerado = gerar_ac_escolha(
                dados_pdf,
                api.caminho_pdf_atual,
                api.pontos_calibracao,
                api.certificado_te_atual,
                api.pontos_calibracao_petro,
                api.dados_report_atual,
                dados_dim_tr=api.dados_dim_tr,
            )

            if dados_pdf.get("tag") and "TT" in dados_pdf.get("tag").upper():
                api.certificado_te_atual = None
            api.dados_report_atual = None
            api.dados_dim_tr = None

            avisos = sum(1 for i in api._issues_pendentes.values() if not i.blocking)
            badge = (dados_pdf.get("tag") or "").split("-")[0] if dados_pdf.get("tag") else ""

            return {
                "sub": f"{dados_pdf.get('tag') or ''} · atestado e XML da ANP",
                "pdf_name": os.path.basename(caminho_gerado) if caminho_gerado else None,
                "badge": badge,
                "avisos": avisos,
                "files": self._listar_arquivos_gerados(caminho_gerado, api.caminho_pdf_atual),
            }

        except Exception as e:
            traceback.print_exc()
            api.alert("Erro", f"Erro na geração: {e}", "error")
            return None

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
