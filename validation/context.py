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

        self.mvs = False

    def _obter_tipo(self):

        
        if self.tipo_instrumento:
            return self.tipo_instrumento

       
        if isinstance(self.pontos_calibracao, list) and self.pontos_calibracao:
            return self.pontos_calibracao[0].get("tipo")

        return None