from typing import List, Dict, Any, Optional
from ..models import BOQItem, TradePackage, Project
from ..schemas import TradePackageResponse, TradePackageDetailResponse
from datetime import datetime, timedelta

class TradePackageGenerator:
    def __init__(self):
        self.trade_definitions = {
            "structural": {
                "name": "Structural Works",
                "description": "Concrete, steel frame, foundations, and structural elements",
                "categories": ["concrete", "steel", "foundation", "structural"],
                "specialist_required": True
            },
            "electrical": {
                "name": "Electrical Installation",
                "description": "Electrical systems, wiring, outlets, and equipment",
                "categories": ["electrical", "lighting", "power"],
                "specialist_required": True
            },
            "plumbing": {
                "name": "Plumbing Works",
                "description": "Water supply, drainage, and plumbing fixtures",
                "categories": ["plumbing", "drainage", "water"],
                "specialist_required": True
            },
            "mechanical": {
                "name": "Mechanical Services",
                "description": "HVAC, ventilation, and mechanical equipment",
                "categories": ["hvac", "ventilation", "mechanical"],
                "specialist_required": True
            },
            "civil": {
                "name": "Civil Works",
                "description": "General construction, masonry, and civil works",
                "categories": ["masonry", "excavation", "civil", "earthwork"],
                "specialist_required": False
            },
            "drywall": {
                "name": "Drywall & Partitions",
                "description": "Interior partitions, drywall, and finishing",
                "categories": ["drywall", "partition", "interior"],
                "specialist_required": False
            },
            "flooring": {
                "name": "Flooring & Finishes",
                "description": "Floor finishes, tiles, and surface treatments",
                "categories": ["flooring", "finishes", "tiles"],
                "specialist_required": False
            }
        }

    def generate_trade_packages(self, project: Project, boq_items: List[BOQItem]) -> List[TradePackage]:
        """Generate trade packages from BOQ items"""
        trade_packages = []
        
        items_by_trade = self._group_items_by_trade(boq_items)
        
        for trade_key, items in items_by_trade.items():
            if items:  # Only create packages for trades that have items
                trade_def = self.trade_definitions.get(trade_key, {
                    "name": trade_key.title(),
                    "description": f"{trade_key.title()} works",
                    "specialist_required": True
                })
                
                estimated_value = self._calculate_estimated_value(items)
                
                trade_package = TradePackage(
                    project_id=project.id,
                    trade_name=trade_key,
                    trade_description=trade_def["description"],
                    boq_items=items,
                    total_estimated_value=estimated_value,
                    specialist_required=trade_def.get("specialist_required", True),
                    bidding_deadline=datetime.utcnow() + timedelta(days=14)  # 2 weeks default
                )
                
                trade_packages.append(trade_package)
        
        return trade_packages

    def _group_items_by_trade(self, boq_items: List[BOQItem]) -> Dict[str, List[BOQItem]]:
        """Group BOQ items by their trade classification"""
        items_by_trade = {}
        
        for item in boq_items:
            trade = item.trade.lower()
            
            if item.category.lower() in ["drywall", "partition", "interior"]:
                trade = "drywall"
            elif item.category.lower() in ["flooring", "finishes", "tiles"]:
                trade = "flooring"
            elif item.category.lower() in ["hvac", "ventilation", "mechanical"]:
                trade = "mechanical"
            
            if trade not in items_by_trade:
                items_by_trade[trade] = []
            
            items_by_trade[trade].append(item)
        
        return items_by_trade

    def _calculate_estimated_value(self, items: List[BOQItem]) -> float:
        """Calculate estimated value for trade package (placeholder rates)"""
        rate_estimates = {
            "structural": {"m³": 250, "m²": 45, "nr": 150, "m": 25},
            "electrical": {"m": 15, "nr": 35, "m²": 20},
            "plumbing": {"m": 20, "nr": 85, "m²": 30},
            "mechanical": {"m": 30, "nr": 200, "m²": 40},
            "civil": {"m³": 180, "m²": 35, "nr": 100, "m": 20},
            "drywall": {"m²": 25, "m": 15, "nr": 50},
            "flooring": {"m²": 40, "m": 10, "nr": 30}
        }
        
        total_value = 0
        for item in items:
            trade_rates = rate_estimates.get(item.trade.lower(), {"m³": 200, "m²": 30, "nr": 100, "m": 20})
            unit_rate = trade_rates.get(item.unit.lower(), 50)  # Default rate
            total_value += item.quantity * unit_rate
        
        return round(total_value, 2)

    def get_trade_package_summary(self, trade_package: TradePackage) -> TradePackageResponse:
        """Get summary response for a trade package"""
        return TradePackageResponse(
            id=trade_package.id,
            project_id=trade_package.project_id,
            trade_name=trade_package.trade_name,
            trade_description=trade_package.trade_description,
            items_count=len(trade_package.boq_items),
            total_estimated_value=trade_package.total_estimated_value,
            specialist_required=trade_package.specialist_required,
            status=trade_package.status,
            created_at=trade_package.created_at,
            bidding_deadline=trade_package.bidding_deadline
        )

    def get_trade_package_detail(self, trade_package: TradePackage) -> TradePackageDetailResponse:
        """Get detailed response for a trade package"""
        from ..schemas import BOQItemResponse
        
        boq_item_responses = [
            BOQItemResponse(
                id=item.id,
                project_id=item.project_id,
                drawing_id=item.drawing_id,
                item_code=item.item_code,
                description=item.description,
                unit=item.unit,
                quantity=item.quantity,
                category=item.category,
                trade=item.trade,
                measurement_standard=item.measurement_standard,
                notes=item.notes,
                created_at=item.created_at
            ) for item in trade_package.boq_items
        ]
        
        return TradePackageDetailResponse(
            id=trade_package.id,
            project_id=trade_package.project_id,
            trade_name=trade_package.trade_name,
            trade_description=trade_package.trade_description,
            boq_items=boq_item_responses,
            total_estimated_value=trade_package.total_estimated_value,
            specialist_required=trade_package.specialist_required,
            status=trade_package.status,
            created_at=trade_package.created_at,
            bidding_deadline=trade_package.bidding_deadline
        )
