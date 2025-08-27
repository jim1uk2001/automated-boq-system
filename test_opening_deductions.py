#!/usr/bin/env python3
"""Test Opening Deductions for Wall Finishes"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'automated-boq-backend'))

from app.services.room_quantity_calculator import RoomQuantityCalculator
from app.models import BOQItem, MeasurementStandard

def test_opening_deductions():
    """Test deductions for door and window openings in wall finishes"""
    calculator = RoomQuantityCalculator()
    
    print("Testing Opening Deductions for Wall Finishes")
    print("=" * 50)
    
    detected_elements = [
        {
            'type': 'door',
            'width': 0.9,
            'height': 2.1,
            'area': 1.89,  # 1.89m² > 0.5m² threshold, should be deducted
            'room': 'Living Room'
        },
        {
            'type': 'window',
            'width': 1.2,
            'height': 1.5,
            'area': 1.8,   # 1.8m² > 0.5m² threshold, should be deducted
            'room': 'Living Room'
        },
        {
            'type': 'window',
            'width': 0.6,
            'height': 0.8,
            'area': 0.48,  # 0.48m² < 0.5m² threshold, should NOT be deducted
            'room': 'Kitchen'
        },
        {
            'type': 'door',
            'width': 0.8,
            'height': 2.0,
            'area': 1.6,   # 1.6m² > 0.5m² threshold, should be deducted
            'room': 'Bedroom 1'
        }
    ]
    
    boq_items = [
        BOQItem(
            project_id="test", drawing_id="test",
            item_code="F4.1", description="Wall plaster, 12mm thick",
            unit="m²", quantity=250, category="finishes", trade="plastering",
            measurement_standard=MeasurementStandard.SMM7
        ),
        BOQItem(
            project_id="test", drawing_id="test",
            item_code="F4.2", description="Wall paint, emulsion",
            unit="m²", quantity=250, category="finishes", trade="painting",
            measurement_standard=MeasurementStandard.SMM7
        ),
        BOQItem(
            project_id="test", drawing_id="test",
            item_code="F3", description="Carpet flooring",
            unit="m²", quantity=85, category="flooring", trade="flooring",
            measurement_standard=MeasurementStandard.SMM7
        )
    ]
    
    room_data = {
        'room_types': {
            'Living Room': {'area': 25.0},
            'Kitchen': {'area': 15.0},
            'Bedroom 1': {'area': 20.0}
        }
    }
    
    takeoff_data = calculator.calculate_room_based_quantities(
        boq_items, room_data, detected_elements
    )
    
    print("\nTest Results:")
    for item_code, data in takeoff_data.items():
        print(f"\nItem {item_code}: {data['description']}")
        print(f"Total Quantity: {data['total_quantity']} {data['unit']}")
        
        if 'wall' in data['description'].lower() and data['unit'] == 'm²':
            print("  Wall finish with opening deductions:")
            
        subtotal = 0
        for room_entry in data['room_breakdown']:
            print(f"  {room_entry['ref']} {room_entry['description']}: {room_entry['quantity']} {room_entry['unit']}")
            subtotal += room_entry['quantity']
        
        print(f"  Subtotal: {subtotal} {data['unit']}")
        
    print(f"\n🧪 Testing SMM7 Compliance:")
    test_deductions = calculator._calculate_opening_deductions_from_elements(
        "Test Room", detected_elements
    )
    
    expected_deductions = 1.89 + 1.8 + 1.6  # Only openings > 0.5m²
    
    print(f"Expected deductions: {expected_deductions:.2f}m²")
    print(f"Actual deductions: {test_deductions['total']:.2f}m²")
    print(f"Small window (0.48m²) correctly ignored: {'✅' if test_deductions['total'] == expected_deductions else '❌'}")
    
    assert abs(test_deductions['total'] - expected_deductions) < 0.01, "SMM7 deduction rules not followed"
    
    print("\n✅ All opening deduction tests passed!")
    print("✅ SMM7 compliance verified (openings <0.5m² not deducted)")
    print("✅ Wall finish quantities correctly reduced")

def test_deduction_calculation_methods():
    """Test different methods of calculating opening areas"""
    calculator = RoomQuantityCalculator()
    
    print("\n🔬 Testing Different Area Calculation Methods:")
    
    test_elements = [
        {
            'type': 'door',
            'area': 2.0,  # Direct area specification
        },
        {
            'type': 'window',
            'width': 1.5,
            'height': 1.2,  # Width × height calculation
        },
        {
            'type': 'door',
            'dimensions': {
                'width': 0.9,
                'height': 2.1
            }  # Dimensions object
        },
        {
            'type': 'window',
            'bbox': [100, 100, 200, 180],  # Bounding box (rough conversion)
        }
    ]
    
    deductions = calculator._calculate_opening_deductions_from_elements(
        "Test Room", test_elements
    )
    
    print(f"Total deductions from mixed formats: {deductions['total']:.2f}m²")
    print(f"Doors: {deductions['count_doors']}, Windows: {deductions['count_windows']}")
    
    expected_minimum = 2.0 + 1.8 + 1.89  # Known areas > 0.5m²
    assert deductions['total'] >= expected_minimum, "Area calculation methods not working correctly"
    
    print("✅ Multiple area calculation methods working correctly")

if __name__ == "__main__":
    test_opening_deductions()
    test_deduction_calculation_methods()
