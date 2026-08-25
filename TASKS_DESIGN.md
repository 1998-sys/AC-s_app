# Alinhamento visual/funcional — Design canvas (CertiFlow.dc.html) → webui/

Objetivo: deixar o front-end real (`webui/`) idêntico ao mockup em
`DESIGN/CertiFlow.dc.html`, incluindo funcionalidades que o mockup implica
(cancelar leitura, resumo do instrumento durante a leitura, opções lado a
lado pra divergências, cadastro estendido do instrumento, processamento em
lote de vários PDFs).

Escopo completo aprovado pelo usuário ("vamos implementar tudo"), incluindo
a feature de lote (seleção de vários PDFs, fila de processamento).

## Fase 1 — Visual/CSS ✅ concluída
- [x] Fontes Google (Archivo/Roboto/Roboto Mono) via `<link>` + variáveis CSS.
- [x] `.brand-lg` (marca grande nas telas Selecionar/Lendo).
- [x] Tracker: padding/tamanho ajustados pra bater com o mockup.
- [x] Spinner no checklist item ativo (`checklist-spin`).
- [x] `.instr-head-badge` (badge de erros abertos na revisão).
- [x] `.instr-tag` ajuste de fonte/line-height.
- [x] `.btn-link` cursor pointer (usado em spans tipo "Trocar").

## Fase 2 — Plumbing backend (Python) ✅ concluída
- [x] `gui/pdf_service.py`: fluxo de seleção em 2 passos —
      `escolher_arquivo_pdf()` (só escolhe) + `iniciar_leitura(caminho)`
      (dispara o processamento em background).
- [x] `cancelar_leitura()` — cancelamento cooperativo (checkpoint após
      extração, antes de avançar pra revisão/saída).
- [x] `_resumo_instrumento()` — payload de foto/badge/campos mostrado assim
      que o TAG é identificado, ainda na tela de leitura.
- [x] `App.showReadingInstrument(...)` chamado do backend.

## Fase 3 — Divergências com duas opções (Python) ✅ concluída
- [x] `ValidationIssue.opcoes` (lista `[{label, valor, recomendado?}]`).
- [x] `rules_sec.py`: `regra_sn_instrumento`, `regra_sn_sensor`, `regra_range`
      (branch "Range divergente") populam `opcoes`.
- [x] `RevisionService.desfazer_divergencia(key)` — volta pendente.
- [x] `serializar_issues()` inclui `opcoes`.
- [x] `Api.desfazer_divergencia` exposto na facade.

## Fase 1-3 — Wiring no front (webui/js/app.js) ✅ concluída e testada manualmente
- [x] Tracker dinâmico via `[data-tracker]` (função `setTracker` mantida
      com esse nome pois `gui/dialogs.py` chama `App.setTracker(...)`).
- [x] Fluxo de seleção em 2 passos: dropzone → `escolherArquivo()` → chip
      do arquivo + botão "Ler certificado" habilitado → `iniciarLeitura()`.
- [x] "Trocar" (`btn-trocar-arquivo`) reseta a seleção.
- [x] "Cancelar leitura" (`btn-cancelar-leitura`) chama
      `pywebview.api.cancelar_leitura()` e volta pra seleção.
- [x] `App.showReadingInstrument(...)` renderiza foto/badge/campos na tela
      de leitura.
- [x] Badge "N erro(s) aberto(s)" na tela de revisão (`review-error-badge`).
- [x] Cards de divergência com `opcoes`: duas opções lado a lado (radio-like,
      recomendada pré-selecionada) + botão "Aplicar e ir para a próxima".
- [x] "Desfazer" nas divergências já resolvidas.
- [x] Removido o botão "Ciente" de avisos sem ação (bate com o mockup —
      linha só com a tag "AVISO", sem botão).
- [x] CSS novo: `.issue-options`, `.issue-option(.selected)`, etc.
- [x] Testado manualmente pelo usuário: app aberto, fluxo de seleção
      confirmado funcionando (chip do arquivo, botão habilitado).

**Pendente de teste manual ainda:** telas de leitura (resumo do
instrumento aparecendo), cancelar leitura, os cards de opção dupla na
revisão de verdade (precisa de um certificado com divergência de SN ou
range pra disparar), e o "Desfazer".

## Fase 4 — Cadastro estendido do instrumento ✅ concluída e testada manualmente
Campos novos vistos no mockup da tela "Editar instrumento":
data de calibração, próxima calibração, nº do certificado, laboratório,
observações, e rodapé "Última alteração por {usuário} em {data/hora}".

- [x] `data/conexao.py::migrar()` — novas colunas (idempotente, mesmo
      padrão do `ALTER TABLE ... ADD COLUMN` já usado):
      `data_calibracao`, `proxima_calibracao`, `numero_certificado`,
      `laboratorio`, `observacoes`, `modificado_por`, `modificado_em`.
      Verificado via `PRAGMA table_info` no banco real após relançar o app.
- [x] `data/utils_db.py` — `buscar_instrumento_por_tag` retorna os campos
      novos; novo helper `atualizar_dados_cadastro(tag, **campos)` com
      whitelist própria (`_CAMPOS_CADASTRO_PERMITIDOS`).
- [x] `gui/instrument_service.py` — `buscar_instrumento`/`salvar_instrumento`
      passam a incluir os campos novos e carimbam `modificado_por`
      (`getpass.getuser()`) / `modificado_em` (timestamp) a cada
      salvamento; `salvar_instrumento` agora retorna esses dois valores
      pro front atualizar o rodapé sem precisar de outra consulta.
- [x] `webui/index.html` — novos campos na tela `#view-edit-instrument`
      (datas, nº certificado, select de laboratório com SGS/LMV/Metroval/
      RBC/Outro, textarea observações, `#edit-ultima-alteracao`).
- [x] `webui/js/app.js` — `consultarInstrumento`/`salvarInstrumento`/
      `setReadOnly` estendidos pros campos novos; `setUltimaAlteracao()`
      novo.
- [x] CSS: `.field select` adicionado à regra existente; `.field-hint`
      novo (rodapé "última alteração").

**Decisão de escopo mantida:** nenhuma regra nova na `ValidationEngine`
comparando esses campos (PDF × cadastro) foi adicionada — só CRUD. Ver
nota abaixo, sem mudança.

**Testado manualmente pelo usuário:** consultou um TAG real
(`PIT-1198B-61`), preencheu os campos novos, salvou, confirmou o rodapé
"Última alteração por ... em ...".

