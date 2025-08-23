#!/usr/bin/env python3
"""
Test script for drawing quality assessment and query generation
"""

import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'automated-boq-backend'))

from app.services.drawing_processor import DrawingProcessor
from app.models import Drawing, DrawingType
import json

async def test_quality_assessment():
    """Test the quality assessment and query generation system"""
    processor = DrawingProcessor()
    
    print("=" * 60)
    print("BOJIM BOQ PRODUCTION SOFTWARE")
    print("Drawing Quality Assessment Test")
    print("=" * 60)
    
    test_scenarios = [
        {
            "name": "High Quality Architectural Drawing",
            "drawing_type": DrawingType.ARCHITECTURAL,
            "dimensions": [
                {"text": "3000mm", "value": 3000},
                {"text": "4500mm", "value": 4500},
                {"text": "2700mm", "value": 2700},
                {"text": "1200mm", "value": 1200},
                {"text": "800mm", "value": 800}
            ],
            "text_annotations": [
                {"text": "Living Room", "confidence": 0.95},
                {"text": "Kitchen", "confidence": 0.92},
                {"text": "Bedroom 1", "confidence": 0.88},
                {"text": "Bathroom", "confidence": 0.90},
                {"text": "Project: Office Building", "confidence": 0.85},
                {"text": "Drawing: Ground Floor Plan", "confidence": 0.87},
                {"text": "Scale: 1:100", "confidence": 0.89},
                {"text": "Revision: A", "confidence": 0.91},
                {"text": "Date: 2024-08-23", "confidence": 0.93}
            ],
            "scale_info": "1:100"
        },
        {
            "name": "Poor Quality Architectural Drawing",
            "drawing_type": DrawingType.ARCHITECTURAL,
            "dimensions": [
                {"text": "unclear", "value": None}
            ],
            "text_annotations": [
                {"text": "room", "confidence": 0.3},
                {"text": "unclear text", "confidence": 0.2}
            ],
            "scale_info": None
        },
        {
            "name": "Incomplete Structural Drawing",
            "drawing_type": DrawingType.STRUCTURAL,
            "dimensions": [
                {"text": "6000mm", "value": 6000},
                {"text": "300x600", "value": 300}
            ],
            "text_annotations": [
                {"text": "beam", "confidence": 0.7},
                {"text": "column", "confidence": 0.6},
                {"text": "foundation", "confidence": 0.5}
            ],
            "scale_info": "1:50"
        },
        {
            "name": "MEP Drawing with Missing Specifications",
            "drawing_type": DrawingType.MEP,
            "dimensions": [
                {"text": "100mm", "value": 100},
                {"text": "150mm", "value": 150}
            ],
            "text_annotations": [
                {"text": "pipe", "confidence": 0.8},
                {"text": "duct", "confidence": 0.75},
                {"text": "electrical", "confidence": 0.7}
            ],
            "scale_info": "1:100"
        }
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\nTest {i}: {scenario['name']}")
        print("-" * 50)
        
        quality_assessment = processor._assess_drawing_quality(
            scenario['dimensions'],
            scenario['text_annotations'],
            scenario['scale_info'],
            scenario['drawing_type']
        )
        
        queries = processor._generate_architect_queries(
            quality_assessment,
            scenario['drawing_type'],
            f"test_drawing_{i}.pdf"
        )
        
        print(f"Quality Score: {quality_assessment['quality_score']}/100")
        print(f"Issues Found: {len(quality_assessment['issues'])}")
        print(f"Is Sufficient: {quality_assessment['is_sufficient']}")
        
        if quality_assessment['issues']:
            print("\nQuality Issues:")
            for issue in quality_assessment['issues']:
                print(f"  - {issue}")
        
        if quality_assessment['recommendations']:
            print("\nRecommendations:")
            for rec in quality_assessment['recommendations']:
                print(f"  - {rec}")
        
        print(f"\nGenerated Queries: {len(queries)}")
        
        if queries:
            high_priority = [q for q in queries if q.get('priority') == 'high']
            medium_priority = [q for q in queries if q.get('priority') == 'medium']
            low_priority = [q for q in queries if q.get('priority') == 'low']
            
            print(f"  High Priority: {len(high_priority)}")
            print(f"  Medium Priority: {len(medium_priority)}")
            print(f"  Low Priority: {len(low_priority)}")
            
            print("\nSample Queries:")
            for j, query in enumerate(queries[:3], 1):
                print(f"  {j}. [{query.get('priority', 'unknown').upper()}] {query.get('question', '')}")
                print(f"     Category: {query.get('category', '')}")
                print(f"     Action: {query.get('suggested_action', '')}")
        
        print("\n" + "=" * 60)
    
    print("\nTesting query formatting...")
    
    sample_queries = [
        {
            "category": "dimensions",
            "priority": "high",
            "question": "Could you please provide dimensional annotations for all major elements?",
            "details": "Missing dimensions prevent automated calculation of quantities.",
            "suggested_action": "Add dimension lines with clear numerical values"
        },
        {
            "category": "scale",
            "priority": "high",
            "question": "Please confirm the drawing scale and add a scale indicator.",
            "details": "Without a clear scale reference, we cannot determine actual sizes.",
            "suggested_action": "Add scale notation (e.g., 1:100, 1:50)"
        }
    ]
    
    from app.main import _format_queries_for_export
    formatted = _format_queries_for_export("sample_drawing.pdf", sample_queries, 45)
    
    print("\nFormatted Query Export:")
    print("-" * 30)
    print(formatted)
    
    print("\n" + "=" * 60)
    print("Quality Assessment Test Complete!")
    print("=" * 60)

def test_drawing_type_classification():
    """Test drawing type classification"""
    processor = DrawingProcessor()
    
    print("\nTesting Drawing Type Classification:")
    print("-" * 40)
    
    test_cases = [
        {
            "text": ["floor plan", "living room", "kitchen", "bedroom"],
            "expected": DrawingType.ARCHITECTURAL
        },
        {
            "text": ["beam", "column", "foundation", "structural"],
            "expected": DrawingType.STRUCTURAL
        },
        {
            "text": ["electrical", "plumbing", "hvac", "mep"],
            "expected": DrawingType.MEP
        },
        {
            "text": ["site", "plot", "boundary", "contour"],
            "expected": DrawingType.SITE
        },
        {
            "text": ["detail", "section", "connection"],
            "expected": DrawingType.DETAIL
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        text_annotations = [{"text": text, "confidence": 0.8} for text in case["text"]]
        result = processor._classify_drawing_type(text_annotations)
        
        status = "✓" if result == case["expected"] else "✗"
        print(f"{status} Test {i}: {case['text']} -> {result}")

if __name__ == "__main__":
    print("Starting Drawing Quality Assessment Tests...")
    asyncio.run(test_quality_assessment())
    test_drawing_type_classification()
    print("\nAll tests completed!")
