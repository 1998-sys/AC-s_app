# ----------------------------------------------------------------
# Project name  : AC's Generator (CertiFlow)
# Module        : pdf.parser_po_ER
# Created       : 23-02-2026
# Programmer(s) : Matheus Bandeira
# ----------------------------------------------------------------
# Remarks       : Parses orifice plate Evaluation Report (ER) PDFs, extracting dimensional measurement results (diameter, beta, thickness, roughness, flatness, bevel angle) and their accept/reject outcomes.
#                 Analisa PDFs de Relatório de Avaliação (ER) de placa de orifício, extraindo os resultados das medições dimensionais (diâmetro, beta, espessura, rugosidade, planeza, ângulo do chanfro) e seus resultados de aprovação/reprovação.
# ----------------------------------------------------------------
# Copyright (c) ODS Metering Systems
# ----------------------------------------------------------------

import re
from pdf.parser_er_common import extrair_numero_evaluation


def _resultado_aceite(resultado):
    """Translates the raw accept/reject result (EN/PT) to "Sim"/"Não".

    Args:
        resultado: String such as "Accepted", "Aceito", "Rejected" or "Reprovado".

    Returns:
        str: "Sim" if accepted, "Não" if rejected, or "NÃO ENCONTRADO" if
        `resultado` is empty or unrecognized.
    """
    if not resultado:
        return "NÃO ENCONTRADO"
    resultado = resultado.strip().lower()
    if resultado in ("accepted", "aceito"):
        return "Sim"
    if resultado in ("rejected", "reprovado"):
        return "Não"
    return "NÃO ENCONTRADO"


def resultado_diametro(texto):
    """Extracts the accept/reject result of the "Orifice Bore Diameter" measurement.

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _resultado_aceite.
    """
    texto = re.sub(r'\s+', ' ', texto)
    padrao = re.compile(
        r'Orifice\s+Bore\s+Diameter.*?Resultado\s*(Accepted|Aceito|Rejected|Reprovado)',
        re.IGNORECASE
    )

    match = padrao.search(texto)
    if match:
        return _resultado_aceite(match.group(1))

    return "NÃO ENCONTRADO"

def extrair_valores_d(texto_pdf: str):
    """Extracts the measured diameter values (e.g., "d1-1 = 50.12 mm") from the report.

    Args:
        texto_pdf: Text extracted from the ER report.

    Returns:
        dict: {identifier: value} with the value converted to decimal point
        (e.g., "50.12"); empty dict if no occurrence is found.
    """
    padrao = re.compile(
        r'\b(d\d+-\d+)\s*=\s*([\d,]+)\s*mm'
    )

    resultados = {
        identificador: valor.replace(',', '.')
        for identificador, valor in padrao.findall(texto_pdf)
    }

    return resultados


def extrair_beta(texto_pdf: str) -> str:
    """Extracts the calculated Beta (β) factor value of the orifice plate.

    Args:
        texto_pdf: Text extracted from the ER report.

    Returns:
        str: Beta factor value with decimal point, or empty string if the
        "β Factor ... Calculated Value:" pattern is not found.
    """
    padrao = re.compile(
        r'β\s*Factor.*?Calculated\s+Value:\s*([\d,]+)',
        re.DOTALL
    )

    match = padrao.search(texto_pdf)

    if match:
        return match.group(1).replace(',', '.')

    return ""

def resultado_beta(texto):
    """Extracts the accept/reject result of the Beta factor (β Factor/Fator Beta da Placa).

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _resultado_aceite.
    """
    texto = re.sub(r'\s+', ' ', texto)

    padrao = re.compile(
        r'(?:β\s*Factor|Beta\s*Factor|Fator\s*Beta\s*da\s*Placa)'
        r'.*?Resultado\s*(Accepted|Aceito|Rejected|Reprovado)',
        re.IGNORECASE
    )

    match = padrao.search(texto)
    if match:
        return _resultado_aceite(match.group(1))

    return "NÃO ENCONTRADO"

def resultado_circularidade(texto):
    """Extracts the accept/reject result of the circularity deviation of the orifice bore diameter.

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _resultado_aceite.
    """
    texto = re.sub(r'\s+', ' ', texto)

    padrao = re.compile(
        r'(?:Circularity\s+Deviation\s+of\s+Orifice\s+Bore\s+Diameter'
        r'|Desvio\s+de\s+Circularidade)'
        r'.*?Resultado\s*(Accepted|Aceito|Rejected|Reprovado)',
        re.IGNORECASE
    )

    match = padrao.search(texto)
    if match:
        return _resultado_aceite(match.group(1))

    return "NÃO ENCONTRADO"

