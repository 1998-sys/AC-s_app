from form.utils_print_PRIO import gerar_ac_prio
from form.utils_print_ORIGEM import gerar_ac_origem


def gerar_ac_escolha(dados, caminho_pdf_atual):

    local = dados.get("local", "").upper()
    if "ENERGIA" in local:
        print(">>> GERANDO AC ORIGEM <<<")
        return gerar_ac_origem(dados, caminho_pdf_atual) 
    else:
        print(">>> GERANDO AC PRIO <<<")
        return gerar_ac_prio(dados, caminho_pdf_atual)