**Decisão consciente de escopo:** o mockup mostra essas divergências
("Data de calibração" e "Nº do certificado" como issues na tela de
revisão), mas isso implicaria *novas regras de negócio* na
`ValidationEngine` comparando PDF × cadastro pra esses campos. Igual ao
que já foi observado no T39 do `TASKS.md` original, regra de metrologia/
negócio não é algo pra eu decidir sozinho — vou implementar só a parte de
cadastro (CRUD) nesta fase, e pergunto antes de adicionar comparação
automática desses campos na revisão.

## Fase 5 — Processamento em lote (múltiplos PDFs em fila) ✅ concluída e testada manualmente
Aprovado pelo usuário: "Feature completa: selecionar vários PDFs,
processar em fila."

Decisões de produto confirmadas pelo usuário:
- Erro num item do meio da fila → **pula e continua** (registra o erro,
  segue pros próximos).
- Item com divergências → **mostra a tela de revisão normalmente**; a fila
  pausa ali, o usuário resolve e clica "Gerar", e a fila avança sozinha.

Implementado:
- [x] `gui/dialogs.py::escolher_arquivos` — `allow_multiple=True`.
- [x] `gui/pdf_service.py::escolher_arquivos_pdf` (substitui o antigo
      `escolher_arquivo_pdf` singular) — retorna lista de `{caminho, nome}`.
- [x] `iniciar_leitura(itens)` agora sempre recebe uma lista (1 ou mais).
      Modo lote ativa sozinho quando `len(itens) > 1`.
- [x] Fila no backend (estado em `Api`: `fila_processamento`, `indice_fila`,
      `resultados_lote`, `eventos_lote`) com dois pontos de avanço:
      - `avancar_apos_sucesso_revisao` — chamado por
        `RevisionService.confirmar_geracao` quando a AC de um item é gerada
        (o caminho SEC/PO/TR que passa pela revisão).
      - `avancar_fila` — chamado por `DialogBridge.voltar_para_selecao` pra
        todo item que **não** passa pela revisão (erro, cancelamento, ou os
        tipos de geração direta: cromatografia/incerteza/linearização).
      Ambos incrementam `indice_fila`, disparam o próximo item ou finalizam
      o lote (`_finalizar_lote` monta o payload agregado e chama
      `App.showOutputLote` via JS).
- [x] `DialogBridge.alert` — em modo lote, suprime o popup de sucesso/erro
      (que pararia a fila esperando clique em OK) e registra via
      `registrar_evento_lote` em vez disso.
- [x] Corrigida a ordem de chamadas `alert()`/`voltar_para_selecao()` em
      vários pontos (`pdf_service.py`, `revision_service.py`) que faziam
      `voltar_para_selecao()` **antes** do `alert()` — isso causava uma
      condição de corrida em lote (a thread do próximo item já rodando
      sobrescreve `caminho_pdf_atual` antes do evento ser registrado com o
      arquivo certo). Agora é sempre alert-then-voltar.
- [x] Corrigidos 4 "becos sem saída" pré-existentes em
      `processors/base_processor.py` e `gui/pdf_service.py::
      solicitar_dados_origem` — casos onde cancelar um diálogo intermediário
      (Evaluation Report, prompt ORIGEM) deixava a tela de leitura travada
      sem navegação nenhuma (bug real também no fluxo de um único arquivo,
      não só em lote).
- [x] `cancelar_leitura()` agora também limpa a fila — um cancelamento
      explícito do usuário aborta o lote inteiro, não só o arquivo atual.
- [x] Front (`webui/index.html` + `webui/js/app.js`):
      - Seleção múltipla: dropzone chama `escolher_arquivos_pdf`; chip
        mostra "N certificados selecionados" quando >1.
      - Tela de leitura: `App.setFilaProgresso(indice, total, nome)` novo —
        atualiza nome do arquivo, reseta checklist/resumo, mostra
        "Certificado X de Y" no rodapé.
      - `confirmarGeracao()` trata os 3 formatos de retorno de
        `confirmar_geracao()`: resultado único (comportamento antigo),
        `{avancando_lote, item}` (registra recente e não navega — a tela já
        foi trocada pelo backend), `{lote, itens, eventos}` (tela agregada).
      - Nova `App.showOutputLote(payload)` — cards agrupados por TAG (igual
        ao mockup: header com badge/laboratório/avisos + linhas PDF/XML) +
        seção de "eventos" pros tipos de geração direta e erros; "Abrir
        todos" abre todos os arquivos gerados de uma vez.
      - CSS novo: `.output-group*`, `.output-count-row`, `.output-events`,
        `.output-event(.erro)`.

**Testado manualmente pelo usuário:** selecionou vários PDFs de uma vez,
fila processou e avançou sozinha entre os itens, tela agregada "Arquivos
gerados" apareceu corretamente no final.

## Depois de tudo
- [x] Rodar a app e testar manualmente cada fase (como já vem sendo feito) —
      todas as 5 fases testadas e aprovadas pelo usuário.
- [ ] Outra rodada de organização de commits + push (mesmo padrão da
      refatoração SOLID), só quando o usuário pedir.

## Fase 6 — Leitura contínua + revisão agregada no lote (PLANEJADA, não implementada)
Ideia do usuário: hoje, no lote, cada certificado interrompe a leitura pra
mostrar a tela de revisão dele (se tiver divergência) antes de seguir pro
próximo — fica um zigue-zague entre "lendo" e "revisando". Proposta:
**separar as duas fases**. Primeiro lê TODOS os certificados da fila em
sequência (fluxo contínuo, com um tempo mínimo de ~2s por item só pra dar
sensação de progresso/interatividade), e só depois de ler tudo mostra
**uma única tela de divergências agregada**, com um grupo por instrumento
(igual a tela de saída em lote já agrupa hoje) e barra de rolagem se tiver
muita coisa.

**Importante, confirmado com o usuário: isso só vale pra lote (>1
certificado). Com um único certificado selecionado, o fluxo continua
exatamente como é hoje** (ler → revisar esse item → gerar → saída) — nada
muda nesse caminho.

### Desenho proposto

**1. Fase de leitura contínua (só quando em lote)**
- Pra cada item da fila: roda a extração + `ValidationEngine` normalmente,
  mas **não mostra mais a tela de revisão** — só guarda o resultado
  (`dados_pdf`, `registro`, `issues`) numa lista nova de instrumentos do
  lote e segue pro próximo item imediatamente.
- Erros de extração continuam iguais a hoje: pulados e registrados em
  `eventos_lote` (não entram na revisão agregada, já que não tem dados pra
  revisar).
