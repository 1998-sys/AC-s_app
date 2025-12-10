"""
import pdfplumber
import re
import xml.etree.ElementTree as ET
import os


def extrair_tabela_calibracao(caminho_pdf):
    tabelas_encontradas = []

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            tables = pagina.extract_tables()
            for t in tables:
                # descartar tabelas muito pequenas ou sem números
                if t and len(t) > 2:
                    tabelas_encontradas.append(t)

    if not tabelas_encontradas:
        return None

    # ---------- Identificar tipo pelo conteúdo ----------
    texto_completo = ""
    with pdfplumber.open(caminho_pdf) as pdf:
        for p in pdf.pages:
            texto_completo += p.extract_text() + "\n"

    # ---- Caso PRESSÃO = possui 2 tabelas e palavras como "kPa", "mA DC" ----
    if "kPa" in texto_completo and len(tabelas_encontradas) >= 2:
        return {
            "tipo": "pressao",
            "tabela": tabelas_encontradas[1]  # segunda tabela
        }

    # ---- Caso TEMPERATURA = normalmente apenas 1 tabela ----
    if ("°C" in texto_completo or "Omega" in texto_completo or "Ω" in texto_completo) \
        and len(tabelas_encontradas) >= 1:
        return {
            "tipo": "temperatura",
            "tabela": tabelas_encontradas[0]
        }

    # fallback genérico
    return {
        "tipo": "desconhecido",
        "tabela": tabelas_encontradas[-1]
    }

def extrair_equacao_curva_calibracao(caminho_pdf):
    # regex melhorada: aceita negativos, vírgula, ponto, espaços, etc.
    padrao = r"y\s*=\s*([-+]?[0-9\.,]+)\s*\+\s*([-+]?[0-9\.,]+)\s*[\.\*]\s*x"
    texto = ""

    # Ler texto completo do PDF
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            t = pagina.extract_text()
            if t:
                texto += t + "\n"

    # Normalizar texto para evitar problemas
    texto = texto.replace("−", "-")  # caso use símbolo unicode de menos

    match = re.search(padrao, texto)
    if not match:
        return {
            "equacao_str": None,
            "intercepto_a": None,
            "coeficiente_b": None
        }

    # Extrair valores
    a = match.group(1).replace(".", "").replace(",", ".")
    b = match.group(2).replace(".", "").replace(",", ".")

    return {
        "equacao_str": f"y = {a} + {b} * x",
        "intercepto_a": float(a),
        "coeficiente_b": float(b),
    }

def aplicar_equacao_pressao(tabela, a, b):
    nova_tabela = []

    # Cabeçalho
    cabecalho = tabela[0]

    # Identificar colunas de interesse
    idx_ma = None
    colunas_divididas = []  # lista de colunas que possuem valores com "/"

    for i, col in enumerate(cabecalho):
        col_lower = col.lower()

        # coluna de média das leituras em mA
        if ("média das leitura" in col_lower or 
            "average reading" in col_lower or 
            "mA" in col_lower) and idx_ma is None:
            idx_ma = i

        # colunas de tendência ou incerteza
        if "tendência" in col_lower or "deviation" in col_lower:
            colunas_divididas.append(i)

        if "incerteza" in col_lower or "uncertainty" in col_lower:
            colunas_divididas.append(i)

    # Renomear coluna de mA
    if idx_ma is not None:
        cabecalho[idx_ma] = "kPa (calculado pela curva)"

    nova_tabela.append(cabecalho)

    # Processar linhas
    for linha in tabela[1:]:
        nova_linha = linha.copy()

        # 1) Converter mA → kPa pela equação
        if idx_ma is not None:
            valor_ma = linha[idx_ma].replace(",", ".")
            try:
                y = float(valor_ma)
                x = (y - a) / b  # inversão da curva
                nova_linha[idx_ma] = f"{x:.3f}".replace(".", ",")
            except:
                nova_linha[idx_ma] = linha[idx_ma]

        # 2) Extrair somente valores após "/" nas colunas de tendência e incerteza
        for col in colunas_divididas:
            valor = linha[col]
            if "/" in valor:
                try:
                    parte_kpa = valor.split("/")[-1].strip()
                    nova_linha[col] = parte_kpa
                except:
                    pass

        nova_tabela.append(nova_linha)

    return nova_tabela

def formatar_local(local: str) -> str:
    if not local:
        return ""

    palavras = local.strip().split()

    # primeira sigla totalmente em maiúsculas
    primeira = palavras[0].upper()

    # demais palavras com apenas inicial maiúscula
    restantes = [p.capitalize() for p in palavras[1:]]

    return " ".join([primeira] + restantes)

def limpar_certificado(cert: str) -> str:
    if not cert:
        return cert
    
    # Remove espaços em volta dos hífens
    cert = re.sub(r'\s*-\s*', '-', cert)
    
    # Remove espaços duplicados restantes
    cert = re.sub(r'\s+', ' ', cert).strip()

    return cert

def formatar_range(valor):
    
    Converte valores numéricos de range para string com vírgula no lugar do ponto.
    Aceita float, int ou string numérica.
    Retorna None se o valor for inválido.
    
    if valor is None:
        return None

    try:
        # Converte para float (aceita número ou string)
        numero = float(str(valor).replace(",", "."))
        # Formata trocando ponto por vírgula
        return str(numero).replace(".", ",")
    except:
        return None

def gerar_xml(dados, tipo,caminho_pdf):
    
    Gera um XML baseado no modelo base.xml sobrescrevendo os valores
    do cabeçalho com base no dicionário 'dados'.

    O arquivo final será salvo na mesma pasta do PDF.
    
    tb_cal=extrair_tabela_calibracao(caminho_pdf=caminho_pdf)
    print(tb_cal)
    cv_cal=extrair_equacao_curva_calibracao(caminho_pdf=caminho_pdf)
    print(cv_cal)
    tb_for=aplicar_equacao_pressao(tb_cal["tabela"], cv_cal["intercepto_a"], cv_cal["coeficiente_b"])
    print(tb_for)


    # Caminho do XML base (tem que estar na mesma pasta do script)
    caminho_base = os.path.join(os.path.dirname(__file__), "base.xml")

    if not os.path.exists(caminho_base):
        raise FileNotFoundError(f"Arquivo base.xml não encontrado em: {caminho_base}")

    # Carregar o XML base
    tree = ET.parse(caminho_base)
    root = tree.getroot()

    # Preenchimento do cabeçalho
    root.find("NroCertificado").text = limpar_certificado(dados.get("certificado", ""))
    root.find("FechaDeCalibracion").text = dados.get("data", "")
    root.find("FechaEmisionCertificado").text = dados.get("report_date", "")
    root.find("Instalacao").text = formatar_local(dados.get("local", ""))
    root.find("TAG").text = dados.get("tag", "")

    root.find('Tipo').text = tipo

    # Serial (se existir)
    serial = dados.get("sn_instrumento")
    root.find("Serial").text = serial if serial else ""

    # Faixa (range)
    min_r = formatar_range(dados.get("min_range"))
    max_r = formatar_range(dados.get("max_range"))
    root.find("FajaInicial").text = str(min_r) if min_r else "0"
    root.find("FajaFinal").text = str(max_r) if max_r else "0"




    # Salvar XML no mesmo local do PDF
    pasta_pdf = os.path.dirname(caminho_pdf)
    nome_xml = dados.get("certificado", "calibracao").replace(" ", "_") + ".xml"
    caminho_saida = os.path.join(pasta_pdf, nome_xml)

    tree.write(caminho_saida, encoding="utf-8", xml_declaration=True)

    return caminho_saida


resultado=extrair_tabela_calibracao('assets\\25-ODS-53-PRE-480 PIT-3020-51.pdf')


print(resultado["tipo"])
for linha in resultado["tabela"]:
    print(linha)
print()

eq=extrair_equacao_curva_calibracao('assets\\25-ODS-53-PRE-480 PIT-3020-51.pdf')
print(eq)
print(')

nova_tabela=aplicar_equacao_pressao(resultado["tabela"], eq["intercepto_a"], eq["coeficiente_b"])
for linha in nova_tabela:
    print(linha)
"""