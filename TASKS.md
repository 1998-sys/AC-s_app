# Backlog de Refatoração SOLID — AC's_app

> Como usar: marque `[x]` quando a task for concluída e commitada. `[~]` = avaliada e decidida como "não
> aplicar" (motivo descrito na própria linha) — não é pendência, é uma decisão registrada. Cada task tem
> um ID (T1, T2...) — use esse ID no commit (`fix(T1): ...`) para rastrear no `git log`. Numa sessão nova
> do Claude Code, basta pedir "continua o TASKS.md" para retomar exatamente daqui, sem precisar re-varrer
> o projeto.

Gerado em: 2026-08-24, a partir de auditoria completa do backend Python (5 agentes cobrindo
core/processors/gui, data/validation, form/, pdf/, importer/xml_model).

---

## 🔴 CRÍTICO — encontrado no teste manual pós-refactor

- [x] **T40** — App travava ("Not Responding") por vários segundos logo na abertura, de forma intermitente.
  **Causa raiz**: `gui/api.py::Api` expunha `self.window` como atributo público. pywebview injeta a `Api`
  como `js_api` e reflete recursivamente (`pywebview/util.py::get_functions`) sobre todo atributo público
  não-privado procurando métodos pra expor ao JS. Ao descer em `self.window` (o objeto nativo do
  WebView2/WinForms), a reflexão caía no grafo de `AccessibilityObject`/`ActiveControl`/etc. — que tem
  referências circulares reais no COM do Windows — e também tentava acessar `CoreWebView2Controller` fora da
  UI thread (violação de threading STA), gerando um `RecursionError` interno do pywebview e travando a
  janela por vários segundos. **Esse bug já existia antes desta sessão** (o `self.window` original tinha o
  mesmo problema); os atributos novos do T12 (`_dialogs`, `_pdf_service` etc.) já nasceram prefixados com
  `_` e não contribuíam pra ele. **Corrigido**: renomeado `self.window` → `self._window` em `gui/api.py` e
  `gui/dialogs.py` (linha com `_` é pulada pela reflexão do pywebview antes de descer nela). Diagnosticado
  lendo o código-fonte instalado do pywebview (`site-packages/webview/util.py`) e confirmado com 5
  lançamentos consecutivos do app monitorando CPU/status a cada 2s — antes: log cheio de
  `[pywebview] Error while processing window.native...` e ocasional "Not Responding"; depois: log vazio,
  "Running" o tempo todo, em todas as 5 tentativas.

---

## 🔴 CRÍTICO — bugs ativos em produção

- [x] **T1** — Indicador de calibração PT100 gravado no bloco errado (AS_FOUND em vez de AS_LEFT).
  `xml_model/xml_petro_generator.py:560-563` — corrigido: `cal_as_found` → `cal_as_left`.
- [x] **T2** — Resultado "Rejeitado/Não Aceito" nunca vira "Não" no PO Evaluation Report (10 funções afetadas).
  `pdf/parser_po_ER.py` — unificado num helper `_resultado_aceite()`, igual ao padrão já correto de `parser_tr_ER.py`.
- [x] **T3** — Template Excel mestre sobrescrito a cada AC gerada (corrupção de dados / race condition).
  `form/utils_print_ORIGEM.py`, `utils_print_PRIO.py`, `utils_print_YINSON.py`,
  `utils_print_YINSON_ATLANTA.py`, `utils_print_PRIO_PO.py` — todos agora copiam para temp antes de salvar.
- [x] **T4** — `categoria.upper()` quebra com `AttributeError` se o campo vier vazio.
  `form/utils_print_PRIO.py:58`, `utils_print_YINSON.py:58`, `utils_print_YINSON_ATLANTA.py:58` — corrigido.
- [x] **T5** — `TypeError: float < None` derruba toda validação de "Manômetro Analógico" (chave `"móvel"` com acento vs `"movel"` normalizado).
  `validation/rules_sec.py` — chave normalizada + guard `if cmc is None: return None` adicionado.
- [x] **T6** — Uma regra de validação que falha descarta todos os issues já coletados (sem try/except no loop).
  `validation/engine.py` — try/except por regra + `ValidationIssue` de erro; também corrigidas as 2 causas-raiz
  (`regra_haste_te` usava `ctx.pdf["tag"]`, `prazo_emissao` chamava `.upper()` antes do guard de `None`).
