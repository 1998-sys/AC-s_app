def gerar_xml_uc(numero_ci: str, dados: dict) -> str:
    """
    Gera o XML do relatório de incerteza a partir do número do CI e do dict
    retornado por organizar_dados_uc.
    SensorTemperatura é incluído com 'NI' quando não há dados.
    TransmissorPD faixa='low' é omitido quando DP Low não existir.
    """
    def v(chave_instrumento: str, campo: str) -> str:
        return dados.get(chave_instrumento, {}).get(campo, "NI")

    def bloco_operation_flow_rate() -> str:
        dp_high = dados.get("dp_high", {})
        dp_low  = dados.get("dp_low",  {})
        max_flow = dp_high.get("vazao_max", "NI")
        min_flow = dp_low.get("vazao_min") or dp_high.get("vazao_min", "NI")
        return (
            f'  <OperationFlowRate>\n'
            f'    <MaxFlowRate>{max_flow}</MaxFlowRate>\n'
            f'    <MinFlowRate>{min_flow}</MinFlowRate>\n'
            f'  </OperationFlowRate>\n'
        )

    def bloco_pd(range_: str, chave: str) -> str:
        if chave not in dados:
            return ""
        d = dados[chave]
        return (
            f'  <DifferentialPressureTransmitter range="{range_}">\n'
            f'    <Certificate>{d.get("tag", "NI")}</Certificate>\n'
            f'    <CertificateNumber>{d.get("certificado", "NI")}</CertificateNumber>\n'
            f'    <MaxFlowRate>{d.get("vazao_max", "NI")}</MaxFlowRate>\n'
            f'    <MinFlowRate>{d.get("vazao_min", "NI")}</MinFlowRate>\n'
            f'  </DifferentialPressureTransmitter>\n'
        )

    xml = (
        f'<?xml version="1.0" encoding="utf-8"?>\n'
        f'<UncertaintyReport company="ODS ENERGY SOLUTIONS">\n\n'
        f'  <CINumber>{numero_ci}</CINumber>\n'
        f'  <Tag>NI</Tag>\n'
        f'  <SystemName>NI</SystemName>\n\n'
        f'  <GasMeterRun>\n'
        f'    <Certificate>{v("trecho", "tag")}</Certificate>\n'
        f'    <InternalDiameter>{v("trecho", "diametro")}</InternalDiameter>\n'
        f'    <CertificateNumber>{v("trecho", "certificado")}</CertificateNumber>\n'
        f'  </GasMeterRun>\n\n'
        f'  <OrificePlace>\n'
        f'    <Certificate>{v("placa", "tag")}</Certificate>\n'
        f'    <DiameterAt20C>{v("placa", "diametro")}</DiameterAt20C>\n'
        f'    <CertificateNumber>{v("placa", "certificado")}</CertificateNumber>\n'
        f'  </OrificePlace>\n\n'

        + bloco_pd("high", "dp_high")
        + ('\n' if "dp_low" in dados else '')
        + bloco_pd("low",  "dp_low")
        + f'\n  <PressureTransmitter>\n'
        + f'    <Certificate>{v("pressao_estatica", "tag")}</Certificate>\n'
        + f'    <CertificateNumber>{v("pressao_estatica", "certificado")}</CertificateNumber>\n'
        + f'  </PressureTransmitter>\n\n'
        + f'  <TemperatureTransmitter>\n'
        + f'    <Certificate>{v("termometro", "tag")}</Certificate>\n'
        + f'    <CertificateNumber>{v("termometro", "certificado")}</CertificateNumber>\n'
        + f'  </TemperatureTransmitter>\n\n'
        + f'  <TemperatureSensor>\n'
        + f'    <Certificate>NI</Certificate>\n'
        + f'    <CertificateNumber>NI</CertificateNumber>\n'
        + f'  </TemperatureSensor>\n\n'
        + bloco_operation_flow_rate()
        + '</UncertaintyReport>'
    )
    return xml