- **Ressalva a avisar o usuário**: Placa de Orifício e Trecho Reto (Gas
  Meter Run) exigem selecionar um Evaluation Report *durante* a leitura
  (`_iniciar_fluxo_com_report`) — isso não é uma divergência, é dado
  faltante pra sequer extrair. Pra esses tipos o fluxo **não fica 100%
  contínuo** (ainda pede a interação no meio); só os instrumentos
  secundários comuns leem de ponta a ponta sem parar.
- Tempo mínimo de ~2s por item: garantir que a troca de tela não pareça um
  flash — se o processamento real for mais rápido que 2s, completa a
  diferença antes de avançar; se for mais lento, não soma tempo extra em
  cima.

**2. Fase de revisão agregada**
- Depois que TODOS os itens da fila terminam a leitura: se **nenhum**
  instrumento tiver divergência, pula direto pra geração (nem mostra a
  tela agregada). Se **algum** tiver, mostra a nova tela
  "Divergências (lote)":
  - Um grupo por instrumento com divergência (foto/badge/TAG, igual ao
    resumo de hoje), cada um com sua lista de cards de divergência
    (reaproveitando os cards que já existem: duas opções, MANTIDO,
    genérico Ignorar/Aplicar, "Pular certificado" por grupo se for
    bloqueante sem ação).
  - Lista inteira dentro de um container com `overflow-y:auto` (rolagem),
    já que pode ter muitos instrumentos com muitas divergências cada.
  - Instrumentos sem nenhuma divergência **não aparecem nessa tela** — vão
    direto pra fase de geração.

**3. Geração em lote a partir da tela agregada**
- Um botão único "Gerar relatórios" no rodapé, habilitado quando nenhum
  grupo tiver divergência bloqueante-com-ação ainda não resolvida.
- Ao clicar, gera a AC de cada instrumento pronto (os sem divergência +
  os que tiveram tudo resolvido/ignorado na tela agregada), acumulando
  resultados/eventos exatamente como a fila já faz hoje.
- Segue pra mesma tela final "Arquivos gerados" (`showOutputLote`) já
  existente, sem mudança nela.

### Impacto técnico (o que precisa mudar)
- **Backend**: novo estado em `Api` pra revisão em lote (lista de
  instrumentos com `dados_pdf`/`registro`/`issues` cada), **sem tocar**
  em `_issues_pendentes`/`_dados_pdf_review`/`_registro_review` (esses
  continuam servindo só o fluxo de arquivo único, inalterado).
  `PdfProcessingService` passa a chamar um novo método de "coleta" em vez
  de `RevisionService.iniciar_revisao()` quando `em_lote_ativo()`; esse
  novo método nunca chama `App.showReview`, só acumula e avança.
  Novos métodos em `RevisionService`: resolver/desfazer/pular por
  instrumento (as chaves de divergência precisam ser namespaced por TAG
  pra não colidir — duas TAGs diferentes podem ter as duas uma divergência
  de chave `"sn_instrumento"`) e um `gerar_lote()` que gera tudo que
  estiver pronto.
- **Front (`webui/`)**: nova tela `#view-review-lote` (ou reaproveitar a
  `#view-review` com um modo "lote" que renderiza N grupos em vez de 1) +
  função `renderDivergenciasLote(payload)` no `app.js`, adaptando
  `renderIssueCard` pra aceitar/propagar a TAG do grupo nos
  `data-*` dos botões.

### Perguntas em aberto (decidir antes de implementar, não durante)
- O gate de confirmação "certificado não corrigido" (MANTIDO) na geração:
  pergunta uma vez agregando todos os instrumentos com pendência assim, ou
  uma vez por instrumento?
- Confirmar que instrumentos sem divergência realmente devem gerar
  automaticamente sem aparecer em lugar nenhum antes da tela final (ou se
  o usuário quer vê-los listados em algum resumo antes de gerar).

**Status: implementado.** Decisões tomadas na implementação (o usuário
mandou "implemente" sem responder as perguntas em aberto explicitamente):
- Gate "certificados não corrigidos" (MANTIDO) pergunta **uma vez só**,
  agregando todos os instrumentos/divergências afetados numa lista —
  `RevisionService.confirmar_geracao_lote()`.
- Instrumentos sem nenhuma divergência realmente não aparecem na tela
  agregada — só entram na geração automática.
- "Pular certificado" na tela agregada apenas remove o grupo e re-renderiza
  (não dispara geração automática, mesmo que seja o último pendente — quem
  decide gerar é sempre o clique em "Gerar relatórios").
- Arquivo já existente durante `gerar_lote`: sobrescreve direto (sem
  confirmação por item, que viraria uma sequência de diálogos) e registra
  um evento "sucesso" avisando que sobrescreveu.

O que mudou no código:
- `gui/revision_service.py`: `iniciar_revisao` agora só redireciona pra
  `coletar_revisao_lote` quando `em_lote_ativo()`; extraído
  `_montar_dados_revisao`/`_montar_resumo_instrumento`/
  `_serializar_issues_dict` (compartilhados entre os dois fluxos). Novo:
  `coletar_revisao_lote`, `_montar_payload_divergencias_lote`,
  `resolver_divergencia_lote`, `desfazer_divergencia_lote`,
  `pular_instrumento_lote`, `confirmar_geracao_lote`, `gerar_lote`,
  `_gerar_e_montar_resultado` (geração fatorada, compartilhada com
  `confirmar_geracao`). Removido `avancar_apos_sucesso_revisao`
  (ficou morto — a tela de revisão de um único item nunca mais é mostrada
  em modo lote) e as ramificações de lote dentro de `confirmar_geracao`
  e `voltar_da_revisao` (o mesmo motivo).
- `gui/pdf_service.py`: `avancar_fila` não decide mais sozinho o que
  mostrar ao esgotar a fila — isso virou `_ao_fila_esgotada` (escolhe entre
  tela de divergências agregada, gerar tudo direto, ou ir pra saída). Novo
  `finalizar_lote_manualmente` (wrapper público de `_finalizar_lote`, usado
  por `gerar_lote`). Tempo mínimo de ~2s por item
  (`TEMPO_MINIMO_POR_ITEM`/`_aguardar_tempo_minimo_item`), aplicado em
  `avancar_fila` antes de avançar pro próximo.
- `gui/api.py`: novo estado `instrumentos_lote`; novos métodos de facade
  `resolver_divergencia_lote`, `desfazer_divergencia_lote`,
  `pular_instrumento_lote`, `confirmar_geracao_lote`.