- [x] **T7** — `iniciar_revisao` roda em thread sem try/except; falha trava a UI silenciosamente.
  `gui/api.py:246-311` — envolvido em try/except com `alert()` + `traceback.print_exc()`; também corrigido
  `registro["tag"]` → `registro.get("tag")`.
- [x] **T8** — `CIProcessor` é código morto; existe caminho divergente para tipo "ci" em `gui/api.py`.
  Removido `processors/ci_processor.py` e sua entrada em `core/processor_factory.py` — o caminho real
  (geração direta via `gerar_xml_uc` em `gui/api.py`) foi mantido como única fonte de verdade.
- [x] **T9** — `dados.get("procedimento", "").get(...)` quebra com `AttributeError` se a chave faltar.
  `xml_model/xml_petro_generator.py:172-176` — corrigido para `(dados.get("procedimento") or {}).get(...)`.
- [x] **T10** — `blocking=None` em vez de `blocking=True` — regra que deveria bloquear não bloqueia.
  `validation/rules_sec.py` (`regra_incert_fidu`) — corrigido para `blocking=True`.
- [x] **T11** — Campo `D5` errado no certificado YINSON ATLANTA PO (confirmado contra o template real via openpyxl).
  `form/utils_print_YINSON_ATLANTA_PO.py:36` — corrigido para `D56`.

---

## 🟠 ALTO — arquitetura (violações SOLID com impacto real)

### `gui/api.py` (god object, 536 linhas)
- [x] **T12** — Separar responsabilidades de `Api` (UI bridge / DB / validação / import-export) em camada de serviço.
  Escolhido o modo "fachada fina + delegação": `Api` continua sendo o único objeto exposto ao pywebview (`js_api`)
  e o único que os `processors/*` conhecem como `self.app` — nenhuma assinatura mudou. Por dentro, criadas 5
  classes de serviço em `gui/`: `dialogs.py::DialogBridge` (bridge JS↔Python), `pdf_service.py::PdfProcessingService`
  (classificação/despacho de PDF/XML), `revision_service.py::RevisionService` (validação + geração de AC),
  `instrument_service.py::InstrumentService` (CRUD de instrumento), `import_export_service.py::ImportExportService`
  (XLSX), mais `support.py` para constantes compartilhadas. `Api.__init__` instancia as 5 e cada método público
  vira uma linha de delegação. Bônus: removida `_resource()` morta (nunca era chamada em gui/api.py).
  **Testado com 33 cenários** (7 blocos: roteamento PDF/XML, revisão com `ValidationEngine` real, resolver
  divergência + gerar AC, CRUD de instrumento, import/export XLSX, abrir arquivo, prompt ORIGEM) comparando
  log de chamadas JS e retorno contra a versão monolítica anterior — todos idênticos. App real testado abrindo
  normalmente depois do refactor.
- [x] **T13** — `_processar_pdf_thread` com if/elif hardcoded por tipo; usar `Dispatcher`/`ProcessorFactory` de fato.
  Dentro do `PdfProcessingService`, o if/elif virou um dict `_geradores_diretos = {"cromatografia": ..., "ci": ...}`
  — adicionar um novo tipo que gera XML direto (sem tela de revisão) agora é uma entrada no dict, não editar a
  cadeia de ifs. Não foi unificado com `ProcessorFactory` (exigiria reviver algo como o `CIProcessor` removido no
  T8, com o mesmo risco de duplicar o caminho); os dois registries (geração direta vs. processor-based) continuam
  separados de propósito. Coberto pelos mesmos 33 cenários de teste do T12 (bloco A testa especificamente essa
  troca: cromatografia, ci, tipo genérico e roteamento .xml).
- [x] **T14** — `_js_await` sem timeout; pode travar thread para sempre.
  `gui/api.py:103-119` — corrigido: timeout de 10min como rede de segurança (não para apressar o usuário no modal).
- [x] **T15** — Bloco de imports críticos com `try/except ImportError: print(...)` degradando silenciosamente.
  `gui/api.py:18-36` — removido; são todos módulos internos, agora falham alto no startup se algo quebrar.

### `core/` e `processors/`
- [x] **T16** — `BaseProcessor` sem template method; `trecho_processor.py`/`placa_processor.py` duplicam fluxo inteiro.
  Extraído template method `_iniciar_fluxo_com_report`/`_solicitar_report`/`_processar_report` em
  `BaseProcessor`, com 7 hooks pequenos que cada subclasse implementa (títulos, mensagens, parser do ER,
  pós-processamento). Testado com 18 cenários (9 por processor: dados ausentes, confirm negado, arquivo não
  selecionado, texto/ER vazio, caminho feliz) comparando log de chamadas e mutação de estado contra a versão
  original antes do refactor — todos idênticos. `SecundarioProcessor` não usa esse fluxo (não pede um
  segundo PDF) e não precisou mudar.
