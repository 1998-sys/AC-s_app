from form.utils_print_PRIO import gerar_ac_prio
from form.utils_print_PRIO_PO import gerar_ac_prio_po
from form.utils_print_ORIGEM import gerar_ac_origem
from form.utils_print_YINSON import gerar_ac_yinson
from form.utils_print_YINSON_ATLANTA import gerar_ac_yinson_atlanta
from form.utils_print_ORIGEM_PO import gerar_ac_origem_PO
from xml_model.xml_generator import gerar_xml_calibracao
from xml_model.xml_petro_generator import gerar_xml_certificado
from xml_model.xml_petro_po import gerar_xml_certificado_po, extrair_valores_medidos
from xml_model.xsd_validator import validar_xml, registrar_log
from xml_model.xml_petro_tr import gerar_xml_certificado_tr

from pathlib import Path
import os


def validar_e_logar(caminho_xml):
    """Valida o XML contra o XSD e, se inválido, remove o arquivo e grava um log de erros.
    Validates the XML against the XSD and, if invalid, deletes the file and writes an error log."""
    erros = validar_xml(caminho_xml)
    if erros:
        log = registrar_log(caminho_xml, erros)
        Path(caminho_xml).unlink(missing_ok=True)
        print(f"[XSD] {len(erros)} erro(s) — XML removido, ver {log}")
    else:
        print(f"[XSD] {Path(caminho_xml).name} válido.")


def obter_caminho_ac(dados, caminho_pdf_original):
    """Calcula o caminho de saída do PDF da AC sem gerá-lo.
    Computes the AC PDF output path without generating it."""
    pasta_saida = os.path.dirname(os.path.abspath(caminho_pdf_original))
    certificado = dados.get("certificado", "").replace(" ", "")
    tag_limpa = dados.get("tag", "").replace(" ", "")
    nome_pdf = f"{certificado}_{tag_limpa}_AC.pdf"
    return os.path.join(pasta_saida, nome_pdf)


def gerar_ac_escolha(dados, caminho_pdf_atual, dados_xml_prio, certificado_te, dados_xml_petro, dados_report):
    """Roteador principal: seleciona o gerador de AC e os XMLs conforme cliente e instrumento.
    Main router: selects the AC generator and XMLs based on client and instrument type.

    Dispatches to the correct template generator (ORIGEM, YINSON, YINSON ATLANTA, PRIO, PO variants)
    and handles XML generation and XSD validation before exporting the PDF.
    Returns the absolute path of the generated PDF."""
    cliente = dados.get("cliente", "").upper()
    local = dados.get("local", "").upper()
    instrumento = dados.get("instrumento", "").upper()

    if "ORIGEM ENERGIA ALAGOAS S.A." in cliente and instrumento == "PLACA DE ORIFICIO":
        print('placa origem')
        caminho_saida = Path(caminho_pdf_atual).with_suffix(".xml")

        gerar_xml_certificado_po(
            informacoes=dados,
            valores_medidos=extrair_valores_medidos(caminho_pdf_atual),
            valores_er=dados_report,
            caminho_saida=caminho_saida
        )
        return gerar_ac_origem_PO(dados, caminho_pdf_atual)

    elif "ORIGEM ENERGIA ALAGOAS S.A." in cliente:
        print(">>> GERANDO AC ORIGEM <<<")
        dados_pdf = dados
        caminho_xml = Path(caminho_pdf_atual).with_suffix(".xml")
        gerar_xml_certificado(dados_pdf, dados_xml_petro, caminho_xml)
        validar_e_logar(caminho_xml)
        return gerar_ac_origem(dados_pdf, caminho_pdf_atual, dados_xml_petro)
    
    elif "YINSON" in cliente and "atlanta" not in local.lower():
        print(">>> GERANDO AC YINSON <<<")
        dados_pdf = dados
        caminho_xml = Path(caminho_pdf_atual).with_suffix(".xml")
        gerar_xml_certificado(dados_pdf, dados_xml_petro, caminho_xml)
        validar_e_logar(caminho_xml)
        return gerar_ac_yinson(dados_pdf, caminho_pdf_atual)
    
    elif "YINSON" in cliente and local == "FPSO ATLANTA":
        print(">>> GERANDO AC YINSON - FPSO ATLANTA <<<")
        dados_pdf = dados
        caminho_xml = Path(caminho_pdf_atual).with_suffix(".xml")
        gerar_xml_certificado(dados_pdf, dados_xml_petro, caminho_xml)
        validar_e_logar(caminho_xml)
        return gerar_ac_yinson_atlanta(dados_pdf, caminho_pdf_atual)
    
    elif "PRIO" in cliente and instrumento == "PLACA DE ORIFICIO":
        print('placa prio')
        caminho_saida = Path(caminho_pdf_atual).with_suffix(".xml")

        gerar_xml_certificado_po(
            informacoes=dados,
            valores_medidos=extrair_valores_medidos(caminho_pdf_atual),
            valores_er=dados_report,
            caminho_saida=caminho_saida
        )

        return gerar_ac_prio_po(dados, caminho_pdf_atual)
    
    elif "PRIO" in cliente and dados.get("instrumento", "").upper() == "GAS METER RUN":
        print(">>> GERANDO XML TRECHO RETO (PRIO) <<<")
        print(dados)
        caminho_xml = Path(caminho_pdf_atual).with_suffix(".xml")
        gerar_xml_certificado_tr(dados, dados_report, caminho_xml)
        # AC PDF ainda não implementado

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
        return gerar_ac_prio(dados_pdf, caminho_pdf_atual)

        