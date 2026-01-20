from form.utils_print_PRIO import gerar_ac_prio
from form.utils_print_ORIGEM import gerar_ac_origem
from form.utils_print_YINSON import gerar_ac_yinson


def gerar_ac_escolha(dados, caminho_pdf_atual):
    dados_pdf = dados

    cliente = dados.get("cliente", "").upper()
    if "ORIGEM ENERGIA ALAGOAS S.A." in cliente:
        print(">>> GERANDO AC ORIGEM <<<")
        dados_pdf = dados
        return gerar_ac_origem(dados_pdf, caminho_pdf_atual) 
    elif "YINSON" in cliente :
        print(">>> GERANDO AC YINSON <<<")
        dados_pdf = dados
        return gerar_ac_yinson(dados_pdf, caminho_pdf_atual)
    elif "PRIO" in cliente:
        print(">>> GERANDO AC PRIO <<<")
        return gerar_ac_prio(dados_pdf, caminho_pdf_atual)