import re
from pdf.extrator import extrair_texto
from xml_model.xml_generator import normalizar_certificado




def resultado_diametro(texto):
    texto = re.sub(r'\s+', ' ', texto)
    padrao = re.compile(
        r'Orifice\s+Bore\s+Diameter.*?Resultado\s*(Accepted|Aceito|Rejected|Reprovado)',
        re.IGNORECASE
    )

    match = padrao.search(texto)

    if match:
        resultado = match.group(1)

        if resultado.lower() in ["accepted", "aceito"]:
            return "Sim"
        elif resultado.lower() in ["rejected", "reprovado"]:
            return "Não"

        return resultado.upper()

    return "NÃO ENCONTRADO"

def extrair_valores_d(texto_pdf: str):

    padrao = re.compile(
        r'\b(d\d+-\d+)\s*=\s*([\d,]+)\s*mm'
    )

    resultados = {
        identificador: valor.replace(',', '.')
        for identificador, valor in padrao.findall(texto_pdf)
    }

    return resultados





def extrair_numero_evaluation(texto_pdf: str):
    padrao = re.compile(
        r'(?:RELATÓRIO\s+DE\s+AVALIAÇÃO\s+)?N[º°\.0]?\s*([A-Z0-9\- ]+?)\s*-?\s*ER\b',
        flags=re.IGNORECASE
    )

    match = padrao.search(texto_pdf)

    if match:
        numero = match.group(1).strip()
        numero = normalizar_certificado(numero)
        return numero

    return None


def extrair_beta(texto_pdf: str) -> str:
    padrao = re.compile(
        r'β\s*Factor.*?Calculated\s+Value:\s*([\d,]+)',
        re.DOTALL
    )

    match = padrao.search(texto_pdf)

    if match:
        return match.group(1).replace(',', '.')

    return ""
    
def resultado_circularidade(texto):
    texto = re.sub(r'\s+', ' ', texto)

    padrao = re.compile(
        r'(?:Circularity\s+Deviation\s+of\s+Orifice\s+Bore\s+Diameter'
        r'|Desvio\s+de\s+Circularidade)'
        r'.*?Resultado\s*(Accepted|Aceito|Rejected|Reprovado)',
        re.IGNORECASE
    )

    match = padrao.search(texto)

    if match:
        resultado = match.group(1)

        if resultado.lower() in ["accepted", "aceito"]:
            return "Sim"
        elif resultado.lower() in ["rejected", "reprovado"]:
            return "Não"

        return resultado.upper()

    return "NÃO ENCONTRADO"

def resultado_espessura(texto):

    texto = re.sub(r'\s+', ' ', texto)

    padrao = re.compile(
        r'Flatness\s+Deviation\s+Thickness\s+E.*?'
        r'Resultado\s*(Accepted|Aceito|Rejected|Reprovado).*?'
        r'Resultado\s*(Accepted|Aceito|Rejected|Reprovado)',
        re.IGNORECASE
    )

    match = padrao.search(texto)

    if match:
        resultado = match.group(2)

        if resultado.lower() in ["accepted", "aceito"]:
            return "Sim"
        elif resultado.lower() in ["rejected", "reprovado"]:
            return "Não"

        return resultado.upper()

    return "NÃO ENCONTRADO"

def extrair_valores_E(texto_pdf: str):
    padrao = re.compile(
        r'\b(E[1357])\s*=\s*([\d,]+)\s*mm'
    )

    resultados = {
        identificador: valor.replace(',', '.')
        for identificador, valor in padrao.findall(texto_pdf)
    }

    return resultados

