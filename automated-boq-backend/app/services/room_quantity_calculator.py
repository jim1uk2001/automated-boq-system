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
                    item, room_area, total_estimated_area
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
        """Estimate room areas from detected elements and room types"""
        room_areas = {}
        
        default_areas = {
            'Living Room': 25.0, 'Kitchen': 15.0, 'Dining Room': 18.0,
            'Bedroom 1': 20.0, 'Bedroom 2': 16.0, 'Bedroom 3': 14.0,
            'Bathroom': 8.0, 'WC': 4.0, 'Hall + Stairs': 12.0,
            'Landing': 6.0, 'Utility Room': 6.0
        }
        
        detected_rooms = room_data.get('room_types', {})
        
        for room_name in detected_rooms:
            if room_name in default_areas:
                room_areas[room_name] = default_areas[room_name]
                
        if not room_areas:
            room_areas = default_areas
            
        return room_areas
        
    def _calculate_room_quantity(self, item: BOQItem, room_area: float, 
                               total_area: float) -> float:
        """Calculate quantity for specific room based on item type"""
        if item.unit.lower() in ['m²', 'm2']:
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