- `webui/index.html`: nova tela `#view-review-lote` (scrollável).
- `webui/js/app.js`: `renderIssueCardLote`/`renderGrupoLote`/
  `renderDivergenciasLote` (paralelos aos do fluxo de arquivo único, pra
  não arriscar quebrar o que já estava testado) +
  `resolverDivergenciaLote`/`desfazerDivergenciaLote`/
  `pularInstrumentoLote`/`confirmarGeracaoLote`. `confirmarGeracao`
  (arquivo único) simplificado de volta, removendo os ramais de lote que
  ficaram mortos.
- `webui/css/styles.css`: `.lote-grupo`/`.lote-grupo-issues`.

**Testado isoladamente (fora da UI, chamando os métodos direto, com
`gerar_ac_escolha` mockado pra não acionar o Excel de verdade):** fila
esgotada com 3 instrumentos (1 sem divergência, 1 com divergência de duas
opções, 1 bloqueante sem ação) → mostra a tela agregada só com os 2 que têm
pendência → resolve um, pula o outro → gera os 2 prontos → fecha o lote
com o evento do pulado na lista de eventos. **Teste na UI real com PDFs de
verdade ainda pendente de confirmação do usuário.**

## Status geral: todas as 5 fases concluídas e testadas manualmente.
Falta só, quando o usuário quiser, organizar tudo em commits e dar push
(mesmo processo já usado pra refatoração SOLID em `TASKS.md`).

## Pendente para amanhã: gate de confirmação em divergência "MANTIDA"
Contexto: ao resolver uma divergência de duas opções (`opcoes`) escolhendo
"Manter o cadastro" (não aplicar), o card passa a ficar num estilo de aviso
com a tag "MANTIDO" em vez do verde de resolvido (isso já foi implementado
e testado — ver `renderIssueCard` em `webui/js/app.js` e o campo `aplicado`
em `gui/revision_service.py::serializar_issues`/`resolver_divergencia`).

O usuário então perguntou se "Gerar relatório e XML" deveria ficar
bloqueado nesse caso. Esclarecimento técnico dado a ele: o AC gerado
**sempre** usa os dados do certificado (`dados_pdf`), nunca o valor do
banco — "manter o cadastro" só decide se o cadastro interno é atualizado
ou não, não afeta o conteúdo do documento gerado. Ele escolheu, com essa
informação:

> "seria a primeira opção mas ele bloqueia para esse caso a geração e
> segue para o próximo"