- [x] **T17** — `secundario_processor.py:16` reimplementa `fluxo_origem` em vez de reusar `processors/utils.py`.
  Corrigido — e era também um bug real: checava `dados_pdf["local"]` (local físico de calibração) em vez de
  `"cliente"` (usado por trecho/placa via `fluxo_origem`). Confirmado via `pdf/parser_certificados.py:597-601`
  e `regra_local_fpso`.
- [x] **T18** — `processor_factory.py:26-31` instancia os 4 processors a cada chamada; trocar por mapa `{tipo: Classe}`.
  Corrigido — agora instancia só a classe pedida.
- [~] **T19** — `Ac_app.py` importa `data.conexao` direto no entrypoint sem camada de bootstrap (DIP).
  **Decisão: não aplicado.** Introduzir uma camada de bootstrap para um único ponto de chamada (`criar_tabela()`/
  `migrar()` no entrypoint) é abstração especulativa sem consumidor real — não há um segundo backend de
  persistência no horizonte. Revisitar só se isso mudar.

### `data/` e `validation/`
- [x] **T20** — Funções de `data/utils_db.py` sem try/except/finally; conexão vaza em qualquer exceção (~17 funções).
  Reescrito com helpers `_query_one`/`_query_all`/`_execute` usando `contextlib.closing` — testado com banco
  SQLite isolado (insert/busca/update/whitelist, todos passando).
- [x] **T21** — `atualizar_campos_extras` monta `SET` via f-string; adicionar whitelist de colunas.
  `data/utils_db.py` — whitelist `_CAMPOS_EXTRAS_PERMITIDOS` adicionada e testada.
- [x] **T22** — `validation/engine.py:61-70` roteamento por if/elif em string; trocar por registro/dict.
  Corrigido para dict `_regras_por_instrumento` + fallback — testado com `ValidationContext` real (3 cenários).
- [~] **T23** — `rules_po.py`/`rules_sec.py` importam `data.utils_db` direto (DIP); impossível testar sem DB real.
  **Decisão: não aplicado.** Mesma lógica do T19 — introduzir uma interface de repositório para 2 módulos de
  regras é indireção sem ganho concreto hoje; os testes de fumaça deste bloco já mostraram que trocar
  `conexao.db_path` por um SQLite temporário é suficiente para testar sem tocar no banco real.
- [x] **T24** — `CMC_REGRAS` com ~175 linhas de triplicação quase idêntica; colapsar e mover para config/dados.
  `validation/rules_sec.py` — colapsado com helper `_mesma_faixa_todas_localidades()`; confirmado que as 10
  categorias tinham valores idênticos nos 3 locais (nenhum dado alterado) e testado contra `obter_cmc()`.

---

## 🟠 ALTO — duplicação massiva entre arquivos (DRY/OCP)

- [x] **T25** — `form/`: 9 arquivos de certificado por cliente, ~85-90% código idêntico. Extrair renderer único
  guiado por config, seguindo o padrão de `form/utils_print_linearizacao.py` (dict `CELLS`).
  Consolidado em 2 grupos, com os 2 arquivos estruturalmente diferentes deixados de fora de propósito:
  - **`form/po_templates.py`**: unifica `utils_print_ORIGEM_PO.py`, `utils_print_YINSON_PO.py` e
    `utils_print_YINSON_ATLANTA_PO.py` (eram byte-a-byte idênticos em estrutura, só variando
    template/células) num único `gerar_ac_po(config, dados, caminho)` + 3 configs.
  - **`form/full_ac_templates.py`**: unifica `utils_print_PRIO.py`, `utils_print_YINSON.py` e
    `utils_print_YINSON_ATLANTA.py` num único `gerar_ac_completo(config, dados, caminho)` + 3 configs.
    Achado importante: PRIO tem uma regra de negócio que os outros dois NÃO têm (distingue PT de PDT pela
    faixa calibrada para uma categoria específica) — preservada via flag `permitir_split_pt_pdt` no config,
    não unificada/removida, já que eu não tenho autoridade de negócio pra decidir se é intencional.
  - **Deixados como estão, sem tocar**: `utils_print_PRIO_PO.py` (tem lógica própria de bordas/área de
    impressão via COM que não se encaixa no padrão) e `utils_print_ORIGEM.py` (layout de checkbox, regra de
    dia útil e mecanismo de observações totalmente diferentes dos outros 3 — juntar arriscaria alterar
    regra de negócio sem confirmação).
  - Os 6 arquivos substituídos foram deletados (nenhum era importado fora de `form/utils_print.py`).
  **Verificação**: capturei o estado da planilha temporária no exato momento em que o Excel COM a abriria
  (sem precisar rodar Excel de verdade), comparando célula-a-célula contra as versões antigas em 21 cenários
  (3 clientes PO + 3 clientes × 6 categorias/casos no grupo completo, incluindo o caso que ativa o split
  PT/PDT só no PRIO) — todos idênticos. Depois, gerei 2 PDFs reais via Excel COM de verdade (PRIO e
  ORIGEM_PO) e inspecionei visualmente o conteúdo: título, campos e data com +1 dia útil corretos.
