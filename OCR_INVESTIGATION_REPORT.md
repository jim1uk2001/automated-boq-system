# OCR Drawing Metadata Detection Investigation Report

## Executive Summary

The Bojim BOQ Production Software's OCR system is successfully detecting text from construction drawings, but drawing metadata (numbers, titles, revisions) is not being extracted due to a **regex pattern mismatch** between expected formats and actual drawing layouts.

## Investigation Methodology

1. **OCR Testing**: Analyzed all three house drawings using EasyOCR
2. **Text Pattern Analysis**: Examined detected text fragments and their relationships  
3. **Regex Pattern Testing**: Tested current extraction patterns against actual OCR output
4. **Root Cause Identification**: Identified format mismatch as primary issue

## Key Findings

### ✅ OCR Detection is Working Correctly

**house_elevations.pdf**:
- Total OCR results: 95 text fragments
- Title block keywords detected: 13 matches
- High confidence scores (0.66-1.00)

**house_floor_plans.pdf**:
- Total OCR results: 94 text fragments  
- Title block keywords detected: 11 matches
- High confidence scores (0.41-1.00)

**house_site_plan.pdf**:
- Total OCR results: 186 text fragments
- Title block keywords detected: 9 matches
- High confidence scores (0.64-1.00)

### ❌ Regex Pattern Mismatch

**Current Patterns Expect**:
```
"Drawing: ABC123"
"Title: Project Name"  
"Rev: A"
"Project: Client Name"
```

**Actual Drawing Format**:
```
"Drawing Title" → "Elevations" (separate fragments)
"Drawing No_" → "PLOO4" (separate fragments)
"Project" → "Dwelling House at 43 Orchard Grove, 8 Ballyraine, Letterkenny, Co. Donegal for Eamonn & Claire McEldowney" (separate fragments)
"Rev" → [value in next fragment]
```

## Specific Detection Results

### house_elevations.pdf
- **Drawing Title**: "Elevations" ✅ (detected but not matched by regex)
- **Drawing Number**: "PLOO4" ✅ (detected but not matched by regex)  
- **Project**: "Dwelling House at 43 Orchard Grove, 8 Ballyraine, Letterkenny, Co. Donegal for Eamonn & Claire McEldowney" ✅ (detected but not matched by regex)
- **Scale**: "1:100" ✅ (detected multiple times)

### house_floor_plans.pdf  
- **Drawing Title**: "Ground Floor & First Floor" ✅ (detected but not matched by regex)
- **Drawing Number**: "PLO03" ✅ (detected but not matched by regex)
- **Scale**: "1:100" ✅ (detected multiple times)

### house_site_plan.pdf
- **Drawing Title**: "Site Layout Plan" ✅ (detected but not matched by regex)  
- **Project**: "Dwelling House at 43 Orchard Grove" ✅ (detected but not matched by regex)
- **Scale**: "1:250" ✅ (detected)

## Current Regex Patterns Analysis

**File**: `automated-boq-backend/app/services/drawing_processor.py`
**Method**: `_extract_title_block_info()`

### Drawing Number Patterns (Lines 841-850)
```python
drawing_number_patterns = [
    r'(?:drawing\s*[:\-=]\s*)([A-Z0-9\-/\.]+)',  # Expects "DRAWING: ABC123"
    r'(?:dwg\.?\s*[:\-=]\s*)([A-Z0-9\-/\.]+)',   # Expects "DWG: ABC123"  
    r'(?:sheet\s*[:\-=]\s*)([A-Z0-9\-/\.]+)',    # Expects "SHEET: ABC123"
    # ... more patterns expecting colon/equals format
]
```

**Problem**: These patterns look for "Label: Value" but actual text is "Drawing No_" followed by "PLOO4" in separate OCR fragments.

### Title Patterns (Lines 858-863)
```python
title_patterns = [
    r'(?:title\s*[:\-=]\s*)([A-Za-z0-9\s\-,\.&()]+?)(?:\s*$|\s+(?:scale|date|rev|drawing))',
    # ... more patterns expecting colon format
]
```

**Problem**: These patterns expect "Title: Project Name" but actual text is "Drawing Title" followed by "Elevations" in separate fragments.

## Proposed Solution Architecture

### 1. Proximity-Based Matching
When "Drawing Title" is detected, examine the next 2-3 OCR fragments for the title value:
```
"Drawing Title" → look ahead → "Elevations" = MATCH
```

### 2. Sequential Pattern Recognition  
Detect title block table structure where labels are followed by values:
```
Fragment[i]: "Drawing No_"
Fragment[i+1]: "Drawn By" 
Fragment[i+2]: "PLOO4"
→ Extract "PLOO4" as drawing number
```

### 3. Context-Aware Extraction
Use spatial/sequential relationships between OCR fragments:
```
"Project" → "Dwelling House at 43 Orchard Grove," → "8" → "Ballyraine, Letterkenny," → "Co. Donegal"
→ Combine into full project name
```

### 4. Hybrid Approach
Keep existing regex patterns for traditional "Label: Value" drawings while adding proximity-based matching for table-format title blocks.

## Implementation Requirements

### Enhanced `_extract_title_block_info()` Method

1. **Add proximity matching logic**:
   - When title block keywords are found, examine following fragments
   - Use confidence scores to validate matches
   - Handle multi-fragment values (like long project names)

2. **Improve pattern robustness**:
   - Add patterns for table-format title blocks
   - Handle variations in spacing and punctuation
   - Support both "Drawing No:" and "Drawing No_" formats

3. **Add fallback mechanisms**:
   - If proximity matching fails, try existing regex patterns
   - Use multiple detection strategies for reliability

### Code Structure Changes Needed

```python
def _extract_title_block_info(self, text_annotations: List[Dict]) -> Dict[str, Any]:
    # Current regex-based extraction (keep as fallback)
    title_block_info = self._extract_with_regex_patterns(text_annotations)
    
    # New proximity-based extraction (primary method)
    proximity_info = self._extract_with_proximity_matching(text_annotations)
    
    # Merge results, prioritizing proximity matches
    return self._merge_extraction_results(title_block_info, proximity_info)

def _extract_with_proximity_matching(self, text_annotations: List[Dict]) -> Dict[str, Any]:
    # Implementation for table-format title blocks
    pass
```

## Testing Strategy

1. **Validate with house drawings**: Test enhanced extraction on all three house drawings
2. **Regression testing**: Ensure traditional "Label: Value" drawings still work  
3. **Edge case handling**: Test with various title block formats
4. **Confidence scoring**: Validate extraction accuracy with confidence thresholds

## Expected Outcomes

After implementing the proposed solution:

- **house_elevations.pdf**: Drawing Title="Elevations", Drawing No="PLOO4", Project="Dwelling House at 43 Orchard Grove..."
- **house_floor_plans.pdf**: Drawing Title="Ground Floor & First Floor", Drawing No="PLO03"  
- **house_site_plan.pdf**: Drawing Title="Site Layout Plan", Project="Dwelling House at 43 Orchard Grove"

This will resolve the "Not detected" issues in the drawing register and provide proper metadata for BOQ documentation.

## Risk Assessment

- **Low Risk**: Changes are additive (proximity matching + existing regex)
- **Backward Compatible**: Existing regex patterns remain as fallback
- **Testable**: Can validate against known drawing formats
- **Reversible**: Changes isolated to single method

## Conclusion

The OCR system is functioning correctly. The issue is purely in the text extraction patterns not matching the table-format title blocks used in modern architectural drawings. The proposed proximity-based matching solution will resolve this while maintaining compatibility with traditional drawing formats.
