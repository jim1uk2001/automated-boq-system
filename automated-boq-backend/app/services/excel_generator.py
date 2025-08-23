from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill, Protection
from openpyxl.worksheet.protection import SheetProtection
from typing import List, Dict, Any, Optional
import io
from ..models import BOQItem, Project

class ExcelGenerator:
    def __init__(self):
        self.header_font = Font(bold=True, size=12)
        self.data_font = Font(size=10)
        self.border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        self.header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")

    def generate_boq_excel(self, project: Project, boq_items: List[BOQItem]) -> bytes:
        """Generate Excel BOQ with protected cells, formulas, and drawing revision tracking"""
        wb = Workbook()
        
        drawing_ws = wb.active
        drawing_ws.title = "Drawing Register"
        
        drawing_ws['A1'] = f"PROJECT: {project.name}"
        drawing_ws['A1'].font = Font(bold=True, size=16, color="FFFFFF")
        drawing_ws['A1'].fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        drawing_ws.merge_cells('A1:G1')
        
        drawing_ws['A2'] = f"MEASUREMENT STANDARD: {project.measurement_standard.value.upper()}"
        drawing_ws['A2'].font = Font(bold=True, size=12, color="FFFFFF")
        drawing_ws['A2'].fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        drawing_ws.merge_cells('A2:G2')
        
        drawing_ws['A3'] = "DRAWING REGISTER - FOR VERSION CONTROL"
        drawing_ws['A3'].font = Font(bold=True, size=14, color="FF0000")
        drawing_ws['A3'].fill = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")
        drawing_ws.merge_cells('A3:G3')
        
        drawing_headers = [
            "Drawing Number", "Drawing Title", "Revision", "Revision Date", 
            "Drawing Type", "File Name", "Upload Date"
        ]
        
        header_row = 5
        for col, header in enumerate(drawing_headers, 1):
            cell = drawing_ws.cell(row=header_row, column=col, value=header)
            cell.font = Font(bold=True, size=12)
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            cell.font = Font(bold=True, size=12, color="FFFFFF")
            cell.border = self.border
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        current_row = header_row + 1
        for drawing in project.drawings:
            drawing_ws.cell(row=current_row, column=1, value=drawing.drawing_number or "N/A")
            drawing_ws.cell(row=current_row, column=2, value=drawing.drawing_title or drawing.filename)
            drawing_ws.cell(row=current_row, column=3, value=drawing.revision_number or "A")
            drawing_ws.cell(row=current_row, column=4, value=drawing.revision_date.strftime("%Y-%m-%d") if drawing.revision_date else "N/A")
            drawing_ws.cell(row=current_row, column=5, value=drawing.drawing_type.value if drawing.drawing_type else "General")
            drawing_ws.cell(row=current_row, column=6, value=drawing.filename)
            drawing_ws.cell(row=current_row, column=7, value=drawing.uploaded_at.strftime("%Y-%m-%d"))
            
            for col in range(1, 8):
                drawing_ws.cell(row=current_row, column=col).border = self.border
            
            current_row += 1
        
        warning_row = current_row + 2
        drawing_ws.cell(row=warning_row, column=1, value="IMPORTANT: Contractors must verify they are pricing the correct drawing revisions listed above.")
        drawing_ws.cell(row=warning_row, column=1).font = Font(bold=True, color="FF0000", size=12)
        drawing_ws.cell(row=warning_row, column=1).fill = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")
        drawing_ws.merge_cells(f'A{warning_row}:G{warning_row}')
        
        drawing_ws.cell(row=warning_row + 1, column=1, value="Any discrepancies between BOQ quantities and drawing revisions must be reported before bid submission.")
        drawing_ws.cell(row=warning_row + 1, column=1).font = Font(bold=True, color="FF0000", size=12)
        drawing_ws.cell(row=warning_row + 1, column=1).fill = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")
        drawing_ws.merge_cells(f'A{warning_row + 1}:G{warning_row + 1}')
        
        drawing_ws.cell(row=warning_row + 2, column=1, value="This register prevents disputes from superseded drawings that could lead to arbitration or litigation.")
        drawing_ws.cell(row=warning_row + 2, column=1).font = Font(bold=True, color="FF0000", size=12)
        drawing_ws.cell(row=warning_row + 2, column=1).fill = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")
        drawing_ws.merge_cells(f'A{warning_row + 2}:G{warning_row + 2}')
        
        column_widths = [15, 30, 10, 12, 15, 25, 12]
        for col, width in enumerate(column_widths, 1):
            drawing_ws.column_dimensions[drawing_ws.cell(row=1, column=col).column_letter].width = width
        
        for row in drawing_ws.iter_rows():
            for cell in row:
                cell.protection = Protection(locked=True)
        drawing_ws.protection.sheet = True
        drawing_ws.protection.password = "boq2024"
        
        ws = wb.create_sheet(title="Bill of Quantities")
        
        headers = [
            "Item No.", "Item Code", "Description", "Unit", 
            "Quantity", "Rate", "Amount", "Category", "Trade"
        ]
        
        ws['A1'] = f"Project: {project.name}"
        ws['A1'].font = Font(bold=True, size=14)
        ws['A2'] = f"Measurement Standard: {project.measurement_standard.value.upper()}"
        ws['A2'].font = Font(bold=True, size=12)
        ws['A4'] = "BILL OF QUANTITIES"
        ws['A4'].font = Font(bold=True, size=16)
        
        header_row = 6
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=header_row, column=col, value=header)
            cell.font = self.header_font
            cell.fill = self.header_fill
            cell.border = self.border
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.protection = Protection(locked=True)
        
        current_row = header_row + 1
        total_amount_formula_cells = []
        
        for idx, item in enumerate(boq_items, 1):
            cell = ws.cell(row=current_row, column=1, value=idx)
            cell.font = self.data_font
            cell.border = self.border
            cell.protection = Protection(locked=True)
            
            cell = ws.cell(row=current_row, column=2, value=item.item_code)
            cell.font = self.data_font
            cell.border = self.border
            cell.protection = Protection(locked=True)
            
            cell = ws.cell(row=current_row, column=3, value=item.description)
            cell.font = self.data_font
            cell.border = self.border
            cell.protection = Protection(locked=True)
            
            cell = ws.cell(row=current_row, column=4, value=item.unit)
            cell.font = self.data_font
            cell.border = self.border
            cell.alignment = Alignment(horizontal='center')
            cell.protection = Protection(locked=True)
            
            cell = ws.cell(row=current_row, column=5, value=item.quantity)
            cell.font = self.data_font
            cell.border = self.border
            cell.number_format = '0.00'
            cell.alignment = Alignment(horizontal='right')
            cell.protection = Protection(locked=True)
            
            cell = ws.cell(row=current_row, column=6, value=0.00)
            cell.font = self.data_font
            cell.border = self.border
            cell.number_format = '0.00'
            cell.alignment = Alignment(horizontal='right')
            cell.protection = Protection(locked=False)  # UNLOCKED
            cell.fill = PatternFill(start_color="FFFF99", end_color="FFFF99", fill_type="solid")  # Yellow highlight
            
            amount_cell = ws.cell(row=current_row, column=7)
            amount_cell.value = f"=E{current_row}*F{current_row}"
            amount_cell.font = self.data_font
            amount_cell.border = self.border
            amount_cell.number_format = '0.00'
            amount_cell.alignment = Alignment(horizontal='right')
            amount_cell.protection = Protection(locked=True)
            total_amount_formula_cells.append(f"G{current_row}")
            
            cell = ws.cell(row=current_row, column=8, value=item.category)
            cell.font = self.data_font
            cell.border = self.border
            cell.protection = Protection(locked=True)
            
            cell = ws.cell(row=current_row, column=9, value=item.trade)
            cell.font = self.data_font
            cell.border = self.border
            cell.protection = Protection(locked=True)
            
            current_row += 1
        
        total_row = current_row + 1
        ws.cell(row=total_row, column=6, value="TOTAL:").font = Font(bold=True)
        ws.cell(row=total_row, column=6).alignment = Alignment(horizontal='right')
        ws.cell(row=total_row, column=6).protection = Protection(locked=True)
        
        total_cell = ws.cell(row=total_row, column=7)
        if total_amount_formula_cells:
            total_cell.value = f"=SUM({','.join(total_amount_formula_cells)})"
        else:
            total_cell.value = 0.00
        total_cell.font = Font(bold=True)
        total_cell.number_format = '0.00'
        total_cell.alignment = Alignment(horizontal='right')
        total_cell.border = Border(top=Side(style='thick'), bottom=Side(style='thick'))
        total_cell.protection = Protection(locked=True)
        
        column_widths = [8, 12, 40, 8, 12, 12, 15, 15, 15]
        for col, width in enumerate(column_widths, 1):
            ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width
        
        instruction_row = total_row + 3
        ws.cell(row=instruction_row, column=1, value="INSTRUCTIONS FOR CONTRACTORS:")
        ws.cell(row=instruction_row, column=1).font = Font(bold=True, color="FF0000")
        
        instructions = [
            "1. Only the RATE column (highlighted in yellow) can be edited",
            "2. Enter your rates in the appropriate currency",
            "3. The AMOUNT column will calculate automatically",
            "4. Do not modify any other cells - they are protected",
            "5. Save the file and upload through the bidding portal"
        ]
        
        for i, instruction in enumerate(instructions):
            ws.cell(row=instruction_row + i + 1, column=1, value=instruction)
            ws.cell(row=instruction_row + i + 1, column=1).font = Font(size=10)
        
        ws.protection.sheet = True
        ws.protection.password = "boq2024"  # Set a password for protection
        ws.protection.formatCells = False
        ws.protection.formatColumns = False
        ws.protection.formatRows = False
        ws.protection.insertColumns = False
        ws.protection.insertRows = False
        ws.protection.deleteColumns = False
        ws.protection.deleteRows = False
        
        excel_buffer = io.BytesIO()
        wb.save(excel_buffer)
        excel_buffer.seek(0)
        return excel_buffer.getvalue()

    def generate_bid_comparison_excel(self, project: Project, bids_data: List[Dict[str, Any]]) -> bytes:
        """Generate Excel comparison of all bids for client review"""
        wb = Workbook()
        ws = wb.active
        ws.title = "Bid Comparison"
        
        ws['A1'] = f"Project: {project.name}"
        ws['A1'].font = Font(bold=True, size=14)
        ws['A2'] = f"Bid Comparison Report"
        ws['A2'].font = Font(bold=True, size=12)
        
        headers = ["Rank", "Contractor", "Company", "Total Amount", "Status", "Submitted Date"]
        header_row = 4
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=header_row, column=col, value=header)
            cell.font = self.header_font
            cell.fill = self.header_fill
            cell.border = self.border
            cell.alignment = Alignment(horizontal='center')
        
        current_row = header_row + 1
        for bid in bids_data:
            ws.cell(row=current_row, column=1, value=bid.get('rank', 'N/A'))
            ws.cell(row=current_row, column=2, value=bid.get('contractor_name', ''))
            ws.cell(row=current_row, column=3, value=bid.get('contractor_company', ''))
            
            amount_cell = ws.cell(row=current_row, column=4, value=bid.get('total_amount', 0))
            amount_cell.number_format = '0.00'
            
            ws.cell(row=current_row, column=5, value=bid.get('status', ''))
            ws.cell(row=current_row, column=6, value=bid.get('submitted_at', ''))
            
            if bid.get('rank') == 1:
                for col in range(1, 7):
                    ws.cell(row=current_row, column=col).fill = PatternFill(
                        start_color="90EE90", end_color="90EE90", fill_type="solid"
                    )
            
            current_row += 1
        
        column_widths = [8, 20, 25, 15, 12, 15]
        for col, width in enumerate(column_widths, 1):
            ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width
        
        excel_buffer = io.BytesIO()
        wb.save(excel_buffer)
        excel_buffer.seek(0)
        return excel_buffer.getvalue()
