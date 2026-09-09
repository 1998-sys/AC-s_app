# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : gerar_documentacao_pdf
# Created       : 04-05-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Builds a PDF technical documentation booklet for the AC's Generator, rendering flowcharts and reference tables of validation rules and supported client templates.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

"""
Generates the AC's Generator documentation PDF with:
  - Main flow (image via mermaid.ink)
  - Validation rules table
  - Supported clients and templates
"""

import base64
import io
import urllib.request
import urllib.error
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from PIL import Image as PILImage

# ---------------------------------------------------------------------------
# Mermaid content
# ---------------------------------------------------------------------------

MERMAID_PRINCIPAL = """
flowchart TD
    A([User selects PDF]) --> B[pdf/utils_parser.py\\nselect_extract]
    B --> C{Detected type}

    C -->|CI| D[xml_uc_generator\\ngerar_xml_uc]
    C -->|Chromatography| E[xml_cromato\\nxml_cromatografia]
    C -->|secundario / placa_orificio / trecho| F[core/dispatcher.py\\ndispatch]

    D --> Z([Finished — XML only])
    E --> Z

    F --> G[core/processor_factory.py\\nget_processor]

    G -->|secundario| H[SecundarioProcessor]
    G -->|placa_orificio| I[PlacaProcessor]
    G -->|trecho| TR[TrechoProcessor]

    H --> J[Extract calibration points\\nxml_extractor + xml_table_extractor]
    I --> K[Request Evaluation Report\\nparser_po_ER]
    TR --> TRK[Request Evaluation Report\\nparser_tr_ER]

    J --> L{ORIGEM client?}
    K --> L
    TRK --> TRL{ORIGEM client?}

    L -->|Yes| M[Modal: Location / SAP / AC No.]
    L -->|No| N[app.processar_comparacao]
    M --> N

    TRL -->|Yes| TRM[Modal: Location / SAP / AC No.]
    TRL -->|No| TRN[app.processar_comparacao]
    TRM --> TRN

    N --> O[validation/engine.py\\nValidationEngine.run]
    TRN --> O

    O --> P{Issues found?}

    P -->|Blocking| Q([Error displayed — generation cancelled])
    P -->|Action available| R[User confirms automatic correction]
    P -->|Warning or no issues| S[Displays warning and continues]
    R --> S
    S --> T[form/utils_print.py\\ngerar_ac_escolha]

    T --> U{Client + Instrument}

    U -->|ORIGEM + PO| V[gerar_xml_certificado_po\\ngerar_ac_origem_PO]
    U -->|ORIGEM| W[gerar_xml_certificado\\ngerar_ac_origem]
    U -->|YINSON ATLANTA| X1[gerar_xml_certificado\\ngerar_ac_yinson_atlanta]
    U -->|YINSON| X2[gerar_xml_certificado\\ngerar_ac_yinson]
    U -->|PRIO + PO| Y[gerar_xml_certificado_po\\ngerar_ac_prio_po]
    U -->|PRIO + Gas Meter Run| TR2[xml_petro_tr.py\\ngerar_xml_certificado_tr\\n⚠ AC PDF pending]
    U -->|PRIO| Z2[gerar_xml_calibracao\\ngerar_xml_certificado\\ngerar_ac_prio]

    V --> VAL[xsd_validator\\nvalidar_e_logar]
    W --> VAL
    X1 --> VAL
    X2 --> VAL
    Y --> VAL
    Z2 --> VAL

    TR2 --> TRFIM([XML generated — no XSD validation for now])

    VAL -->|Invalid| ERR[XML removed + .log generated]
    VAL -->|Valid| PDF[Excel template → AC PDF\\nvia Excel COM]

    PDF --> FIM([AC generated successfully])
"""

