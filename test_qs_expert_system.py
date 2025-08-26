#!/usr/bin/env python3
"""Test QS Expert System functionality"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'automated-boq-backend'))

from app.services.qs_expert_system import QSExpertSystem
from app.models import BOQItem, MeasurementStandard

def test_qs_validation():
    qs_expert = QSExpertSystem()
    
    test_items = [
        BOQItem(project_id="test", item_code="F2.1", description="LED ceiling light fittings", 
               unit="no.", quantity=10, category="electrical", trade="electrical", 
               measurement_standard=MeasurementStandard.SMM7),
        BOQItem(project_id="test", item_code="F2.2", description="Socket outlets 13A", 
               unit="no.", quantity=25, category="electrical", trade="electrical", 
               measurement_standard=MeasurementStandard.SMM7),
        BOQItem(project_id="test", item_code="F2.3", description="Light switches", 
               unit="no.", quantity=10, category="electrical", trade="electrical", 
               measurement_standard=MeasurementStandard.SMM7),
    ]
    
    results = qs_expert.validate_boq_compliance(test_items, MeasurementStandard.SMM7)
    
    print(f"QS Validation Results:")
    print(f"Compliant: {results['compliant']}")
    print(f"Issues: {results['issues']}")
    print(f"Item count: {results['item_count']}")
    
    test_annotations = [
        {'text': 'PVC Triple Glazed Windows', 'confidence': 0.9, 'bbox': [[0,0],[100,0],[100,20],[0,20]]},
        {'text': 'Composite Door with 3 point locking', 'confidence': 0.8, 'bbox': [[0,25],[200,25],[200,45],[0,45]]},
        {'text': '2400mm x 1200mm', 'confidence': 0.95, 'bbox': [[0,50],[150,50],[150,70],[0,70]]}
    ]
    
    from app.models import DrawingType
    specs = qs_expert.extract_specifications_from_text(test_annotations, DrawingType.ARCHITECTURAL)
    
    print(f"\nSpecification Extraction:")
    print(f"Symbols: {len(specs['symbols'])}")
    print(f"Descriptions: {len(specs['descriptions'])}")
    print(f"Materials: {len(specs['materials'])}")
    print(f"Dimensions: {len(specs['dimensions'])}")
    
if __name__ == "__main__":
    test_qs_validation()
