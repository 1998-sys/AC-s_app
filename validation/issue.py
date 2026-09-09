# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : validation.issue
# Created       : 22-12-2025
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Defines the ValidationIssue class that represents a divergence detected during validation, along with its optional correction action.
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
        # Optional: for divergences "PDF says X, registry says Y" — lets the
        # UI show both options side by side instead of a generic
        # "Apply correction" button. Format: [{"label", "valor", "recomendado"?}, ...].
        # The 1st option corresponds to applying `action` (resolver_divergencia with
        # aplicar=True); the 2nd ("Skip certificate") does not fix the registry —
        # in batch mode, choosing this option skips the whole certificate instead of
        # generating the AC with data that would remain divergent from the registry.
        self.opcoes = opcoes