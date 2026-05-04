"""
Gera PDF de documentação do AC's Generator com:
  - Fluxo principal (imagem via mermaid.ink)
  - Tabela de regras de validação
  - Clientes e templates suportados
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
# Conteúdo Mermaid
# ---------------------------------------------------------------------------

MERMAID_PRINCIPAL = """
flowchart TD
    A([Usuário seleciona PDF]) --> B[pdf/utils_parser.py\\nselect_extract]
    B --> C{Tipo detectado}

    C -->|CI| D[xml_uc_generator\\ngerar_xml_uc]
    C -->|Cromatografia| E[xml_cromato\\nxml_cromatografia]
    C -->|secundario / placa_orificio / trecho| F[core/dispatcher.py\\ndispatch]

    D --> Z([Finalizado — apenas XML])
    E --> Z

    F --> G[core/processor_factory.py\\nget_processor]

    G -->|secundario| H[SecundarioProcessor]
    G -->|placa_orificio| I[PlacaProcessor]
    G -->|trecho| TR[TrechoProcessor]

    H --> J[Extrair pontos de calibração\\nxml_extractor + xml_table_extractor]
    I --> K[Solicitar Evaluation Report\\nparser_po_ER]
    TR --> TRK[Solicitar Evaluation Report\\nparser_tr_ER]

    J --> L{Cliente ORIGEM?}
    K --> L
    TRK --> TRL{Cliente ORIGEM?}

    L -->|Sim| M[Modal: Localização / SAP / N° AC]
    L -->|Não| N[app.processar_comparacao]
    M --> N

    TRL -->|Sim| TRM[Modal: Localização / SAP / N° AC]
    TRL -->|Não| TRN[app.processar_comparacao]
    TRM --> TRN

    N --> O[validation/engine.py\\nValidationEngine.run]
    TRN --> O

    O --> P{Issues encontradas?}

    P -->|Bloqueante| Q([Erro exibido — geração cancelada])
    P -->|Ação disponível| R[Usuário confirma correção automática]
    P -->|Aviso ou sem issues| S[Exibe aviso e continua]
    R --> S
    S --> T[form/utils_print.py\\ngerar_ac_escolha]

    T --> U{Cliente + Instrumento}

    U -->|ORIGEM + PO| V[gerar_xml_certificado_po\\ngerar_ac_origem_PO]
    U -->|ORIGEM| W[gerar_xml_certificado\\ngerar_ac_origem]
    U -->|YINSON ATLANTA| X1[gerar_xml_certificado\\ngerar_ac_yinson_atlanta]
    U -->|YINSON| X2[gerar_xml_certificado\\ngerar_ac_yinson]
    U -->|PRIO + PO| Y[gerar_xml_certificado_po\\ngerar_ac_prio_po]
    U -->|PRIO + Gas Meter Run| TR2[xml_petro_tr.py\\ngerar_xml_certificado_tr\\n⚠ AC PDF pendente]
    U -->|PRIO| Z2[gerar_xml_calibracao\\ngerar_xml_certificado\\ngerar_ac_prio]

    V --> VAL[xsd_validator\\nvalidar_e_logar]
    W --> VAL
    X1 --> VAL
    X2 --> VAL
    Y --> VAL
    Z2 --> VAL

    TR2 --> TRFIM([XML gerado — sem validação XSD por ora])

    VAL -->|Inválido| ERR[XML removido + .log gerado]
    VAL -->|Válido| PDF[Excel template → PDF da AC\\nvia Excel COM]

    PDF --> FIM([AC gerada com sucesso])