Ou seja: **confirmação explícita ao clicar em "Gerar"** quando existe
alguma divergência "mantida" sem corrigir
("Certificado não corrigido — as divergências abaixo foram mantidas sem
corrigir o cadastro: [...]. Deseja gerar o relatório e o XML mesmo
assim?"). Se o usuário **recusar**, a geração desse certificado é
bloqueada e o fluxo **segue pro próximo da fila** (modo lote) ou volta pra
seleção (arquivo único) — não fica preso na tela de revisão. Se
**confirmar**, gera normal e segue como já funciona hoje.

**Já implementado (não testado ainda — parei aqui pra retomar amanhã):**
- [x] `gui/revision_service.py::confirmar_geracao` — novo bloco antes do
      `try:` de geração: monta a lista `mantidas` (issues resolvidas com
      `opcoes` e `aplicado is False`), chama `api.confirm(...)`; se o
      usuário recusar, chama `api.alert("Certificado não gerado", ...,
      "error")` seguido de `api._voltar_para_selecao()` — reaproveitando
      TODO o mecanismo de lote já existente da Fase 5 (`DialogBridge.alert`
      já intercepta e registra em `eventos_lote` quando em modo lote;
      `voltar_para_selecao` já chama `avancar_fila()` que avança pro
      próximo item ou fecha o lote). Não precisou tocar em
      `pdf_service.py` nem no front — a reutilização do gate de lote já
      pronto cobriu o caso novo automaticamente.

**Falta para amanhã:**
- [x] `py_compile` do `gui/revision_service.py` — OK.
- [ ] Lançar o app e testar os dois casos:
      1. Arquivo único: divergência mantida → clicar "Gerar" → aparece o
         diálogo → recusar → deve voltar pra tela de seleção sem gerar.
         Confirmar → deve gerar normal.
      2. Lote com 2+ arquivos, um deles com divergência mantida: recusar
         nesse item → deve pular ele (sem gerar) e seguir pro próximo
         certificado da fila sozinho; no final, a tela agregada deve
         mostrar esse item na seção de eventos/falhas, não como card de
         instrumento gerado.
- [ ] Conferir a mensagem exata do diálogo e do evento registrado (título
      "Certificado não corrigido" no confirm, "Certificado não gerado" no
      alert/evento) — ajustar texto se o usuário achar que precisa.
- [x] Barra de progresso de "Divergências" fica **vermelha** (classe
      `.issue-progress-fill.mantido`) em vez de verde quando alguma
      divergência resolvida ficou "mantida" (cadastro não corrigido) —
      pedido do usuário depois de ver o card MANTIDO funcionando.

## Achado crítico (não é bug do design): pywebview 5.4 incompatível com o WebView2 instalado
Ao testar a Fase do gate MANTIDO, o usuário relatou que o seletor de
arquivo parou de abrir. Investigação:

- Eu tinha testado a sessão inteira com o **Python do sistema**
  (`pywebview==6.2.1`), nunca com o **venv do projeto**
  (`pywebview==5.4`, o que o usuário realmente usa).
- Reproduzido no venv: clicar na dropzone não fazia nada — sem erro, sem
  diálogo, e o tracker nem renderizava (sinal de que `init()` no
  `app.js` nunca rodava).
- Diagnóstico direto via `window.evaluate_js` (decorada com
  `@_pywebview_ready_call`) mostrou timeout esperando o evento interno
  `_pywebviewready` — ou seja, a ponte JS do pywebview nunca terminava de
  injetar (`window.pywebview.api` nunca é criado, o evento DOM
  `pywebviewready` nunca dispara, `app.js` nunca inicializa nada).
- **Confirmado que não era regressão do que fizemos hoje**: testei o
  commit `131a859` (antes de qualquer mudança de design, só a refatoração
  SOLID) via `git worktree` temporário (removido depois, sem afetar o
  repo real) rodando com o mesmo venv real — **o mesmo bug acontece lá
  também**. É um problema de ambiente, não do código.
- Causa raiz: WebView2 Runtime instalado na máquina é muito recente
  (151.0.4129.101) pra `pywebview==5.4` (que estava pinado no
  `requirements.txt`).
- **Correção:** `pywebview` atualizado pra `6.2.1` no venv do projeto e no
  `requirements.txt`. Testado: seletor de arquivo volta a funcionar.

## Correção: rolagem na tela "Arquivos gerados" em lote + evento com nome errado
Usuário testou um lote de 3 instrumentos (par PT/TE/TT) e reportou duas
coisas pelo mesmo print:

1. **Pedido:** rolagem tanto pros arquivos de cada instrumento (se tiver
   muitos) quanto pra lista geral de instrumentos processados.
   - `webui/js/app.js::showOutputLote` — arquivos de cada grupo agora
     ficam dentro de `.output-group-files` (novo wrapper), com
     `max-height: 168px; overflow-y: auto`.
   - `webui/css/styles.css` — `.output-groups` (lista de instrumentos)
     ganhou `flex: 1; min-height: 0` pra realmente disputar espaço como
     região rolável independente dentro de `#output-lote`, em vez de só
     depender do scroll da `.view-body` externa; `.output-events` ganhou
     `max-height: 200px; overflow-y: auto` (não deixa a lista de
     falhas/avisos crescer indefinidamente).
2. **Achado à parte, no mesmo print:** os cards de evento "arquivo já
   existia e foi sobrescrito" mostravam o mesmo nome de arquivo errado nos
   3 casos. Causa: `registrar_evento_lote` tirava o "nome" de
   `api.caminho_pdf_atual`, que só é confiável **durante a leitura** (é
   atualizado por item); dentro de `gerar_lote`/`pular_instrumento_lote` —
   que rodam **depois** que toda a leitura da fila já terminou — esse
   valor fica parado no último item lido, não no instrumento do laço
   atual. Corrigido com um parâmetro `nome` opcional em
   `registrar_evento_lote`, passado explicitamente
   (`os.path.basename(inst["caminho_pdf"])`) nesses dois lugares; as
   outras chamadas (durante a leitura) continuam usando o valor implícito,
   que ali é correto.

## Correção: checklist da leitura em lote nunca mostrava "Validando"/"Montando"
`coletar_revisao_lote` (Fase 6) rodava a `ValidationEngine` e já avançava
pro próximo item sem nunca chamar `App.onProgress` de novo depois do
"compare" — os passos "Validando regras da ANP" e "Montando relatório e
XML" do checklist ficavam sempre cinza, parados, mesmo a validação já
tendo rodado por trás. Corrigido: `_progress(70, "validate", ...)` logo
depois de rodar a engine, e `_progress(100, "build", CHECKLIST_ALL)` antes
de avançar pro próximo certificado — mesmo padrão que os tipos de geração
direta (cromatografia/incerteza) já usavam.

**Ressalva de nomenclatura (não é bug, é intencional):** em lote,
"Montando relatório e XML" completa aqui só significa "esse certificado
terminou de ser lido/coletado" — a geração de verdade (Excel/XML) só
acontece depois, em `gerar_lote`, na tela de saída. Isso é assim de
propósito (Fase 6: leitura contínua separada da geração), só reaproveitei
o mesmo checklist visual que a leitura de arquivo único já usa.

## Correção 3 (causa raiz de verdade): `.output-group` encolhia e cortava sem chance de rolar
Depois da correção 2, o usuário testou de novo e o corte visual continuava
idêntico — nenhuma linha de arquivo extra aparecia, nenhuma barra de
rolagem visível. Fui até o fim dessa vez: injetei o mesmo payload numa
janela isolada, contei quantos `.output-file-row` existem de verdade no
DOM (3 por grupo — a renderização do JS estava sempre correta) e comparei
`scrollHeight` vs `clientHeight` de cada contêiner.

Achado real: `.output-group` (cada card de instrumento) **não tinha
`flex: none`**. Como é filho de `#output-groups`, que é
`display:flex;flex-direction:column`, ele herdava o `flex-shrink: 1`
padrão — ou seja, o flexbox podia **encolher cada card** quando os 3
juntos não cabiam no espaço disponível. E como `.output-group` usa
`overflow: hidden` (só pra arredondar os cantos), esse encolhimento
**cortava o conteúdo direto**, sem nunca deixar a rolagem interna de
`.output-group-files` (da correção 1) ser alcançada — o card já chegava
espremido antes disso.

**Correção:** `.output-group { flex: none; }` (mesmo padrão que
`.lote-grupo`, da tela de divergências agregada, já tinha por acaso — só
essa tela de saída estava sem). Também adicionado a `.output-event` por
prevenção (mesmo risco, efeito menor pois não usa `overflow:hidden`).
Confirmado por inspeção: `#output-groups` agora reporta `scrollHeight`
maior que `clientHeight` (599px de conteúdo em ~312px de espaço) — ou
seja, agora ele **de fato** detecta que precisa rolar, coisa que nunca
acontecia antes porque os cards nunca cresciam o suficiente pra disparar
isso.

## Correção 2 (a rolagem anterior não resolveu de verdade): nome de arquivo longo quebrava linha e furava o limite de altura
Usuário testou de novo e reportou que a rolagem "não apareceu, está
estático" — o mesmo corte visual de antes. Investiguei com um script
isolado que injeta `App.showOutputLote(...)` numa janela real e lê
`scrollHeight`/`clientHeight` computados (sem precisar clicar em nada na
UI de verdade).

Achado: `.output-file-name`/`.output-file-meta` não tinham
`white-space: nowrap` — com nomes de arquivo reais (longos, ex.:
`26-ODS-37-PRE-274_044-PT-1020D_AC.pdf`), o texto **quebrava em 2 linhas**,
deixando cada linha de arquivo mais alta do que o `max-height: 168px` que
eu tinha colocado em `.output-group-files` na correção anterior — ou seja,
a correção da rolagem por instrumento **causou** esse corte especificamente
por causa da quebra de linha, não por ter "muitos arquivos" de verdade.

**Correção:** `.output-file-name`/`.output-file-meta` ganharam
`white-space: nowrap; overflow: hidden; text-overflow: ellipsis;` (mesmo
padrão já usado em `.recent-name`/`.output-group-meta`) — nome longo agora
trunca com "..." em vez de quebrar linha. Confirmado por inspeção direta
(mesmo script) com os nomes reais do teste do usuário: 3 arquivos por
grupo agora cabem em ~153px, dentro do limite de 168px, sem cortar.

## Correção: vínculo TE↔TT/TIT usava um "último TE visto" global, não por TAG
O usuário perguntou se o lote respeitava a regra "TE antes do TT/TIT" (o
TT precisa do nº de certificado do TE correspondente pra vincular no XML
da PRIO). Investigando, achei um bug de verdade, não só uma questão de
ordem:

- `gerar_xml_calibracao` só usa `certificado_te` quando o **tipo do
  instrumento nos pontos de calibração** é `"TT"` (não é sobre a TAG
  conter "TIT" — é uma classificação interna, derivada dos pontos, ver
  `determinar_tipo_xml`).
- O valor vinha de `Api.certificado_te_atual`: **um único slot global**
  que guardava o certificado do último TE processado, sem checar se era o
  par certo daquele TT. Isso já era frágil no fluxo de um único arquivo
  (dependia do usuário processar TE→TT na ordem certa, sem garantia) e
  piora em lote: com **mais de um par TE+TT no mesmo lote**, cada TT
  pegaria o certificado do último TE visto até aquele ponto — errado pra
  qualquer par que não fosse o mais recente.

**Correção:** `Api.certificado_te_atual` (slot único) →
`Api.certificados_te_por_par` (dict), casando pela parte do TAG **sem** o
prefixo de tipo (nova `xml_model.xml_generator.chave_par_te` — ex.:
`TE-1234-56` e `TIT-1234-56` → mesma chave `"1234-56"`). A busca do
certificado do TE agora acontece **na hora de gerar** (dentro de
`_gerar_e_montar_resultado`, compartilhado por `confirmar_geracao` e
`gerar_lote`), não mais no momento da leitura — em lote, isso significa
que a ordem de leitura dentro da fila **não importa mais**: como toda a
leitura termina antes de qualquer geração (Fase 6), o dict já está
completo quando cada TT busca seu par, mesmo que tenha sido lido antes do
seu TE. `certificados_te_por_par` vive a sessão inteira do app (não é
resetado por leitura), porque o usuário pode processar TE e TT em ações
separadas, não necessariamente no mesmo lote.

**Testado isoladamente:** simulei o pior caso — 2 pares TE+TIT no mesmo
lote, os dois TIT coletados **antes** dos seus respectivos TE — e cada
TIT recebeu o certificado do seu próprio TE, não o de outro par.

## Correção: arquivos de arrastar-e-soltar iam para a pasta temporária
`obter_caminho_ac` sempre salva o relatório/XML gerado na mesma pasta do
certificado de origem. Como `receber_arquivos_soltos` (drag-and-drop)
salvava o arquivo recebido em `%TEMP%\certiflow_drop`, os arquivos GERADOS
também caíam lá — uma pasta que o Windows pode limpar sozinho e que
ninguém pensaria em checar. Corrigido pra salvar em
`Documentos\AC's Generator\Certificados Recebidos` (mesmo padrão de
`pasta_documentos` já usado no import/export de XLSX). Seleção via diálogo
de arquivo não muda — continua indo pra pasta que o usuário escolheu.

Além disso, por pedido do usuário: a pasta `Certificados Recebidos` deve
ter só os arquivos **gerados** (PDF/XML), não o certificado de origem
arrastado. Novo `gui/support.py::limpar_certificado_solto(caminho)` —
apaga o arquivo se (e só se) ele estiver dentro dessa pasta, chamado
depois de gerar com sucesso em todos os pontos de saída (cromatografia,
incerteza, linearização, e o caminho SEC/PO/TR compartilhado por
`confirmar_geracao`/`gerar_lote` via `_gerar_e_montar_resultado`). Em caso
de erro/certificado pulado, o original permanece (pra permitir tentar de
novo).

**Ação de acompanhamento:** como essa era a versão que o `requirements.txt`
pinava desde antes desta sessão, vale considerar se algum outro ambiente
(outra máquina, o build do PyInstaller) também precisa dessa atualização —
não investigado ainda.

## Achado adicional: certificado com divergência bloqueante sem ação nenhuma travava o lote
Com o pywebview corrigido, o usuário testou um lote de 4 certificados e um
deles ("Incerteza abaixo da CMC", de `regra_cmc`) é uma divergência
**bloqueante** (`blocking=True`) com **`action=None`** — ou seja, sem
nenhum botão "Ignorar"/"Aplicar correção" pra resolver. Antes dessa
correção, não havia NENHUMA saída dessa tela: "Gerar" ficava desabilitado
pra sempre e a fila nunca avançava — de fora parecia que o app "travava no
primeiro e não mostrava os outros".

Existem outras regras com o mesmo padrão (`action=None, blocking=True`) em
`rules_sec.py`: `regra_rangein`, `regra_incert_fidu`, `regra_classe`,
`regra_local_fpso`, `data_proxcal`, `prazo_emissao`, `regra_haste_te` —
todas ficariam presas do mesmo jeito sem o botão de voltar.

**Correção:**
- [x] Botão "←" na tela de revisão (já existia, feito antes) agora chama
      `Api.voltar_da_revisao()` (novo) em vez de `cancelar_leitura()`.
- [x] `RevisionService.voltar_da_revisao()`: fora do lote, só limpa o
      estado de revisão (JS navega de volta pra seleção). **Em lote**,
      registra o certificado como "Certificado pulado" (com o(s)
      título(s) das divergências bloqueantes ainda pendentes como motivo)
      via `registrar_evento_lote`, e chama `voltar_para_selecao()` — que já
      aciona `avancar_fila()` (mesmo mecanismo da Fase 5) pra seguir pro
      próximo item, em vez de cancelar o lote inteiro como
      `cancelar_leitura()` fazia.
- [x] Corrigido de brinde: `App.setFilaProgresso(indice, total)` estava
      faltando o 3º argumento (`nome`) que o JS já esperava — o nome do
      arquivo não aparecia na tela de leitura a partir do 2º item do lote.
- Testado isoladamente (fora da UI, chamando os métodos direto): confirma
  que avança a fila corretamente e registra o evento certo. Teste na UI
  real pendente de confirmação do usuário.

## Polimento pós-fases: janela nativa (Ac_app.py)
- [x] Ícone da janela/taskbar trocado do padrão do Python pro ícone da ODS
      (`logo/logo icon.ico`) via `webview.start(icon=...)` — seguro porque
      roda antes do loop de mensagens da UI começar.
- [x] Título da janela simplificado de "AC's Generator — CertiFlow" pra só
      "CERTIFLOW" (maiúsculo).
- [x] Fonte do "CERTIFLOW" grande (`.brand-lg`) aumentada (26px→34px) nas
      telas de seleção/leitura.
- [~] **Tentativa revertida:** remover o ícone da barra de título
      (`form.ShowIcon = False`) e pintar o texto do título via
      `DwmSetWindowAttribute` (API nativa do Windows 11), acionado no
      evento `window.events.shown`. **Travou o app** ("Not Responding") —
      mesma classe de bug do T40 em `TASKS.md`: o evento `shown` do
      pywebview roda fora da thread de UI, e mexer no `Form` nativo
      (`window.native`) fora da thread certa trava a janela.
      **Decisão do usuário:** manter o ícone da ODS, só maiúsculo mesmo.
      **Lição pra próxima vez:** qualquer customização do `Form`/`window.native`
      do WinForms só é segura se feita antes de `webview.start()` (via
      parâmetros como `icon=`), nunca de dentro de um callback de evento
      (`shown`, `loaded`, etc.) sem confirmar antes em qual thread ele roda.

## Otimização: reaproveitar a instância do Excel COM durante o lote
Usuário percebeu um delay perceptível na transição revisão → saída em lote.
Causa: cada AC gerado (`gerar_ac_*`) abre um processo **novo** do Excel via
`win32.DispatchEx("Excel.Application")` só para exportar o `.xlsx` já
preenchido (pelo openpyxl) como PDF, e fecha esse processo (`excel.Quit()`)
no `finally` — em lote, isso se repete a cada instrumento, e abrir/fechar o
Excel é a parte mais lenta de cada geração.

Alternativa maior (reescrever os 8 templates em HTML/CSS e gerar o PDF sem
Excel) foi discutida e **descartada por ora** — risco alto (8 variantes de
template já aprovadas: PRIO, YINSON, YINSON ATLANTA, ORIGEM + 4 variantes
PO) para um ganho que a alternativa abaixo já entrega com risco bem menor.
Fica registrada como iniciativa futura separada, não decidida a se fazer.

**Plano (reaproveitar 1 instância em vez de N):**
- [x] Adicionar parâmetro opcional `excel=None` em cada gerador que hoje
      cria sua própria instância COM: `gerar_ac_completo` (e os 3 wrappers
      `gerar_ac_prio`/`gerar_ac_yinson`/`gerar_ac_yinson_atlanta`, em
      `form/full_ac_templates.py`), `gerar_ac_po` (e os 3 wrappers
      `gerar_ac_origem_PO`/`gerar_ac_yinson_PO`/`gerar_ac_yinson_atlanta_PO`,
      em `form/po_templates.py`), `gerar_ac_origem`
      (`form/utils_print_ORIGEM.py`) e `gerar_ac_prio_po`
      (`form/utils_print_PRIO_PO.py`). Quando `excel` é passado, a função
      usa essa instância e **não** chama `excel.Quit()`; quando não é
      passado (`None`, comportamento atual), continua criando e encerrando
      a própria instância exatamente como hoje — path de arquivo único
      (`confirmar_geracao`) fica 100% inalterado.
- [x] Propagar `excel=None` pelo roteador `gerar_ac_escolha`
      (`form/utils_print.py`) até o gerador escolhido.
- [x] `RevisionService._gerar_e_montar_resultado` recebe `excel=None` e
      encaminha pro `gerar_ac_escolha`.
- [x] `RevisionService.gerar_lote()`: abre uma única instância do Excel
      COM (`Visible/DisplayAlerts/ScreenUpdating/Interactive = False`)
      antes do loop — só se houver ao menos 1 instrumento na fila — passa
      pra `_gerar_e_montar_resultado` a cada iteração, e garante
      `excel.Quit()` num `finally` depois do loop, mesmo se algum
      instrumento falhar no meio.
- [x] Compilados sem erro todos os arquivos tocados (`form/utils_print.py`,
      `form/full_ac_templates.py`, `form/po_templates.py`,
      `form/utils_print_ORIGEM.py`, `form/utils_print_PRIO_PO.py`,
      `gui/revision_service.py`). App relançado pela venv — teste de um
      lote real pelo usuário pendente de confirmação (delay reduzido +
      sem regressão na geração de arquivo único).

## Correção: "Manter o cadastro" em lote gerava AC com dado divergente
Usuário testou um lote com uma divergência de SN do Instrumento (PDF ≠
banco). Ao escolher "Manter o cadastro" e depois clicar em "Gerar
relatórios", a tela mostrava um confirm "Certificados não corrigidos —
deseja gerar mesmo assim?" e, ao confirmar, o instrumento **era gerado**
mesmo com o cadastro divergente do certificado — um AC com dado
metrologicamente incorreto.

Existem 3 divergências com esse padrão de duas opções ("Usar o
certificado" x "Manter o cadastro"), todas em `validation/rules_sec.py`:
`regra_sn_instrumento` (SN do Instrumento), `regra_sn_sensor` (SN do
Sensor) e `regra_range` (Range divergente).

**Correção:**
- [x] As 3 regras: label da 2ª opção trocado de "Manter o cadastro" pra
      "Pular certificado" (o valor do cadastro atual continua exibido do
      lado, pra manter visível a diferença PDF x Banco).
- [x] `RevisionService.resolver_divergencia_lote`: ao escolher a opção
      "não aplicar" (`aplicar=False`) numa divergência com `opcoes`, em vez
      de marcar `resolved=True, aplicado=False` (e deixar seguir pra
      geração com aviso), agora chama `pular_instrumento_lote(tag,
      motivo=...)` — remove o instrumento inteiro do lote, registrando um
      evento com o título e a mensagem da divergência (que já contém
      "PDF: X / Banco: Y"). Os demais instrumentos do lote seguem
      normalmente.
- [x] `pular_instrumento_lote` ganhou um parâmetro opcional `motivo` (senão
      continua usando os títulos das divergências bloqueantes pendentes,
      como já fazia pro botão "Pular certificado" da tela agregada).
- [x] `confirmar_geracao_lote`: removido o bloco morto que perguntava
      "Certificados não corrigidos, gerar mesmo assim?" — não há mais como
      chegar num instrumento "mantido sem corrigir" nesse ponto, ele já foi
      removido do lote no passo anterior.
- [x] `renderIssueCardLote` (app.js): removida a variante "MANTIDO" do
      card resolvido — em lote, um card só chega resolvido quando a opção
      aplicada de fato corrigiu o cadastro.
- Escopo: só o fluxo em lote. O fluxo de arquivo único
      (`confirmar_geracao`/`resolver_divergencia`, tela de revisão comum)
      não foi alterado — lá o botão "Pular certificado e continuar" já
      existe separadamente (via `voltar_da_revisao`) pra esse caso.

## Botão "←" na tela de divergências do lote
A tela de revisão de arquivo único (`view-review`) já tinha um "←" pra
voltar e escolher outro certificado; a tela agregada `view-review-lote`
(Fase 6) não tinha nenhum jeito de voltar — se o usuário selecionasse os
PDFs errados, só dava pra seguir corrigindo/pulando até o fim do lote.

- [x] Botão "←" (mesmo estilo `.edit-back` do `view-review`) adicionado no
      topo de `view-review-lote`, ao lado do título "Divergências do
      lote".
- [x] `voltarDaRevisaoLote()` (app.js): chama `pywebview.api.cancelar_leitura()`
      (já existente — encerra a fila e limpa `instrumentos_lote`),
      `resetSelecao()` e volta pra tela de seleção. Nenhum código novo no
      backend — reaproveita o mesmo cancelamento cooperativo já usado pelo
      botão "Cancelar" da tela de leitura.

## XML de cromatografia reduzido pra 5 parâmetros
Usuário pediu pra reduzir o XML de cromatografia (gerado a partir de
relatórios da SGS) pro formato de um XML de exemplo já aprovado (cert.
15833/2026.0.A, cliente Origem Energia Alagoas): só `EMPRESA`,
`CERTIFICADO` e 5 parâmetros usados no cálculo de vazão, em vez da
estrutura antiga com `CABECALHO` + lista completa de componentes da
composição do gás + todas as propriedades de ambas as seções do relatório.

**Mapeamento dos 5 parâmetros** (confirmado com o usuário):
- `MASSA_MOLAR` ← "Peso Molecular Total (g/mol)", seção Condição Padrão.
- `DENSIDADE_ABSOLUTA` ← "Densidade (kg/m³)", seção Condição Padrão
  (exclui "Densidade Relativa" explicitamente).
- `FATOR_COMPRESSIBILIDADE_CL` ← "Fator de Compressibilidade", seção
  Condições de Amostragem (condições de linha).
- `VISCOSIDADE_GAS_CL` ← "Viscosidade do Gás (cP)", Condições de
  Amostragem — **sem** tag de incerteza (nota (2) do relatório: vem de
  correlação de referência, não de medição direta, igual ao exemplo).
- `COEFICIENTE_ISENTROPICO_CL` ← "Coeficiente Adiabático" (sinônimo de
  coeficiente isentrópico), Condições de Amostragem.

**Implementação:**
- [x] `xml_model/xml_cromato.py` reescrito: `_buscar_propriedade()` procura
      por nome (sem acento/maiúsculas, com termos obrigatórios/alternativos/
      exclusão) numa lista de propriedades já extraída, em vez de despejar
      a lista inteira no XML. `xml_cromatografia()` monta só os 10 elementos
      do exemplo (2 de identificação + 5 valores + 4 incertezas).
- [x] `EMPRESA` estava errado mesmo antes desta mudança: vinha de
      `extrair_empresa()`, que só identifica o laboratório ("SGS", usado
      pra roteamento em `select_extract`) — sempre gerava `<EMPRESA>SGS</EMPRESA>`,
      nunca o cliente. Criada `extrair_cliente()` (pdf/parser_sgs.py),
      usada só dentro de `extrair_campos_cromato` pro campo `empresa`;
      `extrair_empresa` continua intacta pro roteamento.
- [x] Achado durante o teste com o PDF real da PRIO (anexado pelo
      usuário): o cabeçalho "Cliente:"/"Endereço:" e o título "Propriedades
      do Gas - Condição Padrão (1) Referência" são extraídos com o
      rótulo/título separado do valor (aparecem em posições bem distantes
      no texto) — um problema de layout do template da SGS, não deste
      código. `extrair_cliente()` já nasceu com um fallback (ancora no
      título "RELATÓRIO DE ANÁLISES DE GÁS NATURAL" e pega a linha seguinte
      não vazia). Adicionados fallbacks equivalentes em `numero_cert()`
      (ancora no mesmo título, número colado nele) e `propriedades_padrao()`
      (ancora só na linha "Referência" isolada, quando o título completo
      não é encontrado) — sem alterar o caminho feliz existente.
- [x] Testado isoladamente com o texto do PDF anexado (script de
      diagnóstico, fora da UI): os 5 valores + incertezas saem corretos e
      o XML gerado bate exatamente com a estrutura do exemplo. Teste com o
      app real (arrastar o PDF na tela de leitura) pendente de confirmação
      do usuário.

## Segunda fonte: relatório de cromatografia da própria Origem (LIMS)
Além do relatório da SGS, a Origem também tem um relatório de
cromatografia gerado pelo laboratório interno deles (LIMS "Report
Builder"/mylimsweb.cloud) — layout completamente diferente (tabela
"Resultados Analíticos" com colunas Análise/Resultado/LQ/LD/Incerteza/
Referência/Data). Esse relatório já usa os nomes "Massa Molar",
"Densidade Absoluta", "Fator de compressibilidade - CL", "Viscosidade do
gás - CL" e "Coeficiente Isentrópico - CL" **literalmente** — o que
confirma que o mapeamento padrão/CL definido na 1ª fonte estava certo.

- [x] Novo `pdf/parser_origem_cromato.py`: `identificar_origem_cromato`
      (âncora: "Laboratório Cromatografia - Origem Energia Alagoas"),
      `extrair_campos_cromato_origem` — devolve o `dados` no MESMO formato
      usado por `extrair_campos_cromato` (SGS), então `xml_cromatografia()`
      não precisou de nenhuma mudança pra essa fonte nova.
  - `_linha_propriedade`: busca a linha da tabela pelo nome exato da
    análise, exigindo que o valor venha logo em seguida (sem nada no
    meio) — evita casar "Densidade Absoluta" com a linha "Densidade
    Absoluta - CL ...".
  - `_normalizar_numero`: os valores de Incerteza vêm com ponto decimal e
    às vezes em notação científica (ex.: "5E-05") — convertido pro
    formato brasileiro com vírgula (ex.: "0,00005"), igual ao resto do
    app e ao exemplo aprovado.
  - `extrair_certificado_origem`: o número do relatório aparece em mais
    de uma variante no mesmo PDF (com e sem sufixo ".A"); usa a mais
    específica (mais longa).
- [x] `xml_model/xml_cromato.py`: busca de `MASSA_MOLAR` ampliada pra
      aceitar tanto "Peso Molecular" (SGS) quanto "Massa Molar" (Origem).
- [x] `pdf/utils_parser.py::select_extract`: novo `elif` roteando pra esse
      parser quando `identificar_origem_cromato` bate, antes do fallback
      "instrumento secundário".
- [x] Testado isoladamente com o texto do relatório anexado: XML gerado
      bate 100% com o exemplo aprovado (mesma estrutura, mesmos valores,
      incluindo a conversão de "5E-05"/"0.0015" pra "0,00005"/"0,0015").
      Teste com o app real ainda pendente de confirmação do usuário.
