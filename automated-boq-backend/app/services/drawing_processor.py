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
from .geometric_room_detector import GeometricRoomDetector

logger = logging.getLogger(__name__)

class DrawingProcessor:
    def __init__(self):
        self.easyocr_reader = easyocr.Reader(['en'])
        self.geometric_room_detector = GeometricRoomDetector()
        
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
                'drawing_type': None,
                'room_types': {}
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
                
                try:
                    detected_rooms = self.geometric_room_detector.detect_rooms(temp_path, page_num)
                    if detected_rooms:
                        for room in detected_rooms:
                            if room['label'] and not room['is_external']:
                                room_name = room['label'].strip()
                                results['room_types'][room_name] = {
                                    'polygon': room['polygon'],
                                    'area': room['area'],
                                    'page': page_num
                                }
                        logger.info(f"Geometric room detection found {len(detected_rooms)} rooms on page {page_num}")
                    else:
                        logger.warning(f"No rooms detected geometrically on page {page_num}")
                except Exception as e:
                    logger.warning(f"Geometric room detection failed on page {page_num}: {e}")
                    if 'room_types' in page_results:
                        results['room_types'].update(page_results.get('room_types', {}))
            
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
                'drawing_type': None,
                'room_types': {}
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
            
            try:
                detected_rooms = self.geometric_room_detector.detect_rooms(temp_path)
                if detected_rooms:
                    for room in detected_rooms:
                        if room['label'] and not room['is_external']:
                            room_name = room['label'].strip()
                            results['room_types'][room_name] = {
                                'polygon': room['polygon'],
                                'area': room['area'],
                                'source': 'geometric'
                            }
                    logger.info(f"Geometric room detection found {len(detected_rooms)} rooms in DXF/DWG")
                else:
                    logger.warning(f"No rooms detected geometrically in DXF/DWG file")
            except Exception as e:
                logger.warning(f"Geometric room detection failed for DXF/DWG: {e}")
            
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
                    
                    
                    if re.search(r'render|rendered|external\s+render', text_lower):
                        if "wall_finishes" not in results:
                            results["wall_finishes"] = {}
                        results["wall_finishes"]["Render"] = bbox_converted
                    elif re.search(r'stone|natural\s+stone|stone\s+cladding', text_lower):
                        if "wall_finishes" not in results:
                            results["wall_finishes"] = {}
                        results["wall_finishes"]["Stone"] = bbox_converted
                    elif re.search(r'brick|brickwork|brick\s+wall', text_lower):
                        if "wall_finishes" not in results:
                            results["wall_finishes"] = {}
                        results["wall_finishes"]["Brick"] = bbox_converted
                    elif re.search(r'block|blockwork|concrete\s+block', text_lower):
                        if "wall_finishes" not in results:
                            results["wall_finishes"] = {}
                        results["wall_finishes"]["Block"] = bbox_converted
                    
                    if re.search(r'ground\s+floor|gf\s+plan|ground\s+level', text_lower):
                        if "floor_plans" not in results:
                            results["floor_plans"] = {}
                        results["floor_plans"]["Ground Floor"] = bbox_converted
                    elif re.search(r'first\s+floor|ff\s+plan|upper\s+floor', text_lower):
                        if "floor_plans" not in results:
                            results["floor_plans"] = {}
                        results["floor_plans"]["First Floor"] = bbox_converted
                    elif re.search(r'bungalow|single\s+storey|one\s+storey', text_lower):
                        if "floor_plans" not in results:
                            results["floor_plans"] = {}
                        results["floor_plans"]["Bungalow"] = bbox_converted
                    
                    if self._is_dimension_text(text):
                        results['dimensions'].append({
                            'text': text,
                            'bbox': bbox_converted,
                            'value': self._extract_dimension_value(text)
                        })
                        
            if "room_types" not in results:
                results["room_types"] = {}
            if "wall_finishes" not in results:
                results["wall_finishes"] = {}
            if "floor_plans" not in results:
                results["floor_plans"] = {}
            results['building_types'] = building_types
        except Exception as e:
            logger.warning(f"OCR failed: {str(e)}")
        
        title_block_info = self._extract_title_block_info(results['text_annotations'])
        results['title_block_info'] = title_block_info
        
        detected_scale = self._detect_scale(results['text_annotations'])
        dimension_calibration = self._detect_dimension_calibration(results['text_annotations'], image.shape)
        
        if detected_scale:
            results['scale_info'] = detected_scale
            results['scale'] = detected_scale
            scale_factor = self._calculate_scale_factor(detected_scale)
            results['scale_factor'] = scale_factor
            results['calibration_method'] = 'scale_annotation'
        elif dimension_calibration:
            results['scale_info'] = f"Calibrated from {dimension_calibration['text']}"
            results['scale'] = f"1:{dimension_calibration['mm_per_pixel']:.1f}"
            results['scale_factor'] = dimension_calibration['mm_per_pixel']
            results['calibration_method'] = 'dimension_annotation'
            results['calibration_details'] = dimension_calibration
        else:
            results['scale_info'] = None
            results['scale'] = None
            results['scale_factor'] = None
            results['calibration_method'] = None
        
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

    def _extract_dimension_value(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract numeric value and unit from dimension text"""
        import re
        
        dimension_patterns = [
            r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(mm|millimeters?)',  # "5,000 mm" or "5000.5 mm"
            r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(m|meters?)',       # "5.5 m" or "5 meters"
            r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(cm|centimeters?)', # "550 cm"
            r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(ft|feet)',         # "16 ft"
            r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(in|inches?)',      # "192 in"
            r'(\d+(?:,\d{3})*(?:\.\d+)?)',                     # Plain numbers
        ]
        
        for pattern in dimension_patterns:
            match = re.search(pattern, text.lower())
            if match:
                value_str = match.group(1).replace(',', '')  # Remove commas
                value = float(value_str)
                unit = match.group(2) if len(match.groups()) > 1 else None
                
                if unit in ['m', 'meter', 'meters']:
                    value_mm = value * 1000
                elif unit in ['cm', 'centimeter', 'centimeters']:
                    value_mm = value * 10
                elif unit in ['ft', 'feet']:
                    value_mm = value * 304.8
                elif unit in ['in', 'inch', 'inches']:
                    value_mm = value * 25.4
                else:  # mm or no unit
                    value_mm = value
                
                return {
                    'value': value,
                    'unit': unit or 'mm',
                    'value_mm': value_mm,
                    'original_text': text
                }
        
        return None

    def _detect_scale(self, text_annotations: List[Dict]) -> Optional[str]:
        """Detect drawing scale from OCR text annotations using pattern recognition"""
        import re
        
        all_text = ' '.join([ann.get('text', '') for ann in text_annotations])
        
        scale_patterns = [
            r'scale\s*[:\-=]?\s*1[:|/]\s*(\d+)',     # "Scale: 1:50" or "Scale 1/100"
            r'1[:|/]\s*(\d+)',                        # Direct "1:50" or "1/100"
            r'scale\s*1\s*:\s*(\d+)',                 # "Scale 1 : 50"
            r'@\s*1[:|/]\s*(\d+)',                    # "@1:50" format
            r'(?:^|\s)1[:|/](\d+)(?:\s|$)',          # Standalone scale ratios
        ]
        
        for pattern in scale_patterns:
            match = re.search(pattern, all_text, re.IGNORECASE)
            if match:
                scale_value = int(match.group(1))
                if scale_value > 0:  # Any positive scale is valid (1:1250, 1:anything)
                    return f"1:{scale_value}"
        
        return None
    
    def _calculate_scale_factor(self, scale_string: str) -> Optional[float]:
        """Calculate scale factor for pixel-to-real-world conversion"""
        if not scale_string:
            return None
            
        import re
        match = re.search(r'1[:|/](\d+)', scale_string)
        if match:
            return float(match.group(1))
        return None
    
    def _detect_dimension_calibration(self, text_annotations: List[Dict], image_shape: tuple) -> Optional[Dict[str, Any]]:
        """Detect dimension-based calibration using OCR measurements"""
        import re
        
        calibration_candidates = []
        
        for ann in text_annotations:
            text = ann.get('text', '').strip()
            if not text:
                continue
                
            dimension_info = self._extract_dimension_value(text)
            if dimension_info and dimension_info['value_mm'] > 100:  # Reasonable minimum size
                
                bbox = ann.get('bbox')
                if bbox:
                    try:
                        if isinstance(bbox[0], (list, tuple)):
                            pixel_length = self._calculate_polygon_perimeter([coord for point in bbox for coord in point]) / 4
                        elif len(bbox) == 4 and all(isinstance(x, (int, float)) for x in bbox):
                            # Standard format: [x1, y1, x2, y2]
                            pixel_length = max(abs(bbox[2] - bbox[0]), abs(bbox[3] - bbox[1]))
                        elif len(bbox) >= 6:
                            pixel_length = self._calculate_polygon_perimeter(bbox) / 4
                        else:
                            continue  # Skip invalid bbox formats
                    except (TypeError, IndexError, ValueError):
                        continue  # Skip problematic bbox data
                    
                    if pixel_length > 10:  # Minimum pixel size
                        mm_per_pixel = dimension_info['value_mm'] / pixel_length
                        
                        calibration_candidates.append({
                            'dimension_mm': dimension_info['value_mm'],
                            'pixel_length': pixel_length,
                            'mm_per_pixel': mm_per_pixel,
                            'confidence': ann.get('confidence', 0.8),
                            'text': text,
                            'method': 'dimension_annotation'
                        })
        
        if calibration_candidates:
            valid_candidates = [c for c in calibration_candidates if 0.1 <= c['mm_per_pixel'] <= 100]
            if valid_candidates:
                best_candidate = max(valid_candidates, key=lambda x: x['confidence'])
                return best_candidate
        
        return None
    
    def _calculate_polygon_perimeter(self, polygon_points: List) -> float:
        """Calculate perimeter of polygon for dimension estimation"""
        if len(polygon_points) < 6:  # Need at least 3 points (x,y pairs)
            return 0
        
        perimeter = 0
        points = [(polygon_points[i], polygon_points[i+1]) for i in range(0, len(polygon_points), 2)]
        
        for i in range(len(points)):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % len(points)]
            perimeter += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        
        return perimeter

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
        
        if not scale_info:
            quality_issues.append("no_scale_detected")
            missing_info.append("drawing_scale")
        else:
            scale_factor = self._calculate_scale_factor(scale_info)
            if not scale_factor or scale_factor <= 0:
                quality_issues.append("invalid_scale_detected")
                missing_info.append("valid_drawing_scale")
        
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

    def _generate_architect_queries(self, quality_issues: List[str], filename: str, confidence_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Generate professional queries for architects/engineers"""
        queries = []
        issues = quality_issues
        
        general_queries = self._get_general_queries(issues)
        queries.extend(general_queries)
        
        for query in queries:
            query['drawing_filename'] = filename
        
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
        
        if "invalid_scale_detected" in issues:
            queries.append({
                "category": "scale",
                "priority": "medium",
                "question": "Please verify the drawing scale is correct for accurate measurements.",
                "details": "An unusual scale was detected that may affect measurement accuracy.",
                "suggested_action": "Confirm the scale notation is correct and matches the drawing content"
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

    def _extract_title_block_info(self, text_annotations: List[Dict]) -> Dict[str, Any]:
        """Extract title block information from OCR text annotations"""
        import re
        from datetime import datetime
        
        title_block_info = {
            'drawing_number': None,
            'drawing_title': None,
            'revision_number': None,
            'revision_date': None,
            'project_name': None,
            'project_number': None
        }
        
        all_text = ' '.join([ann.get('text', '') for ann in text_annotations])
        
        title_block_texts = []
        for ann in text_annotations:
            text = ann.get('text', '').strip()
            if text:
                title_block_texts.append(text)
        
        title_block_text = ' '.join(title_block_texts)
        
        drawing_number_patterns = [
            r'(?:drawing\s*[:\-=]\s*)([A-Z0-9\-/\.]+)',  # "DRAWING: ABC123" or "DRAWING= ABC123"
            r'(?:dwg\.?\s*[:\-=]\s*)([A-Z0-9\-/\.]+)',   # "DWG: ABC123" or "DWG= ABC123"
            r'(?:sheet\s*[:\-=]\s*)([A-Z0-9\-/\.]+)',    # "SHEET: ABC123" or "SHEET= ABC123"
            r'(?:drawing\s+(?:no\.?|number)\s*[:\-=]?\s*)([A-Z0-9\-/\.]+)',
            r'(?:dwg\.?\s+(?:no\.?|#)\s*[:\-=]?\s*)([A-Z0-9\-/\.]+)',
            r'(?:sheet\s+(?:no\.?|number)\s*[:\-=]?\s*)([A-Z0-9\-/\.]+)',
            r'([A-Z]{1,3}[0-9]{2,4}[A-Z]?)',  # Common format like A101, SK-001
            r'([0-9]{3,4}[A-Z]?)',  # Simple numeric like 001A
        ]
        
        for pattern in drawing_number_patterns:
            match = re.search(pattern, title_block_text, re.IGNORECASE)
            if match:
                title_block_info['drawing_number'] = match.group(1).strip()
                break
        
        title_patterns = [
            r'(?:title\s*[:\-=]\s*)([A-Za-z0-9\s\-,\.&()]+?)(?:\s*$|\s+(?:scale|date|rev|drawing))',
            r'(?:project\s*[:\-=]\s*)([A-Za-z0-9\s\-,\.&()]+?)(?:\s*$|\s+(?:scale|date|rev|drawing))',
            r'(?:description\s*[:\-=]\s*)([A-Za-z0-9\s\-,\.&()]+?)(?:\s*$|\s+(?:scale|date|rev|drawing))',
            r'(?:job\s*[:\-=]\s*)([A-Za-z0-9\s\-,\.&()]+?)(?:\s*$|\s+(?:scale|date|rev|drawing))',
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, title_block_text, re.IGNORECASE)
            if match:
                title_block_info['drawing_title'] = match.group(1).strip()
                break
        
        revision_patterns = [
            r'(?:revision\s*[:\-=]\s*)([A-Z0-9]+)',      # "Revision: A" or "Revision= A"
            r'(?:rev\.?\s*[:\-=]\s*)([A-Z0-9]+)',        # "Rev: A" or "Rev= A"
            r'\b([A-Z])\s*(?:rev|revision)',         # Single letter revisions
            r'(?:issue\s*[:\-=]\s*)([A-Z0-9]+)',         # "Issue: 1" or "Issue= 1"
            r'(?:^|\s)([A-Z])\s*$',                  # Single letter at end of line
        ]
        
        for pattern in revision_patterns:
            match = re.search(pattern, title_block_text, re.IGNORECASE)
            if match:
                title_block_info['revision_number'] = match.group(1).strip()
                break
        
        date_patterns = [
            r'(?:date\s*:?\s*)(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
            r'(?:dated?\s*:?\s*)(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
            r'(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, title_block_text, re.IGNORECASE)
            if match:
                try:
                    date_str = match.group(1)
                    for fmt in ['%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%m-%d-%Y', '%d.%m.%Y', '%m.%d.%Y']:
                        try:
                            parsed_date = datetime.strptime(date_str, fmt)
                            title_block_info['revision_date'] = parsed_date
                            break
                        except ValueError:
                            continue
                except:
                    pass
                break
        
        project_patterns = [
            r'(?:project\s*[=:\-]\s*)([A-Za-z0-9\s\-,\.&()]+?)(?:\s*$|\s+(?:drawing|dwg|sheet|rev))',  # "PROJECT= Name" or "PROJECT: Name"
            r'(?:client\s*[=:\-]\s*)([A-Za-z0-9\s\-,\.&()]+?)(?:\s*$|\s+(?:project|drawing))',
            r'(?:job\s*[=:\-]\s*)([A-Za-z0-9\s\-,\.&()]+?)(?:\s*$|\s+(?:drawing|dwg))',
            r'(?:for\s+)([A-Za-z0-9\s\-,\.&()]+?)(?:\s*$|\s+(?:drawing|dwg|sheet|rev))',  # "FOR Client Name"
        ]
        
        for pattern in project_patterns:
            match = re.search(pattern, all_text, re.IGNORECASE)
            if match:
                title_block_info['project_name'] = match.group(1).strip()
                break
        
        project_number_patterns = [
            r'(?:project\s+(?:no\.?|number)\s*[=:\-]?\s*)([A-Z0-9\-/]+)',
            r'(?:job\s+(?:no\.?|number)\s*[=:\-]?\s*)([A-Z0-9\-/]+)',
            r'(?:contract\s+(?:no\.?|number)\s*[=:\-]?\s*)([A-Z0-9\-/]+)',
            r'(?:ref\.?\s*[=:\-]?\s*)([A-Z0-9\-/]+)',  # "Ref: 12345" or "Ref= 12345"
            r'(?:reference\s*[=:\-]?\s*)([A-Z0-9\-/]+)',  # "Reference: 12345"
        ]
        
        for pattern in project_number_patterns:
            match = re.search(pattern, all_text, re.IGNORECASE)
            if match:
                title_block_info['project_number'] = match.group(1).strip()
                break
        
        return title_block_info
