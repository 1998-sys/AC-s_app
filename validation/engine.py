from validation.rules import (
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

    # Futuras regras de placa
    # regra_beta_ratio,
    # regra_evaluation,
)


class ValidationEngine:
    def __init__(self):

        # 🔹 Reservado para o futuro
        self.common_rules = []

        # 🔹 Regras de secundário (seu conjunto atual)
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

        # 🔹 Regras exclusivas de placa
        self.placa_rules = [
            # adicionar aqui
        ]

    def run(self, context):
        issues = []

        # Sempre começa com common (mesmo vazio)
        rules_to_run = list(self.common_rules)

        # Seleção por tipo
        if context.tipo_instrumento == "placa_orificio":
            rules_to_run += self.placa_rules
        else:
            # fallback padrão = secundário
            rules_to_run += self.secundario_rules

        for rule in rules_to_run:
            issue = rule(context)
            if issue:
                issues.append(issue)

        return issues