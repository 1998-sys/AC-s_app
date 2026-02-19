from validation.issue import ValidationIssue
from datetime import datetime, timedelta
import unicodedata
import holidays
from data.utils_db import (
    atualizar_sn,
    atualizar_sn_sensor,
    atualizar_range,
    atualizar_tag,
    inserir_instrumento
)

from xml_model.xml_generator import normalizar_certificado

# Utilitários para regras de validação
def normalizar_local(local_calibracao):
    if not local_calibracao:
        return None
    return MAP_LOCAL.get(local_calibracao)

def obter_cmc(categoria, local, valor_referencia):
    familia = MAPA_CATEGORIA_CMC.get(categoria, categoria)
    regras_categoria = CMC_REGRAS.get(familia)
    if not regras_categoria:
        return None

    regras_local = regras_categoria.get(local)
    if not regras_local:
        return None

    for minimo, maximo, cmc in regras_local:
        if minimo <= valor_referencia <= maximo:
            return cmc

    return None

def normalizar_texto(texto):
    if not texto:
        return ""
    texto = texto.upper()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))

def to_float(value):
    try:
        if value is None:
            return None
        return float(str(value).replace(",", "."))
    except Exception:
        return None

def contar_dias_uteis(data_inicial, data_final):
    br_feriados = holidays.Brazil()

    dias_uteis = 0
    data_atual = data_inicial

    while data_atual < data_final:
        data_atual += timedelta(days=1)

        if (
            data_atual.weekday() < 5  # Segunda a sexta
            and data_atual.date() not in br_feriados
        ):
            dias_uteis += 1

    return dias_uteis

# TAG vs SN (MVS ou divergente)
def regra_tag_vs_sn(ctx):
    if ctx.db is None and ctx.reg_sn is not None:
        tipos_mvs = {
            "Manometro Digital",
            "Manometro Diferencial Digital",
            "Termômetro Digital"
        }

        sn_pdf = ctx.pdf.get("sn_instrumento")
        sn_banco = ctx.reg_sn.get("sn_instrumento")
        tipo_equipamento = ctx.pdf.get("categoria")
        
        if sn_pdf and sn_banco and sn_pdf == sn_banco and tipo_equipamento in tipos_mvs:
            ctx.mvs = True
            return ValidationIssue(
                key="mvs",
                title="TAG compatível (MVS)",
                message=(
                    "NS já pertence a um equipamento.\nEquipamento é um MVS?\n\n"
                    f"Banco: {ctx.reg_sn['tag']}\n"
                    f"Certificado: {ctx.pdf['tag']}"
                ),
                action=lambda: inserir_instrumento(
                    ctx.pdf["tag"],
                    ctx.pdf.get("sn_instrumento"),
                    ctx.pdf.get("sn_sensor"),
                    ctx.pdf.get("min_range"),
                    ctx.pdf.get("max_range")
                ),
                blocking=False
            )

        # TAG divergente
        return ValidationIssue(
            key="tag_divergente",
            title="TAG divergente",
            message=(
                "NS já cadastrado com outra TAG.\n\n"
                f"Banco: {ctx.reg_sn['tag']}\n"
                f"Certificado: {ctx.pdf['tag']}"
            ),
            action=lambda: atualizar_tag(
                ctx.pdf["sn_instrumento"],
                ctx.pdf["tag"]
            ),
            blocking=True
        )

# Novo Instrumento
def regra_novo_instrumento(ctx):
    if ctx.db is None and ctx.reg_sn is None:
        return ValidationIssue(
            key="novo_instrumento",
            title="TAG não encontrada",
            message=(
                f"TAG {ctx.pdf['tag']} não existe.\n\n"
                f"SN Instrumento: {ctx.pdf.get('sn_instrumento')}\n"
                f"SN Sensor: {ctx.pdf.get('sn_sensor')}"
            ),
            action=lambda: inserir_instrumento(
                ctx.pdf["tag"],
                ctx.pdf.get("sn_instrumento"),
                ctx.pdf.get("sn_sensor"),
                ctx.pdf.get("min_range"),
                ctx.pdf.get("max_range")
            ),
            blocking=True
        )

