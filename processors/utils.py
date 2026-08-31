# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : processors.utils
# Created       : 17-03-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Implements the ORIGEM-specific flow that fills in AC number and location automatically or prompts the user when they are missing.
#                 Implementa o fluxo específico do cliente ORIGEM que preenche o número da AC e a localização automaticamente ou solicita ao usuário quando estiverem ausentes.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

def fluxo_origem(app, dados_certificado, callback):
    cliente = (dados_certificado.get("cliente") or "").strip().upper()

    if "ORIGEM" not in cliente:
        callback(dados_certificado)
        return

    # Localização/Nº AC podem vir de um documento "Itens Relacionados"
    # separado (ex.: LDN-030.pdf) que o usuário escolhe incluir — ver
    # Api.dados_origem_automaticos. Só pede preenchimento manual quando
    # não encontrar a TAG nesse documento (ou o usuário não incluir um).
    n_ac, localizacao = app.dados_origem_automaticos(dados_certificado.get("tag"))
    if n_ac and localizacao:
        dados_certificado["n_ac"] = n_ac
        dados_certificado["localizacao"] = localizacao
        callback(dados_certificado)
    else:
        app.solicitar_dados_origem(dados_certificado, callback)