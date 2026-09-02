# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : form.utils_print
# Created       : 10-12-2025
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Routes AC generation by client and instrument type, driving XML generation, XSD validation and the matching PDF template.
#                 Roteia a geração da AC por cliente e tipo de instrumento, orquestrando a geração de XML, a validação XSD e o template de PDF correspondente.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

from form.utils_print_PRIO_PO import gerar_ac_prio_po
from form.utils_print_ORIGEM import gerar_ac_origem
from form.full_ac_templates import gerar_ac_prio, gerar_ac_yinson, gerar_ac_yinson_atlanta
from form.po_templates import gerar_ac_origem_PO, gerar_ac_yinson_PO, gerar_ac_yinson_atlanta_PO
from xml_model.xml_generator import gerar_xml_calibracao
from xml_model.xml_petro_generator import gerar_xml_certificado
from xml_model.xml_petro_po import gerar_xml_certificado_po, extrair_valores_medidos
from xml_model.xsd_validator import validar_xml, registrar_log
from xml_model.xml_petro_tr import gerar_xml_certificado_tr

from pathlib import Path
import os


def validar_e_logar(caminho_xml):
    """Validates the XML against the XSD; if invalid, removes the file and writes an error log.

    Args:
        caminho_xml: Path of the XML to validate.
    """
    erros = validar_xml(caminho_xml)
    if erros:
        log = registrar_log(caminho_xml, erros)
        Path(caminho_xml).unlink(missing_ok=True)
        print(f"[XSD] {len(erros)} erro(s) — XML removido, ver {log}")
    else:
        print(f"[XSD] {Path(caminho_xml).name} válido.")


def obter_caminho_ac(dados, caminho_pdf_original):
    """Computes the AC PDF output path without generating it.

    Args:
        dados: Certificate fields (uses "certificado" and "tag").
        caminho_pdf_original: Path of the source PDF, used to determine the
            output folder.

    Returns:
        str: Absolute path the AC PDF would have, following the pattern
        "{certificado}_{tag}_AC.pdf".
    """
    pasta_saida = os.path.dirname(os.path.abspath(caminho_pdf_original))
    certificado = dados.get("certificado", "").replace(" ", "")
    tag_limpa = dados.get("tag", "").replace(" ", "")
    nome_pdf = f"{certificado}_{tag_limpa}_AC.pdf"
    return os.path.join(pasta_saida, nome_pdf)


