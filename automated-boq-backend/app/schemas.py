from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from .models import DrawingType, MeasurementStandard, ProjectStatus, BidStatus

class UserCreate(BaseModel):
    email: str
    name: str
    password: str
    role: str
    company: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    company: Optional[str] = None
    created_at: datetime

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    measurement_standard: MeasurementStandard

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    measurement_standard: MeasurementStandard
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    bidding_deadline: Optional[datetime] = None
    drawings_count: int = 0
    boq_items_count: int = 0
    estimated_cost: Optional[float] = None
    estimated_man_hours: Optional[float] = None

class CostEstimateResponse(BaseModel):
    project_id: str
    total_hours: float
    total_cost: float
    hourly_rate: float
    drawing_processing_hours: float
    boq_generation_hours: float
    setup_hours: float
    standard_multiplier: float
    cost_breakdown: Dict[str, float]
    estimate_report: str

class DrawingUpload(BaseModel):
    project_id: str
    drawing_type: Optional[DrawingType] = None

class DrawingResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    file_type: str
    drawing_type: Optional[DrawingType] = None
    scale: Optional[float] = None
    processed: bool
    processing_status: str
    error_message: Optional[str] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    drawing_title: Optional[str] = None
    revision_number: Optional[str] = None
    revision_date: Optional[datetime] = None
    drawing_number: Optional[str] = None
    quality_score: Optional[int] = None
    architect_queries: List[Dict[str, Any]] = []
    quality_issues: List[str] = []

class ArchitectQueriesResponse(BaseModel):
    project_id: str
    drawing_id: str
    drawing_filename: str
    quality_score: int
    total_queries: int
    high_priority_queries: int
    queries_by_category: Dict[str, List[Dict[str, Any]]]
    formatted_query_list: str

class BOQItemResponse(BaseModel):
    id: str
    project_id: str
    drawing_id: Optional[str] = None
    item_code: str
    description: str
    unit: str
    quantity: float
    category: str
    trade: str
    measurement_standard: MeasurementStandard
    notes: Optional[str] = None
    created_at: datetime

class BidItemCreate(BaseModel):
    boq_item_id: str
    rate: float

class BidCreate(BaseModel):
    project_id: str
    items: List[BidItemCreate]

class BidResponse(BaseModel):
    id: str
    project_id: str
    contractor_id: str
    contractor_name: str
    contractor_company: str
    total_amount: float
    status: BidStatus
    rank: Optional[int] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime

class BidEvaluationResponse(BaseModel):
    project_id: str
    winning_bid_id: str
    winning_contractor: str
    winning_amount: float
    total_bids: int
    evaluation_date: datetime
    ranked_bids: List[Dict[str, Any]]

class ProcessingStatus(BaseModel):
    project_id: str
    total_drawings: int
    processed_drawings: int
    failed_drawings: int
    status: str
    progress_percentage: float

class TradePackageResponse(BaseModel):
    id: str
    project_id: str
    trade_name: str
    trade_description: str
    items_count: int
    total_estimated_value: Optional[float] = None
    specialist_required: bool
    status: str
    created_at: datetime
    bidding_deadline: Optional[datetime] = None

class TradePackageDetailResponse(BaseModel):
    id: str
    project_id: str
    trade_name: str
    trade_description: str
    boq_items: List[BOQItemResponse]
    total_estimated_value: Optional[float] = None
    specialist_required: bool
    status: str
    created_at: datetime
    bidding_deadline: Optional[datetime] = None

class TradeBidResponse(BaseModel):
    id: str
    trade_package_id: str
    project_id: str
    contractor_id: str
    contractor_name: str
    contractor_company: str
    trade_specialization: str
    total_amount: float
    status: BidStatus
    rank: Optional[int] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime

class TradeBidCreate(BaseModel):
    trade_package_id: str
    trade_specialization: str
    items: List[BidItemCreate]
