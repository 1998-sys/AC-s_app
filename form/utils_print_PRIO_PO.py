import openpyxl
import win32com.client as win32
import os
import re
import tempfile
import shutil
from datetime import datetime
from openpyxl.utils import get_column_letter
from openpyxl.styles import Border, Side
from openpyxl.worksheet.page import PageMargins


def gerar_ac_prio_po(
    dados: dict,
    caminho_pdf_original: str,
    caminho_template: str = "TemplateAC_PRIO.xlsx",
    nome_aba: str = "Template Formulário",
    print_area_fixa: str | None = None,     
    linhas_extra_topo: int = 2,             
    aplicar_borda_fallback: bool = True,    
    cor_faixa_teal_hex: str = "0099A8"      
) -> str:
    """Gera o PDF da AC em 1 página, incluindo faixa sob o título e corrigindo logo com “fundo preto”."""

    
    if not os.path.isfile(caminho_template):
        raise FileNotFoundError(f"Template não encontrado: {os.path.abspath(caminho_template)}")
    if not isinstance(dados, dict):
        raise ValueError("O parâmetro 'dados' deve ser um dicionário com os campos necessários.")

    wb = openpyxl.load_workbook(caminho_template)
    if nome_aba not in wb.sheetnames:
        try:
            nome_aba = next(sh for sh in wb.sheetnames if sh.lower() == nome_aba.lower())
        except StopIteration:
            raise KeyError(f"Aba '{nome_aba}' não encontrada. Abas: {wb.sheetnames}")

    ws = wb[nome_aba]

    
    ws["C5"] = dados.get("local", "")
    ws["C6"] = dados.get("local", "")
    ws["C7"] = dados.get("data_calibracao", "")
    ws["F5"] = dados.get("sn_inst", "")
    ws["F6"] = dados.get("certificado", "")
    ws['F7'] = 'ODS Metering Systems'

    
    try:
        ws["G48"] = datetime.now().strftime("%d/%m/%Y")
    except Exception:
        pass

    
    if aplicar_borda_fallback:
        titulo = "Análise crítica de calibração de placas de orifício"
        titulo_row = None
        max_col_usada = 1
        for row in ws.iter_rows(min_row=1, max_row=30):
            for cell in row:
                if cell.value not in (None, ""):
                    max_col_usada = max(max_col_usada, cell.column)
                    if isinstance(cell.value, str) and titulo.lower() in cell.value.lower():
                        titulo_row = cell.row
        if titulo_row:
            linha_borda = max(1, titulo_row + 1)
            col_ini, col_fim = 1, max_col_usada
            teal = cor_faixa_teal_hex.upper()
            border_bottom = Border(bottom=Side(style="thick", color=teal))
            for c in range(col_ini, col_fim + 1):
                addr = f"{get_column_letter(c)}{linha_borda}"
                ws[addr].border = ws[addr].border + border_bottom

    
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = "portrait"
    ws.page_setup.scale = None
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.print_options.horizontalCentered = True
    ws.print_options.verticalCentered = False
    ws.page_margins = PageMargins(top=0.3, bottom=0.3, left=0.3, right=0.3)

    
    if print_area_fixa is None:
        last_row = 1
        last_col = 1
        for row in ws.iter_rows():
            for cell in row:
                if cell.value not in (None, ""):
                    last_row = max(last_row, cell.row)
                    last_col = max(last_col, cell.column)
        last_row += linhas_extra_topo
        ws.print_area = f"A1:{get_column_letter(max(1, last_col))}{max(1, last_row)}"
    else:
        ws.print_area = print_area_fixa

    
    tmp_dir = tempfile.mkdtemp(prefix="ac_prio_")
    xlsx_tmp = os.path.join(tmp_dir, "saida_temp.xlsx")
    wb.save(xlsx_tmp)

   
    pasta_saida = os.path.dirname(os.path.abspath(caminho_pdf_original)) or os.getcwd()
    def _sanitize(t: str) -> str:
        return re.sub(r'[<>:"/\\|?*\n\r\t]+', "-", str(t or "")).strip()
    certificado = _sanitize(dados.get("certificado", "")).replace(" ", "")
    tag_limpa   = _sanitize(dados.get("tag", "")).replace(" ", "")
    nome_pdf = (f"{certificado}_{tag_limpa}_AC.pdf".strip("_")) or "AC.pdf"
    pdf_final = os.path.join(pasta_saida, nome_pdf)
    if os.path.exists(pdf_final):
        try:
            os.remove(pdf_final)
        except PermissionError:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise PermissionError(f"⚠ O arquivo PDF está aberto e não pode ser sobrescrito:\n{pdf_final}")

    
    excel = None
    wb_excel = None
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.ScreenUpdating = False
        excel.Interactive = False

       
        try:
            for win in excel.Windows:
                win.DisplayDrawingObjects = -4104  
        except Exception:
            pass

        wb_excel = excel.Workbooks.Open(os.path.abspath(xlsx_tmp))
        ws_excel = wb_excel.Worksheets(nome_aba)

       
        ws_excel.DisplayPageBreaks = False
        try:
            for i in range(ws_excel.HPageBreaks.Count, 0, -1):
                ws_excel.HPageBreaks(i).Delete()
        except Exception:
            pass
        try:
            for i in range(ws_excel.VPageBreaks.Count, 0, -1):
                ws_excel.VPageBreaks(i).Delete()
        except Exception:
            pass

        
        ps = ws_excel.PageSetup
        ps.Zoom = False
        ps.FitToPagesWide = 1
        ps.FitToPagesTall = 1
        ps.Orientation = 1   
        ps.PaperSize = 9      
        ps.LeftMargin   = excel.InchesToPoints(0.3)
        ps.RightMargin  = excel.InchesToPoints(0.3)
        ps.TopMargin    = excel.InchesToPoints(0.3)
        ps.BottomMargin = excel.InchesToPoints(0.3)
        ps.HeaderMargin = excel.InchesToPoints(0.15)
        ps.FooterMargin = excel.InchesToPoints(0.15)
        ps.CenterHorizontally = True
        ps.CenterVertically   = False
        ps.Draft = False
        ps.BlackAndWhite = False
        ps.LeftHeader = ps.CenterHeader = ps.RightHeader = ""
        ps.LeftFooter = ps.CenterFooter = ps.RightFooter = ""

       
        def _abs_area(area_str: str) -> str:
            if not area_str:
                return ""
            area = str(area_str).split(",")[0].strip()
            if ":" not in area:
                return area
            ini, fim = area.split(":")
            import re as _re
            def abs1(addr: str) -> str:
                addr = addr.strip().upper()
                m = _re.match(r"^([A-Z]+)(\d+)$", addr)
                if not m:
                    return addr
                col, row = m.groups()
                return f"${col}${row}"
            return f"{abs1(ini)}:{abs1(fim)}"
        ws_excel.PageSetup.PrintArea = _abs_area(ws.print_area)

        
        def _union_areas(area1: str, area2: str) -> str:
            def parse(a):
                a = a.replace("$", "")
                left, right = a.split(":")
                import re as _re
                def num_col(col):
                    n = 0
                    for ch in col:
                        n = n*26 + (ord(ch)-64)
                    return n
                lc, lr = _re.match(r"([A-Z]+)(\d+)", left).groups()
                rc, rr = _re.match(r"([A-Z]+)(\d+)", right).groups()
                return (num_col(lc), int(lr), num_col(rc), int(rr))
            def to_addr(c1, r1, c2, r2):
                def col_txt(n):
                    s=""
                    while n:
                        n, r = divmod(n-1, 26)
                        s = chr(65+r)+s
                    return s
                return f"${col_txt(c1)}${r1}:${col_txt(c2)}${r2}"
            if not area1:
                return area2
            if not area2:
                return area1
            a1 = parse(area1); a2 = parse(area2)
            c1 = min(a1[0], a2[0]); r1 = min(a1[1], a2[1])
            c2 = max(a1[2], a2[2]); r2 = max(a1[3], a2[3])
            return to_addr(c1, r1, c2, r2)

        area_atual = ws_excel.PageSetup.PrintArea or ""

        
        msoLinkedPicture = 11
        msoPicture = 13

        try:
            for shp in ws_excel.Shapes:
                
                try:   shp.PrintObject = True
                except Exception: pass
                try:   shp.Placement = 1  
                except Exception: pass
                try:   shp.Shadow.Visible = False
                except Exception: pass
                try:   shp.Glow.Radius = 0
                except Exception: pass
                try:   shp.SoftEdges = 0
                except Exception: pass
                try:   shp.ThreeD.Visible = False
                except Exception: pass

                
                try:
                    if shp.Type in (msoPicture, msoLinkedPicture):
                        shp.Fill.Visible = True
                        shp.Fill.Solid()
                        shp.Fill.ForeColor.RGB = 0xFFFFFF  
                        shp.Line.Visible = False
                        try: shp.PictureFormat.ColorType = 1 
                        except Exception: pass
                except Exception:
                    pass

                
                try:
                    if hasattr(shp, "Line"):
                        shp.Line.Visible = True
                        shp.Line.Weight = max(1.5, getattr(shp.Line, "Weight", 1.0))
                except Exception:
                    pass

                try:
                    tcell = shp.TopLeftCell.Address
                    bcell = shp.BottomRightCell.Address
                    area_shp = f"{tcell}:{bcell}"
                    area_atual = _union_areas(area_atual, area_shp)
                except Exception:
                    pass
        except Exception:
            pass

        if area_atual:
            ws_excel.PageSetup.PrintArea = area_atual


        wb_excel.ExportAsFixedFormat(
            Type=0,  
            Filename=pdf_final,
            Quality=0,
            IncludeDocProperties=True,
            IgnorePrintAreas=False,
            OpenAfterPublish=False
        )

    finally:
        try:
            if wb_excel is not None:
                wb_excel.Close(SaveChanges=False)
        except Exception:
            pass
        try:
            if excel is not None:
                excel.Quit()
        except Exception:
            pass
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return pdf_final