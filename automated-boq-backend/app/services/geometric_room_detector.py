"""
Geometric Room Detection Service
Based on ChatGPT Option 2 - Refined Room Extraction Pipeline

Provides geometric room boundary detection from PDF and DXF drawings
to replace text-based OCR room detection limitations.
"""

import os
import math
from typing import List, Dict, Tuple, Optional, Any
from collections import defaultdict

import numpy as np
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import unary_union
import networkx as nx

class GeometricRoomDetector:
    """
    Geometric room detection using line segment extraction and planar graph analysis.
    Supports DXF (CAD), vector PDF, and raster PDF (scanned) formats.
    """
    
    def __init__(self):
        self.snap_tolerance = 1.0
        self.min_room_area = 100.0
        self.raster_dpi = 300
    
    def detect_rooms(self, file_path: str, page_no: int = 0) -> List[Dict[str, Any]]:
        """
        Main entry point for room detection.
        
        Returns: List of room dictionaries with:
        {
            'polygon': [(x1,y1), (x2,y2), ...],  # room boundary coordinates
            'area': float,                        # room area in drawing units
            'label': str or None,                 # detected room label
            'is_external': bool                   # whether this is external boundary
        }
        """
        try:
            ext = os.path.splitext(file_path)[1].lower()
            
            walls, labels = [], []
            
            if ext == '.dxf':
                walls, labels = self._extract_from_dxf(file_path)
            elif ext == '.pdf':
                try:
                    walls, labels = self._extract_from_vector_pdf(file_path, page_no)
                    if not walls:
                        walls, labels = self._extract_from_raster_pdf(file_path, page_no)
                except Exception:
                    walls, labels = self._extract_from_raster_pdf(file_path, page_no)
            else:
                raise ValueError(f"Unsupported file format: {ext}")
            
            if not walls:
                return []
            
            graph = self._build_planar_graph(walls)
            
            polygons = self._find_face_cycles(graph)
            
            if not polygons:
                return []
            
            rooms = self._associate_labels_to_polygons(polygons, labels)
            
            rooms = [r for r in rooms if r['area'] >= self.min_room_area]
            
            return rooms
            
        except Exception as e:
            print(f"Room detection error: {e}")
            return []
    
    def _snap_point(self, point: Tuple[float, float]) -> Tuple[float, float]:
        """Snap point to grid to merge near-duplicate vertices."""
        x, y = point
        return (
            round(x / self.snap_tolerance) * self.snap_tolerance,
            round(y / self.snap_tolerance) * self.snap_tolerance
        )
    
    def _normalize_polygon_coords(self, coords: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Normalize polygon coordinates, removing duplicate endpoints."""
        pts = [(float(x), float(y)) for x, y in coords]
        if len(pts) > 1 and pts[0] == pts[-1]:
            pts = pts[:-1]
        return pts
    
    def _extract_from_dxf(self, path: str) -> Tuple[List[Tuple[Tuple[float,float],Tuple[float,float]]], List[Dict]]:
        """Extract wall segments and text from DXF file using ezdxf."""
        try:
            import ezdxf
        except ImportError:
            raise ImportError("ezdxf required for DXF files. Install with: pip install ezdxf")
        
        doc = ezdxf.readfile(path)
        msp = doc.modelspace()
        
        walls = []
        labels = []
        
        for entity in msp.query('LINE'):
            p1 = (entity.dxf.start.x, entity.dxf.start.y)
            p2 = (entity.dxf.end.x, entity.dxf.end.y)
            walls.append((self._snap_point(p1), self._snap_point(p2)))
        
        for entity in msp.query('LWPOLYLINE POLYLINE'):
            try:
                pts = list(entity.get_points()) if hasattr(entity, 'get_points') else list(entity.points())
                coords = [(float(p[0]), float(p[1])) for p in pts]
                for a, b in zip(coords, coords[1:]):
                    walls.append((self._snap_point(a), self._snap_point(b)))
            except Exception:
                continue
        
        for entity in msp.query('TEXT MTEXT'):
            try:
                x = float(entity.dxf.insert.x)
                y = float(entity.dxf.insert.y)
                text = entity.plain_text() if hasattr(entity, 'plain_text') else str(entity.dxf.text)
                labels.append({'text': text.strip(), 'pos': (x, y)})
            except Exception:
                continue
        
        return walls, labels
    
    def _extract_from_vector_pdf(self, path: str, page_no: int = 0) -> Tuple[List[Tuple[Tuple[float,float],Tuple[float,float]]], List[Dict]]:
        """Extract line segments and text from vector PDF using PyMuPDF."""
        try:
            import fitz
        except ImportError:
            raise ImportError("PyMuPDF required for PDF files. Install with: pip install pymupdf")
        
        doc = fitz.open(path)
        if page_no >= len(doc):
            raise IndexError('Page number out of range')
        
        page = doc[page_no]
        page_rect = page.mediabox
        height = page_rect.y1 - page_rect.y0
        
        walls = []
        labels = []
        
        for drawing in page.get_drawings():
            for item in drawing['items']:
                if item[0] == 'l':  # line command
                    p1 = item[1]
                    p2 = item[2]
                    a = (p1[0], height - p1[1])
                    b = (p2[0], height - p2[1])
                    walls.append((self._snap_point(a), self._snap_point(b)))
        
        for block in page.get_text('blocks'):
            x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
            if text.strip():
                cx = (x0 + x1) / 2.0
                cy_pdf = (y0 + y1) / 2.0
                cy = height - cy_pdf  # Convert to Cartesian
                labels.append({'text': text.strip(), 'pos': self._snap_point((cx, cy))})
        
        return walls, labels
    
    def _extract_from_raster_pdf(self, path: str, page_no: int = 0) -> Tuple[List[Tuple[Tuple[float,float],Tuple[float,float]]], List[Dict]]:
        """Extract lines and text from raster PDF using OpenCV and Tesseract."""
        try:
            import cv2
            from pdf2image import convert_from_path
            import pytesseract
        except ImportError:
            raise ImportError("opencv-python, pdf2image, pytesseract required for raster PDF. Install with: pip install opencv-python-headless pdf2image pytesseract")
        
        images = convert_from_path(path, dpi=self.raster_dpi)
        if page_no >= len(images):
            raise IndexError('Page number out of range')
        
        pil_img = images[page_no].convert('RGB')
        img = np.array(pil_img)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        
        bin_img = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY_INV, 15, 9)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        closed = cv2.morphologyEx(bin_img, cv2.MORPH_CLOSE, kernel, iterations=2)
        
        lines = cv2.HoughLinesP(closed, rho=1, theta=np.pi/180, threshold=80, 
                               minLineLength=30, maxLineGap=10)
        
        walls = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                h = img.shape[0]
                a = (float(x1), float(h - y1))
                b = (float(x2), float(h - y2))
                walls.append((self._snap_point(a), self._snap_point(b)))
        
        ocr_data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
        labels = []
        n = len(ocr_data['text'])
        h = img.shape[0]
        
        for i in range(n):
            text = ocr_data['text'][i].strip()
            if text:
                x = ocr_data['left'][i]
                y = ocr_data['top'][i]
                w = ocr_data['width'][i]
                hh = ocr_data['height'][i]
                cx = x + w / 2.0
                cy = y + hh / 2.0
                labels.append({'text': text, 'pos': self._snap_point((cx, h - cy))})
        
        return walls, labels
    
    def _build_planar_graph(self, walls: List[Tuple[Tuple[float,float],Tuple[float,float]]]) -> nx.Graph:
        """Build undirected graph from wall line segments."""
        graph = nx.Graph()
        
        for a, b in walls:
            a_snapped = self._snap_point(a)
            b_snapped = self._snap_point(b)
            
            if a_snapped == b_snapped:
                continue
                
            graph.add_node(a_snapped)
            graph.add_node(b_snapped)
            graph.add_edge(a_snapped, b_snapped, geometry=LineString([a_snapped, b_snapped]))
        
        return graph
    
    def _find_face_cycles(self, graph: nx.Graph) -> List[Polygon]:
        """Find closed polygonal faces using shapely polygonize."""
        edge_geometries = [data['geometry'] for u, v, data in graph.edges(data=True) 
                          if 'geometry' in data]
        
        if not edge_geometries:
            return []
        
        merged = unary_union(edge_geometries)
        
        try:
            from shapely.ops import polygonize
            polygons = list(polygonize(merged))
        except Exception:
            return []
        
        valid_polygons = [p for p in polygons 
                         if p.is_valid and p.area >= self.min_room_area]
        
        valid_polygons.sort(key=lambda p: p.area, reverse=True)
        
        return valid_polygons
    
    def _associate_labels_to_polygons(self, polygons: List[Polygon], 
                                    labels: List[Dict]) -> List[Dict[str, Any]]:
        """Associate text labels with room polygons."""
        results = []
        
        for polygon in polygons:
            results.append({
                'polygon': polygon,
                'area': polygon.area,
                'label': None,
                'is_external': False
            })
        
        for label in labels:
            point = Point(label['pos'])
            
            containing = [r for r in results if r['polygon'].contains(point)]
            
            if containing:
                chosen = min(containing, key=lambda r: r['area'])
                if chosen['label']:
                    chosen['label'] += ' | ' + label['text']
                else:
                    chosen['label'] = label['text']
        
        if results:
            largest = max(results, key=lambda r: r['area'])
            largest['is_external'] = True
        
        output = []
        for result in results:
            coords = self._normalize_polygon_coords(result['polygon'].exterior.coords[:])
            output.append({
                'polygon': coords,
                'area': result['area'],
                'label': result['label'],
                'is_external': result['is_external']
            })
        
        return output
