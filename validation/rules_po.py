
from validation.issue import ValidationIssue



def comparar_evaluation_certificado(ctx):
    print('entrou na função de comparação')
    num_eval = None
    certificado = None

    if ctx.report:
        num_eval = ctx.report.get("Numero_Evaluation")
        print(num_eval)

    if ctx.pdf:
        certificado = ctx.pdf.get("certificado")
        print(certificado)

    print("*DEBUG comparar_evaluation_certificado")
    print("num_eval:", num_eval)
    print("certificado:", certificado)

    if not num_eval or not certificado:
        return ValidationIssue(
            key="evaluation_cert_incompleto",
            title="Dados insuficientes",
            message=f"Evaluation: {num_eval}\nCertificado: {certificado}",
            blocking=True
        )

    if num_eval != certificado:
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
