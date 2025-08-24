from typing import List, Dict, Any, Optional
import uuid
from ..models import BOQItem, MeasurementStandard, Drawing
from ..schemas import BOQItemResponse

class BOQGenerator:
    def __init__(self):
        self.measurement_standards = {
            MeasurementStandard.SMM7: self._get_smm7_rules(),
            MeasurementStandard.RICS_NRM: self._get_rics_nrm_rules(),
            MeasurementStandard.CESMM: self._get_cesmm_rules()
        }

    async def generate_boq(self, project_id: str, drawings_data: List[Dict[str, Any]], 
                          standard: MeasurementStandard) -> List[BOQItem]:
        """Generate BOQ items from processed drawing data"""
        boq_items = []
        rules = self.measurement_standards[standard]
        
        print(f"DEBUG: BOQ Generator processing {len(drawings_data)} drawings")
        
        for drawing_data in drawings_data:
            drawing_id = drawing_data.get('drawing_id')
            elements = drawing_data.get('elements', [])
            drawing_type = drawing_data.get('drawing_type')
            
            print(f"DEBUG: Processing drawing {drawing_id}, type: {drawing_type}, elements: {len(elements)}")
            
            if not drawing_type or drawing_type == 'unknown' or drawing_type == 'site':
                drawing_type = 'architectural'
                print(f"DEBUG: Drawing type '{drawing_data.get('drawing_type')}' converted to architectural")
            
            if drawing_type == 'architectural':
                items = self._process_architectural_elements(
                    project_id, drawing_id, elements, rules
                )
                print(f"DEBUG: Architectural processing generated {len(items)} items")
                boq_items.extend(items)
            elif drawing_type == 'structural':
                items = self._process_structural_elements(
                    project_id, drawing_id, elements, rules
                )
                print(f"DEBUG: Structural processing generated {len(items)} items")
                boq_items.extend(items)
            elif drawing_type == 'mep':
                items = self._process_mep_elements(
                    project_id, drawing_id, elements, rules
                )
                print(f"DEBUG: MEP processing generated {len(items)} items")
                boq_items.extend(items)
            else:
                print(f"DEBUG: Unknown drawing type '{drawing_type}', skipping")
        
        print(f"DEBUG: Total BOQ items generated: {len(boq_items)}")
        return boq_items

    def _process_architectural_elements(self, project_id: str, drawing_id: str, 
                                      elements: List[Dict], rules: Dict) -> List[BOQItem]:
        """Process architectural elements into BOQ items"""
        boq_items = []
        
        element_types = {}
        for e in elements:
            elem_type = e.get('type', 'unknown')
            element_types[elem_type] = element_types.get(elem_type, 0) + 1
        print(f"DEBUG: Element types in drawing: {element_types}")
        
        walls = [e for e in elements if e.get('type') == 'line' and e.get('length', 0) > 100]
        areas = [e for e in elements if e.get('type') in ['polyline', 'rectangle'] and e.get('area', 0) > 0]
        
        print(f"DEBUG: Found {len(walls)} potential walls (lines > 100), {len(areas)} potential areas")
        
        if walls:
            total_wall_length = sum(wall.get('length', 0) for wall in walls)
            print(f"DEBUG: Total wall length: {total_wall_length}")
            if total_wall_length > 0:
                boq_items.append(BOQItem(
                    project_id=project_id,
                    drawing_id=drawing_id,
                    item_code=rules['walls']['code'],
                    description=rules['walls']['description'],
                    unit=rules['walls']['unit'],
                    quantity=round(total_wall_length / 1000, 2),  # Convert to meters
                    category="masonry",
                    trade="civil",
                    measurement_standard=MeasurementStandard.SMM7
                ))
        
        if areas:
            total_floor_area = sum(area.get('area', 0) for area in areas)
            print(f"DEBUG: Total floor area: {total_floor_area}")
            if total_floor_area > 0:
                boq_items.append(BOQItem(
                    project_id=project_id,
                    drawing_id=drawing_id,
                    item_code=rules['flooring']['code'],
                    description=rules['flooring']['description'],
                    unit=rules['flooring']['unit'],
                    quantity=round(total_floor_area / 1000000, 2),  # Convert to sq meters
                    category="flooring",
                    trade="civil",
                    measurement_standard=MeasurementStandard.SMM7
                ))
        
        if not boq_items and elements:
            all_lines = [e for e in elements if e.get('type') == 'line']
            if all_lines:
                total_length = sum(line.get('length', 0) for line in all_lines)
                print(f"DEBUG: Creating general construction item from {len(all_lines)} lines, total length: {total_length}")
                if total_length > 0:
                    boq_items.append(BOQItem(
                        project_id=project_id,
                        drawing_id=drawing_id,
                        item_code="GENERAL.1",
                        description="General construction work based on drawing elements",
                        unit="m",
                        quantity=round(total_length / 1000, 2),
                        category="general",
                        trade="civil",
                        measurement_standard=MeasurementStandard.SMM7
                    ))
        
        print(f"DEBUG: Architectural processing created {len(boq_items)} BOQ items")
        return boq_items

    def _process_structural_elements(self, project_id: str, drawing_id: str, 
                                   elements: List[Dict], rules: Dict) -> List[BOQItem]:
        """Process structural elements into BOQ items"""
        boq_items = []
        
        beams = [e for e in elements if e.get('type') == 'line' and e.get('length', 0) > 200]
        if beams:
            total_beam_length = sum(beam.get('length', 0) for beam in beams)
            if total_beam_length > 0:
                boq_items.append(BOQItem(
                    project_id=project_id,
                    drawing_id=drawing_id,
                    item_code=rules['beams']['code'],
                    description=rules['beams']['description'],
                    unit=rules['beams']['unit'],
                    quantity=round(total_beam_length / 1000, 2),
                    category="concrete",
                    trade="structural",
                    measurement_standard=MeasurementStandard.SMM7
                ))
        
        columns = [e for e in elements if e.get('type') == 'circle' or 
                  (e.get('type') == 'rectangle' and e.get('area', 0) < 10000)]
        if columns:
            boq_items.append(BOQItem(
                project_id=project_id,
                drawing_id=drawing_id,
                item_code=rules['columns']['code'],
                description=rules['columns']['description'],
                unit=rules['columns']['unit'],
                quantity=len(columns),
                category="concrete",
                trade="structural",
                measurement_standard=MeasurementStandard.SMM7
            ))
        
        return boq_items

    def _process_mep_elements(self, project_id: str, drawing_id: str, 
                            elements: List[Dict], rules: Dict) -> List[BOQItem]:
        """Process MEP elements into BOQ items"""
        boq_items = []
        
        electrical_lines = [e for e in elements if e.get('type') == 'line']
        if electrical_lines:
            total_conduit_length = sum(line.get('length', 0) for line in electrical_lines)
            if total_conduit_length > 0:
                boq_items.append(BOQItem(
                    project_id=project_id,
                    drawing_id=drawing_id,
                    item_code=rules['conduit']['code'],
                    description=rules['conduit']['description'],
                    unit=rules['conduit']['unit'],
                    quantity=round(total_conduit_length / 1000, 2),
                    category="electrical",
                    trade="electrical",
                    measurement_standard=MeasurementStandard.SMM7
                ))
        
        electrical_points = [e for e in elements if e.get('type') == 'circle']
        if electrical_points:
            boq_items.append(BOQItem(
                project_id=project_id,
                drawing_id=drawing_id,
                item_code=rules['points']['code'],
                description=rules['points']['description'],
                unit=rules['points']['unit'],
                quantity=len(electrical_points),
                category="electrical",
                trade="electrical",
                measurement_standard=MeasurementStandard.SMM7
            ))
        
        return boq_items

    def _get_smm7_rules(self) -> Dict[str, Any]:
        """SMM7 measurement rules and item codes"""
        return {
            'walls': {
                'code': 'F10.1.1.1',
                'description': 'Brick/block walling, stretcher bond',
                'unit': 'm²'
            },
            'flooring': {
                'code': 'M20.1.1.1',
                'description': 'Floor finishes, ceramic tiles',
                'unit': 'm²'
            },
            'beams': {
                'code': 'E20.1.1.1',
                'description': 'Reinforced concrete beams',
                'unit': 'm³'
            },
            'columns': {
                'code': 'E20.2.1.1',
                'description': 'Reinforced concrete columns',
                'unit': 'nr'
            },
            'conduit': {
                'code': 'V20.1.1.1',
                'description': 'PVC conduit installation',
                'unit': 'm'
            },
            'points': {
                'code': 'V21.1.1.1',
                'description': 'Electrical socket outlets',
                'unit': 'nr'
            }
        }

    def _get_rics_nrm_rules(self) -> Dict[str, Any]:
        """RICS NRM measurement rules and item codes"""
        return {
            'walls': {
                'code': '2.1.1',
                'description': 'External walls - masonry construction',
                'unit': 'm²'
            },
            'flooring': {
                'code': '2.8.1',
                'description': 'Floor finishes',
                'unit': 'm²'
            },
            'beams': {
                'code': '2.2.1',
                'description': 'Structural frame - concrete',
                'unit': 'm³'
            },
            'columns': {
                'code': '2.2.2',
                'description': 'Structural columns',
                'unit': 'nr'
            },
            'conduit': {
                'code': '5.1.1',
                'description': 'Electrical installations - conduit',
                'unit': 'm'
            },
            'points': {
                'code': '5.1.2',
                'description': 'Electrical installations - outlets',
                'unit': 'nr'
            }
        }

    def _get_cesmm_rules(self) -> Dict[str, Any]:
        """CESMM measurement rules and item codes"""
        return {
            'walls': {
                'code': 'F1.1.1.1',
                'description': 'Masonry construction',
                'unit': 'm²'
            },
            'flooring': {
                'code': 'G1.1.1.1',
                'description': 'Floor finishes',
                'unit': 'm²'
            },
            'beams': {
                'code': 'E4.1.1.1',
                'description': 'Concrete structures - beams',
                'unit': 'm³'
            },
            'columns': {
                'code': 'E4.2.1.1',
                'description': 'Concrete structures - columns',
                'unit': 'nr'
            },
            'conduit': {
                'code': 'P1.1.1.1',
                'description': 'Electrical conduit systems',
                'unit': 'm'
            },
            'points': {
                'code': 'P1.2.1.1',
                'description': 'Electrical outlet points',
                'unit': 'nr'
            }
        }
