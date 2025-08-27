from typing import List, Dict, Any, Optional, Tuple
from ..models import BOQItem, MeasurementStandard
import math

class RoomQuantityCalculator:
    """
    Calculate room-based quantity breakdowns for BOQ verification
    """
    
    def __init__(self):
        self.room_breakdown_categories = {
            'walls', 'floors', 'ceilings', 'finishes', 'electrical', 
            'plumbing', 'flooring', 'painting', 'plastering'
        }
        self.min_deduction_area = 0.5
        
    def calculate_room_based_quantities(self, boq_items: List[BOQItem], 
                                      room_data: Dict[str, Any],
                                      elements: List[Dict]) -> Dict[str, Any]:
        """
        Calculate room-by-room quantity breakdowns for verification
        """
        takeoff_data = {}
        
        standard_rooms = [
            'Living Room', 'Kitchen', 'Dining Room', 'WC', 'Hall + Stairs',
            'Bedroom 1', 'Bedroom 2', 'Bedroom 3', 'Bathroom', 'Landing', 'Utility Room'
        ]
        
        for item in boq_items:
            if self._should_have_room_breakdown(item):
                room_breakdown = self._calculate_item_room_breakdown(
                    item, room_data, elements, standard_rooms
                )
                if room_breakdown:
                    takeoff_data[item.item_code] = {
                        'description': item.description,
                        'unit': item.unit,
                        'total_quantity': item.quantity,
                        'room_breakdown': room_breakdown
                    }
                    
        return takeoff_data
        
    def _should_have_room_breakdown(self, item: BOQItem) -> bool:
        """Determine if BOQ item should have room-based breakdown"""
        if 'internal door' in item.description.lower() or 'door' in item.description.lower():
            return False
            
        return (item.category.lower() in self.room_breakdown_categories or
                any(keyword in item.description.lower() for keyword in [
                    'skirting', 'flooring', 'carpet', 'tiles', 'paint', 'plaster',
                    'socket', 'light', 'ceiling', 'wall finish'
                ]))
                
    def _calculate_item_room_breakdown(self, item: BOQItem, room_data: Dict[str, Any],
                                     elements: List[Dict], standard_rooms: List[str]) -> List[Dict]:
        """Calculate room-specific quantities for a BOQ item"""
        room_breakdown = []
        
        room_areas = self._estimate_room_areas(room_data, elements)
        
        if not room_areas:
            return []
            
        total_estimated_area = sum(room_areas.values())
        
        for room_name in standard_rooms:
            if room_name in room_areas:
                room_area = room_areas[room_name]
                
                room_quantity = self._calculate_room_quantity(
                    item, room_area, total_estimated_area, room_name, elements
                )
                
                if room_quantity > 0:
                    room_breakdown.append({
                        'ref': f"{len(room_breakdown) + 1}.{len(room_breakdown) + 1}",
                        'description': f"{room_name} — {item.description.split(',')[0].lower()} (for checking only)",
                        'quantity': round(room_quantity, 2),
                        'unit': item.unit
                    })
                    
        return room_breakdown
        
    def _estimate_room_areas(self, room_data: Dict[str, Any], 
                           elements: List[Dict]) -> Dict[str, float]:
        """Calculate room areas from geometric room detection or fallback to estimates"""
        room_areas = {}
        
        default_areas = {
            'Living Room': 25.0, 'Kitchen': 15.0, 'Dining Room': 18.0,
            'Bedroom 1': 20.0, 'Bedroom 2': 16.0, 'Bedroom 3': 14.0,
            'Bathroom': 8.0, 'WC': 4.0, 'Hall + Stairs': 12.0,
            'Landing': 6.0, 'Utility Room': 6.0
        }
        
        detected_rooms = room_data.get('room_types', {})
        
        for room_name, room_info in detected_rooms.items():
            if isinstance(room_info, dict) and 'area' in room_info:
                room_areas[room_name] = float(room_info['area'])
                print(f"Using geometric area for {room_name}: {room_info['area']:.2f} sq units")
            elif isinstance(room_info, dict) and 'polygon' in room_info:
                polygon_coords = room_info['polygon']
                if len(polygon_coords) >= 3:
                    area = self._calculate_polygon_area(polygon_coords)
                    room_areas[room_name] = area
                    print(f"Calculated area for {room_name}: {area:.2f} sq units from polygon")
                else:
                    room_areas[room_name] = default_areas.get(room_name, 10.0)
            else:
                room_areas[room_name] = default_areas.get(room_name, 10.0)
                
        if not room_areas:
            print("No geometric rooms detected, using default room layout")
            room_areas = default_areas
        else:
            print(f"Using geometric room areas for {len(room_areas)} rooms")
            
        return room_areas
    
    def _calculate_polygon_area(self, polygon_coords: List[Tuple[float, float]]) -> float:
        """Calculate area of polygon using shoelace formula"""
        if len(polygon_coords) < 3:
            return 0.0
        
        coords = polygon_coords[:]
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        
        area = 0.0
        n = len(coords) - 1
        for i in range(n):
            area += coords[i][0] * coords[i+1][1]
            area -= coords[i+1][0] * coords[i][1]
        
        return abs(area) / 2.0
    
    def _calculate_opening_deductions_from_elements(self, room_name: str, 
                                                  elements: List[Dict]) -> Dict[str, float]:
        """
        Calculate deductions for detected door and window openings in wall finishes
        following SMM7 standards (openings under 0.5m² are not deducted)
        """
        deductions = {
            'doors': 0.0,
            'windows': 0.0,
            'total': 0.0,
            'count_doors': 0,
            'count_windows': 0
        }
        
        if not elements:
            return deductions
            
        for element in elements:
            element_type = element.get('type', '').lower()
            
            # Calculate element area
            element_area = 0.0
            if 'area' in element:
                element_area = float(element['area'])
            elif 'width' in element and 'height' in element:
                element_area = float(element['width']) * float(element['height'])
            elif 'dimensions' in element:
                dims = element['dimensions']
                if isinstance(dims, dict) and 'width' in dims and 'height' in dims:
                    element_area = float(dims['width']) * float(dims['height'])
            elif 'bbox' in element:
                bbox = element['bbox']
                if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                    width = abs(bbox[2] - bbox[0])
                    height = abs(bbox[3] - bbox[1])
                    element_area = (width * height) / 10000  # Very rough conversion
            
            if element_area > self.min_deduction_area:
                if 'door' in element_type:
                    deductions['doors'] += element_area
                    deductions['count_doors'] += 1
                elif 'window' in element_type:
                    deductions['windows'] += element_area
                    deductions['count_windows'] += 1
                    
        deductions['total'] = deductions['doors'] + deductions['windows']
        return deductions
        
    def _calculate_room_quantity(self, item: BOQItem, room_area: float, 
                               total_area: float, room_name: str = "", 
                               elements: List[Dict] = None) -> float:
        """Calculate quantity for specific room based on item type"""
        if elements is None:
            elements = []
            
        # Check if this is a wall finish item that needs opening deductions
        is_wall_finish = (item.category.lower() in ['finishes', 'painting', 'plastering'] and
                         any(keyword in item.description.lower() for keyword in 
                             ['wall', 'walls', 'plaster', 'paint', 'render', 'wallpaper', 'skim']))
        
        if item.unit.lower() in ['m²', 'm2']:
            if is_wall_finish:
                # For wall finishes, calculate wall area and apply opening deductions
                wall_height = 2.7  # Standard wall height in meters
                perimeter = 4 * math.sqrt(room_area)  # Approximate room perimeter
                wall_area = perimeter * wall_height
                
                deductions = self._calculate_opening_deductions_from_elements(room_name, elements)
                final_area = max(0, wall_area - deductions['total'])
                
                # Log deduction details for verification
                if deductions['total'] > 0:
                    print(f"  {room_name} wall finish deductions:")
                    print(f"    Doors: {deductions['count_doors']} × {deductions['doors']:.2f}m²")
                    print(f"    Windows: {deductions['count_windows']} × {deductions['windows']:.2f}m²")
                    print(f"    Total deducted: {deductions['total']:.2f}m²")
                    print(f"    Wall area: {wall_area:.2f}m² → {final_area:.2f}m²")
                
                return final_area
            else:
                return room_area
        elif item.unit.lower() == 'm':
            perimeter = 4 * math.sqrt(room_area)  # Approximate room perimeter
            return perimeter
        elif item.unit.lower() in ['nr', 'no.', 'each']:
            if 'socket' in item.description.lower():
                return max(1, int(room_area / 8))  # 1 socket per 8m²
            elif 'light' in item.description.lower():
                return max(1, int(room_area / 12))  # 1 light per 12m²
            else:
                return 1 if room_area > 0 else 0
        else:
            if total_area > 0:
                proportion = room_area / total_area
                return item.quantity * proportion
            return 0
