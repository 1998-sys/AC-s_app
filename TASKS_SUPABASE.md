# Migração do banco local (SQLite) para Supabase (Postgres)

Status: implementado e testado contra o Supabase real (2026-10-06). Camada de dados reescrita, dados antigos migrados. Faltam as seções 6/7 e os follow-ups no final do documento.

Escopo atual: toda a camada de dados está isolada em [data/conexao.py](data/conexao.py) e [data/utils_db.py](data/utils_db.py), chamados a partir de [Ac_app.py](Ac_app.py). Hoje o banco é um arquivo SQLite em `%APPDATA%\ACs Generator\instrumentos.db`, com uma única tabela `instrumentos` que guarda só a última calibração de cada tag.

Motivação da migração: viabilizar métricas de BI sobre calibrações atrasadas, o que exige manter o **histórico completo** de calibrações por instrumento (não só a última), incluindo troca de número de série (NS).

## Rollback

Voltar pro commit anterior à migração restaura o código em SQLite, desde que o `instrumentos.db` local não tenha sido apagado — a volta é só de código, não precisa reverter dado nenhum.

Ponto de não-retorno: não é o commit, é o app em uso real começar a gravar calibrações novas direto no Supabase. A partir daí, reverter o código não traz de volta pro SQLite o que só existe no Postgres.

## 0. Schema (histórico de calibrações) — definido

