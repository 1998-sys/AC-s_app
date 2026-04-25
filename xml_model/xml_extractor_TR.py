import pdfplumber
import unicodedata
import re
from xml_model.xml_table_extractor import to_valor_eng


def normalizar_texto(texto):
    if not texto:
        return ""
    texto = texto.lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def separar_valor_unidade(celula):
    """Separa valor numérico e unidade de célula como '52,57 mm' ou '1,48 µm Ra'."""
    if not celula:
        return None, None
    celula = str(celula).strip()
    m = re.match(r"^([\d,\.]+)\s+(.+)$", celula)
    if m:
        unidade = m.group(2).strip()
        if unidade.endswith(" Ra"):
            unidade = unidade[:-3].strip()
        return m.group(1), unidade
    return celula, None


def extrair_dados_dim_tr(caminho_pdf):
    """
    Extrai medições da tabela do relatório dimensional (DIM) de trecho reto.

    Formato da tabela DIM (diferente do cert de placa):
      col[0]: Parâmetro (bilíngue)
      col[1]: Resultado com unidade  ex: '52,57 mm'
      col[2]: Incerteza com unidade  ex: '0,05 mm'
      col[3]: k
      col[4]: Veff  (∞ → 'INFINITO')

    Retorna dict mapeando chave interna a:
      { valor, unidade, incerteza, k, veff }
    """
    mapa_chaves = {
        "diameter d at 20": "d_trecho_ref",
    }

    resultado = {}

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            tabelas = pagina.extract_tables()
            if not tabelas:
                continue

            for tabela in tabelas:
                if not tabela or len(tabela) < 2:
                    continue

                cabecalho = " ".join(str(c) for c in tabela[0] if c)
                if "Parameters" not in cabecalho:
                    continue

                for linha in tabela[1:]:
                    if not linha or len(linha) < 4:
                        continue

                    descricao = normalizar_texto(linha[0])

                    for chave_pdf, chave_final in sorted(
                        mapa_chaves.items(),
                        key=lambda x: len(x[0]),
                        reverse=True,
                    ):
                        if chave_pdf in descricao:
                            valor_raw, unidade = separar_valor_unidade(linha[1])
                            incerteza_raw, _ = separar_valor_unidade(linha[2])
                            k = to_valor_eng(linha[3]) if len(linha) > 3 else None
                            veff = to_valor_eng(linha[4]) if len(linha) > 4 else None

                            resultado[chave_final] = {
                                "valor": to_valor_eng(valor_raw),
                                "unidade": unidade,
                                "incerteza": to_valor_eng(incerteza_raw),
                                "k": k,
                                "veff": veff,
                            }
                            break

    return resultado