def resultado_rugosidade(texto):
    texto = re.sub(r'\s+', ' ', texto)

    padrao = re.compile(
        r'β\s*Factor\s+Upstream\s+Face\s+Roughness.*?'
        r'Resultado\s*(Accepted|Aceito|Rejected|Reprovado).*?'
        r'Resultado\s*(Accepted|Aceito|Rejected|Reprovado)',
        re.IGNORECASE
    )

    match = padrao.search(texto)

    if match:
        # Segundo resultado é o da rugosidade
        resultado = match.group(2)

        if resultado.lower() in ["accepted", "aceito"]:
            return "Sim"
        elif resultado.lower() in ["rejected", "reprovado"]:
            return "Não"

        return resultado.upper()

    return "NÃO ENCONTRADO"

def resultado_planeza(texto):

    texto = re.sub(r'\s+', ' ', texto)

    padrao = re.compile(
        r'Flatness\s+Deviation\s+Thickness\s+E.*?'
        r'Resultado\s*(Accepted|Aceito|Rejected|Reprovado)',
        re.IGNORECASE
    )

    match = padrao.search(texto)

    if match:
        resultado = match.group(1)

        if resultado.lower() in ["accepted", "aceito"]:
            return "Sim"
        elif resultado.lower() in ["rejected", "reprovado"]:
            return "Não"

        return resultado.upper()

    return "NÃO ENCONTRADO"

def resultado_angulo_chanfro(texto):

    
    texto = re.sub(r'\s+', ' ', texto)

    padrao = re.compile(
        r'Orifice\s+Plate\s+Angled\s+Bevel.*?'
        r'Resultado\s*(Accepted|Aceito|Rejected|Reprovado)',
        re.IGNORECASE
    )

    match = padrao.search(texto)

    if match:
        resultado = match.group(1)

        if resultado.lower() in ["accepted", "aceito"]:
            return "Sim"
        elif resultado.lower() in ["rejected", "reprovado"]:
            return "Não"

        return resultado.upper()

    return "NÃO ENCONTRADO"

def extrair_angulo_gh(texto):
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
    texto = re.sub(r'\s+', ' ', texto)

    padrao = re.compile(
        r'Thickness\s*\'e\'.*?Resultado\s*(Accepted|Aceito|Rejected|Reprovado)',
        re.IGNORECASE
    )

    match = padrao.search(texto)

    if match:
        resultado = match.group(1)

        if resultado.lower() in ["accepted", "aceito"]:
            return "Sim"
        elif resultado.lower() in ["rejected", "reprovado"]:
            return "Não"

        return resultado.upper()

    return "NÃO ENCONTRADO"


def extrair_valores_e(texto_pdf: str):
    padrao = re.compile(
        r'\b(e[1357])\s*=\s*([\d.,]+)\s*mm',
        re.IGNORECASE
    )

    resultados = {
        identificador.lower(): float(valor.replace(',', '.'))
        for identificador, valor in padrao.findall(texto_pdf)
    }

    return resultados


    return resultados

def extrair_campos_er(texto):
    num_er = extrair_numero_evaluation(texto)
    result_diam = resultado_diametro(texto)
    valores_diam = extrair_valores_d(texto)
    bt=extrair_beta(texto)
    result_circ = resultado_circularidade(texto)
    result_esp= resultado_espessura(texto)
    valores_esp = extrair_valores_E(texto)
    result_rug = resultado_rugosidade(texto)
    resultado_plan = resultado_planeza(texto)
    ang_chanf = resultado_angulo_chanfro(texto)
    ang_gh = extrair_angulo_gh(texto)
    result_esp_furo = resultado_espessura_furo(texto)
    valores_esp_e = extrair_valores_e(texto)
   
    return {
        'Numero_Evaluation': num_er,
        'Diametro_Interno': result_diam,
        'valores_d_interno': valores_diam,
        'Beta': bt,
        'Circularidade': result_circ,
        'Espessura': result_esp,
        'Valores_Espessura': valores_esp,
        'Rugosidade': result_rug,
        'Planeza': resultado_plan,
        'Angulo_Chanfro': ang_chanf,
        'Angulo_GH': ang_gh,
        'Espessura_Furo': result_esp_furo,
        'Valores_Espessura_Furo': valores_esp_e
    }



