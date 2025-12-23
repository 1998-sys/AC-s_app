📄 AC Analyzer – Processador de Certificados de Calibração

Software desenvolvido para analisar certificados de calibração (PDF) de instrumentos de pressão e temperatura, comparar com uma base local e gerar automaticamente:

-Análise Crítica (AC) em PDF
-Arquivo XML no padrão ODS
-Atualização automática do banco de dados local (SQLite)

⚙️ Funcionalidades Principais

- Leitura automática do PDF
- Extrai TAG, certificado, datas, ranges, SN do instrumento e sensor, valores de calibração, erro fiducial e incerteza global
-Comparação com banco SQLite
-Verifica divergências de TAG, SN, Range, Diametro e comprimento da haste, localização, range de calibração e indicado, erro fiducial e incerteza global (DPT e PT)
-Atualiza automaticamente quando autorizado
-Geração automática da Análise Crítica (PDF)
-Usa o template TemplateAC.xlsx e exporta para PDF via Excel.
-Geração do XML
-Preenche o modelo de XML com dados do certificado e do instrumento.

Suporte a diferentes tipos de instrumentos

-PT / PIT
-DPT
-TT / TIT
-Sensores TE

📁 Estrutura dos Arquivos Necessários

/AC_app
│── Ac_app.exe               → Executável
│── TemplateAC.xlsx          → Template para gerar AC
│── instrumentos.db          → Banco local SQLite
│── /pdf                     → Módulos de extração
│── /xml_model               → Gerador do XML
│── /form                    → Geração do PDF de AC
│── /gui                     → Interface Tkinter

▶️ Como usar

1-Abra o software (executável).
2-Clique em Selecionar Certificado PDF.
3-O programa:

- Lê o PDF
- Compara com o banco
- Exibe divergências

-Gera automaticamente:

    - AC.pdf
    - XML.xml

4-Os arquivos são salvos na mesma pasta do PDF original.