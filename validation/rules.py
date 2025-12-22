from validation.issue import ValidationIssue
from data.utils_db import (
    atualizar_sn,
    atualizar_sn_sensor,
    atualizar_range,
    atualizar_tag,
    inserir_instrumento
)

def to_float(value):
    try:
        if value is None:
            return None
        return float(str(value).replace(",", "."))
    except Exception:
        return None

def regra_tag_vs_sn(ctx):
    if ctx.db is None and ctx.reg_sn is not None:

        if ctx.tag_base_pdf == ctx.tag_base_sn:
            ctx.mvs = True
            return ValidationIssue(
                key="mvs",
                title="TAG compatível (Família MVS)",
                message=(
                    f"NS pertence à mesma família.\n\n"
                    f"Banco: {ctx.reg_sn['tag']}\n"
                    f"Certificado: {ctx.pdf['tag']}"
                ),
                action=lambda: inserir_instrumento(
                    ctx.pdf["tag"],
                    ctx.pdf.get("sn_instrumento"),
                    ctx.pdf.get("sn_sensor"),
                    ctx.pdf.get("min_range"),
                    ctx.pdf.get("max_range")
                ),
                blocking=False
            )

        return ValidationIssue(
            key="tag_divergente",
            title="TAG divergente",
            message=(
                f"NS já cadastrado com outra TAG.\n\n"
                f"Banco: {ctx.reg_sn['tag']}\n"
                f"Certificado: {ctx.pdf['tag']}"
            ),
            action=lambda: atualizar_tag(
                ctx.pdf["sn_instrumento"],
                ctx.pdf["tag"]
            )
        )


def regra_novo_instrumento(ctx):
    if ctx.db is None and ctx.reg_sn is None:
        return ValidationIssue(
            key="novo_instrumento",
            title="TAG não encontrada",
            message=(
                f"TAG {ctx.pdf['tag']} não existe.\n\n"
                f"SN Instrumento: {ctx.pdf.get('sn_instrumento')}\n"
                f"SN Sensor: {ctx.pdf.get('sn_sensor')}"
            ),
            action=lambda: inserir_instrumento(
                ctx.pdf["tag"],
                ctx.pdf.get("sn_instrumento"),
                ctx.pdf.get("sn_sensor"),
                ctx.pdf.get("min_range"),
                ctx.pdf.get("max_range")
            )
        )


def regra_sn_instrumento(ctx):
    if (
        ctx.pdf.get("sn_instrumento")
        and ctx.pdf["sn_instrumento"] != ctx.db["sn_instrumento"]
    ):
        return ValidationIssue(
            key="sn_instrumento",
            title="SN do Instrumento divergente",
            message=(
                f"PDF: {ctx.pdf['sn_instrumento']}\n"
                f"Banco: {ctx.db['sn_instrumento']}"
            ),
            action=lambda: atualizar_sn(
                ctx.db["tag"],
                ctx.pdf["sn_instrumento"]
            )
        )


def regra_sn_sensor(ctx):
    if (
        ctx.pdf.get("sn_sensor")
        and ctx.pdf["sn_sensor"] != ctx.db["sn_sensor"]
    ):
        return ValidationIssue(
            key="sn_sensor",
            title="SN do Sensor divergente",
            message=(
                f"PDF: {ctx.pdf['sn_sensor']}\n"
                f"Banco: {ctx.db['sn_sensor']}"
            ),
            action=lambda: atualizar_sn_sensor(
                ctx.db["tag"],
                ctx.pdf["sn_sensor"]
            )
        )


def regra_range(ctx):
    if ctx.mvs:
        return None

    pdf_min = to_float(ctx.pdf.get("min_range"))
    pdf_max = to_float(ctx.pdf.get("max_range"))

    db_min = to_float(ctx.db.get("min_range"))
    db_max = to_float(ctx.db.get("max_range"))

    # Se PDF não trouxe range, ignora regra
    if pdf_min is None or pdf_max is None:
        return None

    # Atualiza o contexto com valores normalizados
    ctx.pdf["min_range"] = pdf_min
    ctx.pdf["max_range"] = pdf_max
    ctx.db["min_range"] = db_min
    ctx.db["max_range"] = db_max

    # Banco sem range cadastrado
    if db_min is None or db_max is None:
        return ValidationIssue(
            key="range",
            title="Range ausente no banco",
            message=(
                f"PDF: {pdf_min} → {pdf_max}\n"
                f"Banco: não cadastrado"
            ),
            action=lambda: atualizar_range(
                ctx.db["tag"],
                pdf_min,
                pdf_max
            )
        )

    # Comparação numérica REAL
    if pdf_min != db_min or pdf_max != db_max:
        return ValidationIssue(
            key="range",
            title="Range divergente",
            message=(
                f"PDF: {pdf_min} → {pdf_max}\n"
                f"Banco: {db_min} → {db_max}"
            ),
            action=lambda: atualizar_range(
                ctx.db["tag"],
                pdf_min,
                pdf_max
            )
        )

    return None


def regra_haste_te(ctx):
    if "TE" not in ctx.pdf["tag"]:
        return

    try:
        rod = ctx.pdf.get("rod_length")
        dia = ctx.pdf.get("probe_diameter")

        if rod is None or dia is None or float(dia) > float(rod):
            return ValidationIssue(
                key="haste",
                title="Dados de Haste inválidos",
                message=(
                    f"Comprimento: {rod}\n"
                    f"Diâmetro: {dia}"
                ),
                blocking=True
            )

    except Exception:
        return ValidationIssue(
            key="haste_parse",
            title="Erro na leitura da Haste",
            message="Erro ao interpretar os valores.",
            blocking=True
        )