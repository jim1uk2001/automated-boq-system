from typing import List, Dict, Any, Optional
import uuid
import numpy as np
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
        
        building_type_drawings = {}
        
        for drawing_data in drawings_data:
            drawing_id = drawing_data.get('drawing_id')
            elements = drawing_data.get('elements', [])
            drawing_type = drawing_data.get('drawing_type')
            building_types = drawing_data.get('building_types', {})
            
            if not drawing_type or drawing_type == 'unknown' or drawing_type == 'site':
                drawing_type = 'architectural'
            
            if building_types:
                for type_name, _ in building_types.items():
                    if type_name not in building_type_drawings:
                        building_type_drawings[type_name] = []
                    building_type_drawings[type_name].append({
                        'drawing_id': drawing_id,
                        'elements': elements,
                        'drawing_type': drawing_type
                    })
            else:
                if "General" not in building_type_drawings:
                    building_type_drawings["General"] = []
                building_type_drawings["General"].append({
                    'drawing_id': drawing_id,
                    'elements': elements,
                    'drawing_type': drawing_type
                })
        
        for building_type, type_drawings in building_type_drawings.items():
            section_id = str(uuid.uuid4())
            boq_items.append(BOQItem(
                id=section_id,
                project_id=project_id,
                drawing_id=None,
                item_code=f"SECTION",
                description=f"BUILDING {building_type}",
                unit="",
                quantity=0,
                category="section",
                trade="general",
                measurement_standard=standard,
                notes=f"Items for {building_type}"
            ))
            
            for drawing_data in type_drawings:
                drawing_id = drawing_data.get('drawing_id')
                elements = drawing_data.get('elements', [])
                drawing_type = drawing_data.get('drawing_type')
                
                if drawing_type == 'architectural':
                    items = self._process_architectural_elements(
                        project_id, drawing_id, elements, rules, building_type
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
                                      elements: List[Dict], rules: Dict, 
                                      building_type: str = "General") -> List[BOQItem]:
        """Process architectural elements into BOQ items"""
        boq_items = []
        
        element_types = {}
        for e in elements:
            elem_type = e.get('type', 'unknown')
            element_types[elem_type] = element_types.get(elem_type, 0) + 1
        print(f"DEBUG: Element types in drawing: {element_types}")
        
        building_config = self._get_building_type_config(building_type)
        
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
        
        electrical_symbols = [e for e in all_circles if 10 < e.get('radius', 0) <= 50]
        
        # This prevents counting annotation circles and dimension markers as sockets
        electrical_points = self._group_electrical_symbols(electrical_symbols)
        
        electrical_conduits = [e for e in all_lines if 100 < e.get('length', 0) <= 500]  # Short lines
        
        if electrical_points:
            socket_count = self._calculate_electrical_sockets(electrical_points, building_type, building_config)
            
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="V21.1.1.1", description="Electrical socket outlets",
                unit="nr", quantity=socket_count,
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
        
        print(f"DEBUG: Enhanced architectural processing created {len(boq_items)} BOQ items for {building_type}")
        return boq_items
        
    def _group_electrical_symbols(self, symbols: List[Dict]) -> List[Dict]:
        """Group electrical symbols by proximity to identify actual electrical points.
        This prevents counting annotation circles and dimension markers as sockets."""
        if not symbols:
            return []
            
        filtered_symbols = []
        for symbol in symbols:
            radius = symbol.get('radius', 0)
            if 12 <= radius <= 25:  # More restrictive range for actual electrical symbols
                filtered_symbols.append(symbol)
        
        if not filtered_symbols:
            return []
            
        grouped_symbols = []
        processed = set()
        
        for i, symbol in enumerate(filtered_symbols):
            if i in processed:
                continue
                
            group = [symbol]
            processed.add(i)
            
            for j, other in enumerate(filtered_symbols):
                if j in processed:
                    continue
                    
                dist = np.sqrt((symbol['center'][0] - other['center'][0])**2 + 
                              (symbol['center'][1] - other['center'][1])**2)
                if dist < 50:  # 50 pixel threshold for grouping nearby symbols
                    group.append(other)
                    processed.add(j)
                    
            grouped_symbols.append(group[0])  # Use the first symbol in each group
            
        return grouped_symbols
    
    def _get_building_type_config(self, building_type: str) -> Dict[str, Any]:
        """Get configuration parameters for different building types"""
        configs = {
            "General": {
                "socket_multiplier": 1.0,
                "area_multiplier": 1.0,
                "complexity_factor": 1.0,
                "typical_floors": 1
            },
            "Type A": {
                "socket_multiplier": 0.8,
                "area_multiplier": 1.0,
                "complexity_factor": 1.0,
                "typical_floors": 2,
                "sockets_per_house": 25
            },
            "Type B": {
                "socket_multiplier": 1.0,
                "area_multiplier": 1.2,
                "complexity_factor": 1.1,
                "typical_floors": 2,
                "sockets_per_house": 30
            },
            "Office Building": {
                "socket_multiplier": 2.5,
                "area_multiplier": 1.0,
                "complexity_factor": 1.3,
                "typical_floors": 5,
                "sockets_per_100sqm": 40
            },
            "Hospital/Medical": {
                "socket_multiplier": 4.0,
                "area_multiplier": 1.0,
                "complexity_factor": 2.0,
                "typical_floors": 3,
                "sockets_per_100sqm": 80,
                "special_systems": ["medical_gas", "nurse_call", "emergency_power"]
            },
            "Educational": {
                "socket_multiplier": 1.8,
                "area_multiplier": 1.0,
                "complexity_factor": 1.4,
                "typical_floors": 2,
                "sockets_per_100sqm": 30
            },
            "Retail Building": {
                "socket_multiplier": 1.5,
                "area_multiplier": 1.0,
                "complexity_factor": 1.2,
                "typical_floors": 1,
                "sockets_per_100sqm": 25
            },
            "Industrial": {
                "socket_multiplier": 3.0,
                "area_multiplier": 1.0,
                "complexity_factor": 1.8,
                "typical_floors": 1,
                "sockets_per_100sqm": 15,
                "special_systems": ["three_phase_power", "heavy_duty_outlets"]
            },
            "Mixed-Use Development": {
                "socket_multiplier": 2.0,
                "area_multiplier": 1.3,
                "complexity_factor": 1.6,
                "typical_floors": 8,
                "sockets_per_100sqm": 35,
                "mixed_zones": ["residential", "commercial", "retail"]
            },
            "High-Rise Building": {
                "socket_multiplier": 2.2,
                "area_multiplier": 1.0,
                "complexity_factor": 1.8,
                "typical_floors": 20,
                "sockets_per_100sqm": 45,
                "special_systems": ["fire_alarm", "elevator_systems", "building_management"]
            }
        }
        
        return configs.get(building_type, configs["General"])
    
    def _calculate_electrical_sockets(self, electrical_points: List[Dict], 
                                    building_type: str, config: Dict[str, Any]) -> int:
        """Calculate realistic electrical socket count based on building type"""
        detected_count = len(electrical_points)
        
        if building_type in ["Type A", "Type B"]:
            # Residential houses - calculate per house
            houses_count = max(1, detected_count // config.get("sockets_per_house", 25))
            return min(houses_count * config.get("sockets_per_house", 25), 120)
        
        elif "sockets_per_100sqm" in config:
            estimated_area = detected_count * 10  # Rough area estimation
            area_based_sockets = (estimated_area / 100) * config["sockets_per_100sqm"]
            return int(min(area_based_sockets * config["socket_multiplier"], 500))
        
        else:
            base_count = min(detected_count, 100)
            return int(base_count * config["socket_multiplier"])

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
        """SMM7 measurement rules and item codes based on CAWS"""
        return {
            'preliminaries': {
                'code': 'A10.1.1.1',
                'description': 'Project preliminaries',
                'unit': 'item'
            },
            'excavation': {
                'code': 'D20.1.1.1',
                'description': 'Excavation for foundations',
                'unit': 'm³'
            },
            'site_preparation': {
                'code': 'D20.2.1.1',
                'description': 'Site preparation and clearance',
                'unit': 'm²'
            },
            'foundations': {
                'code': 'E10.1.1.1',
                'description': 'Concrete foundations',
                'unit': 'm³'
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
            'slabs': {
                'code': 'E10.2.1.1',
                'description': 'Concrete floor slabs',
                'unit': 'm³'
            },
            'external_walls': {
                'code': 'F10.1.1.1',
                'description': 'External brick/block walling, stretcher bond',
                'unit': 'm²'
            },
            'internal_walls': {
                'code': 'F10.2.1.1',
                'description': 'Internal brick/block walling',
                'unit': 'm²'
            },
            'cavity_walls': {
                'code': 'F10.1.2.1',
                'description': 'Cavity wall construction',
                'unit': 'm²'
            },
            'roof_structure': {
                'code': 'G20.1.1.1',
                'description': 'Timber roof structure',
                'unit': 'm²'
            },
            'floor_structure': {
                'code': 'G20.2.1.1',
                'description': 'Timber floor structure',
                'unit': 'm²'
            },
            'roof_covering': {
                'code': 'H60.1.1.1',
                'description': 'Roof covering and structure',
                'unit': 'm²'
            },
            'external_cladding': {
                'code': 'H20.1.1.1',
                'description': 'External wall cladding',
                'unit': 'm²'
            },
            'damp_proof': {
                'code': 'J40.1.1.1',
                'description': 'Damp proof course/membrane',
                'unit': 'm²'
            },
            'waterproofing': {
                'code': 'J20.1.1.1',
                'description': 'Waterproofing systems',
                'unit': 'm²'
            },
            'partitions': {
                'code': 'K10.1.1.1',
                'description': 'Partition walling, lightweight',
                'unit': 'm²'
            },
            'dry_lining': {
                'code': 'K10.2.1.1',
                'description': 'Dry lining to walls',
                'unit': 'm²'
            },
            'doors': {
                'code': 'L10.1.1.1',
                'description': 'Door openings and frames',
                'unit': 'nr'
            },
            'windows': {
                'code': 'L10.2.1.1',
                'description': 'Window openings and frames',
                'unit': 'nr'
            },
            'glazing': {
                'code': 'L40.1.1.1',
                'description': 'Glazing systems',
                'unit': 'm²'
            },
            'floor_finishes': {
                'code': 'M20.1.1.1',
                'description': 'Floor finishes, ceramic tiles',
                'unit': 'm²'
            },
            'wall_finishes': {
                'code': 'M20.2.1.1',
                'description': 'Wall finishes',
                'unit': 'm²'
            },
            'ceiling_finishes': {
                'code': 'M20.3.1.1',
                'description': 'Ceiling finishes',
                'unit': 'm²'
            },
            'painting': {
                'code': 'M60.1.1.1',
                'description': 'Painting and decorating',
                'unit': 'm²'
            },
            'kitchen_fittings': {
                'code': 'N10.1.1.1',
                'description': 'Kitchen fittings and equipment',
                'unit': 'item'
            },
            'bathroom_fittings': {
                'code': 'N13.1.1.1',
                'description': 'Sanitary appliances',
                'unit': 'nr'
            },
            'sundries': {
                'code': 'P10.1.1.1',
                'description': 'Building fabric sundries',
                'unit': 'item'
            },
            'ironmongery': {
                'code': 'P20.1.1.1',
                'description': 'Door and window ironmongery',
                'unit': 'item'
            },
            'drainage': {
                'code': 'R10.1.1.1',
                'description': 'Sanitary fittings and fixtures',
                'unit': 'nr'
            },
            'waste_disposal': {
                'code': 'R11.1.1.1',
                'description': 'Waste disposal systems',
                'unit': 'm'
            },
            'water_supply': {
                'code': 'S10.1.1.1',
                'description': 'Water supply systems',
                'unit': 'm'
            },
            'gas_supply': {
                'code': 'S11.1.1.1',
                'description': 'Gas supply systems',
                'unit': 'm'
            },
            'heating': {
                'code': 'T10.1.1.1',
                'description': 'Heating systems',
                'unit': 'item'
            },
            'ventilation': {
                'code': 'T31.1.1.1',
                'description': 'Ventilation systems',
                'unit': 'item'
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
            },
            'lighting': {
                'code': 'V22.1.1.1',
                'description': 'Lighting fixtures',
                'unit': 'nr'
            },
            'electrical_panels': {
                'code': 'V10.1.1.1',
                'description': 'Electrical distribution boards',
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
