from typing import List, Dict, Any, Optional, Tuple
from ..models import BOQItem, MeasurementStandard, DrawingType
import re
from enum import Enum

class SpecificationType(str, Enum):
    SYMBOL = "symbol"  # Quantifiable elements (doors, windows, etc.)
    DESCRIPTION = "description"  # Descriptive text for BOQ items
    DIMENSION = "dimension"  # Measurement values
    MATERIAL = "material"  # Material specifications

class QSExpertSystem:
    """
    Quantity Surveyor Expert System - validates BOQ requirements and extracts specifications
    Principle: Measure what is on the drawings, nothing more, nothing less
    """
    
    def __init__(self):
        self.measurement_standards = {
            MeasurementStandard.SMM7: self._get_smm7_validation_rules(),
            MeasurementStandard.RICS_NRM: self._get_nrm_validation_rules(),
            MeasurementStandard.CESMM: self._get_cesmm_validation_rules()
        }
        
    def validate_boq_compliance(self, boq_items: List[BOQItem], 
                              measurement_standard: MeasurementStandard) -> Dict[str, Any]:
        """Validate BOQ items against measurement standard requirements"""
        validation_results = {
            'compliant': True,
            'issues': [],
            'recommendations': [],
            'item_count': len(boq_items),
            'standard': measurement_standard.value
        }
        
        rules = self.measurement_standards.get(measurement_standard, {})
        
        electrical_items = [item for item in boq_items if item.category == "electrical"]
        if not self._validate_electrical_separation(electrical_items, rules):
            validation_results['issues'].append("Electrical items not properly separated per SMM7 standards")
            validation_results['compliant'] = False
            
        deduction_items = [item for item in boq_items if 'deduction' in item.description.lower()]
        if deduction_items:
            validation_results['issues'].append(f"Found {len(deduction_items)} deduction items - these should not appear in BOQ")
            validation_results['compliant'] = False
            
        for item in boq_items:
            if not self._validate_item_specification(item, rules):
                validation_results['issues'].append(f"Item {item.item_code}: insufficient specification detail")
                
        return validation_results
        
    def extract_specifications_from_text(self, text_annotations: List[Dict], 
                                       drawing_type: DrawingType) -> Dict[str, Any]:
        """Extract detailed specifications from OCR text, distinguishing symbols from descriptions"""
        specifications = {
            'symbols': [],  # Quantifiable elements
            'descriptions': [],  # Descriptive specifications
            'materials': [],  # Material specifications
            'dimensions': []  # Measurement values
        }
        
        for annotation in text_annotations:
            text = annotation.get('text', '').strip()
            confidence = annotation.get('confidence', 0)
            
            if confidence < 0.6:  # Skip low confidence text
                continue
                
            spec_type = self._classify_specification_type(text, drawing_type)
            
            if spec_type == SpecificationType.SYMBOL:
                specifications['symbols'].append({
                    'text': text,
                    'bbox': annotation.get('bbox'),
                    'confidence': confidence,
                    'quantity_indicator': self._extract_quantity_from_symbol(text)
                })
            elif spec_type == SpecificationType.DESCRIPTION:
                specifications['descriptions'].append({
                    'text': text,
                    'bbox': annotation.get('bbox'),
                    'confidence': confidence,
                    'specification_details': self._parse_specification_details(text)
                })
            elif spec_type == SpecificationType.MATERIAL:
                specifications['materials'].append({
                    'text': text,
                    'material_type': self._identify_material_type(text),
                    'properties': self._extract_material_properties(text)
                })
                
        return specifications
        
    def generate_detailed_boq_descriptions(self, base_description: str, 
                                         specifications: Dict[str, Any]) -> str:
        """Generate detailed BOQ descriptions with specifications from drawings"""
        enhanced_description = base_description
        
        if specifications.get('materials'):
            material_specs = []
            for material in specifications['materials']:
                if material.get('properties'):
                    material_specs.append(f"{material['material_type']} {material['properties']}")
            if material_specs:
                enhanced_description += f", {', '.join(material_specs)}"
                
        if specifications.get('dimensions'):
            dim_specs = [dim['text'] for dim in specifications['dimensions']]
            if dim_specs:
                enhanced_description += f", dimensions: {', '.join(dim_specs)}"
                
        return enhanced_description
        
    def _validate_electrical_separation(self, electrical_items: List[BOQItem], 
                                      rules: Dict[str, Any]) -> bool:
        """Validate that electrical items are properly separated per SMM7"""
        required_electrical_codes = ['F2.1', 'F2.2', 'F2.3', 'F2.4', 'F2.5', 'F2.6']
        found_codes = [item.item_code for item in electrical_items]
        
        return len(set(found_codes) & set(required_electrical_codes)) >= 4
        
    def _validate_item_specification(self, item: BOQItem, rules: Dict[str, Any]) -> bool:
        """Validate that BOQ item has sufficient specification detail"""
        description = item.description.lower()
        
        if item.category in ['doors', 'windows']:
            required_specs = ['material', 'size', 'type']
            return any(spec in description for spec in required_specs)
            
        return True  # Basic validation for other categories
        
    def _classify_specification_type(self, text: str, drawing_type: DrawingType) -> SpecificationType:
        """Classify text as symbol, description, dimension, or material specification"""
        text_lower = text.lower()
        
        if re.search(r'\d+\.?\d*\s*(mm|m|cm|ft|in)', text_lower):
            return SpecificationType.DIMENSION
            
        if re.search(r'(door|window|socket|light|switch)\s*\d+', text_lower):
            return SpecificationType.SYMBOL
            
        if re.search(r'(pvc|timber|steel|concrete|brick|block|glazed)', text_lower):
            return SpecificationType.MATERIAL
            
        return SpecificationType.DESCRIPTION
        
    def _extract_quantity_from_symbol(self, text: str) -> Optional[int]:
        """Extract quantity number from symbol text"""
        match = re.search(r'(\d+)', text)
        return int(match.group(1)) if match else None
        
    def _parse_specification_details(self, text: str) -> Dict[str, Any]:
        """Parse detailed specifications from descriptive text"""
        details = {}
        text_lower = text.lower()
        
        if 'triple' in text_lower and 'glazed' in text_lower:
            details['glazing'] = 'triple_glazed'
        elif 'double' in text_lower and 'glazed' in text_lower:
            details['glazing'] = 'double_glazed'
            
        if '3 point' in text_lower and 'lock' in text_lower:
            details['locking'] = '3_point_locking'
            
        if 'composite' in text_lower:
            details['material'] = 'composite'
        elif 'pvc' in text_lower:
            details['material'] = 'pvc'
            
        return details
        
    def _identify_material_type(self, text: str) -> str:
        """Identify the type of material from text"""
        text_lower = text.lower()
        
        if 'pvc' in text_lower:
            return 'PVC'
        elif 'timber' in text_lower or 'wood' in text_lower:
            return 'Timber'
        elif 'steel' in text_lower:
            return 'Steel'
        elif 'concrete' in text_lower:
            return 'Concrete'
        elif 'brick' in text_lower:
            return 'Brick'
        elif 'block' in text_lower:
            return 'Block'
            
        return 'Unknown'
        
    def _extract_material_properties(self, text: str) -> str:
        """Extract material properties from text"""
        properties = []
        
        thickness_match = re.search(r'(\d+\.?\d*)\s*(mm|m)', text.lower())
        if thickness_match:
            properties.append(f"{thickness_match.group(1)}{thickness_match.group(2)} thick")
            
        return ', '.join(properties) if properties else ''
        
    def _get_smm7_validation_rules(self) -> Dict[str, Any]:
        """SMM7 specific validation rules"""
        return {
            'electrical_separation_required': True,
            'deductions_excluded': True,
            'minimum_specification_detail': True,
            'required_electrical_items': ['lighting', 'sockets', 'switches', 'wiring', 'consumer_unit', 'smoke_alarms']
        }
        
    def _get_nrm_validation_rules(self) -> Dict[str, Any]:
        """RICS NRM specific validation rules"""
        return {
            'electrical_separation_required': True,
            'deductions_excluded': True,
            'minimum_specification_detail': True
        }
        
    def _get_cesmm_validation_rules(self) -> Dict[str, Any]:
        """CESMM specific validation rules"""
        return {
            'electrical_separation_required': False,  # Different approach in CESMM
            'deductions_excluded': True,
            'minimum_specification_detail': True
        }
