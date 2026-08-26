# Tarefas — Relatórios de Linearização e Falha Presumida

Plano de implementação para adicionar duas novas saídas ao fluxo de calibração de medidores de vazão: **Relatório de Linearização** e **Relatório de Falha Presumida**, cada um gerado em PDF + planilha preenchida, a partir do XML de calibração já produzido pela skill `xml-calibracao-petrobras:gerar-xml-calibracao`.

---

## Atualização — Linearização implementada e corrigida

A Linearização já tem código funcionando (`xml_model/xml_extractor_FT.py` +
`form/utils_print_linearizacao.py`, disparado por
`gui/pdf_service.py::_processar_xml_ft` ao soltar um XML
`CERTIFICADO_CALIBRACAO_EXTERNA_MEDIDOR_VAZAO` no app). O mapa de células
tinha vários endereços "TODO: confirmar" — confirmados agora abrindo
`Template_Linearizacao.xlsx` de verdade com openpyxl e testando com o
certificado `26039184M` (FT-1198B-01, Coriolis, 15 pontos) anexado nesta
sessão. Achados importantes:

- **Todo o mapa de colunas da tabela estava 1 coluna adiantado** (ex.:
  Vazão é a coluna `C`, não `B`; Volume de Referência é `G`, não `F`; etc.)
  — corrigido.
