from data.utils_db import (
    buscar_instrumento_por_tag,
    atualizar_sn,
    atualizar_sn_sensor,
    atualizar_range,
    atualizar_sn_placa,
)

from gui.support import to_float_safe


class InstrumentService:
    """CRUD simples de instrumentos usado pela tela de editar/consultar instrumento."""

    def __init__(self, api):
        self.api = api

    def buscar_instrumento(self, tag):
        reg = buscar_instrumento_por_tag((tag or "").upper())
        if not reg:
            self.api.alert("Erro", "TAG não encontrada.", "error")
            return None
        return {
            "tipo": reg.get("tipo", "SEC"),
            "sn_instrumento": reg.get("sn_instrumento") or "",
            "sn_sensor": reg.get("sn_sensor") or "",
            "min_range": "" if reg.get("min_range") is None else reg["min_range"],
            "max_range": "" if reg.get("max_range") is None else reg["max_range"],
        }

    def salvar_instrumento(self, payload):
        tag = (payload.get("tag") or "").upper()
        if not tag:
            self.api.alert("Erro", "Informe a TAG.", "error")
            return False

        if payload.get("tipo") == "PO":
            atualizar_sn_placa(tag, payload.get("sn_instrumento", ""))
        else:
            min_r = to_float_safe(payload.get("min_range"))
            max_r = to_float_safe(payload.get("max_range"))
            if min_r is None or max_r is None:
                self.api.alert("Erro", "Ranges inválidos.", "error")
                return False
            atualizar_sn(tag, payload.get("sn_instrumento", ""))
            atualizar_sn_sensor(tag, payload.get("sn_sensor", ""))
            atualizar_range(tag, min_r, max_r)

        self.api.alert("Sucesso", "Dados salvos.", "success")
        return True
