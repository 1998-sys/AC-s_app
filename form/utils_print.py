from form.utils_print_PRIO import gerar_ac_prio
from form.utils_print_ORIGEM import gerar_ac_origem
from form.utils_print_YINSON import gerar_ac_yinson
from xml_model.xml_generator import gerar_xml_calibracao
from xml_model.xml_petro_generator import gerar_xml_certificado
from pathlib import Path

def gerar_ac_escolha(dados, caminho_pdf_atual, dados_xml_prio, certificado_te, dados_xml_petro):
    dados_pdf = dados

    cliente = dados.get("cliente", "").upper()
    if "ORIGEM ENERGIA ALAGOAS S.A." in cliente:
        print(">>> GERANDO AC ORIGEM <<<")
        dados_pdf = dados
        return gerar_ac_origem(dados_pdf, caminho_pdf_atual) 
    elif "YINSON" in cliente :
        print(">>> GERANDO AC YINSON <<<")
        dados_pdf = dados
        gerar_xml_certificado(
                        dados_pdf,
                        dados_xml_petro,
                        Path(caminho_pdf_atual).with_suffix(".xml"),
                    )
        return gerar_ac_yinson(dados_pdf, caminho_pdf_atual)
    elif "PRIO" in cliente:
        print(">>> GERANDO AC PRIO <<<")
        gerar_xml_calibracao(
                        dados_pdf,
                        dados_xml_prio,
                        Path(caminho_pdf_atual).with_suffix(".xml"),
                        certificado_te
                    )
        return gerar_ac_prio(dados_pdf, caminho_pdf_atual)
    

        