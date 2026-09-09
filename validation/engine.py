# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : validation.engine
# Created       : 22-12-2025
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Runs the applicable set of validation rules against a context and collects the resulting divergence issues, choosing the rule set based on instrument type.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import traceback

from validation.issue import ValidationIssue
from validation.rules_sec import (
    regra_tag_vs_sn,
    regra_novo_instrumento,
    regra_sn_instrumento,
    regra_sn_sensor,
    regra_range,
    regra_haste_te,
    regra_local_fpso,
    regra_rangein,
    regra_incert_fidu,
    regra_cmc,
    regra_classe,
    data_proxcal,
    prazo_emissao,
)

from validation.rules_po import (
    regra_nova_placa,
    comparar_evaluation_certificado,
    validar_parametros_report
)


class ValidationEngine:
    def __init__(self):
        """Builds the validation rule sets and the mapping from instrument type to the rule set to apply."""

        self.common_rules = []

        self.secundario_rules = [
            regra_tag_vs_sn,
            regra_novo_instrumento,
            regra_sn_instrumento,
            regra_sn_sensor,
            regra_range,
            regra_haste_te,
            regra_local_fpso,
            regra_rangein,
            regra_incert_fidu,
            regra_cmc,
            regra_classe,
            data_proxcal,
            prazo_emissao
        ]

   
        self.placa_rules = [
            regra_nova_placa,
            comparar_evaluation_certificado,
            validar_parametros_report
        ]

        self.trecho_rules = [
            # rules for Gas Meter Run will be added here in the future
        ]

        # secundario_rules is the default set: covers a missing "instrumento" or
        # any value that isn't one of the types with their own rules below.
        self._regras_por_instrumento = {
            "Gas Meter Run": self.trecho_rules,
            "Placa de Orificio": self.placa_rules,
        }

    def run(self, context):
        """Runs, against `context`, the rule set corresponding to the PDF's instrument and collects the divergences found.

        Args:
            context: ValidationContext instance holding the data to validate.

        Returns:
            list[ValidationIssue]: divergences found (one per rule that returned something
            other than None).

        Notes:
            If a rule raises an exception, it does not stop the others: it is recorded as
            its own blocking ValidationIssue (`erro_regra_<nome>`) and validation continues.
        """
        issues = []

        instrumento = context.pdf.get("instrumento")
        rules_to_run = list(self.common_rules) + self._regras_por_instrumento.get(
            instrumento, self.secundario_rules
        )

        for rule in rules_to_run:
            nome_regra = getattr(rule, "__name__", "desconhecida")
            try:
                issue = rule(context)
            except Exception as exc:
                traceback.print_exc()
                issues.append(ValidationIssue(
                    key=f"erro_regra_{nome_regra}",
                    title="Erro ao executar regra de validação",
                    message=(
                        f"A regra '{nome_regra}' falhou durante a validação: {exc}\n\n"
                        "As demais divergências continuam sendo exibidas normalmente. "
                        "Verifique os dados do certificado antes de prosseguir."
                    ),
                    blocking=True
                ))
                continue

            if issue:
                issues.append(issue)

        return issues