import cv2
import numpy as np
import pytesseract
import easyocr
import ezdxf
from PIL import Image
from typing import List, Dict, Any, Optional, Tuple
import os
import tempfile
import logging
from ..models import Drawing, DrawingType

logger = logging.getLogger(__name__)

class DrawingProcessor:
    def __init__(self):
        self.easyocr_reader = easyocr.Reader(['en'])
        
    async def process_drawing(self, drawing: Drawing, file_content: bytes) -> Dict[str, Any]:
        """Process a drawing file and extract dimensions and elements"""
        try:
            if drawing.file_type.lower() == 'pdf':
                results = await self._process_pdf(drawing, file_content)
            elif drawing.file_type.lower() in ['dwg', 'dxf']:
                results = await self._process_autocad(drawing, file_content)
            else:
                raise ValueError(f"Unsupported file type: {drawing.file_type}")
            
            quality_assessment = self._assess_drawing_quality(
                results.get('dimensions', []),
                results.get('text_annotations', []),
                results.get('scale_info'),
                drawing.drawing_type
            )
            
            queries = self._generate_architect_queries(
                quality_assessment,
                drawing.drawing_type,
                drawing.filename
            )
            
            results['quality_assessment'] = quality_assessment
            results['architect_queries'] = queries
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing drawing {drawing.id}: {str(e)}")
            raise

    async def _process_pdf(self, drawing: Drawing, file_content: bytes) -> Dict[str, Any]:
        """Process PDF drawing using computer vision and OCR"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(file_content)
            temp_path = temp_file.name

        try:
            import fitz  # PyMuPDF for PDF processing
            doc = fitz.open(temp_path)
            
            results = {
                'elements': [],
                'dimensions': [],
                'text_annotations': [],
                'scale_info': None,
                'drawing_type': None
            }
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
                img_data = pix.tobytes("png")
                
                nparr = np.frombuffer(img_data, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                page_results = await self._analyze_image(image)
                
                results['elements'].extend(page_results['elements'])
                results['dimensions'].extend(page_results['dimensions'])
                results['text_annotations'].extend(page_results['text_annotations'])
                
                if not results['scale_info'] and page_results['scale_info']:
                    results['scale_info'] = page_results['scale_info']
                
                if not results['drawing_type'] and page_results['drawing_type']:
                    results['drawing_type'] = page_results['drawing_type']
            
            doc.close()
            return results
            
        finally:
            os.unlink(temp_path)

    async def _process_autocad(self, drawing: Drawing, file_content: bytes) -> Dict[str, Any]:
        """Process AutoCAD file using ezdxf"""
        with tempfile.NamedTemporaryFile(suffix=f'.{drawing.file_type}', delete=False) as temp_file:
            temp_file.write(file_content)
            temp_path = temp_file.name

        try:
            doc = ezdxf.readfile(temp_path)
            modelspace = doc.modelspace()
            
            results = {
                'elements': [],
                'dimensions': [],
                'text_annotations': [],
                'scale_info': None,
                'drawing_type': None
            }
            
            for entity in modelspace:
                if entity.dxftype() == 'LINE':
                    start = entity.dxf.start
                    end = entity.dxf.end
                    results['elements'].append({
                        'type': 'line',
                        'start': (float(start.x), float(start.y)),
                        'end': (float(end.x), float(end.y)),
                        'length': float((end - start).magnitude)
                    })
                elif entity.dxftype() == 'CIRCLE':
                    center = entity.dxf.center
                    radius = entity.dxf.radius
                    results['elements'].append({
                        'type': 'circle',
                        'center': (float(center.x), float(center.y)),
                        'radius': float(radius),
                        'area': float(np.pi * radius ** 2)
                    })
                elif entity.dxftype() == 'LWPOLYLINE':
                    points = [(float(p[0]), float(p[1])) for p in entity.get_points()]
                    results['elements'].append({
                        'type': 'polyline',
                        'points': points,
                        'closed': bool(entity.closed),
                        'area': float(self._calculate_polygon_area(points)) if entity.closed else 0.0
                    })
                elif entity.dxftype() == 'TEXT':
                    position = entity.dxf.insert
                    results['text_annotations'].append({
                        'text': str(entity.dxf.text),
                        'position': (float(position.x), float(position.y)),
                        'height': float(entity.dxf.height)
                    })
                elif entity.dxftype() == 'DIMENSION':
                    results['dimensions'].append({
                        'type': 'dimension',
                        'measurement': float(entity.get_measurement()),
                        'text': str(entity.dxf.text) if hasattr(entity.dxf, 'text') else None
                    })
            
            results['drawing_type'] = self._classify_autocad_drawing(doc)
            
            return results
            
        finally:
            os.unlink(temp_path)

    async def _analyze_image(self, image: np.ndarray) -> Dict[str, Any]:
        """Analyze image using computer vision techniques"""
        results = {
            'elements': [],
            'dimensions': [],
            'text_annotations': [],
            'scale_info': None,
            'drawing_type': None
        }
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=50, maxLineGap=10)
        
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
                results['elements'].append({
                    'type': 'line',
                    'start': (int(x1), int(y1)),
                    'end': (int(x2), int(y2)),
                    'length': float(length)
                })
        
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, 20, param1=50, param2=30, minRadius=10, maxRadius=100)
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (x, y, r) in circles:
                results['elements'].append({
                    'type': 'circle',
                    'center': (int(x), int(y)),
                    'radius': int(r),
                    'area': float(np.pi * r ** 2)
                })
        
        try:
            ocr_results = self.easyocr_reader.readtext(image)
            building_types = {}
            
            for (bbox, text, confidence) in ocr_results:
                if confidence > 0.5:  # Filter low confidence results
                    bbox_converted = [[float(coord[0]), float(coord[1])] for coord in bbox]
                    results['text_annotations'].append({
                        'text': text,
                        'bbox': bbox_converted,
                        'confidence': float(confidence)
                    })
                    
                    import re
                    text_lower = text.lower()
                    
                    if re.search(r'type\s+[a-z]', text_lower) or re.search(r'house\s+type\s+[a-z]', text_lower):
                        building_type = re.search(r'type\s+([a-z])', text_lower)
                        if building_type:
                            type_name = f"Type {building_type.group(1).upper()}"
                            building_types[type_name] = bbox_converted
                    
                    elif re.search(r'office\s+building|commercial\s+building|retail\s+building', text_lower):
                        if 'office' in text_lower:
                            building_types["Office Building"] = bbox_converted
                        elif 'retail' in text_lower:
                            building_types["Retail Building"] = bbox_converted
                        else:
                            building_types["Commercial Building"] = bbox_converted
                    
                    elif re.search(r'hospital|medical\s+center|clinic', text_lower):
                        building_types["Hospital/Medical"] = bbox_converted
                    elif re.search(r'school|university|college|educational', text_lower):
                        building_types["Educational"] = bbox_converted
                    elif re.search(r'police\s+station|fire\s+station|government', text_lower):
                        building_types["Government/Public Safety"] = bbox_converted
                    
                    elif re.search(r'warehouse|factory|industrial|manufacturing', text_lower):
                        building_types["Industrial"] = bbox_converted
                    
                    elif re.search(r'mixed\s+use|multi\s+use|residential.*commercial|commercial.*residential', text_lower):
                        building_types["Mixed-Use Development"] = bbox_converted
                    
                    elif re.search(r'tower|high\s+rise|multi\s+story|apartment\s+building', text_lower):
                        if 'apartment' in text_lower:
                            building_types["Apartment Building"] = bbox_converted
                        else:
                            building_types["High-Rise Building"] = bbox_converted
                    
                    elif re.search(r'class\s+[abc]\s+building|building\s+class\s+[abc]', text_lower):
                        class_match = re.search(r'class\s+([abc])', text_lower)
                        if class_match:
                            building_types[f"Class {class_match.group(1).upper()} Building"] = bbox_converted
                    
                    if self._is_dimension_text(text):
                        results['dimensions'].append({
                            'text': text,
                            'bbox': bbox_converted,
                            'value': self._extract_dimension_value(text)
                        })
                        
            results['building_types'] = building_types
        except Exception as e:
            logger.warning(f"OCR failed: {str(e)}")
        
        results['drawing_type'] = self._classify_drawing_type(results['text_annotations'])
        
        return results

    def _calculate_polygon_area(self, points: List[Tuple[float, float]]) -> float:
        """Calculate area of polygon using shoelace formula"""
        if len(points) < 3:
            return 0
        
        area = 0
        for i in range(len(points)):
            j = (i + 1) % len(points)
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]
        return abs(area) / 2

    def _is_dimension_text(self, text: str) -> bool:
        """Check if text appears to be a dimension"""
        import re
        dimension_patterns = [
            r'\d+\.?\d*\s*m{1,2}',  # metric
            r'\d+\.?\d*\s*ft',      # feet
            r'\d+\'-\d+\"',         # feet-inches
            r'\d+\.?\d*\"',         # inches
            r'^\d+\.?\d*$'          # plain numbers
        ]
        
        for pattern in dimension_patterns:
            if re.search(pattern, text.lower()):
                return True
        return False

    def _extract_dimension_value(self, text: str) -> Optional[float]:
        """Extract numeric value from dimension text"""
        import re
        
        match = re.search(r'(\d+\.?\d*)', text)
        if match:
            return float(match.group(1))
        return None

    def _classify_drawing_type(self, text_annotations: List[Dict]) -> Optional[DrawingType]:
        """Classify drawing type based on text content"""
        all_text = ' '.join([ann['text'].lower() for ann in text_annotations])
        
        if any(keyword in all_text for keyword in ['floor plan', 'plan', 'layout']):
            return DrawingType.ARCHITECTURAL
        elif any(keyword in all_text for keyword in ['beam', 'column', 'foundation', 'structural']):
            return DrawingType.STRUCTURAL
        elif any(keyword in all_text for keyword in ['electrical', 'plumbing', 'hvac', 'mep']):
            return DrawingType.MEP
        elif any(keyword in all_text for keyword in ['site', 'plot', 'boundary']):
            return DrawingType.SITE
        elif any(keyword in all_text for keyword in ['detail', 'section']):
            return DrawingType.DETAIL
        
        return None

    def _classify_autocad_drawing(self, doc) -> Optional[DrawingType]:
        """Classify AutoCAD drawing based on layers and content"""
        layer_names = [layer.dxf.name.lower() for layer in doc.layers]
        
        if any('arch' in name or 'plan' in name for name in layer_names):
            return DrawingType.ARCHITECTURAL
        elif any('struct' in name or 'beam' in name or 'column' in name for name in layer_names):
            return DrawingType.STRUCTURAL
        elif any('elec' in name or 'plumb' in name or 'hvac' in name for name in layer_names):
            return DrawingType.MEP
        elif any('site' in name or 'civil' in name for name in layer_names):
            return DrawingType.SITE
        
        return None

    def _assess_drawing_quality(self, dimensions: List[Dict], text_annotations: List[Dict], 
                               scale_info: Optional[Any], drawing_type: Optional[DrawingType]) -> Dict[str, Any]:
        """Assess drawing quality and identify missing information"""
        quality_issues = []
        missing_info = []
        
        min_dimensions = 3
        min_text_confidence = 0.6
        min_title_block_info = 2
        
        if len(dimensions) < min_dimensions:
            quality_issues.append("insufficient_dimensions")
            missing_info.append("dimension_labels")
        
        if text_annotations:
            low_confidence_text = [ta for ta in text_annotations if ta.get('confidence', 0) < min_text_confidence]
            if len(low_confidence_text) > len(text_annotations) * 0.3:
                quality_issues.append("poor_text_quality")
                missing_info.append("clear_text_labels")
        else:
            quality_issues.append("no_text_detected")
            missing_info.append("text_annotations")
        
        if not scale_info:
            quality_issues.append("no_scale_detected")
            missing_info.append("scale_indicator")
        
        title_block_keywords = ['title', 'project', 'drawing', 'revision', 'date', 'scale']
        title_block_matches = 0
        for ta in text_annotations:
            text_lower = ta.get('text', '').lower()
            for keyword in title_block_keywords:
                if keyword in text_lower:
                    title_block_matches += 1
                    break
        
        if title_block_matches < min_title_block_info:
            quality_issues.append("incomplete_title_block")
            missing_info.append("title_block_information")
        
        if drawing_type:
            type_issues = self._check_drawing_type_requirements(drawing_type, text_annotations, dimensions)
            quality_issues.extend(type_issues)
        
        quality_score = max(0, 100 - len(quality_issues) * 15)
        
        return {
            'quality_score': quality_score,
            'issues': quality_issues,
            'missing_info': missing_info,
            'is_sufficient': len(quality_issues) <= 2 and quality_score >= 60,
            'recommendations': self._generate_quality_recommendations(quality_issues)
        }

    def _check_drawing_type_requirements(self, drawing_type: DrawingType, text_annotations: List[Dict], dimensions: List[Dict]) -> List[str]:
        """Check drawing-type specific requirements"""
        issues = []
        all_text = ' '.join([ann.get('text', '').lower() for ann in text_annotations])
        
        if drawing_type == DrawingType.ARCHITECTURAL:
            if not any(keyword in all_text for keyword in ['room', 'area', 'space', 'floor']):
                issues.append("missing_room_labels")
            if len(dimensions) < 5:
                issues.append("insufficient_room_dimensions")
                
        elif drawing_type == DrawingType.STRUCTURAL:
            if not any(keyword in all_text for keyword in ['beam', 'column', 'slab', 'foundation']):
                issues.append("missing_structural_elements")
            if not any(keyword in all_text for keyword in ['concrete', 'steel', 'reinforcement']):
                issues.append("missing_material_specifications")
                
        elif drawing_type == DrawingType.MEP:
            if not any(keyword in all_text for keyword in ['pipe', 'duct', 'cable', 'equipment']):
                issues.append("missing_mep_elements")
            if not any(keyword in all_text for keyword in ['size', 'diameter', 'capacity']):
                issues.append("missing_equipment_specifications")
                
        elif drawing_type == DrawingType.SITE:
            if not any(keyword in all_text for keyword in ['level', 'elevation', 'contour', 'grade']):
                issues.append("missing_site_levels")
            if len(dimensions) < 3:
                issues.append("insufficient_site_dimensions")
        
        return issues

    def _generate_quality_recommendations(self, quality_issues: List[str]) -> List[str]:
        """Generate actionable improvement suggestions"""
        recommendations = []
        
        issue_recommendations = {
            "insufficient_dimensions": "Add dimensional annotations for all major elements and spaces",
            "poor_text_quality": "Improve text clarity and legibility - use larger fonts and higher contrast",
            "no_text_detected": "Add text annotations and labels for all elements",
            "no_scale_detected": "Include a clear scale indicator (e.g., 1:100, 1:50)",
            "incomplete_title_block": "Complete title block with project name, drawing title, revision, and date",
            "missing_room_labels": "Label all rooms and spaces with their intended use",
            "insufficient_room_dimensions": "Add dimensions for all room boundaries and openings",
            "missing_structural_elements": "Clearly label all structural elements (beams, columns, slabs)",
            "missing_material_specifications": "Specify material types and grades for structural elements",
            "missing_mep_elements": "Label all MEP equipment, pipes, ducts, and cables",
            "missing_equipment_specifications": "Include equipment capacities, sizes, and specifications",
            "missing_site_levels": "Add elevation markers and contour lines for site levels",
            "insufficient_site_dimensions": "Include boundary dimensions and setback measurements"
        }
        
        for issue in quality_issues:
            if issue in issue_recommendations:
                recommendations.append(issue_recommendations[issue])
        
        return recommendations

    def _generate_architect_queries(self, quality_assessment: Dict[str, Any], 
                                   drawing_type: Optional[DrawingType], filename: str) -> List[Dict[str, Any]]:
        """Generate professional queries for architects/engineers"""
        queries = []
        issues = quality_assessment.get('issues', [])
        quality_score = quality_assessment.get('quality_score', 100)
        
        if quality_score >= 80:
            return queries
        
        general_queries = self._get_general_queries(issues)
        queries.extend(general_queries)
        
        if drawing_type:
            type_specific_queries = self._get_type_specific_queries(drawing_type, issues)
            queries.extend(type_specific_queries)
        
        for query in queries:
            query['drawing_filename'] = filename
            query['quality_score'] = quality_score
        
        return queries

    def _get_general_queries(self, issues: List[str]) -> List[Dict[str, Any]]:
        """Generate general queries for common issues"""
        queries = []
        
        if "insufficient_dimensions" in issues:
            queries.append({
                "category": "dimensions",
                "priority": "high",
                "question": "Could you please provide dimensional annotations for all major elements? We need measurements for accurate quantity takeoff.",
                "details": "Missing dimensions prevent automated calculation of quantities. Please add dimensions for walls, openings, and major elements.",
                "suggested_action": "Add dimension lines with clear numerical values in standard units (mm or m)"
            })
        
        if "no_scale_detected" in issues:
            queries.append({
                "category": "scale",
                "priority": "high", 
                "question": "Please confirm the drawing scale and add a scale indicator to the drawing.",
                "details": "Without a clear scale reference, we cannot accurately determine actual sizes from the drawing.",
                "suggested_action": "Add scale notation (e.g., 1:100, 1:50) and/or a scale bar"
            })
        
        if "poor_text_quality" in issues or "no_text_detected" in issues:
            queries.append({
                "category": "legibility",
                "priority": "medium",
                "question": "Could you improve the text clarity and add missing labels?",
                "details": "Some text is unclear or missing, which affects our ability to identify elements correctly.",
                "suggested_action": "Use larger, clearer fonts and ensure all elements are properly labeled"
            })
        
        if "incomplete_title_block" in issues:
            queries.append({
                "category": "documentation",
                "priority": "medium",
                "question": "Please complete the title block with project information, drawing title, revision number, and date.",
                "details": "Complete documentation is essential for version control and project tracking.",
                "suggested_action": "Fill in all title block fields including project name, drawing number, revision, and date"
            })
        
        return queries

    def _get_type_specific_queries(self, drawing_type: DrawingType, issues: List[str]) -> List[Dict[str, Any]]:
        """Generate drawing-type specific queries"""
        queries = []
        
        if drawing_type == DrawingType.ARCHITECTURAL:
            if "missing_room_labels" in issues:
                queries.append({
                    "category": "architectural",
                    "priority": "high",
                    "question": "Please label all rooms and spaces with their intended use (e.g., Living Room, Kitchen, Bedroom).",
                    "details": "Room labels are essential for calculating area-based quantities and understanding space functions.",
                    "suggested_action": "Add text labels inside each room indicating its purpose and area if possible"
                })
            
            if "insufficient_room_dimensions" in issues:
                queries.append({
                    "category": "architectural", 
                    "priority": "high",
                    "question": "Could you add dimensions for all room boundaries, door and window openings?",
                    "details": "We need room dimensions to calculate floor areas, wall lengths, and opening quantities.",
                    "suggested_action": "Dimension all walls, indicate door/window sizes and positions"
                })
        
        elif drawing_type == DrawingType.STRUCTURAL:
            if "missing_structural_elements" in issues:
                queries.append({
                    "category": "structural",
                    "priority": "high", 
                    "question": "Please clearly identify and label all structural elements (beams, columns, slabs, foundations).",
                    "details": "Structural element identification is crucial for calculating concrete, steel, and formwork quantities.",
                    "suggested_action": "Label each beam (e.g., B1, B2), column (C1, C2), and slab with reference numbers"
                })
            
            if "missing_material_specifications" in issues:
                queries.append({
                    "category": "structural",
                    "priority": "medium",
                    "question": "Could you specify material grades and types for structural elements?",
                    "details": "Material specifications affect quantity calculations and cost estimation.",
                    "suggested_action": "Add notes indicating concrete grades (e.g., C25/30) and steel specifications"
                })
        
        elif drawing_type == DrawingType.MEP:
            if "missing_mep_elements" in issues:
                queries.append({
                    "category": "mep",
                    "priority": "high",
                    "question": "Please identify and label all MEP equipment, pipes, ducts, and electrical components.",
                    "details": "MEP element identification is necessary for calculating equipment and installation quantities.",
                    "suggested_action": "Label all equipment with reference numbers and indicate pipe/duct routing"
                })
            
            if "missing_equipment_specifications" in issues:
                queries.append({
                    "category": "mep",
                    "priority": "medium",
                    "question": "Could you provide equipment specifications including capacities, sizes, and ratings?",
                    "details": "Equipment specifications are needed for accurate material and installation cost calculations.",
                    "suggested_action": "Add equipment schedules or notes with capacities, sizes, and electrical ratings"
                })
        
        elif drawing_type == DrawingType.SITE:
            if "missing_site_levels" in issues:
                queries.append({
                    "category": "site",
                    "priority": "high",
                    "question": "Please add elevation markers and contour lines showing existing and proposed site levels.",
                    "details": "Site levels are essential for calculating earthwork quantities (cut and fill volumes).",
                    "suggested_action": "Add spot levels, contour lines, and indicate finished floor levels"
                })
            
            if "insufficient_site_dimensions" in issues:
                queries.append({
                    "category": "site",
                    "priority": "high",
                    "question": "Could you provide boundary dimensions, setbacks, and key site measurements?",
                    "details": "Site dimensions are needed for calculating areas, perimeters, and positioning elements.",
                    "suggested_action": "Dimension property boundaries, building setbacks, and major site features"
                })
        
        return queries
