from validation.issue import ValidationIssue
import unicodedata
from data.utils_db import (
    atualizar_sn,
    atualizar_sn_sensor,
    atualizar_range,
    atualizar_tag,
    inserir_instrumento
)

# =========================
# UTILITÁRIOS
# =========================

def normalizar_texto(texto):
    if not texto:
        return ""
    texto = texto.upper()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def to_float(value):
    try:
        if value is None:
            return None
        return float(str(value).replace(",", "."))
    except Exception:
        return None


# =========================
# REGRA 1 — TAG vs SN (MVS ou divergente)
# =========================

def regra_tag_vs_sn(ctx):
    if ctx.db is None and ctx.reg_sn is not None:

        # Família MVS
        if ctx.tag_base_pdf == ctx.tag_base_sn:
            ctx.mvs = True
            return ValidationIssue(
                key="mvs",
                title="TAG compatível (Família MVS)",
                message=(
                    "NS pertence à mesma família.\n\n"
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

        # TAG divergente
        return ValidationIssue(
            key="tag_divergente",
            title="TAG divergente",
            message=(
                "NS já cadastrado com outra TAG.\n\n"
                f"Banco: {ctx.reg_sn['tag']}\n"
                f"Certificado: {ctx.pdf['tag']}"
            ),
            action=lambda: atualizar_tag(
                ctx.pdf["sn_instrumento"],
                ctx.pdf["tag"]
            ),
            blocking=True
        )


# =========================
# REGRA 2 — Novo Instrumento
# =========================

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
            ),
            blocking=True
        )


# =========================
# REGRA 3 — SN do Instrumento
# =========================

def regra_sn_instrumento(ctx):
    if ctx.db is None:
        return None

    if (
        ctx.pdf.get("sn_instrumento")
        and ctx.pdf["sn_instrumento"] != ctx.db.get("sn_instrumento")
    ):
        return ValidationIssue(
            key="sn_instrumento",
            title="SN do Instrumento divergente",
            message=(
                f"PDF: {ctx.pdf['sn_instrumento']}\n"
                f"Banco: {ctx.db.get('sn_instrumento')}"
            ),
            action=lambda: (
                atualizar_sn(ctx.db["tag"], ctx.pdf["sn_instrumento"]),
                ctx.pdf.__setitem__("sn_atualizado", True)
            )
        )


# =========================
# REGRA 4 — SN do Sensor
# =========================

def regra_sn_sensor(ctx):
    if ctx.db is None:
        return None

    if (
        ctx.pdf.get("sn_sensor")
        and ctx.pdf["sn_sensor"] != ctx.db.get("sn_sensor")
    ):
        return ValidationIssue(
            key="sn_sensor",
            title="SN do Sensor divergente",
            message=(
                f"PDF: {ctx.pdf['sn_sensor']}\n"
                f"Banco: {ctx.db.get('sn_sensor')}"
            ),
            action=lambda: (
                atualizar_sn_sensor(ctx.db["tag"], ctx.pdf["sn_sensor"]),
                ctx.pdf.__setitem__("sn_atualizado", True)
            )
        )


# =========================
# REGRA 5 — RANGE
# =========================

def regra_range(ctx):
    if ctx.db is None or ctx.mvs:
        return None

    pdf_min = to_float(ctx.pdf.get("min_range"))
    pdf_max = to_float(ctx.pdf.get("max_range"))

    if pdf_min is None or pdf_max is None:
        return None

    db_min = to_float(ctx.db.get("min_range"))
    db_max = to_float(ctx.db.get("max_range"))

    ctx.pdf["min_range"] = pdf_min
    ctx.pdf["max_range"] = pdf_max
    ctx.db["min_range"] = db_min
    ctx.db["max_range"] = db_max

    if db_min is None or db_max is None:
        return ValidationIssue(
            key="range",
            title="Range ausente no banco",
            message=(
                f"PDF: {pdf_min} → {pdf_max}\n"
                "Banco: não cadastrado"
            ),
            action=lambda: (
                atualizar_range(ctx.db["tag"], pdf_min, pdf_max),
                ctx.pdf.__setitem__("range_atualizado", True)
            )
        )

    if pdf_min != db_min or pdf_max != db_max:
        return ValidationIssue(
            key="range",
            title="Range divergente",
            message=(
                f"PDF: {pdf_min} → {pdf_max}\n"
                f"Banco: {db_min} → {db_max}"
            ),
            action=lambda: (
                atualizar_range(ctx.db["tag"], pdf_min, pdf_max),
                ctx.pdf.__setitem__("range_atualizado", True)
            )
        )

    return None


# =========================
# REGRA 6 — HASTE (somente TE)
# =========================

def regra_haste_te(ctx):
    if "TE" not in ctx.pdf["tag"]:
        return None

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

    return None


# =========================
# REGRA 7 — LOCAL (FPSO / POLVO)
# =========================

def regra_local_fpso(ctx):
    local_pdf = normalizar_texto(ctx.pdf.get("local"))

    if not local_pdf:
        return ValidationIssue(
            key="local_ausente",
            title="Local não informado",
            message="O campo LOCAL não foi encontrado no PDF.",
            blocking=True
        )

    fpsos = {
        "FPSO FRADE": ["FPSO", "FRADE"],
        "FPSO FORTE": ["FPSO", "FORTE"],
        "FPSO BRAVO": ["FPSO", "BRAVO"],
        "POLVO": ["POLVO"]
    }

    for nome, palavras in fpsos.items():
        if all(p in local_pdf for p in palavras):
            ctx.fpso_identificado = nome
            return None

    return ValidationIssue(
        key="local_invalido",
        title="Local incompatível",
        message=(
            f"Local informado:\n{ctx.pdf.get('local')}\n\n"
            "Não corresponde a:\n"
            "- FPSO FRADE\n"
            "- FPSO FORTE\n"
            "- FPSO BRAVO\n"
            "- POLVO"
        ),
        blocking=True
    )