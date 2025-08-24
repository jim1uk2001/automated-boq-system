from typing import List, Dict, Any
from ..models import Project, BOQItem, Drawing, MeasurementStandard
import math
from enum import Enum

class Currency(str, Enum):
    GBP = "GBP"  # British Pound - UK
    USD = "USD"  # US Dollar - US
    EUR = "EUR"  # Euro - Ireland
    AED = "AED"  # UAE Dirham - UAE

class CostEstimator:
    """Advanced cost estimation service for construction projects"""
    
    def __init__(self):
        self.hourly_rate = 45.0  # £45 per hour professional rate
        self.currency = Currency.GBP  # Default currency
        
        self.exchange_rates = {
            Currency.GBP: 1.0,      # British Pound (base)
            Currency.USD: 1.27,     # US Dollar
            Currency.EUR: 1.17,     # Euro
            Currency.AED: 4.67      # UAE Dirham
        }
        
        self.currency_symbols = {
            Currency.GBP: "£",
            Currency.USD: "$",
            Currency.EUR: "€",
            Currency.AED: "AED "
        }
        
        self.drawing_processing_hours = {
            "architectural": 2.5,
            "structural": 3.0,
            "mep": 2.0,
            "site": 1.5,
            "detail": 1.0
        }
        
        self.category_hours = {
            "excavation": 0.15,
            "concrete": 0.20,
            "masonry": 0.18,
            "steel": 0.25,
            "roofing": 0.22,
            "finishes": 0.12,
            "electrical": 0.18,
            "plumbing": 0.16,
            "hvac": 0.20,
            "general": 0.10
        }
        
        self.standard_multipliers = {
            MeasurementStandard.SMM7: 1.0,
            MeasurementStandard.RICS_NRM: 1.1,
            MeasurementStandard.CESMM: 1.2
        }

    def estimate_project_cost(self, project: Project, currency: Currency = Currency.GBP) -> Dict[str, Any]:
        """Calculate estimated cost and man-hours for project using advanced algorithms"""
        
        drawing_hours = self._calculate_drawing_hours(project.drawings)
        
        boq_hours = self._calculate_boq_hours(project.boq_items)
        
        standard_multiplier = self.standard_multipliers.get(project.measurement_standard, 1.0)
        
        total_hours = (drawing_hours + boq_hours) * standard_multiplier
        
        setup_hours = 2.0
        total_hours += setup_hours
        
        exchange_rate = self.exchange_rates.get(currency, 1.0)
        hourly_rate_converted = self.hourly_rate * exchange_rate
        total_cost = total_hours * hourly_rate_converted
        
        breakdown = {
            "manual_drawing_hours": drawing_hours,
            "manual_boq_hours": boq_hours,
            "setup_hours": setup_hours,
            "standard_multiplier": standard_multiplier,
            "total_hours": total_hours,
            "hourly_rate": hourly_rate_converted,
            "base_hourly_rate": self.hourly_rate,
            "currency": currency.value,
            "currency_symbol": self.currency_symbols[currency],
            "exchange_rate": exchange_rate,
            "total_cost": total_cost,
            "cost_breakdown": {
                "manual_drawing_analysis": drawing_hours * hourly_rate_converted * standard_multiplier,
                "manual_boq_preparation": boq_hours * hourly_rate_converted * standard_multiplier,
                "project_setup": setup_hours * hourly_rate_converted
            }
        }
        
        return breakdown

    def _calculate_drawing_hours(self, drawings: List[Drawing]) -> float:
        """Calculate hours needed for drawing processing and analysis"""
        total_hours = 0.0
        
        for drawing in drawings:
            drawing_type = drawing.drawing_type.value if drawing.drawing_type else "general"
            base_hours = self.drawing_processing_hours.get(drawing_type, 1.0)
            
            if drawing.file_type.lower() == "pdf":
                complexity_factor = 1.5
            elif drawing.file_type.lower() in ["dwg", "dxf"]:
                complexity_factor = 1.0
            else:
                complexity_factor = 1.2
            
            total_hours += base_hours * complexity_factor
        
        return total_hours

    def _calculate_boq_hours(self, boq_items: List[BOQItem]) -> float:
        """Calculate hours needed for BOQ generation and quantity takeoff"""
        total_hours = 0.0
        
        for item in boq_items:
            category = item.category.lower()
            base_hours = self.category_hours.get(category, 0.10)
            
            if item.quantity > 1000:
                quantity_factor = 1.3
            elif item.quantity > 100:
                quantity_factor = 1.1
            else:
                quantity_factor = 1.0
            
            total_hours += base_hours * quantity_factor
        
        return total_hours

    def generate_estimate_report(self, project: Project, currency: Currency = Currency.GBP) -> str:
        """Generate detailed cost estimate report for customer"""
        estimate = self.estimate_project_cost(project, currency)
        
        currency_symbol = estimate['currency_symbol']
        
        report = f"""
BOJIM BOQ PRODUCTION SOFTWARE - COST ESTIMATE
(Based on Manual Quantity Surveying Equivalent)

Project: {project.name}
Measurement Standard: {project.measurement_standard.value.upper()}
Currency: {estimate['currency']}
Date: {project.created_at.strftime('%Y-%m-%d')}

MANUAL DRAWING ANALYSIS EQUIVALENT:
- Number of drawings: {len(project.drawings)}
- Manual analysis hours: {estimate['manual_drawing_hours']:.2f}
- Cost: {currency_symbol}{estimate['cost_breakdown']['manual_drawing_analysis']:.2f}

MANUAL BOQ PREPARATION EQUIVALENT:
- Number of items: {len(project.boq_items)}
- Manual measurement hours: {estimate['manual_boq_hours']:.2f}
- Cost: {currency_symbol}{estimate['cost_breakdown']['manual_boq_preparation']:.2f}

PROJECT SETUP & COORDINATION:
- Setup & calibration hours: {estimate['setup_hours']:.2f}
- Cost: {currency_symbol}{estimate['cost_breakdown']['project_setup']:.2f}

COMPLEXITY ADJUSTMENT:
- Standard: {project.measurement_standard.value.upper()}
- Multiplier: {estimate['standard_multiplier']:.1f}x

CURRENCY CONVERSION:
- Base rate: £{estimate['base_hourly_rate']:.2f} GBP
- Exchange rate: {estimate['exchange_rate']:.2f}
- Converted rate: {currency_symbol}{estimate['hourly_rate']:.2f} {estimate['currency']}

TOTAL ESTIMATE:
- Total manual equivalent hours: {estimate['total_hours']:.2f}
- Professional hourly rate: {currency_symbol}{estimate['hourly_rate']:.2f}
- TOTAL COST: {currency_symbol}{estimate['total_cost']:.2f}

This estimate reflects the market rate for manual quantity surveying work.
Competitive pricing based on traditional methods while delivering faster results.
Supports multiple currencies: GBP (UK), USD (US), EUR (Ireland), AED (UAE).
"""
        return report