# SN do Instrumento
def regra_sn_instrumento(ctx):
    if ctx.db is None:
        return None

    if (
        ctx.pdf.get("sn_instrumento")
        and ctx.pdf["sn_instrumento"] != ctx.db.get("sn_instrumento")
    ):
        return ValidationIssue(
            key="sn_instrumento",
            title="SN do Instrumento divergente",
            message=(
                f"PDF: {ctx.pdf['sn_instrumento']}\n"
                f"Banco: {ctx.db.get('sn_instrumento')}"
            ),
            action=lambda: (
                atualizar_sn(ctx.db["tag"], ctx.pdf["sn_instrumento"]),
                ctx.pdf.__setitem__("sn_atualizado", True)
            )
        )

# SN do Sensor
def regra_sn_sensor(ctx):
    if ctx.db is None:
        return None

    if (
        ctx.pdf.get("sn_sensor")
        and ctx.pdf["sn_sensor"] != ctx.db.get("sn_sensor")
    ):
        return ValidationIssue(
            key="sn_sensor",
            title="SN do Sensor divergente",
            message=(
                f"PDF: {ctx.pdf['sn_sensor']}\n"
                f"Banco: {ctx.db.get('sn_sensor')}"
            ),
            action=lambda: (
                atualizar_sn_sensor(ctx.db["tag"], ctx.pdf["sn_sensor"]),
                ctx.pdf.__setitem__("sn_atualizado", True)
            )
        )

# RANGE
def regra_range(ctx):
    if ctx.db is None:
        return None

    pdf_min = to_float(ctx.pdf.get("min_range"))
    pdf_max = to_float(ctx.pdf.get("max_range"))

    if pdf_min is None or pdf_max is None:
        return None

    db_min = to_float(ctx.db.get("min_range"))
    db_max = to_float(ctx.db.get("max_range"))

    ctx.pdf["min_range"] = pdf_min
    ctx.pdf["max_range"] = pdf_max
    ctx.db["min_range"] = db_min
    ctx.db["max_range"] = db_max

    if db_min is None or db_max is None:
        return ValidationIssue(
            key="range",
            title="Range ausente no banco",
            message=(
                f"PDF: {pdf_min} → {pdf_max}\n"
                "Banco: não cadastrado"
            ),
            action=lambda: (
                atualizar_range(ctx.db["tag"], pdf_min, pdf_max),
                ctx.pdf.__setitem__("range_atualizado", True)
            )
        )

    if pdf_min != db_min or pdf_max != db_max:
        return ValidationIssue(
            key="range",
            title="Range divergente",
            message=(
                f"PDF: {pdf_min} → {pdf_max}\n"
                f"Banco: {db_min} → {db_max}"
            ),
            action=lambda: (
                atualizar_range(ctx.db["tag"], pdf_min, pdf_max),
                ctx.pdf.__setitem__("range_atualizado", True)
            )
        )

    return None

# HASTE (somente TE)
def regra_haste_te(ctx):
    if "TE" not in ctx.pdf["tag"]:
        return None

    try:
        rod = ctx.pdf.get("rod_length")
        dia = ctx.pdf.get("probe_diameter")

        if rod is None or dia is None or float(dia) > float(rod):
            return ValidationIssue(
                key="haste",
                title="Dados de Haste inválidos",
                message=(
                    f"Comprimento: {rod}\n"
                    f"Diâmetro: {dia}"
                ),
                blocking=True
            )

    except Exception:
        return ValidationIssue(
            key="haste_parse",
            title="Erro na leitura da Haste",
            message="Erro ao interpretar os valores.",
            blocking=True
        )

    return None

# LOCAL
def regra_local_fpso(ctx):
    local_pdf = normalizar_texto(ctx.pdf.get("local"))

    fpsos = {
        "FPSO FRADE": ["FPSO", "FRADE"],
        "FPSO FORTE": ["FPSO", "FORTE"],
        "FPSO BRAVO": ["FPSO", "BRAVO"],
        "POLVO": ["POLVO"],
        "ORIGEM ENERGIA ALAGOAS S.A.": ["ORIGEM", "ENERGIA", "ALAGOAS"],
        "FPSO MARIA QUITERIA": ["FPSO", "MARIA", "QUITERIA"],
        "FPSO ANNA NERY": ["FPSO", "ANNA", "NERY"],
        "FPSO ATLANTA": ["FPSO", "ATLANTA"]
        
    }

    for nome_fpso, palavras in fpsos.items():
        if all(p in local_pdf for p in palavras):
            return None  # OK

    return ValidationIssue(
        key="local_invalido",
        title="Local incompatível",
        message=f"Verifique o local informado: ({ctx.pdf.get('local')})",
        blocking=True
    )

