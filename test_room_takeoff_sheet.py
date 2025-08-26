#!/usr/bin/env python3
"""Test Room-Based Take-off Sheet Generation"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'automated-boq-backend'))

from app.services.room_quantity_calculator import RoomQuantityCalculator
from app.models import BOQItem, MeasurementStandard

def test_room_takeoff_calculations():
    """Test room-based quantity calculations"""
    calculator = RoomQuantityCalculator()
    
    boq_items = [
        BOQItem(
            project_id="test", drawing_id="test",
            item_code="F1", description="Timber skirting to perimeter",
            unit="m", quantity=142, category="finishes", trade="joinery",
            measurement_standard=MeasurementStandard.SMM7
        ),
        BOQItem(
            project_id="test", drawing_id="test",
            item_code="F2.1", description="LED ceiling lights",
            unit="nr", quantity=12, category="electrical", trade="electrical",
            measurement_standard=MeasurementStandard.SMM7
        ),
        BOQItem(
            project_id="test", drawing_id="test",
            item_code="D1", description="Internal doors",
            unit="nr", quantity=8, category="doors", trade="joinery",
            measurement_standard=MeasurementStandard.SMM7
        )
    ]
    
    room_data = {
        'room_types': {
            'Living Room': {'bbox': [[0,0],[100,0],[100,100],[0,100]]},
            'Kitchen': {'bbox': [[0,0],[80,0],[80,80],[0,80]]},
            'Bedroom 1': {'bbox': [[0,0],[90,0],[90,90],[0,90]]}
        }
    }
    
    elements = []
    
    takeoff_data = calculator.calculate_room_based_quantities(
        boq_items, room_data, elements
    )
    
    print("Room-Based Take-off Sheet Test Results:")
    print("=" * 50)
    
    for item_code, data in takeoff_data.items():
        print(f"\nItem {item_code}: {data['description']}")
        print(f"Total Quantity: {data['total_quantity']} {data['unit']}")
        print("Room Breakdown:")
        
        subtotal = 0
        for room_entry in data['room_breakdown']:
            print(f"  {room_entry['ref']} {room_entry['description']}: {room_entry['quantity']} {room_entry['unit']}")
            subtotal += room_entry['quantity']
        
        print(f"  Subtotal: {subtotal} {data['unit']}")
        print(f"  BOQ Total: {data['total_quantity']} {data['unit']}")
        
        assert len(data['room_breakdown']) > 0, f"Item {item_code} should have room breakdown"
        
    assert 'D1' not in takeoff_data, "Internal doors should not have room breakdown"
    
    assert 'F1' in takeoff_data, "Skirting should have room breakdown"
    assert 'F2.1' in takeoff_data, "Lights should have room breakdown"
    
    print("\n✅ All room-based takeoff tests passed!")
    print("✅ Room breakdown calculations working correctly")
    print("✅ Internal doors correctly excluded from room breakdown")
    
if __name__ == "__main__":
    test_room_takeoff_calculations()
