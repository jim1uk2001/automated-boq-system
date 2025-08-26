from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, Protection
from openpyxl.utils import get_column_letter
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
        self.section_font = Font(bold=True, size=14)
        self.title_font = Font(bold=True, size=18)
        self.data_font = Font(size=10)
        self.preamble_font = Font(size=10)
        
        self.thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

    def generate_boq_excel(self, project: Project, boq_items: List[BOQItem]) -> bytes:
        """Generate professional multi-sheet Excel BOQ following SMM7 standards"""
        wb = Workbook()
        cover = wb.active
        cover.title = 'Cover'
        drawings = wb.create_sheet('Drawings')
        preambles = wb.create_sheet('Preambles')
        boq = wb.create_sheet('BOQ')

        self._create_cover_page(cover, project)
        self._create_drawings_register(drawings, project)
        self._create_preambles_page(preambles, project.measurement_standard)
        self._create_boq_page(boq, project, boq_items)

        wb.active = cover
        
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()
    
    def _create_cover_page(self, ws, project: Project):
        """Create professional cover page following user's template"""
        ws.merge_cells('B2:F2')
        ws['B2'] = project.name
        ws['B2'].font = Font(size=18, bold=True)
        ws['B2'].alignment = Alignment(horizontal='center')
        
        ws.merge_cells('B4:F4')
        ws['B4'] = f'Bill of Quantities prepared in accordance with {project.measurement_standard.value}'
        ws['B4'].alignment = Alignment(horizontal='center')
        
        ws['F6'] = f'Date: {datetime.now().strftime("%d-%b-%Y")}'
        ws['F6'].alignment = Alignment(horizontal='right')
        
        ws.merge_cells('B10:F10')
        ws['B10'] = 'Produced by Bojim BOQ Production Software'
        ws['B10'].font = Font(italic=True)
        ws['B10'].alignment = Alignment(horizontal='center')
    
    def _create_drawings_register(self, ws, project: Project):
        """Create drawings register page following user's template"""
        headers = ['Drawing No.', 'Title', 'Revision', 'Date', 'Notes']
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=2, column=col_num, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
            ws.column_dimensions[get_column_letter(col_num)].width = 20

        for i, drawing in enumerate(project.drawings, 1):
            row_data = [
                drawing.drawing_number or f'D{i:03d}',
                drawing.drawing_title or drawing.filename,
                drawing.revision_number or 'A',
                drawing.revision_date.strftime("%d-%b-%Y") if drawing.revision_date else 'Not detected',
                'Verify revision matches BOQ quantities'
            ]
            
            for col_num, value in enumerate(row_data, 1):
                cell = ws.cell(row=i + 2, column=col_num, value=value)
                cell.alignment = Alignment(horizontal='left')

        warning_row = len(project.drawings) + 5
        ws.merge_cells(f'A{warning_row}:E{warning_row}')
        warning_cell = ws[f'A{warning_row}']
        warning_cell.value = "WARNING: Contractors must verify they are pricing the correct drawing revisions. Discrepancies between BOQ quantities and drawing revisions may result in contract disputes."
        warning_cell.font = Font(bold=True, italic=True, size=10)
        warning_cell.alignment = Alignment(horizontal='left', wrap_text=True)
    
    def _create_preambles_page(self, ws, standard):
        """Create preambles page using existing measurement standard preambles"""
        preambles_data = self._get_measurement_standard_preambles(standard.value)
        
        row = 2
        for heading, text in preambles_data:
            ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=6)
            ws.cell(row=row, column=2, value=heading).font = Font(bold=True)
            ws.cell(row=row, column=2).alignment = Alignment(horizontal='left')
            row += 1
            ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=6)
            ws.cell(row=row, column=2, value=text).alignment = Alignment(horizontal='left', wrap_text=True)
            row += 2  # empty row for spacing
    
    def _create_boq_page(self, ws, project: Project, boq_items: List[BOQItem]):
        """Create main BOQ page with professional sectioned formatting"""
        headers = ['Item', 'Description of Work (SMM7)', 'Unit', 'Quantity', 'Rate (£)', 'Amount (£)']
        
        column_widths = [6.8, 80.5, 6.8, 13.2, 12.5, 14.0]  # Professional SMM7 template column widths
        
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=2, column=col_num, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
            ws.column_dimensions[get_column_letter(col_num)].width = column_widths[col_num - 1]

        grouped_items = {}
        for item in boq_items:
            category = item.category or 'General'
            if category not in grouped_items:
                grouped_items[category] = []
            grouped_items[category].append(item)

        row = 4
        section_counter = 1
        
        for category, items in grouped_items.items():
            ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=6)
            ws.cell(row=row, column=2, value=f"SECTION {section_counter}: {category.upper()}").font = Font(bold=True)
            row += 1
            row += 1
            ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=6)
            ws.cell(row=row, column=2, value=category.title()).font = Font(italic=True)
            row += 2
            
            for i, item in enumerate(items, 1):
                ws.cell(row=row, column=1, value=f"{section_counter}.{i}")
                ws.cell(row=row, column=2, value=item.description)
                ws.cell(row=row, column=3, value=item.unit)
                ws.cell(row=row, column=4, value=item.quantity)
                ws.cell(row=row, column=5, value='')  # Rate (editable)
                ws.cell(row=row, column=6, value=f'=D{row}*E{row}')  # Amount formula
                
                ws.row_dimensions[row].height = 25
                
                for col in range(1, 7):
                    cell = ws.cell(row=row, column=col)
                    cell.border = self.thin_border
                    cell.alignment = Alignment(horizontal='left' if col == 2 else 'center', wrap_text=True if col == 2 else False)
                    if col == 5:  # Rate column - editable
                        cell.protection = Protection(locked=False)
                
                row += 2  # empty row after each item following template
            
            section_counter += 1
            row += 2  # Two empty rows at end of section following template

        ws.protection.sheet = True
        ws.protection.password = "boq2024"
        ws.protection.enable()

    def _get_measurement_standard_preambles(self, standard: str) -> List[tuple]:
        """Get comprehensive preambles for specific measurement standard"""
        
        if standard == "SMM7":
            return [
                ('General', 'All works shall be executed in accordance with the SMM7 standard method of measurement and the project drawings.'),
                ('Quantities', 'Quantities given in this Bill of Quantities are approximate. The contractor must verify all quantities on site prior to execution.'),
                ('Rates', 'Rates shall include all materials, labor, plant, scaffolding, transport, and overheads necessary for proper execution of the work.'),
                ('Dimensions', 'All dimensions must be checked on site before commencing any work. Discrepancies between drawings, specifications, and the SMM7 items must be reported to the client or engineer.'),
                ('Temporary Works and Statutory Compliance', 'Temporary works, protection of existing structures, and compliance with statutory regulations are deemed included unless stated otherwise.'),
                ('Materials', 'All materials shall comply with relevant British Standards and Codes of Practice.'),
                ('Health & Safety', 'The contractor shall ensure full compliance with current health and safety legislation at all times.'),
                ('Measurement Rules', 'Linear, area, and volume measurements shall be taken in accordance with SMM7 conventions.'),
                ('Provisional Sums & Variations', 'Daywork, prime cost sums, provisional sums, and variations arising from site conditions or client requirements shall be applied as described in SMM7.'),
                ('Quality of Work', 'All work shall be completed in a good and workmanlike manner and shall conform to the drawings, specifications, and SMM7 rules.')
            ]
        elif standard == "RICS_NRM":
            return [
                ('General', 'All works shall be executed in accordance with the RICS_NRM standard method of measurement and the project drawings.'),
                ('Quantities', 'Quantities given in this Bill of Quantities are approximate. The contractor must verify all quantities on site prior to execution.'),
                ('Rates', 'Rates shall include all materials, labor, plant, scaffolding, transport, and overheads necessary for proper execution of the work.'),
                ('Dimensions', 'All dimensions must be checked on site before commencing any work. Discrepancies between drawings, specifications, and the RICS_NRM items must be reported to the client or engineer.'),
                ('Temporary Works and Statutory Compliance', 'Temporary works, protection of existing structures, and compliance with statutory regulations are deemed included unless stated otherwise.'),
                ('Materials', 'All materials shall comply with relevant British Standards and Codes of Practice.'),
                ('Health & Safety', 'The contractor shall ensure full compliance with current health and safety legislation at all times.'),
                ('Measurement Rules', 'Linear, area, and volume measurements shall be taken in accordance with RICS_NRM conventions.'),
                ('Provisional Sums & Variations', 'Daywork, prime cost sums, provisional sums, and variations arising from site conditions or client requirements shall be applied as described in RICS_NRM.'),
                ('Quality of Work', 'All work shall be completed in a good and workmanlike manner and shall conform to the drawings, specifications, and RICS_NRM rules.')
            ]
        else:  # CESMM
            return [
                ('General', 'All works shall be executed in accordance with the CESMM standard method of measurement and the project drawings.'),
                ('Quantities', 'Quantities given in this Bill of Quantities are approximate. The contractor must verify all quantities on site prior to execution.'),
                ('Rates', 'Rates shall include all materials, labor, plant, scaffolding, transport, and overheads necessary for proper execution of the work.'),
                ('Dimensions', 'All dimensions must be checked on site before commencing any work. Discrepancies between drawings, specifications, and the CESMM items must be reported to the client or engineer.'),
                ('Temporary Works and Statutory Compliance', 'Temporary works, protection of existing structures, and compliance with statutory regulations are deemed included unless stated otherwise.'),
                ('Materials', 'All materials shall comply with relevant British Standards and Codes of Practice.'),
                ('Health & Safety', 'The contractor shall ensure full compliance with current health and safety legislation at all times.'),
                ('Measurement Rules', 'Linear, area, and volume measurements shall be taken in accordance with CESMM conventions.'),
                ('Provisional Sums & Variations', 'Daywork, prime cost sums, provisional sums, and variations arising from site conditions or client requirements shall be applied as described in CESMM.'),
                ('Quality of Work', 'All work shall be completed in a good and workmanlike manner and shall conform to the drawings, specifications, and CESMM rules.')
            ]

    def _extract_project_info_from_drawings(self, drawings) -> Dict[str, Any]:
        """Extract project information from drawing metadata"""
        project_info = {}
        
        for drawing in drawings:
            if hasattr(drawing, 'metadata') and drawing.metadata:
                if 'project_number' in drawing.metadata:
                    project_info['project_number'] = drawing.metadata['project_number']
                if 'client_name' in drawing.metadata:
                    project_info['client_name'] = drawing.metadata['client_name']
                if 'project_title' in drawing.metadata:
                    project_info['project_title'] = drawing.metadata['project_title']
        
        return project_info

    def generate_boq_pdf(self, project: Project, boq_items: List[BOQItem]) -> bytes:
        """Generate PDF BOQ document"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1  # Center alignment
        )
        story.append(Paragraph(f"Bill of Quantities - {project.name}", title_style))
        story.append(Spacer(1, 12))
        
        story.append(Paragraph(f"Measurement Standard: {project.measurement_standard.value}", styles['Normal']))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y')}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        data = [['Item', 'Code', 'Description', 'Unit', 'Quantity', 'Rate', 'Amount']]
        
        for i, item in enumerate(boq_items, 1):
            data.append([
                str(i),
                item.item_code or '',
                item.description,
                item.unit,
                str(item.quantity),
                '',  # Rate column empty for pricing
                ''   # Amount column empty for pricing
            ])
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        doc.build(story)
        
        buffer.seek(0)
        return buffer.getvalue()

    def generate_bid_comparison_excel(self, project: Project, bids: List[Dict]) -> bytes:
        """Generate bid comparison Excel document"""
        wb = Workbook()
        ws = wb.active
        ws.title = "Bid Comparison"
        
        headers = ['Rank', 'Contractor', 'Total Bid (£)', 'Submission Date', 'Status']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, size=12)
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        for row, bid in enumerate(bids, 2):
            ws.cell(row=row, column=1, value=bid.get('rank', ''))
            ws.cell(row=row, column=2, value=bid.get('contractor_name', ''))
            ws.cell(row=row, column=3, value=bid.get('total_amount', ''))
            ws.cell(row=row, column=4, value=bid.get('submission_date', ''))
            ws.cell(row=row, column=5, value=bid.get('status', ''))
        
        column_widths = [8, 25, 15, 15, 12]
        for col, width in enumerate(column_widths, 1):
            column_letter = get_column_letter(col)
            ws.column_dimensions[column_letter].width = width
        
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()