# RANGE indicado x calibrado
def regra_rangein(ctx):

    # Converter valores do PDF para float
    pdf_min = to_float(ctx.pdf.get("min_range"))
    pdf_max = to_float(ctx.pdf.get("max_range"))
    pdf_imin = to_float(ctx.pdf.get("inmin_range"))
    pdf_imax = to_float(ctx.pdf.get("inmax_range"))

    # Se algum valor não puder ser convertido, ignora a regra
    if pdf_min is None or pdf_max is None or pdf_imin is None or pdf_imax is None:
        return None

    # Atualiza o contexto com os valores normalizados
    ctx.pdf["min_range"] = pdf_min
    ctx.pdf["max_range"] = pdf_max
    ctx.pdf["inmin_range"] = pdf_imin
    ctx.pdf["inmax_range"] = pdf_imax

    # Validação: range calibrado deve estar contido no range indicado
    if pdf_min < pdf_imin or pdf_max > pdf_imax:
        return ValidationIssue(
            key="range_calibracao",
            title="Range de calibração fora do range indicado",
            message=(
                f"Range indicado (PDF): {pdf_min} → {pdf_max}\n"
                f"Range calibrado (PDF): {pdf_imin} → {pdf_imax}\n\n"
                "O range calibrado está fora do range indicado."
            ),
            action=None,     # Apenas informativo
            blocking=True    # Bloqueia a geração da AC
        )

    return None

# Incerteza e Erro fiducial 
def regra_incert_fidu(ctx):

    # Converter valores do PDF para float
    incert= to_float(ctx.pdf.get("incerteza"))
    fiducial = to_float(ctx.pdf.get("erro_fid"))

   
    if incert is None or fiducial is None:
        return None

    
    ctx.pdf["erro_fid"] = fiducial 
    ctx.pdf["incerteza"] = incert

 
    if incert >= 0.1 or fiducial > 0.1:
        return ValidationIssue(
            key="incert_fiducial",
            title="Incerteza/Erro Fiducial",
            message=(
                f"Incerteza (PDF): {incert}\n"
                f"Erro fiducial (PDF): {fiducial}\n\n"
                "Incerteza ou Erro fiducial acima de  0.1%"
            ),
            action=None,     # Apenas informativo
            blocking=None    # Bloqueia a geração da AC
        )

    return None

MAPA_CATEGORIA_CMC = {
    # Temperatura
    "Termorresistência PT-100 - 2 Fios": "TERMORRESISTENCIA_PT100",
    "Termorresistência PT-100 - 3 Fios": "TERMORRESISTENCIA_PT100",
    "Termorresistência PT-100 - 4 Fios": "TERMORRESISTENCIA_PT100",
    "Termômetro Digital": 'Termômetro',
    "Termômetro Analógico": 'Termômetro',
}

# Mapeamento do local de calibração
MAP_LOCAL = {
    "Calibration performed at the permanent facility": "permanente",
    "Calibration performed at the customer's facility": "cliente",
    "Calibration performed in the mobile installation (container)": "movel",
}

