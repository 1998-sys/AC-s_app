# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : validation.context
# Created       : 22-12-2025
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Bundles the PDF-extracted data, the database record and calibration points into a single context object passed to validation rules.
#                 Reúne os dados extraídos do PDF, o registro do banco e os pontos de calibração em um único objeto de contexto passado às regras de validação.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

class ValidationContext:
    def __init__(
        self,
        dados_pdf,
        registro,
        reg_sn,
        tag_base_pdf,
        tag_base_sn,
        pontos=None,
        tipo_instrumento=None,
        dados_report=None,
        valores_medidos=None
    ):
        """Builds the validation context from the PDF-extracted data, the database record and the calibration points.

        Args:
            dados_pdf: data extracted from the PDF certificate.
            registro: instrument record in the database (by TAG), or None if not registered.
            reg_sn: instrument record in the database (by serial number), used when there
                is no match by TAG.
            tag_base_pdf: base TAG extracted from the PDF, used in comparisons that ignore suffixes.
            tag_base_sn: base TAG of the record found by serial number.
            pontos: list of calibration points (default: empty list).
            tipo_instrumento: instrument type, when already known; if omitted, it is
                inferred from the first calibration point.
            dados_report: Evaluation Report data, when applicable (orifice plates).
            valores_medidos: measured values associated with the certificate, when applicable.
        """
        self.pdf = dados_pdf
        self.db = registro
        self.reg_sn = reg_sn

        self.tag_base_pdf = tag_base_pdf
        self.tag_base_sn = tag_base_sn

        self.pontos_calibracao = pontos or []
        self.tipo_instrumento = tipo_instrumento

        self.tipo = self._obter_tipo()

        self.report = dados_report
        self.valores_medidos = valores_medidos

    def _obter_tipo(self):
        """Resolves the instrument type: uses `tipo_instrumento` if provided, otherwise the type of the first calibration point."""


        if self.tipo_instrumento:
            return self.tipo_instrumento

       
        if isinstance(self.pontos_calibracao, list) and self.pontos_calibracao:
            return self.pontos_calibracao[0].get("tipo")

        return None