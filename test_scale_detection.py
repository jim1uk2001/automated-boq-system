#!/usr/bin/env python3
"""
Test script to verify scale detection functionality
"""
import sys
import os
sys.path.append('/home/ubuntu/automated-boq-system/automated-boq-backend')

from app.services.drawing_processor import DrawingProcessor
import asyncio

async def test_scale_detection():
    """Test scale detection with various text patterns"""
    
    print("🔍 Testing scale detection patterns...")
    
    processor = DrawingProcessor()
    
    test_cases = [
        {"text": "Scale: 1:50", "expected": "1:50"},
        {"text": "SCALE 1/100", "expected": "1:100"},
        {"text": "1:75", "expected": "1:75"},
        {"text": "@1:200", "expected": "1:200"},
        {"text": "Scale 1 : 25", "expected": "1:25"},
        {"text": "No scale info", "expected": None},
        {"text": "1:5000", "expected": None},
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        mock_annotations = [{"text": test_case["text"]}]
        detected_scale = processor._detect_scale(mock_annotations)
        
        if detected_scale == test_case["expected"]:
            print(f"  ✅ Test {i}: '{test_case['text']}' → {detected_scale}")
        else:
            print(f"  ❌ Test {i}: '{test_case['text']}' → Expected: {test_case['expected']}, Got: {detected_scale}")
    
    print("\n🧮 Testing scale factor calculation...")
    test_scales = ["1:50", "1:100", "1:25", None]
    for scale in test_scales:
        factor = processor._calculate_scale_factor(scale)
        print(f"  Scale {scale} → Factor: {factor}")
    
    print("\n✅ Scale detection tests completed!")

if __name__ == "__main__":
    asyncio.run(test_scale_detection())