# Regras CMC 
CMC_REGRAS = {
    "Manometro Analógico": {
        "permanente": [
            (0.1, 16, 0.04),
            (16, 70, 0.05),
            (70, 68000, 0.03),
        ],
        "cliente": [
            (0.1, 16, 0.04),
            (16, 70, 0.05),
            (70, 68000, 0.03),
        ],
        "movel": [
            (0.1, 16, 0.04),
            (16, 70, 0.05),
            (70, 68000, 0.03),
        ],
    },

    "Manometro Diferencial Analógico": {
        "permanente": [
            (0.1, 16, 0.04),
            (16, 70, 0.05),
            (70, 68000, 0.03),
        ],
        "cliente": [
            (0.1, 16, 0.04),
            (16, 70, 0.05),
            (70, 68000, 0.03),
        ],
        "movel": [
            (0.1, 16, 0.04),
            (16, 70, 0.05),
            (70, 68000, 0.03),
        ],
    },

    "Manometro Digital": {
        "permanente": [
            (0.1, 16, 0.04),
            (16, 70, 0.05),
            (70, 68000, 0.03),
        ],
        "cliente": [
            (0.1, 16, 0.04),
            (16, 70, 0.05),
            (70, 68000, 0.03),
        ],
        "movel": [
            (0.1, 16, 0.04),
            (16, 70, 0.05),
            (70, 68000, 0.03),
        ],
    },

    "Manometro Diferencial Digital": {
        "permanente": [
            (0.1, 16, 0.04),
            (16, 70, 0.05),
            (70, 68000, 0.03),
        ],
        "cliente": [
            (0.1, 16, 0.04),
            (16, 70, 0.05),
            (70, 68000, 0.03),
        ],
        "movel": [
            (0.1, 16, 0.04),
            (16, 70, 0.05),
            (70, 68000, 0.03),
        ],
    },

    "Manometro Digital Absoluto": {
        "permanente": [
            (15, 170, 0.05),
            (170, 68000, 0.03),
        ],
        "cliente": [
            (15, 170, 0.05),
            (170, 68000, 0.03),
        ],
        "movel": [
            (15, 170, 0.05),
            (170, 68000, 0.03),
        ],
    },

    "Transmissor de Pressão com Saída em Unidade Elétrica": {
        "permanente": [
            (0.1, 16, 0.05),
            (16, 70, 0.06),
            (70, 68000, 0.04),
        ],
        "cliente": [
            (0.1, 16, 0.05),
            (16, 70, 0.06),
            (70, 68000, 0.04),
        ],
        "movel": [
            (0.1, 16, 0.05),
            (16, 70, 0.06),
            (70, 68000, 0.04),
        ],
    },

    "Transmissor de Pressão Absoluta com Saída em Unidade Elétrica": {
        "permanente": [
            (15, 170, 0.06),
            (170, 68000, 0.04),
        ],
        "cliente": [
            (15, 170, 0.06),
            (170, 68000, 0.04),
        ],
        "movel": [
            (15, 170, 0.06),
            (170, 68000, 0.04),
        ],
    },

    "TERMORRESISTENCIA_PT100":{
        "permanente": [
            (-50, -45, 0.12),
            (-45, 140, 0.10),
            (140, 350, 0.11),
        ],
        "cliente": [
            (-50, -45, 0.12),
            (-45, 140, 0.10),
            (140, 350, 0.1),
        ],
        "movel": [
            (-50, -45, 0.12),
            (-45, 140, 0.10),
            (140, 350, 0.11),
        ],
    },
    "Transmissor de Temperatura com saída em unidade elétrica":{        
        "permanente": [
            (-50, 350, 0.06),
        ],
        "cliente": [
            (-50, 350, 0.06),
        ],
        "movel": [
            (-50, 350, 0.06),
        ],
        
    },
    'Termômetro': {
        "permanente": [
            (-50, -45, 0.12),
            (-45, 140, 0.10),
            (140, 350, 0.11),
        ],
        "cliente": [
            (-50, -45, 0.12),
            (-45, 140, 0.10),
            (140, 350, 0.11),
        ],
        "movel": [
            (-50, -45, 0.12),
            (-45, 140, 0.10),
            (140, 350, 0.11),
        ],
    }
    }