def resultado_espessura(texto):
    """Extracts the accept/reject result of the thickness ("Flatness Deviation Thickness E").

    The section carries two "Resultado" results in sequence (flatness and
    thickness); this function captures the second one, referring to thickness.

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _resultado_aceite.
    """
    texto = re.sub(r'\s+', ' ', texto)

    padrao = re.compile(
        r'Flatness\s+Deviation\s+Thickness\s+E.*?'
        r'Resultado\s*(Accepted|Aceito|Rejected|Reprovado).*?'
        r'Resultado\s*(Accepted|Aceito|Rejected|Reprovado)',
        re.IGNORECASE
    )

    match = padrao.search(texto)
    if match:
        return _resultado_aceite(match.group(2))

    return "NÃO ENCONTRADO"

def extrair_valores_E(texto_pdf: str):
    """Extracts the measured thickness values at points E1, E3, E5, E7 (e.g., "E1 = 3.21 mm").

    Args:
        texto_pdf: Text extracted from the ER report.

    Returns:
        dict: {identifier: value} with the value converted to decimal point;
        empty dict if no occurrence is found.
    """
    padrao = re.compile(
        r'\b(E[1357])\s*=\s*([\d,]+)\s*mm'
    )

    resultados = {
        identificador: valor.replace(',', '.')
        for identificador, valor in padrao.findall(texto_pdf)
    }

    return resultados

def resultado_rugosidade(texto):
    """Extracts the accept/reject result of the upstream face roughness ("Upstream Face Roughness").

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _resultado_aceite.
    """
    texto = re.sub(r'\s+', ' ', texto)

    padrao = re.compile(
        r'Upstream\s+Face\s+Roughness.*?'
        r'Resultado\s*(Accepted|Aceito|Rejected|Reprovado)',
        re.IGNORECASE
    )

    match = padrao.search(texto)
    if match:
        return _resultado_aceite(match.group(1))

    return "NÃO ENCONTRADO"

def resultado_planeza(texto):
    """Extracts the accept/reject result of the flatness ("Flatness Deviation Thickness E").

    Unlike resultado_espessura, this captures the first "Resultado" of the
    section, referring to flatness.

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _resultado_aceite.
    """
    texto = re.sub(r'\s+', ' ', texto)

    padrao = re.compile(
        r'Flatness\s+Deviation\s+Thickness\s+E.*?'
        r'Resultado\s*(Accepted|Aceito|Rejected|Reprovado)',
        re.IGNORECASE
    )

    match = padrao.search(texto)
    if match:
        return _resultado_aceite(match.group(1))

    return "NÃO ENCONTRADO"

def resultado_angulo_chanfro(texto):
    """Extracts the accept/reject result of the bevel angle ("Orifice Plate Angled Bevel").

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _resultado_aceite.
    """

    texto = re.sub(r'\s+', ' ', texto)

    padrao = re.compile(
        r'Orifice\s+Plate\s+Angled\s+Bevel.*?'
        r'Resultado\s*(Accepted|Aceito|Rejected|Reprovado)',
        re.IGNORECASE
    )

    match = padrao.search(texto)
    if match:
        return _resultado_aceite(match.group(1))

    return "NÃO ENCONTRADO"

def extrair_angulo_gh(texto):
    """Extracts the G-H angle value (e.g., "G-H = 45.0") from the report.

    Args:
        texto: Text extracted from the ER report.

    Returns:
        str: Angle value with decimal point, or None if `texto` is empty
        or the pattern is not found.
    """
    if not texto:
        return None

    texto_limpo = texto.replace("\n", " ")

    padrao = re.search(
        r'G\s*[-–]?\s*H\s*=\s*([\d.,]+)',
        texto_limpo,
        re.IGNORECASE
    )

    if padrao:
        return padrao.group(1).strip().replace(",", ".")

    return None

def resultado_espessura_furo(texto):
    """Extracts the accept/reject result of the bore thickness ("Thickness 'e'").

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _resultado_aceite.
    """
    texto = re.sub(r'\s+', ' ', texto)

    padrao = re.compile(
        r'Thickness\s*\'e\'.*?Resultado\s*(Accepted|Aceito|Rejected|Reprovado)',
        re.IGNORECASE
    )

    match = padrao.search(texto)
    if match:
        return _resultado_aceite(match.group(1))

    return "NÃO ENCONTRADO"

def extrair_valores_e(texto_pdf: str):
    """Extracts the measured bore thickness values at points e1, e3, e5, e7 (e.g., "e1 = 3.21 mm").

    Args:
        texto_pdf: Text extracted from the ER report.

    Returns:
        dict: {identifier (lowercase): value (float)}; empty dict if no
        occurrence is found.
    """
    padrao = re.compile(
        r'\b(e[1357])\s*=\s*([\d.,]+)\s*mm',
        re.IGNORECASE
    )

    resultados = {
        identificador.lower(): float(valor.replace(',', '.'))
        for identificador, valor in padrao.findall(texto_pdf)
    }

    return resultados

