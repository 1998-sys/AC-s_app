# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : processors.utils
# Created       : 17-03-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Implements the ORIGEM-specific flow that fills in AC number and location automatically or prompts the user when they are missing.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

def fluxo_origem(app, dados_certificado, callback):
    """Fills in the AC number and location automatically for ORIGEM
    clients, or prompts the user when they are not found.

    If the certificate's client is not ORIGEM, simply forwards the data
    unchanged. For ORIGEM clients, tries to obtain the AC number and
    location from a "Related Items" document (see
    `Api.dados_origem_automaticos`); if both are found, fills in the data
    automatically, otherwise requests manual input from the user.

    Args:
        app: Reference to the application, used to obtain automatic data
            or request manual input.
        dados_certificado: Certificate data; updated in-place with
            `n_ac` and `localizacao` when found automatically.
        callback: Function called with the final certificate data to
            continue the flow.
    """
    cliente = (dados_certificado.get("cliente") or "").strip().upper()

    if "ORIGEM" not in cliente:
        callback(dados_certificado)
        return

    # Location/AC No. can come from a separate "Related Items" document
    # (e.g., LDN-030.pdf) that the user chooses to include — see
    # Api.dados_origem_automaticos. Only asks for manual input when the
    # TAG is not found in that document (or the user doesn't include one).
    n_ac, localizacao = app.dados_origem_automaticos(dados_certificado.get("tag"))
    if n_ac and localizacao:
        dados_certificado["n_ac"] = n_ac
        dados_certificado["localizacao"] = localizacao
        callback(dados_certificado)
    else:
        app.solicitar_dados_origem(dados_certificado, callback)