def regra_cmc(ctx):
    tag = ctx.pdf.get("tag")
    categoria = ctx.pdf.get("categoria")
    local_raw = ctx.pdf.get("local_calibracao")
    incerteza = ctx.pdf.get("incerteza")
    local = normalizar_local(local_raw)
    pontos = ctx.pontos_calibracao
    certificado= ctx.pdf.get("certificado")

    if ctx.pontos_calibracao and ctx.pontos_calibracao[0].get("tipo") in ("PT", "DPT"):
        refs = [
            p["referencia"]
            for p in pontos
            if p.get("tipo") in ("PT", "DPT") and p.get("referencia") is not None
        ]

        amplitude = max(refs) - min(refs) if len(refs) >= 2 else None

        if not categoria or not local or not pontos or amplitude is None or incerteza is None:
            return None
        
        cmc = obter_cmc(categoria, local, abs(amplitude))

        if incerteza < cmc:
            return ValidationIssue(
                key="cmc_execedida",
                title="Incerteza abaixo da CMC",
                message=("A incerteza informada no certificado está\n"
                        "abaixo da Capacidade de Medição e Calibração (CMC)"
                        " aplicável.\n\n"
                        f'Tag: {tag}\n'
                        f'Certificado: {normalizar_certificado(certificado)}\n'
                        f"Categoria: {categoria}\n"
                        f'Local de calibração: {local}\n'
                        f'Faixa Calibrada (amplitude): {amplitude}\n'
                        f'Incerteza declarada: {incerteza}\n'
                        f'CMC aplicável: {cmc}\n'
                        'Conclusão: NÃO ATENDE A CMC.'),
                        action=None,
                        blocking=True)            
        return None
    
    else:
        erros = []

        for p in pontos:

            incerteza = to_float(p.get("incerteza"))
            referencia = to_float(p.get("referencia"))
            if incerteza is None or referencia is None:
                continue
            cmc = obter_cmc(categoria, local, abs(referencia)) 
            if cmc is None:
                continue

          

            if incerteza < cmc:
                erros.append(
                    f"Ponto {referencia} °C → "
                    f"Incerteza={incerteza} °C | CMC={cmc} °C"
                    )

        if erros:
            return ValidationIssue(
                key="cmc_temperatura",
                title="Incerteza abaixo da CMC",
                message=(
                    "A incerteza informada no certificado está\n"
                    "abaixo da Capacidade de Medição e Calibração (CMC)"
                    " aplicável.\n\n"
                    f'Tag: {tag}\n'
                    f'Certificado: {normalizar_certificado(certificado)}\n'
                    f"Categoria: {categoria}\n"
                    f"Local de calibração: {local}\n\n"
                    "Pontos fora da CMC:\n" +
                    "\n".join(erros)
                ),
                action=None,
                blocking=True
            )

        return None
    

def regra_classe(ctx):
    classe_raw = ctx.pdf.get("classe")
    if not classe_raw or classe_raw == "NA":
        return None
    classe = classe_raw.strip().upper().replace(" ", "")

    classes_validas = [
        "FISCAL",
        "APROPRIAÇÃO",
        "TRANSFERÊNCIADECUSTÓDIA",
        "OPERACIONAL"
    ]

    if classe not in classes_validas:
        return ValidationIssue(
            key="classe_invalida",
            title="Classe inválida",
            message=f"Classe informada nao compatível: {classe_raw}",
            blocking=True
        )

    return None


def data_proxcal(ctx):
    data_atual_str = ctx.pdf.get("data")
    data_prox_cal_str = ctx.pdf.get("proxima_cal")

    if not data_prox_cal_str:
        return None

    try:
        data_atual = datetime.strptime(data_atual_str, "%d/%m/%Y")
        data_prox_cal = datetime.strptime(data_prox_cal_str, "%d/%m/%Y")
    except ValueError:
        return None

    if data_prox_cal < data_atual:
        return ValidationIssue(
            key="data_proxima_calibracao",
            title="Data de próxima calibração inválida",
            message=(
                f"Data de calibração: {data_atual_str}\n"
                f"Data de próxima calibração: {data_prox_cal_str}\n\n"
                "A data de próxima calibração não pode ser anterior à data de calibração."
            ),
            blocking=True
        )
    return None


def prazo_emissao(ctx):
    data_cal_str = ctx.pdf.get("data")
    data_emissao_str = ctx.pdf.get("report_date")
    cliente = ctx.pdf.get("cliente").upper()

    if not data_cal_str or not data_emissao_str or not cliente:
        return None

    try:
        data_cal = datetime.strptime(data_cal_str, "%d/%m/%Y")
        data_emissao = datetime.strptime(data_emissao_str, "%d/%m/%Y")
    except ValueError:
        return None

    if cliente == "PRIO":
        prazo = 3
    elif cliente in ["YINSON", "ORIGEM ENERGIA ALAGOAS S.A."]:
        prazo = 10
    else:
        return None  

    dias_uteis = contar_dias_uteis(data_cal, data_emissao)
    print(dias_uteis)

    if dias_uteis > prazo:
        return ValidationIssue(
            key="prazo_emissao",
            title="Prazo de emissão excedido",
            message=(
                f"Cliente: {cliente}\n"
                f"Data calibração: {data_cal_str}\n"
                f"Data emissão: {data_emissao_str}\n"
                f"Dias úteis decorridos: {dias_uteis}\n\n"
                f"O prazo máximo permitido é de {prazo} dias úteis."
            ),
            blocking=True
        )

    return None

