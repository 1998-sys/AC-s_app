def fluxo_origem(app, dados_certificado, callback):
    cliente = (dados_certificado.get("cliente") or "").strip().upper()

    if "ORIGEM" in cliente:
        app.solicitar_dados_origem(dados_certificado, callback)
    else:
        callback(dados_certificado)