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
        """Generate BOQ items from processed drawing data - consolidates quantities from multiple drawings of same building"""
        rules = self.measurement_standards[standard]
        
        print(f"DEBUG: BOQ Generator processing {len(drawings_data)} drawings for same building")
        
        all_elements = []
        all_drawing_ids = []
        processed_drawings = set()
        
        for drawing_data in drawings_data:
            drawing_id = drawing_data.get('drawing_id')
            elements = drawing_data.get('elements', [])
            drawing_type = drawing_data.get('drawing_type')
            
            if drawing_id in processed_drawings:
                continue
            processed_drawings.add(drawing_id)
            
            if not drawing_type or drawing_type == 'unknown' or drawing_type == 'site':
                drawing_type = 'architectural'
            
            print(f"DEBUG: Collecting elements from drawing {drawing_id} ({drawing_type}) with {len(elements)} elements")
            
            for element in elements:
                element['source_drawing_type'] = drawing_type
                element['source_drawing_id'] = drawing_id
            
            all_elements.extend(elements)
            all_drawing_ids.append(drawing_id)
        
        print(f"DEBUG: Processing {len(all_elements)} total elements from {len(all_drawing_ids)} drawings as single building")
        
        representative_drawing_id = all_drawing_ids[0] if all_drawing_ids else "consolidated"
        
        boq_items = self._process_consolidated_building_elements(
            project_id, representative_drawing_id, all_elements, rules, "General"
        )
        
        print(f"DEBUG: Generated {len(boq_items)} consolidated BOQ items for single building")
        return boq_items

    def _process_consolidated_building_elements(self, project_id: str, drawing_id: str, 
                                             all_elements: List[Dict], rules: Dict, 
                                             building_type: str = "General") -> List[BOQItem]:
        """Process elements from multiple drawings as a single consolidated building"""
        
        all_lines = [e for e in all_elements if e.get('type') == 'line']
        all_circles = [e for e in all_elements if e.get('type') == 'circle']
        all_rectangles = [e for e in all_elements if e.get('type') == 'rectangle']
        all_polylines = [e for e in all_elements if e.get('type') == 'polyline']
        
        print(f"DEBUG: Consolidated elements - {len(all_lines)} lines, {len(all_circles)} circles, {len(all_rectangles)} rectangles, {len(all_polylines)} polylines")
        
        total_building_area = 0
        if all_rectangles:
            largest_rect = max(all_rectangles, key=lambda x: x.get('area', 0))
            total_building_area = largest_rect.get('area', 0) / 1000000
            print(f"DEBUG: Using largest rectangle from drawing {largest_rect.get('source_drawing_id', 'unknown')}")
        
        if total_building_area == 0:
            exterior_walls = [e for e in all_lines if e.get('length', 0) > 3000]
            if exterior_walls:
                total_perimeter = sum(wall.get('length', 0) for wall in exterior_walls) / 1000
                total_building_area = (total_perimeter / 4) ** 2
        
        if total_building_area == 0:
            total_building_area = 100
        
        print(f"DEBUG: Consolidated building area: {total_building_area}m²")
        
        return self._generate_building_boq_items(
            project_id, drawing_id, total_building_area, all_lines, all_circles, 
            all_rectangles, all_polylines, rules
        )

    def _process_architectural_elements(self, project_id: str, drawing_id: str, 
                                      elements: List[Dict], rules: Dict, 
                                      building_type: str = "General",
                                      room_types: Dict = None,
                                      wall_finishes: Dict = None) -> List[BOQItem]:
        """Process architectural elements into comprehensive SMM7 BOQ items"""
        
        all_lines = [e for e in elements if e.get('type') == 'line']
        all_circles = [e for e in elements if e.get('type') == 'circle']
        all_rectangles = [e for e in elements if e.get('type') == 'rectangle']
        all_polylines = [e for e in elements if e.get('type') == 'polyline']
        
        total_building_area = 0
        if all_rectangles:
            largest_rect = max(all_rectangles, key=lambda x: x.get('area', 0))
            total_building_area = largest_rect.get('area', 0) / 1000000
        elif all_lines:
            exterior_walls = [e for e in all_lines if e.get('length', 0) > 3000]
            if exterior_walls:
                total_perimeter = sum(wall.get('length', 0) for wall in exterior_walls) / 1000
                total_building_area = (total_perimeter / 4) ** 2
        
        if total_building_area == 0:
            total_building_area = 100
        
        return self._generate_building_boq_items(
            project_id, drawing_id, total_building_area, all_lines, all_circles,
            all_rectangles, all_polylines, rules
        )

    def _generate_building_boq_items(self, project_id: str, drawing_id: str, 
                                   total_building_area: float, all_lines: List[Dict],
                                   all_circles: List[Dict], all_rectangles: List[Dict],
                                   all_polylines: List[Dict], rules: Dict) -> List[BOQItem]:
        """Generate BOQ items for a single building using consolidated elements"""
        boq_items = []
        
        building_type = "General"
        building_config = self._get_building_type_config(building_type)
        room_types = {}
        wall_finishes = {}
        
        exterior_walls = [e for e in all_lines if e.get('length', 0) > 3000]
        interior_walls = [e for e in all_lines if 1000 < e.get('length', 0) <= 3000]
        partition_walls = [e for e in all_lines if 500 < e.get('length', 0) <= 1000]
        
        print(f"DEBUG: Estimated building area: {total_building_area}m²")
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="A1", description="Contractor's preliminaries, site establishment, welfare, scaffolding, insurances, H&S",
            unit="item", quantity=1,
            category="preliminaries", trade="general", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="A2", description="Temporary works (hoardings, fencing, signage)",
            unit="item", quantity=1,
            category="preliminaries", trade="general", measurement_standard=MeasurementStandard.SMM7
        ))
        
        site_area = total_building_area * 1.2
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="B1", description="Site clearance to footprint area",
            unit="m²", quantity=round(site_area, 2),
            category="substructure", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="B2", description="Topsoil strip 150mm",
            unit="m³", quantity=round(site_area * 0.15, 2),
            category="substructure", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="B3", description="Trench excavation for strip foundations",
            unit="m³", quantity=round(total_building_area * 0.45, 2),
            category="substructure", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="B4", description="Hardcore filling, compacted in layers",
            unit="m³", quantity=round(total_building_area * 0.6, 2),
            category="substructure", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="B5", description="Blinding concrete 100mm thick",
            unit="m²", quantity=round(total_building_area, 2),
            category="substructure", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="B6", description="Strip foundations 600 × 200mm in concrete",
            unit="m³", quantity=round(total_building_area * 0.09, 2),
            category="substructure", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        foundation_perimeter = 4 * (total_building_area ** 0.5)  # Perimeter of square building
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="B7", description="DPC – 300mm above ground level",
            unit="m", quantity=round(foundation_perimeter, 2),
            category="substructure", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="B8", description="Underground drainage including pipes, manholes, and connections",
            unit="m", quantity=round(foundation_perimeter * 0.7, 2),
            category="substructure", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        external_wall_area = foundation_perimeter * 2.7  # Assume 2.7m height
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C1.1", description="Facing brickwork 102.5mm thick to external walls",
            unit="m²", quantity=round(external_wall_area, 2),
            category="masonry", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C1.2", description="Blockwork 100mm thick to inner leaf of cavity wall",
            unit="m²", quantity=round(external_wall_area, 2),
            category="masonry", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C1.3", description="50mm cavity insulation",
            unit="m²", quantity=round(external_wall_area, 2),
            category="insulation", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        door_symbols = self._detect_door_symbols(all_lines, all_rectangles, all_circles)
        door_count = max(len(door_symbols), 3)  # Min 3 doors for residential
        window_count = max(len([e for e in all_rectangles if 1000000 <= e.get('area', 0) <= 4000000]), 8)  # Min 8 windows
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C1.4", description="Precast concrete lintels over openings",
            unit="m", quantity=round((door_count + window_count) * 1.2, 2),
            category="concrete", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C1.5", description="Precast concrete window cills 150 × 100mm",
            unit="m", quantity=round(window_count * 1.2, 2),
            category="concrete", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        opening_area = (door_count * 2.1 * 0.9) + (window_count * 1.5 * 1.2)  # Keep for calculations
        
        internal_wall_length = total_building_area * 0.6  # Estimate internal walls
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C2.1", description="100mm blockwork partitions",
            unit="m²", quantity=round(internal_wall_length * 2.7 * 0.6, 2),
            category="masonry", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C2.2", description="50mm timber stud partitions",
            unit="m²", quantity=round(internal_wall_length * 2.7 * 0.4, 2),
            category="partitions", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C3.1", description="Ground floor concrete slab 100mm thick",
            unit="m²", quantity=round(total_building_area, 2),
            category="concrete", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C3.2", description="Screed 50mm thick",
            unit="m²", quantity=round(total_building_area, 2),
            category="concrete", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        upper_floor_area = total_building_area * 0.5
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C3.3", description="First floor timber joists & decking",
            unit="m²", quantity=round(upper_floor_area, 2),
            category="timber", trade="joinery", measurement_standard=MeasurementStandard.SMM7
        ))
        
        roof_area = total_building_area * 1.3  # Include roof pitch
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C4.1", description="Treated softwood rafters 47 × 150mm @ 400mm centres",
            unit="m", quantity=round(roof_area * 2.5, 2),
            category="timber", trade="joinery", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C4.2", description="Roof battens 25 × 50mm",
            unit="m", quantity=round(roof_area * 1.8, 2),
            category="timber", trade="joinery", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C4.3", description="Roof covering: clay tiles incl. ridges & hips",
            unit="m²", quantity=round(roof_area, 2),
            category="roofing", trade="roofing", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C4.4", description="Fascias, soffits, bargeboards",
            unit="m", quantity=round(foundation_perimeter * 1.2, 2),
            category="timber", trade="joinery", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C4.5", description="Rainwater gutters & downpipes",
            unit="m", quantity=round(foundation_perimeter * 0.7, 2),
            category="drainage", trade="plumbing", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C5.1", description="External windows – frames & glazing",
            unit="no.", quantity=window_count,
            category="windows", trade="joinery", measurement_standard=MeasurementStandard.SMM7
        ))
        
        external_door_count = max(door_count // 3, 1)  # Assume 1/3 are external
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C5.2", description="External doors – frames & doorsets",
            unit="no.", quantity=external_door_count,
            category="doors", trade="joinery", measurement_standard=MeasurementStandard.SMM7
        ))
        
        internal_door_count = door_count - external_door_count
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="C5.3", description="Internal doors – frames & doorsets",
            unit="no.", quantity=internal_door_count,
            category="doors", trade="joinery", measurement_standard=MeasurementStandard.SMM7
        ))
        
        total_wall_area = external_wall_area + (internal_wall_length * 2.7 * 2)  # Both sides of internal walls
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="D1.1", description="13mm plaster to walls",
            unit="m²", quantity=round(total_wall_area * 0.8, 2),  # 80% of walls plastered
            category="finishes", trade="plastering", measurement_standard=MeasurementStandard.SMM7
        ))
        
        total_ceiling_area = total_building_area + upper_floor_area
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="D1.2", description="13mm plasterboard ceilings, skim finish",
            unit="m²", quantity=round(total_ceiling_area, 2),
            category="finishes", trade="plastering", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="D1.3", description="Emulsion paint finish to walls",
            unit="m²", quantity=round(total_wall_area * 0.8, 2),
            category="finishes", trade="painting", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="D1.4", description="Emulsion paint finish to ceilings",
            unit="m²", quantity=round(total_ceiling_area, 2),
            category="finishes", trade="painting", measurement_standard=MeasurementStandard.SMM7
        ))
        
        timber_area = (door_count * 4) + (foundation_perimeter * 0.3)  # Doors + skirtings
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="D1.5", description="Gloss paint to timber joinery (doors, skirtings)",
            unit="m²", quantity=round(timber_area, 2),
            category="finishes", trade="painting", measurement_standard=MeasurementStandard.SMM7
        ))
        
        kitchen_bathroom_area = total_building_area * 0.15  # 15% tiled areas
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="D2.1", description="Floor tiling (kitchen & bathroom)",
            unit="m²", quantity=round(kitchen_bathroom_area, 2),
            category="finishes", trade="tiling", measurement_standard=MeasurementStandard.SMM7
        ))
        
        living_area = total_building_area * 0.4  # 40% timber flooring
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="D2.2", description="Timber flooring – living areas",
            unit="m²", quantity=round(living_area, 2),
            category="finishes", trade="flooring", measurement_standard=MeasurementStandard.SMM7
        ))
        
        bedroom_area = total_building_area * 0.45  # 45% carpet
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="D2.3", description="Carpet – bedrooms",
            unit="m²", quantity=round(bedroom_area, 2),
            category="finishes", trade="flooring", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="E1", description="Kitchen units & worktops",
            unit="item", quantity=1,
            category="fittings", trade="joinery", measurement_standard=MeasurementStandard.SMM7
        ))
        
        bathroom_count = max(len([room for room in room_types.keys() if 'bathroom' in room.lower()]), 1)
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="E2", description="Bathroom sanitaryware (WC, basin, bath, taps)",
            unit="item", quantity=bathroom_count,
            category="fittings", trade="plumbing", measurement_standard=MeasurementStandard.SMM7
        ))
        
        bedroom_count = max(len([room for room in room_types.keys() if 'bedroom' in room.lower()]), 3)
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="E3", description="Wardrobes / built-in cupboards",
            unit="item", quantity=bedroom_count,
            category="fittings", trade="joinery", measurement_standard=MeasurementStandard.SMM7
        ))
        
        if upper_floor_area > 0:  # Only if two-storey
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="E4", description="Staircase & balustrade",
                unit="item", quantity=1,
                category="fittings", trade="joinery", measurement_standard=MeasurementStandard.SMM7
            ))
        
        pipe_length = total_building_area * 0.5  # Estimate pipe runs
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="F1.1", description="Cold water supply, hot water pipework",
            unit="m", quantity=round(pipe_length, 2),
            category="plumbing", trade="plumbing", measurement_standard=MeasurementStandard.SMM7
        ))
        
        waste_pipe_length = total_building_area * 0.3
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="F1.2", description="Waste & soil pipes",
            unit="m", quantity=round(waste_pipe_length, 2),
            category="plumbing", trade="plumbing", measurement_standard=MeasurementStandard.SMM7
        ))
        
        radiator_count = max(bedroom_count + 2, 6)  # Bedrooms + living areas
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="F1.3", description="Radiators incl. valves & connections",
            unit="no.", quantity=radiator_count,
            category="heating", trade="plumbing", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="F1.4", description="Boiler & associated pipework",
            unit="item", quantity=1,
            category="heating", trade="plumbing", measurement_standard=MeasurementStandard.SMM7
        ))
        
        socket_count = building_config.get('sockets_per_house', 25)
        light_count = max(bedroom_count + 4, 10)  # Bedrooms + living areas + kitchen + bathrooms
        switch_count = light_count  # One switch per light fitting typically
        wiring_length = total_building_area * 0.8  # Estimate wiring length based on building area
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="F2.1", description="LED ceiling light fittings, supply and fix complete",
            unit="no.", quantity=light_count,
            category="electrical", trade="electrical", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="F2.2", description="Socket outlets 13A, supply and fix complete",
            unit="no.", quantity=socket_count,
            category="electrical", trade="electrical", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="F2.3", description="Light switches single pole, supply and fix complete",
            unit="no.", quantity=switch_count,
            category="electrical", trade="electrical", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="F2.4", description="2.5mm² PVC insulated copper cable in conduit",
            unit="m", quantity=round(wiring_length, 2),
            category="electrical", trade="electrical", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="F2.5", description="Consumer unit and distribution board",
            unit="item", quantity=1,
            category="electrical", trade="electrical", measurement_standard=MeasurementStandard.SMM7
        ))
        
        smoke_alarm_count = max(bedroom_count + 2, 5)  # Bedrooms + hallways + living
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="F2.6", description="Smoke alarms",
            unit="no.", quantity=smoke_alarm_count,
            category="electrical", trade="electrical", measurement_standard=MeasurementStandard.SMM7
        ))
        
        path_area = total_building_area * 0.4  # Paths and patios
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="G1", description="Paths & patios – concrete",
            unit="m²", quantity=round(path_area, 2),
            category="external", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        driveway_area = total_building_area * 0.25  # Driveway
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="G2", description="Driveway – block paving",
            unit="m²", quantity=round(driveway_area, 2),
            category="external", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        fencing_length = foundation_perimeter * 0.6  # 60% of perimeter fenced
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="G3", description="Fencing & gates",
            unit="m", quantity=round(fencing_length, 2),
            category="external", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        garden_area = site_area - total_building_area - path_area - driveway_area
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="G4", description="Soft landscaping – turf, planting",
            unit="m²", quantity=round(max(garden_area, 0), 2),
            category="external", trade="landscaping", measurement_standard=MeasurementStandard.SMM7
        ))
        
        boq_items.append(BOQItem(
            project_id=project_id, drawing_id=drawing_id,
            item_code="G5", description="External drainage connections",
            unit="m", quantity=round(foundation_perimeter * 0.3, 2),
            category="external", trade="civil", measurement_standard=MeasurementStandard.SMM7
        ))
        
        print(f"DEBUG: Generated {len(boq_items)} comprehensive SMM7 BOQ items")
        return boq_items
        
        # Bathroom fixture detection based on room types and small circles
        bathroom_fixtures = []
        if "Bathroom" in room_types:
            small_circles = [c for c in all_circles if 5 <= c.get('radius', 0) <= 15]
            bathroom_fixtures.extend(small_circles)
        
        if bathroom_fixtures:
            fixture_count = max(len(bathroom_fixtures), len(room_types.get("Bathroom", [])) * 3)
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="N13.1.1.1", description="Sanitary appliances and fittings",
                unit="nr", quantity=fixture_count,
                category="plumbing", trade="plumbing", measurement_standard=MeasurementStandard.SMM7
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
        
        large_areas = [e for e in (all_rectangles + all_polylines) if e.get('area', 0) > 50000000]  # Very large areas (>50m²)
        medium_areas = [e for e in (all_rectangles + all_polylines) if 10000000 <= e.get('area', 0) <= 50000000]  # Medium areas (10-50m²)
        
        if large_areas or medium_areas:
            total_building_area = sum(area.get('area', 0) for area in (large_areas + medium_areas)) / 1000000
            excavation_volume = total_building_area * 0.5  # Assume 0.5m depth
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="D20.1.1.1", description="Excavation for foundations",
                unit="m³", quantity=round(excavation_volume, 2),
                category="excavation", trade="civil", measurement_standard=MeasurementStandard.SMM7
            ))
        
        if wall_finishes:
            total_external_wall_area = sum(wall.get('length', 0) for wall in exterior_walls) / 1000 * 2.7
            
            if "Render" in wall_finishes:
                render_area = total_external_wall_area * 0.6  # Assume 60% render
                boq_items.append(BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="M20.2.2.1", description="External wall render finish",
                    unit="m²", quantity=round(render_area, 2),
                    category="finishes", trade="civil", measurement_standard=MeasurementStandard.SMM7
                ))
            
            if "Stone" in wall_finishes:
                stone_area = total_external_wall_area * 0.4  # Assume 40% stone
                boq_items.append(BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="F30.1.1.1", description="Natural stone cladding",
                    unit="m²", quantity=round(stone_area, 2),
                    category="finishes", trade="masonry", measurement_standard=MeasurementStandard.SMM7
                ))
        
        window_symbols = []
        for rect in all_rectangles:
            area = rect.get('area', 0)
            if 1000000 <= area <= 4000000:  # 1-4m² in mm²
                window_symbols.append(rect)
        
        if window_symbols:
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="L10.2.1.1", description="Windows and frames",
                unit="nr", quantity=len(window_symbols),
                category="windows", trade="joinery", measurement_standard=MeasurementStandard.SMM7
            ))
        
        bathroom_fixtures = []
        if "Bathroom" in room_types:
            small_circles = [c for c in all_circles if 5 <= c.get('radius', 0) <= 15]
            bathroom_fixtures.extend(small_circles)
        
        if bathroom_fixtures:
            fixture_count = max(len(bathroom_fixtures), len(room_types.get("Bathroom", [])) * 3)
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="N13.1.1.1", description="Sanitary appliances and fittings",
                unit="nr", quantity=fixture_count,
                category="plumbing", trade="plumbing", measurement_standard=MeasurementStandard.SMM7
            ))
        
        if wall_finishes:
            total_external_wall_area = sum(wall.get('length', 0) for wall in exterior_walls) / 1000 * 2.7
            
            if "Render" in wall_finishes:
                render_area = total_external_wall_area * 0.6  # Assume 60% render
                boq_items.append(BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="M20.2.2.1", description="External wall render finish",
                    unit="m²", quantity=round(render_area, 2),
                    category="finishes", trade="civil", measurement_standard=MeasurementStandard.SMM7
                ))
            
            if "Stone" in wall_finishes:
                stone_area = total_external_wall_area * 0.4  # Assume 40% stone
                boq_items.append(BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="F30.1.1.1", description="Natural stone cladding",
                    unit="m²", quantity=round(stone_area, 2),
                    category="finishes", trade="masonry", measurement_standard=MeasurementStandard.SMM7
                ))
        
        if room_types:
            for room_type, _ in room_types.items():
                if room_type == "Kitchen":
                    boq_items.append(BOQItem(
                        project_id=project_id, drawing_id=drawing_id,
                        item_code="N10.1.1.1", description="Kitchen fittings and equipment",
                        unit="item", quantity=1,
                        category="fittings", trade="joinery", measurement_standard=MeasurementStandard.SMM7
                    ))
                elif room_type == "Bathroom":
                    boq_items.append(BOQItem(
                        project_id=project_id, drawing_id=drawing_id,
                        item_code="M40.1.1.1", description="Ceramic wall tiling to bathrooms",
                        unit="m²", quantity=20,  # Typical bathroom tiling
                        category="finishes", trade="tiling", measurement_standard=MeasurementStandard.SMM7
                    ))
        
        total_building_area = 0
        if all_rectangles:
            largest_rect = max(all_rectangles, key=lambda r: r.get('area', 0))
            total_building_area = largest_rect.get('area', 0) / 1000000  # Convert mm² to m²
        
        if total_building_area == 0 and exterior_walls:
            perimeter = sum(wall.get('length', 0) for wall in exterior_walls) / 1000  # Convert to meters
            total_building_area = (perimeter / 4) ** 2
        
        if total_building_area > 0:
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="D20.1.1.1", description="Excavation for foundations",
                unit="m³", quantity=round(total_building_area * 0.6, 2),
                category="excavation", trade="civil", measurement_standard=MeasurementStandard.SMM7
            ))
            
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="E10.1.1.1", description="Concrete foundations",
                unit="m³", quantity=round(total_building_area * 0.4, 2),
                category="concrete", trade="structural", measurement_standard=MeasurementStandard.SMM7
            ))
            
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="J40.1.1.1", description="Damp proof course",
                unit="m²", quantity=round(total_building_area * 0.8, 2),
                category="waterproofing", trade="civil", measurement_standard=MeasurementStandard.SMM7
            ))
        
        if exterior_walls:
            total_wall_length = sum(wall.get('length', 0) for wall in exterior_walls) / 1000
            wall_area = total_wall_length * 2.7
            
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="F10.1.1.1", description="External brick/block walling",
                unit="m²", quantity=round(wall_area, 2),
                category="masonry", trade="masonry", measurement_standard=MeasurementStandard.SMM7
            ))
            
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="F10.2.1.1", description="Internal brick/block walling",
                unit="m²", quantity=round(wall_area * 0.6, 2),
                category="masonry", trade="masonry", measurement_standard=MeasurementStandard.SMM7
            ))
        
        if total_building_area > 0:
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="G20.1.1.1", description="Timber roof structure",
                unit="m²", quantity=round(total_building_area * 1.2, 2),
                category="roofing", trade="carpentry", measurement_standard=MeasurementStandard.SMM7
            ))
            
            boq_items.append(BOQItem(
                project_id=project_id, drawing_id=drawing_id,
                item_code="H60.1.1.1", description="Roof covering and structure",
                unit="m²", quantity=round(total_building_area * 1.2, 2),
                category="roofing", trade="roofing", measurement_standard=MeasurementStandard.SMM7
            ))
        
        if wall_finishes:
            total_external_wall_area = sum(wall.get('length', 0) for wall in exterior_walls) / 1000 * 2.7
            
            if "Render" in wall_finishes:
                render_area = total_external_wall_area * 0.6
                boq_items.append(BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="M20.2.2.1", description="External wall render finish",
                    unit="m²", quantity=round(render_area, 2),
                    category="finishes", trade="civil", measurement_standard=MeasurementStandard.SMM7
                ))
            
            if "Stone" in wall_finishes:
                stone_area = total_external_wall_area * 0.4
                boq_items.append(BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="F30.1.1.1", description="Natural stone cladding",
                    unit="m²", quantity=round(stone_area, 2),
                    category="finishes", trade="masonry", measurement_standard=MeasurementStandard.SMM7
                ))
        
        if room_types:
            for room_type, _ in room_types.items():
                if room_type == "Kitchen":
                    boq_items.extend([
                        BOQItem(
                            project_id=project_id, drawing_id=drawing_id,
                            item_code="N10.1.1.1", description="Kitchen fittings and equipment",
                            unit="item", quantity=1,
                            category="fittings", trade="joinery", measurement_standard=MeasurementStandard.SMM7
                        ),
                        BOQItem(
                            project_id=project_id, drawing_id=drawing_id,
                            item_code="M40.2.1.1", description="Ceramic floor tiling to kitchen",
                            unit="m²", quantity=15,
                            category="finishes", trade="tiling", measurement_standard=MeasurementStandard.SMM7
                        ),
                        BOQItem(
                            project_id=project_id, drawing_id=drawing_id,
                            item_code="M40.1.2.1", description="Ceramic wall tiling to kitchen",
                            unit="m²", quantity=25,
                            category="finishes", trade="tiling", measurement_standard=MeasurementStandard.SMM7
                        )
                    ])
                elif room_type == "Bathroom":
                    boq_items.extend([
                        BOQItem(
                            project_id=project_id, drawing_id=drawing_id,
                            item_code="M40.1.1.1", description="Ceramic wall tiling to bathrooms",
                            unit="m²", quantity=20,
                            category="finishes", trade="tiling", measurement_standard=MeasurementStandard.SMM7
                        ),
                        BOQItem(
                            project_id=project_id, drawing_id=drawing_id,
                            item_code="M40.2.2.1", description="Ceramic floor tiling to bathrooms",
                            unit="m²", quantity=6,
                            category="finishes", trade="tiling", measurement_standard=MeasurementStandard.SMM7
                        ),
                        BOQItem(
                            project_id=project_id, drawing_id=drawing_id,
                            item_code="R10.1.1.1", description="Sanitary fittings and fixtures",
                            unit="nr", quantity=3,
                            category="plumbing", trade="plumbing", measurement_standard=MeasurementStandard.SMM7
                        )
                    ])
                elif room_type == "Living Room":
                    boq_items.append(BOQItem(
                        project_id=project_id, drawing_id=drawing_id,
                        item_code="M20.1.2.1", description="Carpet flooring to living areas",
                        unit="m²", quantity=25,
                        category="finishes", trade="flooring", measurement_standard=MeasurementStandard.SMM7
                    ))
                elif room_type == "Bedroom":
                    boq_items.append(BOQItem(
                        project_id=project_id, drawing_id=drawing_id,
                        item_code="M20.1.3.1", description="Carpet flooring to bedrooms",
                        unit="m²", quantity=12,
                        category="finishes", trade="flooring", measurement_standard=MeasurementStandard.SMM7
                    ))
        
        if total_building_area > 0:
            boq_items.extend([
                BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="V20.1.1.1", description="PVC conduit installation",
                    unit="m", quantity=round(total_building_area * 2, 2),
                    category="electrical", trade="electrical", measurement_standard=MeasurementStandard.SMM7
                ),
                BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="V21.2.1.1", description="Light switches",
                    unit="nr", quantity=15,
                    category="electrical", trade="electrical", measurement_standard=MeasurementStandard.SMM7
                ),
                BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="V22.1.1.1", description="Lighting fixtures",
                    unit="nr", quantity=20,
                    category="electrical", trade="electrical", measurement_standard=MeasurementStandard.SMM7
                ),
                BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="V10.1.1.1", description="Consumer unit and distribution board",
                    unit="nr", quantity=1,
                    category="electrical", trade="electrical", measurement_standard=MeasurementStandard.SMM7
                )
            ])
        
        if total_building_area > 0:
            boq_items.extend([
                BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="S10.1.1.1", description="Water supply systems",
                    unit="m", quantity=round(total_building_area * 1.5, 2),
                    category="plumbing", trade="plumbing", measurement_standard=MeasurementStandard.SMM7
                ),
                BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="T10.1.1.1", description="Central heating system",
                    unit="item", quantity=1,
                    category="heating", trade="mechanical", measurement_standard=MeasurementStandard.SMM7
                ),
                BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="T31.1.1.1", description="Radiators",
                    unit="nr", quantity=8,
                    category="heating", trade="mechanical", measurement_standard=MeasurementStandard.SMM7
                )
            ])
        
        door_symbols = self._detect_door_symbols(all_lines, all_rectangles, all_circles)
        
        external_doors = []
        internal_doors = []
        for door in door_symbols:
            is_external = self._is_door_external(door, exterior_walls)
            if is_external:
                external_doors.append(door)
            else:
                internal_doors.append(door)
        
        if len(external_doors) == 0:
            external_doors = [{'length': 800, 'type': 'external_door'}]  # Default external door
        if len(internal_doors) < 2:
            internal_doors = [{'length': 750, 'type': 'internal_door'} for _ in range(max(2, 3 - len(internal_doors)))]  # Default internal doors
        
        if external_doors or internal_doors:
            boq_items.extend([
                BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="P20.1.1.1", description="Door furniture and ironmongery",
                    unit="set", quantity=len(external_doors) + len(internal_doors),
                    category="ironmongery", trade="joinery", measurement_standard=MeasurementStandard.SMM7
                ),
                BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="L20.1.1.1", description="Stairs and balustrades",
                    unit="nr", quantity=1 if building_type == "Type A" else 0,
                    category="joinery", trade="joinery", measurement_standard=MeasurementStandard.SMM7
                )
            ])
        
        if total_building_area > 0:
            boq_items.extend([
                BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="P10.1.1.1", description="Wall insulation",
                    unit="m²", quantity=round(total_building_area * 2, 2),
                    category="insulation", trade="insulation", measurement_standard=MeasurementStandard.SMM7
                ),
                BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="P10.2.1.1", description="Roof insulation",
                    unit="m²", quantity=round(total_building_area * 1.2, 2),
                    category="insulation", trade="insulation", measurement_standard=MeasurementStandard.SMM7
                )
            ])
        
        if total_building_area > 0:
            boq_items.extend([
                BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="R12.1.1.1", description="Soil and waste drainage",
                    unit="m", quantity=round(total_building_area * 0.8, 2),
                    category="drainage", trade="drainage", measurement_standard=MeasurementStandard.SMM7
                ),
                BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="R13.1.1.1", description="Land drainage",
                    unit="m", quantity=round(total_building_area * 0.6, 2),
                    category="drainage", trade="drainage", measurement_standard=MeasurementStandard.SMM7
                )
            ])
        
        if total_building_area > 0:
            boq_items.extend([
                BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="M60.1.1.1", description="Painting to internal walls",
                    unit="m²", quantity=round(total_building_area * 3, 2),
                    category="decoration", trade="decoration", measurement_standard=MeasurementStandard.SMM7
                ),
                BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="M60.2.1.1", description="Painting to external walls",
                    unit="m²", quantity=round(total_building_area * 1.5, 2),
                    category="decoration", trade="decoration", measurement_standard=MeasurementStandard.SMM7
                ),
                BOQItem(
                    project_id=project_id, drawing_id=drawing_id,
                    item_code="M60.3.1.1", description="Painting to ceilings",
                    unit="m²", quantity=round(total_building_area, 2),
                    category="decoration", trade="decoration", measurement_standard=MeasurementStandard.SMM7
                )
            ])
        
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
                "sockets_per_house": 25,
                "description": "Two-storey house with ground and first floor",
                "floor_types": ["Ground Floor", "First Floor"]
            },
            "Type B": {
                "socket_multiplier": 1.0,
                "area_multiplier": 1.2,
                "complexity_factor": 1.1,
                "typical_floors": 1,
                "sockets_per_house": 20,
                "description": "Single-storey bungalow",
                "floor_types": ["Bungalow"]
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
    
    def _detect_door_symbols(self, all_lines: List[Dict], all_rectangles: List[Dict], all_circles: List[Dict]) -> List[Dict]:
        """
        Detect actual door symbols using architectural symbol recognition
        instead of counting arbitrary lines between 700-1000 pixels
        """
        door_symbols = []
        
        door_arcs = []
        for circle in all_circles:
            radius = circle.get('radius', 0)
            if 400 <= radius <= 800:
                door_arcs.append(circle)
        
        potential_doors = []
        for line in all_lines:
            length = line.get('length', 0)
            if 500 <= length <= 1200:
                start = line.get('start', (0, 0))
                end = line.get('end', (0, 0))
                
                has_frame_context = self._has_door_frame_context(line, all_lines)
                
                has_swing_arc = self._has_nearby_door_swing(line, door_arcs)
                
                if has_frame_context or has_swing_arc:
                    potential_doors.append(line)
        
        # For residential buildings, use conservative estimates based on building area
        # This prevents over-counting while the symbol recognition is being refined
        building_area = getattr(self, '_current_building_area', 150)  # Default 150 sqm
        
        if building_area <= 200:  # Small residential
            estimated_external = max(int(building_area / 50), 1)
            estimated_internal = max(int(building_area / 15), 3)
            total_estimated = estimated_external + estimated_internal
            
            door_count = min(len(potential_doors), total_estimated)
            
            for i in range(door_count):
                door_symbols.append({
                    'type': 'door_symbol',
                    'length': 800,  # Standard door width
                    'confidence': 'estimated',
                    'method': 'conservative_residential'
                })
        
        else:  # Larger buildings - use detected symbols with validation
            door_symbols = potential_doors[:min(len(potential_doors), int(building_area / 10))]
        
        return door_symbols
    
    def _has_door_frame_context(self, door_line: Dict, all_lines: List[Dict]) -> bool:
        """Check if a line has door frame context (perpendicular lines at ends)"""
        start = door_line.get('start', (0, 0))
        end = door_line.get('end', (0, 0))
        tolerance = 50  # Pixel tolerance for frame detection
        
        frame_lines = 0
        for line in all_lines:
            line_start = line.get('start', (0, 0))
            line_end = line.get('end', (0, 0))
            
            if (abs(line_start[0] - start[0]) < tolerance and abs(line_start[1] - start[1]) < tolerance) or \
               (abs(line_start[0] - end[0]) < tolerance and abs(line_start[1] - end[1]) < tolerance):
                frame_lines += 1
        
        return frame_lines >= 1  # At least one frame line
    
    def _has_nearby_door_swing(self, door_line: Dict, door_arcs: List[Dict]) -> bool:
        """Check if there's a door swing arc near the door opening"""
        start = door_line.get('start', (0, 0))
        end = door_line.get('end', (0, 0))
        door_center = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        
        for arc in door_arcs:
            arc_center = arc.get('center', (0, 0))
            distance = ((door_center[0] - arc_center[0])**2 + (door_center[1] - arc_center[1])**2)**0.5
            
            if distance < 200:  # Within 200 pixels
                return True
        
        return False
    
    def _is_door_external(self, door: Dict, exterior_walls: List[Dict]) -> bool:
        """Determine if a door is external based on proximity to exterior walls"""
        door_center = self._get_line_center(door)
        
        for wall in exterior_walls:
            wall_center = self._get_line_center(wall)
            distance = np.sqrt((door_center[0] - wall_center[0])**2 + 
                             (door_center[1] - wall_center[1])**2)
            if distance < 100:  # Within 100 pixels of exterior wall
                return True
        return False
    
    def _get_line_center(self, line: Dict) -> tuple:
        """Get the center point of a line"""
        start = line.get('start', (0, 0))
        end = line.get('end', (0, 0))
        return ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    
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
        """RICS NRM measurement rules and item codes - comprehensive NRM 2 Building Works"""
        return {
            'site_preparation': {'code': '1.1.1', 'description': 'Site preparation and clearance', 'unit': 'm²'},
            'temporary_works': {'code': '1.2.1', 'description': 'Temporary works and site establishment', 'unit': 'item'},
            'site_accommodation': {'code': '1.3.1', 'description': 'Site accommodation and welfare', 'unit': 'item'},
            
            'excavation': {'code': '2.1.1', 'description': 'Excavation and earthworks', 'unit': 'm³'},
            'foundations': {'code': '2.2.1', 'description': 'Foundation systems', 'unit': 'm³'},
            'basement_works': {'code': '2.3.1', 'description': 'Basement construction', 'unit': 'm³'},
            'ground_floors': {'code': '2.4.1', 'description': 'Ground floor construction', 'unit': 'm²'},
            
            'frame': {'code': '3.1.1', 'description': 'Structural frame', 'unit': 'm³'},
            'upper_floors': {'code': '3.2.1', 'description': 'Upper floor construction', 'unit': 'm²'},
            'roof': {'code': '3.3.1', 'description': 'Roof construction', 'unit': 'm²'},
            'stairs': {'code': '3.4.1', 'description': 'Stair construction', 'unit': 'nr'},
            'external_walls': {'code': '3.5.1', 'description': 'External walls', 'unit': 'm²'},
            'windows_external_doors': {'code': '3.6.1', 'description': 'Windows and external doors', 'unit': 'nr'},
            'internal_walls_partitions': {'code': '3.7.1', 'description': 'Internal walls and partitions', 'unit': 'm²'},
            'internal_doors': {'code': '3.8.1', 'description': 'Internal doors', 'unit': 'nr'},
            
            'wall_finishes': {'code': '4.1.1', 'description': 'Internal wall finishes', 'unit': 'm²'},
            'floor_finishes': {'code': '4.2.1', 'description': 'Internal floor finishes', 'unit': 'm²'},
            'ceiling_finishes': {'code': '4.3.1', 'description': 'Internal ceiling finishes', 'unit': 'm²'},
            'fittings_furnishings': {'code': '4.4.1', 'description': 'Fittings and furnishings', 'unit': 'item'},
            
            'sanitary_appliances': {'code': '5.1.1', 'description': 'Sanitary appliances', 'unit': 'nr'},
            'services_equipment': {'code': '5.2.1', 'description': 'Services equipment', 'unit': 'item'},
            'disposal_installations': {'code': '5.3.1', 'description': 'Disposal installations', 'unit': 'm'},
            'water_installations': {'code': '5.4.1', 'description': 'Water installations', 'unit': 'm'},
            'heat_source': {'code': '5.5.1', 'description': 'Heat source', 'unit': 'item'},
            'space_heating_cooling': {'code': '5.6.1', 'description': 'Space heating and cooling', 'unit': 'item'},
            'ventilation': {'code': '5.7.1', 'description': 'Ventilation systems', 'unit': 'item'},
            'electrical_installations': {'code': '5.8.1', 'description': 'Electrical installations', 'unit': 'nr'},
            'fuel_installations': {'code': '5.9.1', 'description': 'Fuel installations', 'unit': 'm'},
            'lift_installations': {'code': '5.10.1', 'description': 'Lift and conveyor installations', 'unit': 'nr'},
            'fire_safety': {'code': '5.11.1', 'description': 'Fire and lightning protection', 'unit': 'item'},
            'communication_security': {'code': '5.12.1', 'description': 'Communication and security systems', 'unit': 'item'},
            'special_installations': {'code': '5.13.1', 'description': 'Special installations', 'unit': 'item'},
            'builder_work_services': {'code': '5.14.1', 'description': 'Builder work in connection with services', 'unit': 'item'},
            
            'prefabricated_buildings': {'code': '6.1.1', 'description': 'Prefabricated buildings', 'unit': 'item'},
            
            'minor_demolition': {'code': '7.1.1', 'description': 'Minor demolition works', 'unit': 'm³'},
            'repairs_cleaning': {'code': '7.2.1', 'description': 'Repairs and cleaning', 'unit': 'm²'},
            'renovation_works': {'code': '7.3.1', 'description': 'Renovation works', 'unit': 'item'},
            
            'site_works': {'code': '8.1.1', 'description': 'Site works', 'unit': 'm²'},
            'roads_paths': {'code': '8.2.1', 'description': 'Roads, paths and pavings', 'unit': 'm²'},
            'soft_landscaping': {'code': '8.3.1', 'description': 'Soft landscaping', 'unit': 'm²'},
            'fencing_gates': {'code': '8.4.1', 'description': 'Fencing and gates', 'unit': 'm'},
            'external_fixtures': {'code': '8.5.1', 'description': 'External fixtures', 'unit': 'nr'},
            'drainage': {'code': '8.6.1', 'description': 'Drainage', 'unit': 'm'},
            'external_services': {'code': '8.7.1', 'description': 'External services', 'unit': 'm'},
            'minor_building_works': {'code': '8.8.1', 'description': 'Minor building works', 'unit': 'item'}
        }

    def _get_cesmm_rules(self) -> Dict[str, Any]:
        """CESMM measurement rules and item codes - comprehensive CESMM4 work classes"""
        return {
            'general_items': {'code': 'A1.1.1.1', 'description': 'General items', 'unit': 'item'},
            'method_related_charges': {'code': 'A2.1.1.1', 'description': 'Method-related charges', 'unit': 'item'},
            
            'demolition': {'code': 'D1.1.1.1', 'description': 'Demolition of structures', 'unit': 'm³'},
            'site_clearance': {'code': 'D2.1.1.1', 'description': 'Site clearance', 'unit': 'm²'},
            
            'excavation': {'code': 'E1.1.1.1', 'description': 'General excavation', 'unit': 'm³'},
            'filling': {'code': 'E2.1.1.1', 'description': 'Filling and compaction', 'unit': 'm³'},
            'landscaping': {'code': 'E3.1.1.1', 'description': 'Landscaping', 'unit': 'm²'},
            
            'foundations': {'code': 'F1.1.1.1', 'description': 'Concrete foundations', 'unit': 'm³'},
            'slabs': {'code': 'F2.1.1.1', 'description': 'Concrete slabs', 'unit': 'm³'},
            'walls': {'code': 'F3.1.1.1', 'description': 'Concrete walls', 'unit': 'm³'},
            'columns': {'code': 'F4.1.1.1', 'description': 'Concrete columns', 'unit': 'm³'},
            'beams': {'code': 'F5.1.1.1', 'description': 'Concrete beams', 'unit': 'm³'},
            
            'formwork': {'code': 'G1.1.1.1', 'description': 'Formwork', 'unit': 'm²'},
            'reinforcement': {'code': 'G2.1.1.1', 'description': 'Reinforcement', 'unit': 't'},
            'joints': {'code': 'G3.1.1.1', 'description': 'Joints in concrete', 'unit': 'm'},
            
            'precast_units': {'code': 'H1.1.1.1', 'description': 'Precast concrete units', 'unit': 'nr'},
            'composite_construction': {'code': 'H2.1.1.1', 'description': 'Composite construction', 'unit': 'm²'},
            
            'pipes_concrete': {'code': 'I1.1.1.1', 'description': 'Concrete pipes', 'unit': 'm'},
            'pipes_clay': {'code': 'I2.1.1.1', 'description': 'Clay pipes', 'unit': 'm'},
            'pipes_plastic': {'code': 'I3.1.1.1', 'description': 'Plastic pipes', 'unit': 'm'},
            'pipes_metal': {'code': 'I4.1.1.1', 'description': 'Metal pipes', 'unit': 'm'},
            
            'pipe_fittings': {'code': 'J1.1.1.1', 'description': 'Pipe fittings and valves', 'unit': 'nr'},
            'pipe_ancillaries': {'code': 'J2.1.1.1', 'description': 'Pipe ancillaries', 'unit': 'nr'},
            
            'manholes': {'code': 'K1.1.1.1', 'description': 'Manholes and chambers', 'unit': 'nr'},
            'inspection_chambers': {'code': 'K2.1.1.1', 'description': 'Inspection chambers', 'unit': 'nr'},
            
            'steel_framing': {'code': 'M1.1.1.1', 'description': 'Steel framing', 'unit': 't'},
            'metal_decking': {'code': 'M2.1.1.1', 'description': 'Metal decking', 'unit': 'm²'},
            
            'metalwork_general': {'code': 'N1.1.1.1', 'description': 'General metalwork', 'unit': 't'},
            'fencing_metalwork': {'code': 'N2.1.1.1', 'description': 'Fencing and gates', 'unit': 'm'},
            
            'structural_timber': {'code': 'O1.1.1.1', 'description': 'Structural timber', 'unit': 'm³'},
            'timber_boarding': {'code': 'O2.1.1.1', 'description': 'Timber boarding', 'unit': 'm²'},
            
            'road_pavements': {'code': 'R1.1.1.1', 'description': 'Road pavements', 'unit': 'm²'},
            'footways': {'code': 'R2.1.1.1', 'description': 'Footways and cycleways', 'unit': 'm²'},
            'road_markings': {'code': 'R3.1.1.1', 'description': 'Road markings and signs', 'unit': 'nr'},
            
            'brickwork': {'code': 'U1.1.1.1', 'description': 'Brickwork construction', 'unit': 'm²'},
            'blockwork': {'code': 'U2.1.1.1', 'description': 'Blockwork construction', 'unit': 'm²'},
            'stone_masonry': {'code': 'U3.1.1.1', 'description': 'Stone masonry', 'unit': 'm²'},
            
            'surface_treatments': {'code': 'V1.1.1.1', 'description': 'Surface treatments', 'unit': 'm²'},
            'painting_decoration': {'code': 'V2.1.1.1', 'description': 'Painting and decoration', 'unit': 'm²'},
            
            'waterproof_membranes': {'code': 'W1.1.1.1', 'description': 'Waterproof membranes', 'unit': 'm²'},
            'joint_sealants': {'code': 'W2.1.1.1', 'description': 'Joint sealants', 'unit': 'm'},
            
            'sundry_items': {'code': 'X1.1.1.1', 'description': 'Sundry items', 'unit': 'item'},
            'testing_commissioning': {'code': 'X2.1.1.1', 'description': 'Testing and commissioning', 'unit': 'item'},
            
            'building_fabric': {'code': 'Z1.1.1.1', 'description': 'Building fabric', 'unit': 'm²'},
            'building_services': {'code': 'Z2.1.1.1', 'description': 'Building services', 'unit': 'item'}
        }