- [x] **T26** — `xml_model/`: 6 arquivos repetem boilerplate "Element → tostring → minidom → prettyxml → salvar".
  Extraído `xml_model/xml_common.py::salvar_xml_bonito()` — testado byte-a-byte idêntico ao comportamento
  antigo (com e sem `standalone=True`) e todos os 6 módulos re-importam sem erro (sem import circular).
- [x] **T27** — `xml_petro_po.py:18-104` repete o mesmo padrão de 4 linhas 11 vezes; usar loop com tabela de tuplas.
  Extraído helper `_campo_medida()` para os 5 blocos com estrutura idêntica (circularidade, rugosidade
  montante/jusante, planeza, ângulo de chanfro); os blocos com estrutura aninhada diferente (`VALOR_MEDIO`)
  foram deixados como estavam para não arriscar trocar valores em certificado real. Testado byte-a-byte
  contra a versão original (git HEAD) em 3 cenários: dados completos, `valores_medidos=None`, chaves parciais.
- [x] **T28** — Unificar `parser_po_ER.py`/`parser_tr_ER.py` em `pdf/parser_er_common.py` (resolve T2 de quebra).
  Criado `pdf/parser_er_common.py` com `extrair_numero_evaluation()` e `normalizar_espacos()` compartilhados
  (corrige de quebra um bug latente inofensivo no regex de traço do PO). Os helpers `_resultado_aceite`
  (PO) e `_to_aprovado` (TR) foram mantidos separados de propósito — operam sobre formatos de regex
  diferentes (PO captura uma palavra curta; TR captura a frase completa "Not Accepted"), forçar a fusão
  arriscaria comportamento. Testado: PO e TR retornam o mesmo número de certificado para o mesmo texto.
- [x] **T29** — Deletar `normalizar_categoria()` morta (sempre retorna `None`) em `xml_model/xml_table_extractor.py:14-23`
  — pode sombrear a versão correta em `xml_petro_generator.py:46-60`. Confirmado via grep que não era importada
  em lugar nenhum; removida.
- [x] **T30** — `xml_uc_generator.py:25-92`: 5 funções idênticas; colapsar em `criar_bloco_padrao(root, tag, dados)`.
  Feito — testado gerando XML de exemplo e conferindo estrutura (Diameter presente só em GasMeterRun/OrificePlate).
- [x] **T31** — `data/utils_db.py`: unificado `buscar_por_sn_instrumento`/`buscar_por_sn_sensor` e
  `buscar_placa_por_sn`/`buscar_placa_por_tag` em `buscar_por_campo`/`buscar_placa_por_campo` com whitelist.
  Bônus: corrigido `"tipo": row[5] or "secundario"` → `"SEC"` (valor morto que nada mais no código reconhecia,
  já que a migração normaliza para `'SEC'` — `data/conexao.py:71`).
- [x] **T32** — `importer/relatorio.py` e `importer/exportador.py` duplicavam lógica de winreg; extraído
  `data/utils_fs.py::pasta_documentos()`. Testado (resolve a pasta Documentos e cria subpasta).

---

## 🟡 MÉDIO — robustez e segurança

