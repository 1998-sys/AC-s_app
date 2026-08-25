# 📄 CertiFlow — AC's Generator

Aplicativo desktop da ODS Metering Systems para gerar **Análises Críticas
(AC)** de calibração de instrumentos, em conformidade com as regras da
ANP. Lê o certificado de calibração em **PDF**, compara com o cadastro
local (SQLite) e gera automaticamente:

- 📑 **Análise Crítica (AC) em PDF**
- 🧾 **XML no padrão ANP/cliente**
- 🗄️ **Atualização do cadastro local do instrumento**

Interface em **pywebview** (HTML/CSS/JS embutido numa janela nativa do
Windows) — não é mais a GUI em Tkinter das versões antigas.

---

## ⚙️ Funcionalidades principais

- 📄 Leitura de **um ou vários certificados por vez** (modo lote): a
  fila lê tudo primeiro, depois mostra uma tela só com as divergências
  pendentes de cada instrumento, e gera as ACs prontas de uma vez.
- 🔎 Extração automática de TAG, número do certificado, datas, ranges,
  SN do instrumento/sensor, pontos de calibração, erro fiducial,
  incerteza, entre outros — conforme o tipo de documento identificado.
- 🗃️ Comparação com o cadastro (SQLite) e verificação de divergências:
  - TAG, SN (instrumento/sensor), Range, Range indicado x calibrado
  - Diâmetro e comprimento da haste (TE), Localização (FPSO/cliente)
  - Erro fiducial e incerteza (inclusive contra a CMC aplicável)
  - Classificação (Fiscal/Apropriação/Transferência de Custódia/
    Operacional) e prazo de emissão — regras específicas por cliente
- ✍️ Resolução interativa das divergências: aplicar a correção no
  cadastro, manter/ignorar, ou pular o certificado quando não há
  correção possível (ex.: incerteza abaixo da CMC) — em lote, sem
  travar a fila nem parar nos demais certificados.
- 📑 Geração da **AC em PDF** a partir de templates `.xlsx` (preenchidos
  via openpyxl, exportados a PDF via automação COM do Excel — reaproveita
  uma única instância do Excel para todo o lote).
- 🧾 Geração do **XML** no padrão ANP/cliente correspondente.
- 🧪 Relatórios de **cromatografia** (SGS ou laboratório interno da
  Origem Energia Alagoas) e de **cálculo de incerteza (CI)**: geram o
  XML direto, sem passar pela tela de revisão.
- 🖊️ Cadastro/edição manual de instrumento pela interface.
- 📤📥 Importação/exportação em massa do cadastro via `.xlsx`.
- 🖱️ Arrastar e soltar arquivos soltos direto na tela (guardados numa
  pasta permanente em Documentos).

---

## 🏭 Clientes e tipos de instrumento suportados

**Clientes (geração de AC/XML):** PRIO, YINSON, YINSON ATLANTA, ORIGEM
ENERGIA ALAGOAS S.A. — cada um com seu próprio template de AC e, para
placa de orifício, uma variante própria (PO).

**Tipos de instrumento/documento:**
- PT / PIT, DPT, TT / TIT, sensores TE (com vínculo automático
  TE ↔ TT/TIT pelo par de TAG)
- Manômetros analógicos/digitais (inclusive diferenciais e absolutos)
- Termorresistências PT-100, termômetros, transmissores de temperatura
- Placa de orifício
- Trecho reto / Gas Meter Run (gera o XML de dimensional; AC em PDF
  ainda não implementada para esse tipo)
- Relatório de cromatografia (SGS ou Origem Energia Alagoas)
- Relatório de cálculo de incerteza (CI)

---

## 📁 Estrutura do projeto

```text
AC's_app/
│── Ac_app.py                 → Ponto de entrada (abre a janela pywebview)
│── instrumentos.db           → Banco de dados local (SQLite)
│── TemplateAC_*.xlsx         → Templates da AC por cliente/variante
│
├── webui/                    → Front-end (HTML/CSS/JS) — telas do CertiFlow
├── gui/                      → Api (ponte JS↔Python) e serviços (leitura,
│                                revisão, importação/exportação)
├── pdf/                      → Extração de dados dos PDFs por tipo de doc
├── validation/                → Motor de regras de validação (divergências)
├── xml_model/                 → Geração dos XMLs (ANP/petro/PO/TR/cromato/CI)
├── form/                      → Preenchimento do template Excel e export a PDF
├── processors/                → Roteamento por tipo de instrumento (Dispatcher)
└── data/                      → Acesso ao banco (SQLite) e ao sistema de arquivos
```

---

## 🖥️ Telas

![Telas do CertiFlow: seleção, leitura, revisão (única e em lote), saída e cadastro](docs/certiflow-demo.gif)

Seleção do certificado → leitura → revisão de divergências (arquivo único
e agregada em lote) → arquivos gerados → cadastro/edição de instrumento.

---

## ▶️ Como executar

Requer **Python 3.12**, **Microsoft Excel** instalado (automação COM
usada pra exportar a AC em PDF) e o **WebView2 Runtime** do Windows
(já vem por padrão no Windows 10/11 atualizados).

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python.exe Ac_app.py
```

> Sempre use o Python do `venv` do projeto — uma versão diferente do
> pywebview instalada globalmente pode quebrar os diálogos de arquivo
> silenciosamente.

Pra gerar o executável (`.exe`), o projeto já tem `Ac_app.spec` pronto
pro PyInstaller.

---

## 🧭 Fluxo de uso

1. Abra o app e clique em **Selecionar certificado(s) PDF** (dá pra
   escolher mais de um — ativa o modo lote automaticamente).
2. Clique em **Ler certificado(s)**: o app extrai os dados e compara
   com o cadastro.
3. **Um único certificado:** revise as divergências (se houver) e
   clique em **Gerar relatório e XML**.
   **Lote:** a leitura de todos os arquivos acontece primeiro; ao
   final, uma tela agregada mostra só os instrumentos com divergência
   pendente — resolva cada uma (ou pule o certificado) e clique em
   **Gerar relatórios** pra gerar todos os que estiverem prontos.
4. Os arquivos (AC em PDF + XML) são salvos na mesma pasta do PDF
   original.

> Para calibração em malha aberta (TE + TT/TIT), leia os dois
> certificados juntos (mesmo lote ou em sequência) — o sistema vincula
> o certificado do TE ao TT/TIT correspondente automaticamente pelo
> par de TAG, independente da ordem de leitura.
