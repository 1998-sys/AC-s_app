# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : validation.issue
# Created       : 22-12-2025
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Defines the ValidationIssue class that represents a divergence detected during validation, along with its optional correction action.
#                 Define a classe ValidationIssue, que representa uma divergência detectada durante a validação, junto com sua ação de correção opcional.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

class ValidationIssue:
    def __init__(
        self,
        key,
        title,
        message,
        action=None,
        blocking=False,
        opcoes=None,
    ):
        """Represents a divergence found during validation, with its correction action and optional resolution options.

        Args:
            key: short identifier of the divergence.
            title: title shown to the user.
            message: detailed message shown to the user.
            action: callable to run in order to fix the divergence (applies the correction
                to the database), if any.
            blocking: if True, the divergence prevents AC generation until it is resolved.
            opcoes: optional list of dicts {"label", "valor", "recomendado"?} for the UI to
                show the resolution options side by side — the 1st option corresponds to
                applying `action`, the 2nd usually represents skipping the certificate
                without changing the registry.
        """
        self.key = key
        self.title = title
        self.message = message
        self.action = action
        self.blocking = blocking
        # Opcional: para divergências "PDF diz X, cadastro diz Y" — permite a
        # UI mostrar as duas opções lado a lado em vez de um botão genérico
        # "Aplicar correção". Formato: [{"label", "valor", "recomendado"?}, ...].
        # A 1ª opção corresponde a aplicar `action` (resolver_divergencia com
        # aplicar=True); a 2ª ("Pular certificado") não corrige o cadastro —
        # em lote, escolher essa opção pula o certificado inteiro em vez de
        # gerar a AC com um dado que ficaria divergente do cadastro.
        self.opcoes = opcoes