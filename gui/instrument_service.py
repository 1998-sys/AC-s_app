# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : gui.instrument_service
# Created       : 24-08-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Implements the lookup and save logic for the instrument registration/edit screen.
#                 Implementa a busca e o salvamento da tela de cadastro/edição de instrumento.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import getpass
from datetime import datetime

from data.utils_db import (
    buscar_instrumento_por_tag,
    atualizar_sn,
    atualizar_sn_sensor,
    atualizar_range,
    atualizar_sn_placa,
    atualizar_dados_cadastro,
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
            "data_calibracao": reg.get("data_calibracao") or "",
            "proxima_calibracao": reg.get("proxima_calibracao") or "",
            "numero_certificado": reg.get("numero_certificado") or "",
            "laboratorio": reg.get("laboratorio") or "",
            "observacoes": reg.get("observacoes") or "",
            "modificado_por": reg.get("modificado_por") or "",
            "modificado_em": reg.get("modificado_em") or "",
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

        modificado_em = datetime.now().strftime("%d/%m/%Y %H:%M")
        atualizar_dados_cadastro(
            tag,
            data_calibracao=payload.get("data_calibracao", ""),
            proxima_calibracao=payload.get("proxima_calibracao", ""),
            numero_certificado=payload.get("numero_certificado", ""),
            laboratorio=payload.get("laboratorio", ""),
            observacoes=payload.get("observacoes", ""),
            modificado_por=getpass.getuser(),
            modificado_em=modificado_em,
        )

        self.api.alert("Sucesso", "Dados salvos.", "success")
        return {"modificado_por": getpass.getuser(), "modificado_em": modificado_em}
