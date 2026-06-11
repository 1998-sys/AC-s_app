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


MAPA_SECOES = {
    "upstream pipe 1": "tubo_a_montante_1",
    "tubo a montante 1": "tubo_a_montante_1",
    "upstream pipe 2": "tubo_a_montante_2",
    "tubo a montante 2": "tubo_a_montante_2",
    "downstream pipe": "tubo_a_jusante",
    "tubo a jusante": "tubo_a_jusante",
    "orifice carrier": "porta_placa",
    "porta placa": "porta_placa",
    "zanker": "zanker",
    "orifice flange": "flange_de_orificio",
    "flange de orificio": "flange_de_orificio",
    "meter run for flare": "meter_run_for_flare_ultrasonic",
    "trecho reto para medidor": "meter_run_for_flare_ultrasonic",
}


def _identificar_secao(texto):
    texto_norm = normalizar_texto(texto)
    for chave, valor in sorted(MAPA_SECOES.items(), key=lambda x: len(x[0]), reverse=True):
        if chave in texto_norm:
            return valor
    return None


def _chave_parametro(descricao_raw):
    # Usa apenas a primeira linha (inglês) para gerar a chave
    primeira_linha = str(descricao_raw).split("\n")[0]
    norm = normalizar_texto(primeira_linha)
    norm = re.sub(r"[^a-z0-9 ]", "", norm)
    norm = re.sub(r"\s+", "_", norm).strip("_")
    return norm[:60] if norm else None


def extrair_dados_dim_tr(caminho_pdf):
    """
    Extrai todas as tabelas de resultados do relatório dimensional (DIM),
    organizadas pela seção que precede cada tabela (Upstream Pipe 1/2,
    Downstream Pipe, Orifice Carrier, Zanker). A ordem é detectada
    dinamicamente — pode variar entre documentos.

    Retorna:
        {
            "upstream_pipe_1": { "medium_internal_diameter_at_20c": { valor, unidade, incerteza, k, veff }, ... },
            "upstream_pipe_2": { ... },
            "downstream_pipe": { ... },
            "orifice_carrier": { ... },
            "zanker":          { ... },
        }
    """
    resultado = {}
    secao_atual = None

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages[1:]:
            tabelas_obj = pagina.find_tables()
            if not tabelas_obj:
                continue

            prev_bottom = 0
            for tab_obj in tabelas_obj:
                # texto entre o fim da tabela anterior e o topo desta
                bbox_acima = (0, prev_bottom, pagina.width, tab_obj.bbox[1])
                texto_acima = pagina.crop(bbox_acima).extract_text() or ""
                prev_bottom = tab_obj.bbox[3]

                secao_nova = _identificar_secao(texto_acima)
                if secao_nova:
                    secao_atual = secao_nova

                if secao_atual not in ("porta_placa", "flange_de_orificio", "meter_run_for_flare_ultrasonic"):
                    continue

                dados = tab_obj.extract()
                if not dados or len(dados) < 2:
                    continue

                cabecalho = normalizar_texto(" ".join(str(c or "") for c in dados[0]))
                if "parameters" not in cabecalho and "parametros" not in cabecalho:
                    continue

                if secao_atual not in resultado:
                    resultado[secao_atual] = {}

                for linha in dados[1:]:
                    if not linha or not linha[0]:
                        continue
                    descricao = str(linha[0]).strip()
                    if not descricao:
                        continue

                    chave = _chave_parametro(descricao)
                    if not chave:
                        continue

                    # porta_placa: só os diâmetros D; flange_de_orificio: só diâmetro a 20°C
                    # meter_run_for_flare_ultrasonic: só Medium Internal Pipe Diameter (D) at 20°C
                    if secao_atual == "porta_placa":
                        if "diameter" not in chave or "cilindricity" in chave or "2d_4d" in chave:
                            continue
                    elif secao_atual == "flange_de_orificio":
                        if "diameter" not in chave or "at_20" not in chave:
                            continue
                    elif secao_atual == "meter_run_for_flare_ultrasonic":
                        if "diameter_d_at_20c" not in chave or "between" in chave:
                            continue

                    valor_raw, unidade = separar_valor_unidade(
                        str(linha[1]).strip() if len(linha) > 1 and linha[1] else ""
                    )
                    incerteza_raw, _ = separar_valor_unidade(
                        str(linha[2]).strip() if len(linha) > 2 and linha[2] else ""
                    )
                    k    = to_valor_eng(linha[3]) if len(linha) > 3 else None
                    veff = to_valor_eng(linha[4]) if len(linha) > 4 else None

                    resultado[secao_atual][chave] = {
                        "valor":     to_valor_eng(valor_raw),
                        "unidade":   unidade,
                        "incerteza": to_valor_eng(incerteza_raw),
                        "k":         k,
                        "veff":      veff,
                    }

    return {k: v for k, v in resultado.items() if v}