- [x] **T33** — Restringir `except Exception` genérico/silencioso em pontos críticos e logar.
  `pdf/extrator.py` e `pdf/parser_UC.py`: mantido broad-except (é fronteira parseando PDF arbitrário de
  terceiros — narrow aqui seria frágil), mas trocado `print(msg)` por `traceback.print_exc()` completo.
  `pdf/parser_certificados.py:65`: restringido para `except ValueError` (só isso pode ocorrer ali).
  `xml_model/xsd_validator.py`: reescrito para não conflatar "XSD ausente/ambiente quebrado" (agora propaga)
  com "XML gerado é inválido" (`etree.XMLSyntaxError`, ainda retorna lista de erro). `data/utils_db.py` já
  tinha sido resolvido no T20. Testado com XML malformado e XML bem-formado mas não-conforme.
- [x] **T34** — Risco de XXE em parse de XML de terceiros; usar `defusedxml` ou `XMLParser(resolve_entities=False)`.
  `xml_model/xml_extractor_FT.py` (parseia certificado *externo* de terceiros): trocado para
  `defusedxml.ElementTree` — já era dependência do `requirements.txt` mas nunca tinha sido usada em lugar
  nenhum. `xml_model/xsd_validator.py` (XML gerado internamente, risco bem menor, mas defesa em profundidade):
  parser com `resolve_entities=False, no_network=True`. `xml_model/validador.py` foi deletado (ver T36).
  Testado: uma entidade externa apontando pra `/etc/hostname` agora levanta `EntitiesForbidden` em vez de
  resolver silenciosamente.
- [x] **T35** — Código executando no import do módulo (fora de `if __name__ == "__main__":`).
  `pdf_primario_terc/certificado_info.py` e `pdf_primario_terc/chat_prompt.py` (renomeado no T37) — ambos
  guardados. Confirmado via grep que nenhum outro módulo importa esses dois.
- [x] **T36** — Deletar `xml_model/validador.py` (script de debug esquecido, nunca importado, quebra se importado).
  Confirmado via grep e removido.
- [x] **T37** — Renomear `pdf_primario_terc/extrator_metroval.py` (é GUI Tkinter) e `chat_prompt.py` (é o
  extrator real via docling) — nomes trocados. Renomeados para `fluxo_certificado_externo_gui.py` e
  `extrator_docling.py`. Bônus: `fluxo_certificado_externo_gui.py` também executava a GUI Tkinter inteira
  no import (mesma classe de bug do T35) — guardado também.
- [~] **T38** — Padronizar convenção de "campo ausente" entre parsers (hoje: `None`, `"NI"`, `"NÃO ENCONTRADO"`, `{"key": []}`).
  **Decisão: não aplicado.** Verificado que `"NI"` não é um sentinela interno do Python — é um valor de
  domínio real ("Não Informado") escrito literalmente no XML de certificado final
  (`xml_model/xml_uc_generator.py`, dezenas de ocorrências). "Padronizar" isso exigiria auditar cada consumidor
  pra saber se cada campo deveria virar `None` internamente e só virar `"NI"` na borda de geração do XML —
  é uma mudança de comportamento em potencial em documentos de calibração reais, não um refactor neutro.
  Precisa de confirmação de negócio/metrologia por campo, não é algo que eu deva decidir sozinho.
- [x] **T39** — Evitar re-extração do mesmo PDF até 3x (`pdf/utils_parser.py:10-12` + `parser_UC.py:311/281`); passar texto já extraído.
  `identificar_uc` agora recebe `texto` (não `caminho`) — não reabre mais o PDF. `extrair_campos_uc` ganhou
  um parâmetro opcional `texto`; quando `select_extract` já extraiu o texto, ele é reaproveitado. Reduz de 3x
  para 1x a extração completa do PDF por certificado de incerteza processado. Mantém uso standalone
  (`extrair_campos_uc(caminho)` sem o segundo argumento) funcionando como antes. Testado com contagem de
  chamadas via monkeypatch — confirmado 1x em vez de 2x/3x nos dois pontos.

---

## 🟢 BAIXO — limpeza geral (lote único, baixo risco)

- [x] Remover `print()` de debug em produção: `validation/engine.py` (já removidos no T6), `rules_po.py`
  (5 prints, incluindo um comentado), `rules_sec.py` (já removidos 2 no T6; removido o último em
  `regra_classe`), `xml_petro_generator.py` (`obter_unidade_eng`), `xml_table_extractor.py` (`processar_pdf`),
  `xml_petro_tr.py` (log de sucesso — stdout vai pro devnull em build empacotado, não tinha valor),
  `pdf/parser_UC.py` (3 prints). Compilado e reimportado tudo depois.