def gerar_ac_escolha(dados, caminho_pdf_atual, dados_xml_prio, certificado_te, dados_xml_petro, dados_report, dados_dim_tr=None, excel=None):
    """Main router: selects the AC generator and the XMLs based on client and instrument.

    Dispatches to the correct template generator (ORIGEM, YINSON, YINSON
    ATLANTA, PRIO and the PO variants) and handles XML generation and XSD
    validation before exporting the PDF.

    Args:
        dados: Certificate fields (client, location, instrument, etc.).
        caminho_pdf_atual: Path of the source PDF (calibration report).
        dados_xml_prio: Data used in generating the standard PRIO XML.
        certificado_te: Associated thermoresistance certificate (PRIO flow).
        dados_xml_petro: Data used in generating the Petrobras XML.
        dados_report: Values extracted from the report, used in the orifice
            plate XMLs.
        dados_dim_tr: Straight-run pipe dimensions, required only in the
            "GAS METER RUN" flow.
        excel: Already-open Excel COM instance (reused across a batch),
            passed through to the chosen generator.

    Returns:
        The absolute path of the generated PDF, or None when the flow does
        not yet generate a PDF (the "GAS METER RUN" case, whose straight-run
        XML is sufficient for now).
    """
    cliente = dados.get("cliente", "").upper()
    local = dados.get("local", "").upper()
    instrumento = dados.get("instrumento", "").upper()
    

    if "ORIGEM ENERGIA ALAGOAS S.A." in cliente and instrumento == "PLACA DE ORIFICIO":
        caminho_saida = Path(caminho_pdf_atual).with_suffix(".xml")

        gerar_xml_certificado_po(
            informacoes=dados,
            valores_medidos=extrair_valores_medidos(caminho_pdf_atual),
            valores_er=dados_report,
            caminho_saida=caminho_saida
        )
        return gerar_ac_origem_PO(dados, caminho_pdf_atual, excel=excel)
    
    elif instrumento == "GAS METER RUN":
        print(">>> GERANDO XML TRECHO RETO (PRIO) <<<")
        print(dados)
        print(dados_dim_tr)
        caminho_xml = Path(caminho_pdf_atual).with_suffix(".xml")
        gerar_xml_certificado_tr(dados, dados_dim_tr, caminho_xml)
        #validar_e_logar(caminho_xml)
        # AC PDF ainda não implementado
        return

    elif "ORIGEM ENERGIA ALAGOAS S.A." in cliente:
        print(">>> GERANDO AC ORIGEM <<<")
        dados_pdf = dados
        caminho_xml = Path(caminho_pdf_atual).with_suffix(".xml")
        gerar_xml_certificado(dados_pdf, dados_xml_petro, caminho_xml)
        validar_e_logar(caminho_xml)
        return gerar_ac_origem(dados_pdf, caminho_pdf_atual, dados_xml_petro, excel=excel)
    
    if "YINSON" in cliente and instrumento == "PLACA DE ORIFICIO" and "ATLANTA" in local:
        print(">>> GERANDO AC YINSON ATLANTA PLACA <<<")
        caminho_saida = Path(caminho_pdf_atual).with_suffix(".xml")

        gerar_xml_certificado_po(
            informacoes=dados,
            valores_medidos=extrair_valores_medidos(caminho_pdf_atual),
            valores_er=dados_report,
            caminho_saida=caminho_saida
        )
        return gerar_ac_yinson_atlanta_PO(dados, caminho_pdf_atual, excel=excel)

    if "YINSON" in cliente and instrumento == "PLACA DE ORIFICIO":
        print(">>> GERANDO AC YINSON PLACA <<<")
        caminho_saida = Path(caminho_pdf_atual).with_suffix(".xml")

        gerar_xml_certificado_po(
            informacoes=dados,
            valores_medidos=extrair_valores_medidos(caminho_pdf_atual),
            valores_er=dados_report,
            caminho_saida=caminho_saida
        )
        return gerar_ac_yinson_PO(dados, caminho_pdf_atual, excel=excel)
    
    elif "YINSON" in cliente and "atlanta" not in local.lower():
        print(">>> GERANDO AC YINSON <<<")
        dados_pdf = dados
        caminho_xml = Path(caminho_pdf_atual).with_suffix(".xml")
        gerar_xml_certificado(dados_pdf, dados_xml_petro, caminho_xml)
        validar_e_logar(caminho_xml)
        return gerar_ac_yinson(dados_pdf, caminho_pdf_atual, excel=excel)
    
    elif "YINSON" in cliente and local == "FPSO ATLANTA":
        print(">>> GERANDO AC YINSON - FPSO ATLANTA <<<")
        dados_pdf = dados
        caminho_xml = Path(caminho_pdf_atual).with_suffix(".xml")
        gerar_xml_certificado(dados_pdf, dados_xml_petro, caminho_xml)
        validar_e_logar(caminho_xml)
        return gerar_ac_yinson_atlanta(dados_pdf, caminho_pdf_atual, excel=excel)
    
    elif "PRIO" in cliente and instrumento == "PLACA DE ORIFICIO":
        print('placa prio')
        caminho_saida = Path(caminho_pdf_atual).with_suffix(".xml")

        gerar_xml_certificado_po(
            informacoes=dados,
            valores_medidos=extrair_valores_medidos(caminho_pdf_atual),
            valores_er=dados_report,
            caminho_saida=caminho_saida
        )

        return gerar_ac_prio_po(dados, caminho_pdf_atual, excel=excel)
    
    elif "PRIO" in cliente:
        print(">>> GERANDO AC PRIO <<<")
        dados_pdf = dados
        xml_destino_padrao = Path(caminho_pdf_atual).with_suffix(".xml")
        xml_destino_petro  = Path(caminho_pdf_atual).with_name(f"{Path(caminho_pdf_atual).stem}_petro.xml")

        gerar_xml_calibracao(
            dados_pdf,
            dados_xml_prio,
            xml_destino_padrao,
            certificado_te
        )
        gerar_xml_certificado(
            dados_pdf,
            dados_xml_petro,
            xml_destino_petro,
        )
        validar_e_logar(xml_destino_petro)
        return gerar_ac_prio(dados_pdf, caminho_pdf_atual, excel=excel)

        