"""

MERMAID_XSD = """
flowchart TD
    A[XML gerado em xml_model/] --> B[form/utils_print.py\\nvalidar_e_logar]
    B --> C[xml_model/xsd_validator.py\\nvalidar_xml]
    C --> D[Carrega PetrobrasSchemaV3.0.0.xsd\\nvia lxml XMLSchema]
    D --> E{XML válido?}
    E -->|Sim| F[Imprime: arquivo válido\\nXML mantido]
    E -->|Não| G[registrar_log\\nGrava .log com erros]
    G --> H[XML removido com unlink]
    H --> I([Erros visíveis no .log\\nna mesma pasta do PDF])
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def mermaid_to_png_bytes(mermaid_code: str) -> bytes | None:
    """Converte código Mermaid para PNG via mermaid.ink."""
    encoded = base64.urlsafe_b64encode(mermaid_code.strip().encode("utf-8")).decode("utf-8")
    url = f"https://mermaid.ink/img/{encoded}?bgColor=ffffff&width=1400"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.URLError as exc:
        print(f"[AVISO] Não foi possível buscar imagem do mermaid.ink: {exc}")
        return None


def png_bytes_to_rl_image(png_bytes: bytes, max_width: float, max_height: float) -> Image | None:
    """Converte bytes PNG para Image do reportlab respeitando proporção."""
    try:
        pil = PILImage.open(io.BytesIO(png_bytes))
        w_px, h_px = pil.size
        scale = min(max_width / w_px, max_height / h_px)
        return Image(io.BytesIO(png_bytes), width=w_px * scale, height=h_px * scale)
    except Exception as exc:
        print(f"[AVISO] Falha ao processar imagem: {exc}")
        return None


# ---------------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------------

def build_styles():
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
# Tabelas de dados
# ---------------------------------------------------------------------------

VALIDATION_RULES = [
    ("regra_tag_vs_sn",       "Divergência entre TAG e SN (detecção MVS)"),
    ("regra_novo_instrumento","Instrumento não cadastrado → oferta de inserção automática"),
    ("regra_sn_instrumento",  "SN do instrumento difere do cadastro"),
    ("regra_sn_sensor",       "SN do sensor difere do cadastro"),
    ("regra_range",           "Faixa de calibração difere do cadastro"),
    ("regra_haste_te",        "Validação de haste do sensor TE"),
    ("regra_local_fpso",      "Localização FPSO inconsistente"),
    ("regra_rangein",         "Range indicado vs range de calibração"),
    ("regra_incert_fidu",     "Incerteza / erro fiducial fora do limite"),
    ("regra_cmc",             "CMC (Capability Measurement Capability)"),
    ("regra_classe",          "Classe do instrumento"),
    ("data_proxcal",          "Data da próxima calibração"),
    ("prazo_emissao",         "Prazo de emissão do certificado"),
]

CLIENTS_TEMPLATES = [
    ("ORIGEM Energia Alagoas", "Secundário",        "TemplateAC_ORIGEM.xlsx",          "xml_petro_generator.py",              "✓"),
    ("ORIGEM Energia Alagoas", "Placa de Orifício", "TemplateAC_PO_ORIGEM.xlsx",       "xml_petro_po.py",                     "✓"),
    ("PRIO",                   "Secundário",        "TemplateAC_PRIO.xlsx",            "xml_generator.py + xml_petro_generator.py", "✓"),
    ("PRIO",                   "Placa de Orifício", "TemplateAC_PO_PRIO.xlsx",         "xml_petro_po.py",                     "✓"),
    ("PRIO",                   "Gas Meter Run",     "—",                               "xml_petro_tr.py",                     "pendente"),
    ("YINSON",                 "Secundário",        "TemplateAC_YINSON.xlsx",          "xml_petro_generator.py",              "✓"),
    ("YINSON (FPSO Atlanta)",  "Secundário",        "TemplateAC_YINSON - ATLANTA.xlsx","xml_petro_generator.py",              "✓"),
]


def make_validation_table():
    header = ["Regra", "O que verifica"]
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
    header = ["Cliente", "Instrumento", "Template Excel", "Gerador XML", "AC PDF"]
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

    # Célula "pendente" em laranja (linha 5, coluna 4)
    for i, row in enumerate(CLIENTS_TEMPLATES, start=1):
        if row[-1] == "pendente":
            style.append(("TEXTCOLOR", (-1, i), (-1, i), colors.HexColor("#e07b00")))
            style.append(("FONTNAME",  (-1, i), (-1, i), "Helvetica-Oblique"))

    tbl.setStyle(TableStyle(style))
    return tbl


