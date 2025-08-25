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
            
            if not drawing_type or drawing_type == 'unknown' or drawing_type == 'site':
                drawing_type = 'architectural'
            
            if drawing_type == 'architectural':
                items = self._process_architectural_elements(
                    project_id, drawing_id, elements, rules
                )
                boq_items.extend(items)
            elif drawing_type == 'structural':
                items = self._process_structural_elements(
                    project_id, drawing_id, elements, rules
                )
                boq_items.extend(items)
            elif drawing_type == 'mep':
                items = self._process_mep_elements(
                    project_id, drawing_id, elements, rules
                )
                boq_items.extend(items)
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
        
        all_lines = [e for e in elements if e.get('type') == 'line']
        all_circles = [e for e in elements if e.get('type') == 'circle']
        all_rectangles = [e for e in elements if e.get('type') == 'rectangle']
        all_polylines = [e for e in elements if e.get('type') == 'polyline']
        
        print(f"DEBUG: Found {len(all_lines)} lines, {len(all_circles)} circles, {len(all_rectangles)} rectangles, {len(all_polylines)} polylines")
        
        exterior_walls = [e for e in all_lines if e.get('length', 0) > 3000]  # Long walls (>3m)
        interior_walls = [e for e in all_lines if 1000 < e.get('length', 0) <= 3000]  # Medium walls (1-3m)
        partition_walls = [e for e in all_lines if 500 < e.get('length', 0) <= 1000]  # Short walls (0.5-1m)
        
        if exterior_walls:
            total_length = sum(wall.get('length', 0) for wall in exterior_walls) / 1000
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code=rules['walls']['code'], description="External brick/block walling",
                unit="m²", quantity=round(total_length * 2.7, 2),  # Assume 2.7m height
                category="masonry", trade="civil", measurement_standard=MeasurementStandard.SMM7
            ))
        
        if interior_walls:
            total_length = sum(wall.get('length', 0) for wall in interior_walls) / 1000
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="F10.2.1.1", description="Internal brick/block walling",
                unit="m²", quantity=round(total_length * 2.7, 2),
                category="masonry", trade="civil", measurement_standard=MeasurementStandard.SMM7
            ))
        
        if partition_walls:
            total_length = sum(wall.get('length', 0) for wall in partition_walls) / 1000
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="K10.1.1.1", description="Partition walling, lightweight",
                unit="m²", quantity=round(total_length * 2.7, 2),
                category="partitions", trade="civil", measurement_standard=MeasurementStandard.SMM7
            ))
        
        large_areas = [e for e in (all_rectangles + all_polylines) if e.get('area', 0) > 50000000]  # >50m²
        medium_areas = [e for e in (all_rectangles + all_polylines) if 10000000 < e.get('area', 0) <= 50000000]  # 10-50m²
        small_areas = [e for e in (all_rectangles + all_polylines) if 1000000 < e.get('area', 0) <= 10000000]  # 1-10m²
        
        if large_areas:
            total_area = sum(area.get('area', 0) for area in large_areas) / 1000000
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="M20.1.1.1", description="Floor finishes, main areas",
                unit="m²", quantity=round(total_area, 2),
                category="flooring", trade="civil", measurement_standard=MeasurementStandard.SMM7
            ))
        
        if medium_areas:
            total_area = sum(area.get('area', 0) for area in medium_areas) / 1000000
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="M20.2.1.1", description="Floor finishes, secondary areas",
                unit="m²", quantity=round(total_area, 2),
                category="flooring", trade="civil", measurement_standard=MeasurementStandard.SMM7
            ))
        
        if small_areas:
            total_area = sum(area.get('area', 0) for area in small_areas) / 1000000
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="M20.3.1.1", description="Floor finishes, ancillary areas",
                unit="m²", quantity=round(total_area, 2),
                category="flooring", trade="civil", measurement_standard=MeasurementStandard.SMM7
            ))
        
        door_openings = [e for e in all_rectangles if 500000 < e.get('area', 0) < 5000000]  # 0.5-5m² openings
        window_openings = [e for e in all_rectangles if 100000 < e.get('area', 0) <= 500000]  # 0.1-0.5m² openings
        
        if door_openings:
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="L10.1.1.1", description="Door openings and frames",
                unit="nr", quantity=len(door_openings),
                category="doors", trade="joinery", measurement_standard=MeasurementStandard.SMM7
            ))
        
        if window_openings:
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="L10.2.1.1", description="Window openings and frames",
                unit="nr", quantity=len(window_openings),
                category="windows", trade="joinery", measurement_standard=MeasurementStandard.SMM7
            ))
        
        columns = [e for e in all_circles if e.get('radius', 0) > 100]  # Circles > 10cm radius
        beams = [e for e in all_lines if e.get('length', 0) > 2000 and e.get('thickness', 0) > 50]  # Thick long lines
        
        if columns:
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="E20.2.1.1", description="Reinforced concrete columns",
                unit="nr", quantity=len(columns),
                category="concrete", trade="structural", measurement_standard=MeasurementStandard.SMM7
            ))
        
        if beams:
            total_beam_length = sum(beam.get('length', 0) for beam in beams) / 1000
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="E20.1.1.1", description="Reinforced concrete beams",
                unit="m", quantity=round(total_beam_length, 2),
                category="concrete", trade="structural", measurement_standard=MeasurementStandard.SMM7
            ))
        
        electrical_points = [e for e in all_circles if 10 < e.get('radius', 0) <= 50]  # Small circles
        electrical_conduits = [e for e in all_lines if 100 < e.get('length', 0) <= 500]  # Short lines
        
        if electrical_points:
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="V21.1.1.1", description="Electrical socket outlets",
                unit="nr", quantity=len(electrical_points),
                category="electrical", trade="electrical", measurement_standard=MeasurementStandard.SMM7
            ))
        
        if electrical_conduits:
            total_conduit_length = sum(conduit.get('length', 0) for conduit in electrical_conduits) / 1000
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="V20.1.1.1", description="PVC conduit installation",
                unit="m", quantity=round(total_conduit_length, 2),
                category="electrical", trade="electrical", measurement_standard=MeasurementStandard.SMM7
            ))
        
        plumbing_fixtures = [e for e in all_circles if 5 < e.get('radius', 0) <= 25]  # Very small circles
        
        if plumbing_fixtures:
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="R10.1.1.1", description="Sanitary fittings and fixtures",
                unit="nr", quantity=len(plumbing_fixtures),
                category="plumbing", trade="plumbing", measurement_standard=MeasurementStandard.SMM7
            ))
        
        roof_areas = [e for e in (all_rectangles + all_polylines) if e.get('area', 0) > 20000000]  # Large areas
        
        if roof_areas:
            total_roof_area = sum(area.get('area', 0) for area in roof_areas) / 1000000
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="H60.1.1.1", description="Roof covering and structure",
                unit="m²", quantity=round(total_roof_area, 2),
                category="roofing", trade="roofing", measurement_standard=MeasurementStandard.SMM7
            ))
        
        if large_areas or medium_areas:
            total_building_area = sum(area.get('area', 0) for area in (large_areas + medium_areas)) / 1000000
            excavation_volume = total_building_area * 0.5  # Assume 0.5m depth
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="D20.1.1.1", description="Excavation for foundations",
                unit="m³", quantity=round(excavation_volume, 2),
                category="excavation", trade="civil", measurement_standard=MeasurementStandard.SMM7
            ))
        
        print(f"DEBUG: Enhanced architectural processing created {len(boq_items)} BOQ items")
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
