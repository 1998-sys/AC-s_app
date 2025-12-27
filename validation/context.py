class ValidationContext:
    def __init__(
        self,
        dados_pdf,
        registro,
        reg_sn,
        tag_base_pdf,
        tag_base_sn,
        pontos=None   # ← NOVO
    ):
        # ---- dados existentes (NÃO MUDAR) ----
        self.pdf = dados_pdf
        self.db = registro
        self.reg_sn = reg_sn

        self.tag_base_pdf = tag_base_pdf
        self.tag_base_sn = tag_base_sn

        self.mvs = False

        # ---- novo atributo ----
        self.pontos = pontos or []