MERMAID_XSD = """
flowchart TD
    A[XML generated in xml_model/] --> B[form/utils_print.py\\nvalidar_e_logar]
    B --> C[xml_model/xsd_validator.py\\nvalidar_xml]
    C --> D[Loads PetrobrasSchemaV3.0.0.xsd\\nvia lxml XMLSchema]
    D --> E{Valid XML?}
    E -->|Yes| F[Prints: valid file\\nXML kept]
    E -->|No| G[registrar_log\\nWrites .log with errors]
    G --> H[XML removed via unlink]
    H --> I([Errors visible in the .log\\nin the same folder as the PDF])
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def mermaid_to_png_bytes(mermaid_code: str) -> bytes | None:
    """Render a Mermaid diagram as a PNG by calling the external mermaid.ink service.

    Args:
        mermaid_code: Diagram source code in Mermaid format.

    Returns:
        bytes | None: Bytes of the rendered PNG, or None if the request to mermaid.ink fails
        (e.g., no internet connection).
    """
    encoded = base64.urlsafe_b64encode(mermaid_code.strip().encode("utf-8")).decode("utf-8")
    url = f"https://mermaid.ink/img/{encoded}?bgColor=ffffff&width=1400"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.URLError as exc:
        print(f"[WARNING] Could not fetch image from mermaid.ink: {exc}")
        return None


def png_bytes_to_rl_image(png_bytes: bytes, max_width: float, max_height: float) -> Image | None:
    """Convert PNG bytes into a reportlab Image, resized to fit the given limits without distorting the original aspect ratio.

    Args:
        png_bytes: Binary content of the PNG to convert.
        max_width: Maximum width available in the document (same unit used by reportlab).
        max_height: Maximum height available in the document (same unit used by reportlab).

    Returns:
        Image | None: Flowable ready to insert into the document, or None if the PNG cannot be processed.
    """
    try:
        pil = PILImage.open(io.BytesIO(png_bytes))
        w_px, h_px = pil.size
        scale = min(max_width / w_px, max_height / h_px)
        return Image(io.BytesIO(png_bytes), width=w_px * scale, height=h_px * scale)
    except Exception as exc:
        print(f"[WARNING] Failed to process image: {exc}")
        return None


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def build_styles():
    """Build the paragraph styles (title, subtitle, section, note) used in the documentation PDF.

    Returns:
        tuple: (title, subtitle, section, note, normal) — ParagraphStyle instances ready to use,
        in that order.
    """
    base = getSampleStyleSheet()

    title = ParagraphStyle(
        "DocTitle",
        parent=base["Title"],
        fontSize=22,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1a2e"),
        alignment=TA_CENTER,
    )
    subtitle = ParagraphStyle(
        "Subtitle",
        parent=base["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#555555"),
        alignment=TA_CENTER,
        spaceAfter=20,
    )
    section = ParagraphStyle(
        "Section",
        parent=base["Heading1"],
        fontSize=14,
        textColor=colors.HexColor("#16213e"),
        spaceBefore=18,
        spaceAfter=8,
        borderPad=4,
    )
    note = ParagraphStyle(
        "Note",
        parent=base["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#666666"),
        leftIndent=12,
        italic=True,
    )
    return title, subtitle, section, note, base["Normal"]


# ---------------------------------------------------------------------------
# Data tables
# ---------------------------------------------------------------------------

VALIDATION_RULES = [
    ("regra_tag_vs_sn",       "Mismatch between TAG and SN (MVS detection)"),
    ("regra_novo_instrumento","Instrument not registered → offers automatic insertion"),
    ("regra_sn_instrumento",  "Instrument SN differs from the registered record"),
    ("regra_sn_sensor",       "Sensor SN differs from the registered record"),
    ("regra_range",           "Calibration range differs from the registered record"),
    ("regra_haste_te",        "TE sensor rod validation"),
    ("regra_local_fpso",      "Inconsistent FPSO location"),
    ("regra_rangein",         "Indicated range vs. calibration range"),
    ("regra_incert_fidu",     "Uncertainty / fiducial error out of limit"),
    ("regra_cmc",             "CMC (Capability Measurement Capability)"),
    ("regra_classe",          "Instrument class"),
    ("data_proxcal",          "Next calibration date"),
    ("prazo_emissao",         "Certificate issuance deadline"),
]

CLIENTS_TEMPLATES = [
    ("ORIGEM Energia Alagoas", "Secondary",       "TemplateAC_ORIGEM.xlsx",          "xml_petro_generator.py",              "✓"),
    ("ORIGEM Energia Alagoas", "Orifice Plate",   "TemplateAC_PO_ORIGEM.xlsx",       "xml_petro_po.py",                     "✓"),
    ("PRIO",                   "Secondary",       "TemplateAC_PRIO.xlsx",            "xml_generator.py + xml_petro_generator.py", "✓"),
    ("PRIO",                   "Orifice Plate",   "TemplateAC_PO_PRIO.xlsx",         "xml_petro_po.py",                     "✓"),
    ("PRIO",                   "Gas Meter Run",   "—",                               "xml_petro_tr.py",                     "pending"),
    ("YINSON",                 "Secondary",       "TemplateAC_YINSON.xlsx",          "xml_petro_generator.py",              "✓"),
    ("YINSON (FPSO Atlanta)",  "Secondary",       "TemplateAC_YINSON - ATLANTA.xlsx","xml_petro_generator.py",              "✓"),
]


def make_validation_table():
    """Build the reportlab table with the validation rules and what each one checks (from VALIDATION_RULES).

    Returns:
        Table: Already-styled reportlab table, ready to insert into the document's story.
    """
    header = ["Rule", "What it checks"]
    data = [header] + list(VALIDATION_RULES)

    col_widths = [5.5 * cm, 12 * cm]
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#16213e")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  10),
        ("ALIGN",        (0, 0), (-1, 0),  "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f0f4ff"), colors.white]),
        ("FONTNAME",     (0, 1), (0, -1),  "Courier"),
        ("FONTSIZE",     (0, 1), (-1, -1), 9),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ]))
    return tbl


def make_clients_table():
    """Build the reportlab table of supported clients, instruments and templates (from CLIENTS_TEMPLATES), highlighting rows marked "pendente" in orange.

    Returns:
        Table: Already-styled reportlab table, ready to insert into the document's story.
    """
    header = ["Client", "Instrument", "Excel Template", "XML Generator", "AC PDF"]
    data = [header] + list(CLIENTS_TEMPLATES)

    col_widths = [4.2 * cm, 3.2 * cm, 5.0 * cm, 5.3 * cm, 1.8 * cm]
    tbl = Table(data, colWidths=col_widths, repeatRows=1)

    style = [
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#16213e")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  9),
        ("ALIGN",        (0, 0), (-1, 0),  "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f0f4ff"), colors.white]),
        ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 1), (-1, -1), 8),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("ALIGN",        (-1, 1), (-1, -1), "CENTER"),
    ]

    # "pending" cell in orange (row 5, column 4)
    for i, row in enumerate(CLIENTS_TEMPLATES, start=1):
        if row[-1] == "pending":
            style.append(("TEXTCOLOR", (-1, i), (-1, i), colors.HexColor("#e07b00")))
            style.append(("FONTNAME",  (-1, i), (-1, i), "Helvetica-Oblique"))

    tbl.setStyle(TableStyle(style))
    return tbl


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

def gerar_pdf(output_path: str = "docs/Documentacao_ACs_Generator.pdf"):
    """Generate the AC's Generator technical documentation PDF, with flowcharts (via mermaid.ink), validation rules and the supported clients/templates table, and save it to disk.

    Args:
        output_path: Path of the PDF file to generate (default: "docs/Documentacao_ACs_Generator.pdf",
            relative to the current directory).

    Notes:
        Requires an internet connection to render the Mermaid flowcharts via mermaid.ink;
        if the request fails, the PDF is still generated, with a note reporting that the
        image is unavailable.
    """
    title_s, subtitle_s, section_s, note_s, normal_s = build_styles()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="AC's Generator — Documentation",
        author="ODS Metering Systems",
    )

    PAGE_W = A4[0] - 4 * cm   # usable width
    PAGE_H = A4[1] - 4 * cm

    story = []

    # ── Header ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph("AC's Generator", title_s))
    story.append(Paragraph("Technical Documentation — Main Flow · Rules · Clients", subtitle_s))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#16213e")))
    story.append(Spacer(1, 0.4 * cm))

    # ── Main Flow ────────────────────────────────────────────────────
    story.append(Paragraph("1. Main Flow — PDF → AC + XML", section_s))
    story.append(Paragraph(
        "Starting from a PDF calibration certificate, the system detects the instrument type, "
        "extracts the data, validates it against the database and the XSD schemas, and generates "
        "the Petrobras XML along with the Critical Analysis (AC) PDF.",
        normal_s,
    ))
    story.append(Spacer(1, 0.3 * cm))

    print("Fetching main flowchart from mermaid.ink...")
    png = mermaid_to_png_bytes(MERMAID_PRINCIPAL)
    if png:
        rl_img = png_bytes_to_rl_image(png, PAGE_W, PAGE_H * 0.85)
        if rl_img:
            story.append(rl_img)
        else:
            story.append(Paragraph("[Image could not be rendered]", note_s))
    else:
        story.append(Paragraph(
            "[Flowchart unavailable — no connection to mermaid.ink]", note_s
        ))

    # ── XSD Validation Flow ───────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("2. XSD Validation Flow", section_s))
    story.append(Paragraph(
        "After the XML is generated, the file is validated against the <i>PetrobrasSchemaV3.0.0.xsd</i> schema. "
        "If an error occurs, the XML is removed and a <code>.log</code> file is generated in the same folder as the PDF.",
        normal_s,
    ))
    story.append(Spacer(1, 0.3 * cm))

    print("Fetching XSD flowchart from mermaid.ink...")
    png_xsd = mermaid_to_png_bytes(MERMAID_XSD)
    if png_xsd:
        rl_img_xsd = png_bytes_to_rl_image(png_xsd, PAGE_W, PAGE_H * 0.45)
        if rl_img_xsd:
            story.append(rl_img_xsd)

    story.append(Paragraph(
        "Note: the Gas Meter Run flow does not yet go through XSD validation — "
        "the XML is generated directly for testing.",
        note_s,
    ))

    # ── Validation Rules ────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("3. Validation Rules — Secondary Instruments", section_s))
    story.append(Paragraph(
        "The validation engine (<code>validation/engine.py</code>) runs the rules below. "
        "Each rule can return a warning, a corrective action, or a generation block.",
        normal_s,
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(make_validation_table())

    # ── Clients and Templates ───────────────────────────────────────────────
    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph("4. Supported Clients and Templates", section_s))
    story.append(Paragraph(
        "Each client × instrument combination has a dedicated Excel template "
        "and a specific XML generator. The <i>AC PDF</i> column indicates whether the "
        "PDF generation is implemented (✓) or pending.",
        normal_s,
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(make_clients_table())

    # ── Informative footer ─────────────────────────────────────────────────
    story.append(Spacer(1, 0.6 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#aaaaaa")))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "ODS Metering Systems · AC's Generator · Automatically generated documentation",
        ParagraphStyle("footer", parent=normal_s, fontSize=8,
                       textColor=colors.HexColor("#999999"), alignment=TA_CENTER),
    ))

    doc.build(story)
    print(f"\nPDF generated: {output_path}")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    gerar_pdf()
