class ValidationContext:
    def __init__(
        self,
        dados_pdf,
        registro,
        reg_sn,
        tag_base_pdf,
        tag_base_sn,
        pontos=None   
    ):
        
        self.pdf = dados_pdf
        self.db = registro
        self.reg_sn = reg_sn

        self.tag_base_pdf = tag_base_pdf
        self.tag_base_sn = tag_base_sn

        self.mvs = False

       
        self.pontos = pontos or []

        
        self.tipo = self._obter_tipo()

    def _obter_tipo(self):
        if not self.pontos:
            return None
        return self.pontos[0].get("tipo")