def resultado_comp_cilin(texto):
    """Extracts the accept/reject result of the orifice cylinder length
    (label "Thickness 'e'" or "Comprimento do Cilindro do Orifício").

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _resultado_aceite.
    """
    texto = re.sub(r'\s+', ' ', texto)

    padrao = re.compile(
        r"(?:Thickness\s*'e'|Comprimento\s+do\s+Cilindro\s+do\s+Orif[ií]cio)"
        r".*?Resultado\s*(Accepted|Aceito|Rejected|Reprovado)",
        re.IGNORECASE
    )

    match = padrao.search(texto)
    if match:
        return _resultado_aceite(match.group(1))

    return "NÃO ENCONTRADO"

def resultado_montante(texto):
    """Extracts the accept/reject result of the upstream face roughness
    (label "Upstream Face Roughness" or "Rugosidade da Face a Montante da Placa").

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _resultado_aceite.
    """
    texto = re.sub(r'\s+', ' ', texto)

    padrao = re.compile(
        r'(?:Upstream\s+Face\s+Roughness|Rugosidade\s+da\s+Face\s+a\s+Montante\s+da\s+Placa)'
        r'.*?Resultado\s*(Accepted|Aceito|Rejected|Reprovado)',
        re.IGNORECASE
    )
    match = padrao.search(texto)
    if match:
        return _resultado_aceite(match.group(1))

    return "NÃO ENCONTRADO"

def resultado_angulo_face_montante(texto):
    """Extracts the accept/reject result of the upstream face angle.

    Notes:
        Uses the same regex as resultado_montante (label "Upstream Face
        Roughness"/"Rugosidade da Face a Montante da Placa"); kept as a
        separate function because it feeds a distinct key in extrair_campos_er.

    Returns:
        str: "Sim"/"Não"/"NÃO ENCONTRADO", see _resultado_aceite.
    """
    texto = re.sub(r'\s+', ' ', texto)

    padrao = re.compile(
        r"(?:Upstream\s+Face\s+Roughness"
        r"|Rugosidade\s+da\s+Face\s+a\s+Montante\s+da\s+Placa)"
        r".*?Resultado\s*(Accepted|Aceito|Rejected|Reprovado)",
        re.IGNORECASE
    )

    match = padrao.search(texto)
    if match:
        return _resultado_aceite(match.group(1))

    return "NÃO ENCONTRADO"

def extrair_campos_er(texto):
    """Builds the complete field dictionary of the orifice plate Evaluation Report (ER).

    Orchestrates every extractor in this module (ER number, diameter, Beta
    factor, circularity, thickness, roughness, flatness, bevel angle, G-H
    angle, bore thickness, cylinder length and upstream face angle).

    Args:
        texto: Text extracted from the ER report.

    Returns:
        dict: Report fields ready for use by the rest of the system
        (see the keys in the returned dict for the complete list).
    """
    num_er = extrair_numero_evaluation(texto)
    result_diam = resultado_diametro(texto)
    valores_diam = extrair_valores_d(texto)
    bt=extrair_beta(texto)
    result_bt = resultado_beta(texto)
    result_circ = resultado_circularidade(texto)
    result_esp= resultado_espessura(texto)
    valores_esp = extrair_valores_E(texto)
    result_rug = resultado_rugosidade(texto)
    resultado_plan = resultado_planeza(texto)
    ang_chanf = resultado_angulo_chanfro(texto)
    ang_gh = extrair_angulo_gh(texto)
    result_esp_furo = resultado_espessura_furo(texto)
    valores_esp_e = extrair_valores_e(texto)
    comp_cil = resultado_comp_cilin(texto)
    montante = resultado_montante(texto)
    ang_montante = resultado_angulo_face_montante(texto)

    return {
        'Numero_Evaluation': num_er,
        'Diametro_Interno': result_diam,
        'valores_d_interno': valores_diam,
        'Beta': bt,
        'resultado_beta': result_bt,
        'Circularidade': result_circ,
        'Espessura': result_esp,
        'Valores_Espessura': valores_esp,
        'Rugosidade': result_rug,
        'Planeza': resultado_plan,
        'Angulo_Chanfro': ang_chanf,
        'Angulo_GH': ang_gh,
        'Espessura_Furo': result_esp_furo,
        'Valores_Espessura_Furo': valores_esp_e,
        'Comprimento_Cilindro': comp_cil,
        'montante': montante,
        'angulo_face_montante': ang_montante
    }
