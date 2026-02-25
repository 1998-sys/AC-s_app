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

    # Futuras regras de placa
    # regra_beta_ratio,
    # regra_evaluation,
)


class ValidationEngine:
    def __init__(self):

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
        
        ]

    def run(self, context):
        issues = []

        
        rules_to_run = list(self.common_rules)

      
        if context.tipo_instrumento == "placa_orificio":
            rules_to_run += self.placa_rules
        else:
            
            rules_to_run += self.secundario_rules

        for rule in rules_to_run:
            issue = rule(context)
            if issue:
                issues.append(issue)

        return issues