# ---------------------------------------------------------------------------
# Geração do PDF
# ---------------------------------------------------------------------------

def gerar_pdf(output_path: str = "Documentacao_ACs_Generator.pdf"):
    title_s, subtitle_s, section_s, note_s, normal_s = build_styles()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="AC's Generator — Documentação",
        author="ODS Metering Systems",
    )

    PAGE_W = A4[0] - 4 * cm   # largura útil
    PAGE_H = A4[1] - 4 * cm

    story = []

    # ── Cabeçalho ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph("AC's Generator", title_s))
    story.append(Paragraph("Documentação Técnica — Fluxo Principal · Regras · Clientes", subtitle_s))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#16213e")))
    story.append(Spacer(1, 0.4 * cm))

    # ── Fluxo Principal ────────────────────────────────────────────────────
    story.append(Paragraph("1. Fluxo Principal — PDF → AC + XML", section_s))
    story.append(Paragraph(
        "A partir de um certificado de calibração em PDF, o sistema detecta o tipo de instrumento, "
        "extrai os dados, valida contra o banco de dados e os schemas XSD, e gera o XML Petrobras "
        "junto com o PDF da Análise Crítica.",
        normal_s,
    ))
    story.append(Spacer(1, 0.3 * cm))

    print("Buscando fluxograma principal no mermaid.ink...")
    png = mermaid_to_png_bytes(MERMAID_PRINCIPAL)
    if png:
        rl_img = png_bytes_to_rl_image(png, PAGE_W, PAGE_H * 0.85)
        if rl_img:
            story.append(rl_img)
        else:
            story.append(Paragraph("[Imagem não pôde ser renderizada]", note_s))
    else:
        story.append(Paragraph(
            "[Fluxograma indisponível — sem conexão com mermaid.ink]", note_s
        ))

    # ── Fluxo Validação XSD ───────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("2. Fluxo de Validação XSD", section_s))
    story.append(Paragraph(
        "Após a geração do XML, o arquivo é validado contra o schema <i>PetrobrasSchemaV3.0.0.xsd</i>. "
        "Em caso de erro, o XML é removido e um <code>.log</code> é gerado na mesma pasta do PDF.",
        normal_s,
    ))
    story.append(Spacer(1, 0.3 * cm))

    print("Buscando fluxograma XSD no mermaid.ink...")
    png_xsd = mermaid_to_png_bytes(MERMAID_XSD)
    if png_xsd:
        rl_img_xsd = png_bytes_to_rl_image(png_xsd, PAGE_W, PAGE_H * 0.45)
        if rl_img_xsd:
            story.append(rl_img_xsd)

    story.append(Paragraph(
        "Nota: o fluxo de Gas Meter Run ainda não passa pela validação XSD — "
        "o XML é gerado diretamente para testes.",
        note_s,
    ))

    # ── Regras de Validação ────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("3. Regras de Validação — Instrumentos Secundários", section_s))
    story.append(Paragraph(
        "O motor de validação (<code>validation/engine.py</code>) executa as regras abaixo. "
        "Cada regra pode retornar um aviso, uma ação corretiva ou um bloqueio de geração.",
        normal_s,
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(make_validation_table())

    # ── Clientes e Templates ───────────────────────────────────────────────
    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph("4. Clientes e Templates Suportados", section_s))
    story.append(Paragraph(
        "Cada combinação cliente × instrumento possui um template Excel dedicado "
        "e um gerador XML específico. A coluna <i>AC PDF</i> indica se a geração "
        "do PDF está implementada (✓) ou pendente.",
        normal_s,
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(make_clients_table())

    # ── Rodapé informativo ─────────────────────────────────────────────────
    story.append(Spacer(1, 0.6 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#aaaaaa")))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "ODS Metering Systems · AC's Generator · Documentação gerada automaticamente",
        ParagraphStyle("footer", parent=normal_s, fontSize=8,
                       textColor=colors.HexColor("#999999"), alignment=TA_CENTER),
    ))

    doc.build(story)
    print(f"\nPDF gerado: {output_path}")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    gerar_pdf()