Identidade = unidade física por tag (`tag` + `sn_instrumento`), já que uma tag de placa pode ter mais de uma unidade cadastrada ao mesmo tempo (instalada + reserva — hoje já é assim, ver `buscar_placas_por_tag` em [utils_db.py:138](data/utils_db.py#L138)). Histórico de calibração em tabela separada, append-only (1 linha por certificado, nunca UPDATE).

**`instrumentos`** — identidade (tag + unidade física), muda só quando troca a unidade instalada
- `id` PK
- `tag`
- `sn_instrumento`
- `tipo` (`SEC` / `PO`)
- `sistema`
- `aplicacao`
- `ativo`
- `em_uso` (bool) — só uma linha com `true` por `tag` (a unidade instalada agora; as demais são reserva/retiradas)
- `modificado_por` / `modificado_em` — última troca de situação (instalado ↔ reserva) desta unidade; é daqui que sai "quando foi a última troca de NS" de uma tag
- UNIQUE (`tag`, `sn_instrumento`)

**`calibracoes`** — histórico, 1 linha por certificado, nunca sofre UPDATE
- `id` PK
- `instrumento_id` FK → `instrumentos.id`
- `sn_sensor` (nullable — o sensor é relatado junto no mesmo certificado do transmissor, mas pode trocar entre uma calibração e outra independente do transmissor; ver `extrair_sn` em [parser_certificados.py:849](pdf/parser_certificados.py#L849))
- `min_range` / `max_range` (nullable — podem mudar numa recalibração)
- `numero_certificado`
- `laboratorio`
- `data_calibracao`
- `proxima_calibracao`
- `observacoes`
- `modificado_por` / `modificado_em`

Consultas derivadas (não precisam de tabela própria):
- **Calibração atual por instrumento**: view `vw_calibracao_atual`, `DISTINCT ON (instrumento_id) ... ORDER BY data_calibracao DESC`
- **Atrasados (BI)**: `LEFT JOIN` de `instrumentos` (`em_uso = true`) com `vw_calibracao_atual` (não é `INNER JOIN` — instrumento cadastrado manualmente ainda sem calibração não tem linha na view). `proxima_calibracao IS NULL` = nunca calibrado (tratar separado de "atrasado" no BI); `proxima_calibracao < hoje` = atrasado
- **Troca de NS do instrumento**: `instrumentos.modificado_em` da linha `em_uso = true` da tag
- **Troca de NS do sensor**: comparar `sn_sensor` entre calibrações consecutivas do mesmo `instrumento_id`

### DDL de referência (Postgres)

```sql
CREATE TABLE instrumentos (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tag             TEXT NOT NULL,
    sn_instrumento  TEXT NOT NULL,
    tipo            TEXT NOT NULL DEFAULT 'SEC',
    sistema         TEXT,
    aplicacao       TEXT,
    ativo           TEXT,
    em_uso          BOOLEAN NOT NULL DEFAULT TRUE,
    modificado_por  TEXT,
    modificado_em   TIMESTAMPTZ,
    UNIQUE (tag, sn_instrumento)
);

CREATE TABLE calibracoes (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instrumento_id      BIGINT NOT NULL REFERENCES instrumentos(id),
    sn_sensor           TEXT,
    min_range           NUMERIC,
    max_range           NUMERIC,
    numero_certificado  TEXT,
    laboratorio         TEXT,
    data_calibracao     DATE,
    proxima_calibracao  DATE,
    observacoes         TEXT,
    modificado_por      TEXT,
    modificado_em       TIMESTAMPTZ
);

CREATE INDEX idx_calibracoes_instrumento_data ON calibracoes (instrumento_id, data_calibracao DESC);

CREATE VIEW vw_calibracao_atual AS
SELECT DISTINCT ON (instrumento_id) *
FROM calibracoes
ORDER BY instrumento_id, data_calibracao DESC;
```

Instrumento pode ser cadastrado sem calibração (tela de cadastro manual) — `calibracoes` não é obrigatória ter linha para todo `instrumento`, por isso a query de atrasados usa `LEFT JOIN`.

**Detalhe de implementação que não estava no desenho original**: `data_calibracao`/`proxima_calibracao` (`DATE`) e `modificado_em` (`TIMESTAMPTZ`) são tipos nativos no Postgres, mas a tela de editar instrumento manda/espera strings `"dd/mm/aaaa"` (`webui/js/app.js` + `webui/index.html:231`). A conversão BR ↔ tipo nativo fica isolada dentro de [data/utils_db.py](data/utils_db.py) (`_parse_data_br`, `_parse_datetime_br`, `_formatar_data_br`, `_formatar_datetime_br`) — nenhum chamador externo precisou mudar.

## 1. Criar o projeto no Supabase
- [x] Projeto criado, pooler em modo Transaction (porta 6543) — combina com o padrão do app de abrir/fechar conexão por chamada
- [x] Connection string em `.env` (raiz do projeto, ignorado pelo git — `.env.example` é o template)

## 2. Trocar o driver
- [x] `psycopg2-binary==2.9.13` adicionado ao `requirements.txt` e instalado no venv
- [x] `sqlite3` removido de [data/conexao.py](data/conexao.py)

## 3. Reescrever `conexao.py`
- [x] `conectar()` abre conexão Postgres via `SUPABASE_DB_URL` (carregado com `python-dotenv`)
- [x] `criar_tabela()` cria `instrumentos`, `calibracoes`, índice e a view `vw_calibracao_atual` (todos `IF NOT EXISTS`/`CREATE OR REPLACE`)
- [x] `migrar()` mantido por paridade de API com `Ac_app.py` (hoje só reforça índice/view, idempotente)

## 4. Ajustar `utils_db.py`
- [x] Todas as ~20 funções reescritas para o schema de 2 tabelas, preservando 100% das assinaturas e formatos de retorno — nenhum chamador (`gui/`, `validation/`, `importer/`, `form/`) precisou mudar
- [x] Placeholders `%s`, tipos `NUMERIC`/`DATE`/`TIMESTAMPTZ`/`BOOLEAN`
- [x] Flag `em_uso` implementado (`_instrumento_ativo`, `_trocar_unidade_ativa`) — resolve de quebra uma ambiguidade que já existia em `atualizar_sn_placa` (atualizava todas as linhas da tag quando havia placa reserva)

## 5. Migrar os dados existentes
- [x] [scripts/migrar_sqlite_para_supabase.py](scripts/migrar_sqlite_para_supabase.py) — idempotente, suporta `--dry-run`
- [x] Rodado de verdade nesta máquina: 25 `instrumentos` + 25 `calibracoes` migrados, contagem conferida direto no Postgres
- **Caveat de idempotência**: nenhuma das 25 linhas migradas tinha `numero_certificado` preenchido (ninguém usava a tela de edição pra isso ainda) — como a dedupe de `calibracoes` é por `(instrumento_id, numero_certificado)`, rodar o script de novo duplicaria essas 25 linhas de calibração. Só rodar de novo se for pra migrar uma OUTRA máquina/base, não a mesma.

## 6. Offline / multi-usuário
- [ ] Definir comportamento do app sem internet (hoje não existe esse caso, com arquivo local)
- [ ] Revisar se updates concorrentes precisam de lock além dos campos já existentes `modificado_por` / `modificado_em`
- [ ] **Build PyInstaller**: o `.exe` gerado (`dist/`) precisa do `.env` (ou de outra forma de prover `SUPABASE_DB_URL`) na máquina de quem for rodar — ainda não revisado como isso se distribui pro time

## 7. Testes
- [ ] Teste de integração da camada de dados (contra Supabase ou um Postgres local via Docker)
- [ ] Rodar a suíte existente (`tests/`) após a troca

## 8. População automática de `calibracoes` a partir do certificado — feito (2026-10-06)

Nova função `registrar_calibracao(tag, numero_certificado, ...)` em [data/utils_db.py](data/utils_db.py): sempre faz **INSERT** (histórico de verdade, diferente de `atualizar_dados_cadastro` que edita a última linha — essa continua existindo só para a tela manual). É no-op se o certificado (`instrumento_id` + `numero_certificado`) já tiver sido registrado antes (evita duplicar ao regenerar a mesma AC), e no-op se a tag não tiver instrumento ativo cadastrado (cadastrar um instrumento novo continua sendo decisão explícita do usuário nas divergências "novo instrumento"/"nova placa").

Chamada em `_registrar_calibracao_automatica` ([gui/revision_service.py](gui/revision_service.py)), dentro de `_gerar_e_montar_resultado` — roda uma vez por certificado gerado, tanto no fluxo único quanto no lote, pra PO e SEC (nomes de campo diferem entre os dois: placa usa `sn_inst`/`data_calibracao`, secundário usa `sn_instrumento`/`data`/`proxima_cal` — ver `pdf/parser_po.py` vs `pdf/parser_certificados.py`). Best-effort: qualquer erro é capturado e logado, nunca derruba a geração do PDF/XML (que já aconteceu com sucesso antes dessa chamada).

**Campo que fica de fora, propositalmente**: `laboratorio` não é extraído de nenhum certificado hoje (não existe esse campo normalizado nos parsers) — continua `NULL` nesse caminho automático, preenchível manualmente depois na tela de edição se for preciso.

Validado com teste isolado contra o Supabase real: 1º certificado cria a calibração; reprocessar o MESMO certificado não duplica; um certificado diferente da mesma tag cria uma 2ª linha de histórico.

## Pendências restantes
- Seção 6 (offline / multi-usuário / distribuição do `.env` no build PyInstaller) e seção 7 (testes automatizados da camada de dados) continuam em aberto.
- As 25 calibrações já migradas (seção 5) não têm `numero_certificado` — a partir de agora, novos certificados processados vão ter o número preenchido e entrar no histórico corretamente.

## Decisões em aberto
- (preencher conforme formos decidindo)
