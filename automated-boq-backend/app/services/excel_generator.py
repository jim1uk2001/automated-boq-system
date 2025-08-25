from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill, Protection
from openpyxl.worksheet.protection import SheetProtection
from typing import List, Dict, Any, Optional
import io
from ..models import BOQItem, Project
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from datetime import datetime

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
            column_letter = chr(64 + col)  # Convert column number to letter (A, B, C, etc.)
            drawing_ws.column_dimensions[column_letter].width = width
        
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
        
        project_info_from_drawings = self._extract_project_info_from_drawings(project.drawings)
        header_row_offset = 0
        if project_info_from_drawings:
            if project_info_from_drawings.get('project_number'):
                ws['A2'] = f"Project Number: {project_info_from_drawings.get('project_number')}"
                ws['A2'].font = Font(bold=True, size=12)
                header_row_offset += 1
            if project_info_from_drawings.get('client_name'):
                ws[f'A{2 + header_row_offset}'] = f"Client: {project_info_from_drawings.get('client_name')}"
                ws[f'A{2 + header_row_offset}'].font = Font(bold=True, size=12)
                header_row_offset += 1
        
        ws[f'A{2 + header_row_offset}'] = f"Measurement Standard: {project.measurement_standard.value.upper()}"
        ws[f'A{2 + header_row_offset}'].font = Font(bold=True, size=12)
        ws[f'A{4 + header_row_offset}'] = "BILL OF QUANTITIES"
        ws[f'A{4 + header_row_offset}'].font = Font(bold=True, size=16)
        
        header_row = 6 + header_row_offset
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=header_row, column=col, value=header)
            cell.font = self.header_font
            cell.fill = self.header_fill
            cell.border = self.border
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.protection = Protection(locked=True)
        
        current_row = header_row + 1
        total_amount_formula_cells = []
        
        item_idx = 1
        for item in boq_items:
            if item.item_code == "SECTION":
                cell = ws.cell(row=current_row, column=1)
                cell.value = item.description
                cell.font = Font(bold=True, size=12)
                ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=9)
                for col in range(1, 10):
                    cell = ws.cell(row=current_row, column=col)
                    cell.fill = PatternFill(start_color="AAAAAA", end_color="AAAAAA", fill_type="solid")
                    cell.alignment = Alignment(horizontal='center')
                current_row += 1
                continue
            
            cell = ws.cell(row=current_row, column=1, value=item_idx)
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
            item_idx += 1
        
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

    def _extract_project_info_from_drawings(self, drawings: List) -> Dict[str, str]:
        """Extract project information from processed drawings for BOQ front page"""
        project_info = {}
        
        for drawing in drawings:
            if hasattr(drawing, 'project_name') and drawing.project_name:
                project_info['project_name'] = drawing.project_name
            if hasattr(drawing, 'project_number') and drawing.project_number:
                project_info['project_number'] = drawing.project_number
            
            if hasattr(drawing, 'project_name') and drawing.project_name:
                import re
                client_match = re.search(r'(?:for\s+|client\s*:\s*)([A-Za-z\s&]+)', drawing.project_name, re.IGNORECASE)
                if client_match:
                    project_info['client_name'] = client_match.group(1).strip()
        
        return project_info
    
    def generate_boq_pdf(self, boq_items: List[Dict[str, Any]], project_name: str, 
                        drawings: List[Dict[str, Any]] = None, 
                        measurement_standard: str = "SMM7") -> bytes:
        """Generate a PDF version of the BOQ"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72,
                              topMargin=72, bottomMargin=18)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12
        )
        
        story = []
        
        story.append(Paragraph(f"Bill of Quantities - {project_name}", title_style))
        story.append(Spacer(1, 12))
        
        story.append(Paragraph("Project Information", heading_style))
        project_info = [
            ['Project Name:', project_name],
            ['Measurement Standard:', measurement_standard],
            ['Generated:', datetime.now().strftime('%d/%m/%Y %H:%M')],
            ['Total Items:', str(len(boq_items))]
        ]
        
        project_table = Table(project_info, colWidths=[2*inch, 4*inch])
        project_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(project_table)
        story.append(Spacer(1, 20))
        
        if drawings:
            story.append(Paragraph("Drawing Register", heading_style))
            drawing_data = [['Drawing Title', 'Revision', 'Type', 'Status']]
            for drawing in drawings:
                drawing_data.append([
                    drawing.get('filename', 'N/A'),
                    drawing.get('revision', 'A'),
                    drawing.get('file_type', 'PDF').upper(),
                    drawing.get('status', 'Processed')
                ])
            
            drawing_table = Table(drawing_data, colWidths=[2.5*inch, 1*inch, 1*inch, 1.5*inch])
            drawing_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(drawing_table)
            story.append(PageBreak())
        
        story.append(Paragraph("Bill of Quantities", heading_style))
        
        trades = {}
        for item in boq_items:
            trade = item.get('trade', 'General')
            if trade not in trades:
                trades[trade] = []
            trades[trade].append(item)
        
        for trade, items in trades.items():
            story.append(Paragraph(f"{trade} Works", heading_style))
            
            boq_data = [['Item', 'Description', 'Unit', 'Quantity', 'Rate (£)', 'Amount (£)']]
            
            trade_total = 0
            for i, item in enumerate(items, 1):
                quantity = float(item.get('quantity', 0))
                rate = float(item.get('unit_rate', 0))
                amount = quantity * rate
                trade_total += amount
                
                boq_data.append([
                    f"{trade[0]}.{i:02d}",
                    item.get('description', 'N/A'),
                    item.get('unit', 'Nr'),
                    f"{quantity:.2f}",
                    f"{rate:.2f}",
                    f"{amount:.2f}"
                ])
            
            boq_data.append(['', f'Sub-total for {trade}', '', '', '', f"{trade_total:.2f}"])
            
            boq_table = Table(boq_data, colWidths=[0.8*inch, 2.5*inch, 0.8*inch, 1*inch, 1*inch, 1*inch])
            boq_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (1, 1), (1, -2), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ]))
            story.append(boq_table)
            story.append(Spacer(1, 20))
        
        grand_total = sum(float(item.get('quantity', 0)) * float(item.get('unit_rate', 0)) for item in boq_items)
        total_data = [['', '', '', '', 'GRAND TOTAL:', f"£{grand_total:.2f}"]]
        total_table = Table(total_data, colWidths=[0.8*inch, 2.5*inch, 0.8*inch, 1*inch, 1*inch, 1*inch])
        total_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightblue),
            ('GRID', (4, 0), (-1, -1), 2, colors.black),
        ]))
        story.append(total_table)
        
        story.append(Spacer(1, 30))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            alignment=1
        )
        story.append(Paragraph("Generated by Bojim BOQ Production Software", footer_style))
        story.append(Paragraph(f"Compliant with {measurement_standard} Standards", footer_style))
        
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

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