- **Frequência (E), K-factor corrigido (O) e Status (S) já são fórmulas
  no próprio template**, calculadas a partir de Vazão/Volumes/Meter
  Factor que escrevemos — não precisam (e não devem) ser escritas pelo
  Python. Isso também **responde o item 1 abaixo** ("Critério de
  APROVADO/REPROVADO"): a fórmula de Status já embutida é
  `ABS(Erro%) > 0,2% → REPROVADO` se Aplicação for "FISCAL" ou
  "TRANSFERÊNCIA DE CUSTÓDIA", senão `> 0,6% → REPROVADO`. A cor
  verde/vermelho também é formatação condicional nativa do Excel
  (S22:T41), não precisa de `PatternFill` no Python.
- A 2ª tabela ("Dados a Serem Configurados"), o **KF médio** e os
  **limites de alarme** (baixo/alto) também são só fórmulas que espelham
  a 1ª tabela — nenhum desses precisa ser escrito pelo Python.
- **Bug real encontrado e corrigido**: as linhas 32-41 (pontos 11-20) e
  seu espelho 66-75 na 2ª tabela vêm **ocultas por padrão** no template —
  um certificado com mais de 10 pontos tinha os pontos extras
  simplesmente sumindo do PDF exportado, mesmo com os dados escritos na
  planilha. Corrigido: `gerar_linearizacao` agora reexibe (`hidden =
  False`) as linhas usadas.
- **Outro bug real**: `wb_excel.ExportAsFixedFormat` estava sendo chamado
  no `Workbook` inteiro, exportando **as 2 abas** — a de Linearização E a
  de "Falha Presumida" (ainda com os dados de exemplo do template, de um
  medidor completamente diferente). Corrigido: exporta só
  `wb_excel.Worksheets("Linearização")`.
- **Mais um bug de borda encontrado pelo usuário** (testando com o
  certificado de 15 pontos de verdade): as linhas reexibidas (32+, antes
  ocultas) tinham um estilo de borda diferente das linhas 22-31 —
  colunas mescladas (E:F, I:J, K:L, O:P, Q:R) saíam com borda grossa em
  vez de fina, e a linha 31 mantinha sua borda grossa de fechamento
  mesmo deixando de ser a última linha. Corrigido com
  `_ajustar_linhas_tabela`: toda linha usada (exceto o cabeçalho da
  tabela, linha 22) tem a borda normalizada pela linha 30 (uma linha
  "do meio", borda fina), e só a última linha realmente usada recebe a
  borda grossa de fechamento embaixo. De brinde, a mesma função agora
  também **oculta** linhas 27-31 quando há menos de 10 pontos — antes
  ficavam visíveis e vazias no PDF (o oposto do bug de 32-41 ficarem
  ocultas com mais de 10).
- Testado de ponta a ponta (fora da UI, chamando `extrair_dados_ft` +
  `gerar_linearizacao` direto) com o certificado de 15 pontos e também
  com um caso sintético de 5 pontos — XLSX e PDF saem corretos, 1 página
  só, todos os pontos visíveis com borda uniforme, Status "APROVADO" em
  todos (bate com a fórmula, já que nenhum ponto passa de 0,6% de erro).
  Teste com o app real (soltar o XML na tela do CertiFlow) ainda
  pendente de confirmação do usuário.

Falha Presumida continua **não implementada** (só existe como aba de
exemplo no template) — segue valendo o plano original abaixo pra ela.

---

## 0. Validação dos arquivos recebidos nesta sessão

- `CERT_CAL_EXT_MEDVAZAO_26039184M.xml` — válido conforme o schema Petrobras v3.0.0 (já checado anteriormente). Medidor Coriolis KROHNE OPTMASS 2000C S100, TAG `FT-1198B-01`, cliente PRIO FORTE S/A., unidade FPSO BRAVO.
- `Linearizacao_FT1198B_abr26.xlsx` — usado aqui só como **modelo de layout e fórmulas**, não como dado real do FT-1198B-01. Atenção: apesar do nome do arquivo citar "FT1198B", os dados internos da planilha são de **outro medidor** (TAG `FT-1198C-01`, TURBINA Faure Herman TZN80-150, N° série 9022152, certificado `LMV 49575-26`, cliente PRIO/BRAVO). Isso é normal para um template de exemplo, mas é importante não confundir os dois medidores ao testar a implementação.
- A planilha tem 2 abas: `Linearização` e `Falha Presumida`, cada uma com layout e fórmulas próprias (mapeamento abaixo).

---

## 1. Decisões de negócio a confirmar ANTES de codar

Estas regras não estão explícitas nas fórmulas da planilha-modelo e precisam ser definidas com quem valida os relatórios hoje (provavelmente a engenharia de metrologia da ODS), antes de implementar os cálculos:

- [x] **Critério de APROVADO/REPROVADO** na aba Linearização — resolvido (ver "Atualização" no topo do arquivo): é a própria fórmula de `Status` do template, `ABS(Erro%) > 0,2%` (Aplicação FISCAL/TRANSFERÊNCIA DE CUSTÓDIA) ou `> 0,6%` (demais). **Falha Presumida** ainda não tem essa fórmula confirmada — a coluna `Status`/`Fator de Correção (Fci)` da aba Falha Presumida do template também merece a mesma inspeção antes de implementar essa 2ª saída.
- [ ] **Falha Presumida — emparelhamento de pontos**: os dois certificados (anterior e atual) podem ter vazões de calibração diferentes. Como comparar quando os pontos não coincidem exatamente? (interpolar a curva, usar o ponto mais próximo, ou exigir que os pontos sejam os mesmos e travar se não forem)
- [ ] **Campo "Fator de Correção (Fci)"**: na planilha-modelo aparece sempre como `-`. Em que condição ele deve ser calculado e qual a fórmula (aparenta ser usado só quando o ponto é reprovado, para indicar um fator de ajuste a aplicar)?
- [ ] **Linearização se aplica a quais tipos de medidor?** O layout (Frequência = K-Factor × Vazão / 3600) é típico de medidores com saída de pulso/frequência (TURBINA, DESLOCAMENTO POSITIVO). Faz sentido gerar esse relatório para CORIOLIS, MAGNÉTICO, ULTRASSÔNICO e V-CONE também, ou só para os que têm K-Factor em pulsos/m³? (o próprio FT-1198B-01 é Coriolis — confirmar se ele realmente usa linearização por frequência ou se o exemplo enviado foi só para mostrar o layout)
- [ ] **Origem do template da planilha**: o arquivo-modelo (`Linearizacao_FT1198B_abr26.xlsx` ou similar) deve ficar embutido como asset fixo dentro da skill, ou o usuário vai anexá-lo toda vez que pedir o relatório?
- [ ] **Layout do PDF**: os PDFs devem ser uma exportação direta das abas da planilha (mantendo o layout atual), ou um PDF com identidade visual própria da ODS, só usando os mesmos dados/fórmulas?

---

## 2. Mapeamento de dados — Aba "Linearização"

| Campo na planilha (célula) | Origem no XML do certificado |
|---|---|
| Cliente (D9) | `CLIENTE/NOME` |
| Instalação (D10) | `CLIENTE/UNIDADE_OPERACIONAL` |
| TAG do Sistema (D11) / TAG (M12) | `MEDIDOR_VAZAO/TAG` |
| Aplicação (D12) | não existe no XML hoje — perguntar ao usuário ou deixar NI |
| Sistema (D13) | não existe no XML hoje — perguntar ao usuário ou deixar NI |
| Data da Calibração (D14) | `MEDIDOR_VAZAO/DATA_CALIBRACAO` |
| Tipo do Medidor (D15) | `MEDIDOR_VAZAO/TIPO` |
| Nº Certificado (M9) | `NUMERO_CERTIFICADO` |
| Modelo (M10) | `MEDIDOR_VAZAO/MODELO` |
| Fabricante (M11) | `MEDIDOR_VAZAO/FABRICANTE` |
| Nº Série (M13) | `MEDIDOR_VAZAO/NUM_SERIE` |
| Diâmetro (M14) | `MEDIDOR_VAZAO/DIAMETRO_NOMINAL` |
| Faixa Calibrada (M15) | `MEDIDOR_VAZAO/CALIBRACAO_AS_FOUND/FAIXA_CALIBRADA` (MIN–MAX) |
| K-Factor do medidor (D19) | `MEDIDOR_VAZAO/FATOR_K_DO_MEDIDOR` |
| Tabela de pontos (linhas 22+): Vazão, Volume Referência, Volume do Medidor, Meter Factor, Erro, Incerteza | um `PONTO_DE_CALIBRACAO` por linha: `VAZAO_CALIBRADA`, `VOLUME_PADRAO` (×1000 → L), `VOLUME_MEDIDOR` (×1000 → L), `FATOR_DO_MEDIDOR/VALOR`, `DESVIO_MEDIO`, `FATOR_DO_MEDIDOR/INCERTEZA_EXP` |

Campos **calculados** (fórmulas já presentes na planilha-modelo, linhas 45–50):

- `Frequência (Hz) = (K-Factor do medidor × Vazão) / 3600`
- `MF = Volume de Referência / Volume do Medidor` (já vem pronto no XML como `FATOR_DO_MEDIDOR/VALOR`, não precisa recalcular)
- `KFc (K-Factor corrigido) = K-Factor do medidor / MF`
- `Status` = ver decisão pendente no item 1

Tabela "Dados a Serem Configurados no Computador de Vazão" (linhas 55+): repete N°, Vazão, Frequência e KFc de cada ponto (até 20 linhas fixas no template), mais:
- `KF médio` = média dos KFc de todos os pontos
- `Alarme de vazão baixa` = MIN da faixa calibrada
- `Alarme de vazão alta` = MAX da faixa calibrada

---

## 3. Mapeamento de dados — Aba "Falha Presumida"

Reaproveita o mesmo cabeçalho e tabela de "Valores do Certificado de Calibração" da aba Linearização (ver seção 2), mas usando os dados da **calibração atual**.

Seção específica "Cálculo Falha Presumida" (linha 81+) precisa de **dois** XMLs do mesmo medidor:

| Campo | Origem |
|---|---|
| Coluna "MF Calibração anterior" | `FATOR_DO_MEDIDOR/VALOR` de cada ponto no XML da calibração **anterior** |
| Coluna "MF Calibração atual" | `FATOR_DO_MEDIDOR/VALOR` de cada ponto no XML da calibração **atual** (o que acabamos de gerar) |
| Diff MF | `MF_atual − MF_anterior` |
| Fator de Correção (Fci) | ver decisão pendente no item 1 |
| Status | ver decisão pendente no item 1 |
| Cabeçalho com números dos 2 certificados (G85, I85) | `NUMERO_CERTIFICADO` de cada XML |

---

## 4. Fluxo de entrada de dados (conforme descrito pelo usuário)

- [ ] Relatório de **Linearização**: precisa só do XML da calibração atual (já temos isso pronto ao final da skill `gerar-xml-calibracao`).
- [ ] Relatório de **Falha Presumida**: precisa do XML da calibração atual **+** solicitar ao usuário o XML da calibração anterior do mesmo medidor (a skill deve pedir esse anexo explicitamente quando não vier junto).
- [ ] Definir se as duas novas skills disparam automaticamente ao final de `gerar-xml-calibracao` (perguntando ao usuário se quer gerar os relatórios) ou se são skills separadas, disparadas por pedido explícito ("gerar linearização", "gerar falha presumida").

---

## 5. Tarefas de implementação (ordem sugerida)

### Fase 1 — Estrutura da skill
- [ ] Decidir: nova skill dentro do plugin `xml-calibracao-petrobras` (ex.: `gerar-relatorio-linearizacao` e `gerar-relatorio-falha-presumida`) ou uma única skill que gera os dois relatórios juntos.
- [ ] Escrever `SKILL.md` com frases de gatilho (ex.: "gerar linearização", "relatório de linearização", "falha presumida", "avaliação de falha presumida", "computador de vazão").
- [ ] Incluir o arquivo de template `.xlsx` (com as 2 abas e fórmulas) como asset da skill, em `references/`.

### Fase 2 — Extração e cálculo
- [ ] Implementar leitura do(s) XML(s) de entrada (validando contra o schema Petrobras, igual já é feito em `gerar-xml-calibracao`).
- [ ] Implementar o mapeamento da seção 2 (Linearização): calcular Frequência, KFc, KF médio e limites de alarme por ponto.
- [ ] Implementar o mapeamento da seção 3 (Falha Presumida): emparelhar pontos entre os dois certificados e calcular Diff MF (regra de emparelhamento definida no item 1).
- [ ] Implementar a regra de Status/Fci assim que definida com o usuário (item 1).

### Fase 3 — Geração dos arquivos de saída
- [ ] Gerar a planilha `.xlsx` preenchida a partir do template, preservando formatação/fórmulas originais.
- [ ] Gerar o PDF de cada relatório (Linearização e Falha Presumida) — decidir layout conforme item 1.
- [ ] Nomear os arquivos de saída de forma consistente com o padrão já usado (ex.: `LINEARIZACAO_<TAG>_<NUMERO_CERTIFICADO>.pdf`, `FALHA_PRESUMIDA_<TAG>_<NUMERO_CERTIFICADO>.pdf`).

### Fase 4 — Validação
- [ ] Rodar a implementação com os dois arquivos de exemplo desta conversa (mesmo sendo de medidores diferentes) para conferir se os campos batem célula a célula com o template.
- [ ] Conseguir (ou pedir ao usuário) um par real de certificados do mesmo medidor com pontos de calibração diferentes, para validar a Falha Presumida de ponta a ponta.
- [ ] Conferir manualmente pelo menos um caso de "REPROVADO" assim que a regra do item 1 estiver definida, para garantir que o relatório sinaliza corretamente.

### Fase 5 — Entrega
- [ ] Atualizar a descrição da skill principal (`gerar-xml-calibracao`) ou o `README` do plugin mencionando as novas saídas disponíveis.
- [ ] Testar o fluxo completo: PDF do certificado → XML → (opcional: XML anterior) → Linearização + Falha Presumida em PDF/xlsx.
