from validation.rules import (
    regra_tag_vs_sn,
    regra_novo_instrumento,
    regra_sn_instrumento,
    regra_sn_sensor,
    regra_range,
    regra_haste_te,
    regra_local_fpso
)


class ValidationEngine:
    def __init__(self):
        self.rules = [
            regra_tag_vs_sn,
            regra_novo_instrumento,
            regra_sn_instrumento,
            regra_sn_sensor,
            regra_range,
            regra_haste_te,
            regra_local_fpso
        ]

    def run(self, context):
        issues = []

        for rule in self.rules:
            issue = rule(context)
            if issue:
                issues.append(issue)

        return issues