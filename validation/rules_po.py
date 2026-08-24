import re
from validation.issue import ValidationIssue
from data.utils_db import inserir_placa, buscar_placa_por_tag, buscar_placa_por_sn


def normalizar_numero_certificado(valor):
    if not valor:
        return valor
    valor = re.sub(r"[‐-–—]", "-", valor)
    valor = re.sub(r"\s+", "", valor)
    valor = valor.upper()

    return valor


_TAG_AUSENTE_PO = {"N/A", "N/C", "NI", "NA"}

def regra_nova_placa(ctx):
    tag_raw = (ctx.pdf.get("tag") or "").strip().upper()
    sn      = ctx.pdf.get("sn_inst")

    if not sn:
        return None

    # Placa sem TAG (N/A, N/C, etc.): identificar pelo SN para evitar conflito entre placas
    if not tag_raw or tag_raw in _TAG_AUSENTE_PO:
        registro = buscar_placa_por_sn(sn)
        if registro is None:
            return ValidationIssue(
                key="nova_placa",
                title="Placa não cadastrada",
                message=(
                    f"Placa sem TAG — identificada pelo SN: {sn}\n\n"
                    "Deseja cadastrar a placa?"
                ),
                action=lambda: inserir_placa(sn, sn),
                blocking=False
            )
        return None

    # Placa com TAG: comportamento padrão
    tag = tag_raw
    registro = buscar_placa_por_tag(tag)

    if registro is None:
        return ValidationIssue(
            key="nova_placa",
            title="Placa não cadastrada",
            message=(
                f"TAG {tag} não encontrada no banco.\n\n"
                f"NS: {sn}\n\n"
                "Deseja cadastrar a placa?"
            ),
            action=lambda: inserir_placa(tag, sn),
            blocking=False
        )

    if registro["sn_instrumento"] != sn:
        return ValidationIssue(
            key="sn_placa_divergente",
            title="NS da placa divergente",
            message=(
                f"TAG: {tag}\n\n"
                f"NS Certificado: {sn}\n"
                f"NS Banco: {registro['sn_instrumento']}"
            ),
            blocking=True
        )

    return None


def comparar_evaluation_certificado(ctx):
    num_eval = None
    certificado = None

    if ctx.report:
        num_eval = ctx.report.get("Numero_Evaluation")

    if ctx.pdf:
        certificado = ctx.pdf.get("certificado")

    num_eval_norm = normalizar_numero_certificado(num_eval)
    certificado_norm = normalizar_numero_certificado(certificado)

    if not num_eval_norm or not certificado_norm:
        return ValidationIssue(
            key="evaluation_cert_incompleto",
            title="Dados insuficientes",
            message=f"Evaluation: {num_eval}\nCertificado: {certificado}",
            blocking=True
        )

    if num_eval_norm != certificado_norm:
        return ValidationIssue(
            key="evaluation_cert_diferentes",
            title="Evaluation e Certificado divergentes",
            message=(
                f"Evaluation: {num_eval}\n"
                f"Certificado: {certificado}\n\n"
                "Os números não coincidem."
            ),
            blocking=True
        )

    return None

def validar_parametros_report(ctx):
    if not ctx.report:
        return ValidationIssue(
            key="report_inexistente",
            title="Evaluation Report ausente",
            message="Não foi possível localizar os dados do Evaluation Report.",
            blocking=True
        )

    report = ctx.report

    parametros_obrigatorios = {
        "Diametro_Interno": "Diâmetro Interno do Orifício",
        "resultado_beta": "Fator Beta",
        "Circularidade": "Circularidade",
        "Espessura": "Espessura da Placa",
        "Rugosidade": "Rugosidade da Face",
        "Planeza": "Planeza",
        "Angulo_Chanfro": "Ângulo do Chanfro",
        "Espessura_Furo": "Espessura do Furo",
        "Comprimento_Cilindro": "Comprimento do Cilindro",
        "montante": "Rugosidade da Face a Montante",
        "angulo_face_montante": "Ângulo entre Orifício e Face a Montante"
    }

    parametros_invalidos = []

    for chave, descricao in parametros_obrigatorios.items():
        valor = report.get(chave)

        if valor != "Sim":
            parametros_invalidos.append(descricao)

    if parametros_invalidos:
        lista = "\n".join(f"- {p}" for p in parametros_invalidos)

        return ValidationIssue(
            key="parametros_report_invalidos",
            title="Parâmetros inválidos no Evaluation Report",
            message=(
                "Os seguintes parâmetros não estão aprovados no Evaluation Report:\n\n"
                f"{lista}\n\n"
                "Verifique o relatório de avaliação."
            ),
            blocking=True
        )

    return None