- [x] Remover imports mortos: `parser_po.py` (`extrair_texto`), `parser_po_ER.py` (`extrair_texto`,
  já reescrito no T2/T28), `parser_tr_ER.py` (`extrair_texto`), `parser_sgs.py` (`extrair_texto` E
  `xml_cromatografia`, os dois mortos), `xml_petro_po.py` (`normalizar_categoria`, já removido no T26).
- [x] Corrigido chave duplicada `'sn_inst'` em `pdf/parser_po.py` — testado que o dict resultante não repete a chave.
- [x] `xml_petro_generator.py` — `ET.Element("PONTOS_DE_CALIBRACAO")` duplicado removido. Bônus: corrigido
  `gerar_pontos_calibracao_pt100(resultados, unidade_eng="°C")` → default `None` — o default antigo era uma
  `str`, mas o corpo da função chama `.get()` nela como se fosse dict; quebraria com `AttributeError` se
  alguém chamasse a função sem o segundo argumento (hoje nenhum call site faz isso, mas era uma bomba-relógio).
  Testado chamando sem o segundo argumento — não quebra mais.
- [x] Investigado `criar_faixa_nominal`/`tipo_transmissor_pressao` (`xml_petro_generator.py`):
  **`criar_faixa_nominal` deletada** — confirmado que é duplicata morta; o bloco `FAIXA_NOMINAL` real já é
  montado inline em 2 lugares (`escrever_pontos_calibracao`, para instrumentos de temperatura e de pressão).
  **`tipo_transmissor_pressao` mantida, não conectada — sinalizando para decisão sua**: o elemento
  `TIPO_TRANSMISSOR_PRESSAO` é opcional no XSD (`minOccurs="0"`, confirmado no schema), então a ausência não
  invalida o XML gerado. Mas a função já tem lógica de negócio pronta (distingue "diferencial" de "estática"
  por categoria) que nunca foi ligada ao fluxo de `INSTRUMENTO_PRESSAO`. Não conectei porque isso mudaria o
  conteúdo de certificados reais sem confirmação — é uma decisão sua se quer habilitar esse campo opcional.
- [x] Campo `ctx.mvs` (`validation/context.py`, escrito em `rules_sec.py::regra_tag_vs_sn`) — confirmado via
  grep que nunca é lido em lugar nenhum (o `ValidationIssue` retornado pela regra já carrega toda a
  informação relevante na mensagem). Removido dos dois lugares. Testado: a regra MVS continua disparando
  o issue normalmente, só a variável de estado morta foi removida.
- [~] `processors/placa_processor.py` — checagem `if not self.app.dados_certificado_atual: raise ValueError(...)`.
  **Reavaliado e mantido, não removido.** Durante o T16 percebi que essa checagem não é necessariamente
  "impossível" como a lista original supunha: `_solicitar_report` tem diálogos bloqueantes (`confirm`,
  `escolher_arquivo`) e depois processa em background thread, tudo sobre a mesma instância `Api` compartilhada
  — nesse intervalo, nada impede o usuário de disparar `selecionar_pdf()` de novo e sobrescrever
  `dados_certificado_atual` antes dessa thread terminar. Prefiro manter uma guarda barata a arriscar
  reintroduzir uma falha silenciosa de condição de corrida sem ganho real em trocá-la.

---

## Notas de execução

- **Status (2026-08-24): backlog inteiro concluído** — 🔴 Crítico, 🟠 Alto, 🟡 Médio e 🟢 Baixo, todos os
  itens `[x]` ou `[~]` (decisão registrada de não aplicar/manter, com motivo). Dois pontos deixados
  deliberadamente para decisão de negócio, não código: `tipo_transmissor_pressao()` em
  `xml_petro_generator.py` (campo opcional do XSD com lógica pronta mas nunca conectada) e T38 (convenção
  de "campo ausente" — mexe em valores reais de certificado, não é refactor neutro).
- Cada task marcada `[x]` foi verificada com testes de equivalência automatizados contra o comportamento
  anterior (não só compilação) — ver detalhes em cada item.
- Nada foi commitado ainda — só editado no working tree. Ainda não convertido em commits.
- Front-end (`webui/js/app.js`, `dialogs.js`) ainda não entrou nesta auditoria — pendente se quiser incluir.
- `DESIGN/CertiFlow.dc.html` é um mockup de design (Claude Design canvas), não faz parte do runtime do app.
