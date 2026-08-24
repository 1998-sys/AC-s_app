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
- [ ] Rodar `python -m py_compile gui/revision_service.py` (não rodei —
      fui interrompido antes de confirmar).
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
