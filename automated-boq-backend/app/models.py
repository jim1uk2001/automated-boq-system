from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import uuid

class DrawingType(str, Enum):
    ARCHITECTURAL = "architectural"
    STRUCTURAL = "structural"
    MEP = "mep"
    SITE = "site"
    DETAIL = "detail"

class MeasurementStandard(str, Enum):
    SMM7 = "SMM7"
    RICS_NRM = "RICS_NRM"
    CESMM = "CESMM"

class ProjectStatus(str, Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    READY_FOR_BIDDING = "ready_for_bidding"
    BIDDING_OPEN = "bidding_open"
    BIDDING_CLOSED = "bidding_closed"
    AWARDED = "awarded"

class DrawingStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"

class BidStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    EVALUATED = "evaluated"
    AWARDED = "awarded"
    REJECTED = "rejected"

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    name: str
    password: str
    role: str  # "client", "contractor", "admin"
    company: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Drawing(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    filename: str
    file_path: Optional[str] = None
    file_type: str  # "pdf", "dwg", "dxf"
    file_size: Optional[int] = None
    file_data: Optional[bytes] = Field(default=None, exclude=True)
    drawing_type: Optional[DrawingType] = None
    scale: Optional[str] = None
    revision: Optional[str] = None
    title: Optional[str] = None
    status: DrawingStatus = DrawingStatus.UPLOADED
    error_message: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    quality_score: Optional[int] = None
    architect_queries: List[Dict[str, Any]] = []
    quality_issues: List[str] = []
    processed_data: Optional[Dict[str, Any]] = None  # Store extracted elements, dimensions, text_annotations
    building_types: Optional[Dict[str, Any]] = None  # Store detected building types
    room_types: Optional[Dict[str, Any]] = None  # Store detected room types
    wall_finishes: Optional[Dict[str, Any]] = None  # Store detected wall finishes
    floor_plans: Optional[Dict[str, Any]] = None  # Store detected floor plan indicators

class BOQItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    drawing_id: Optional[str] = None
    item_code: str
    description: str
    unit: str
    quantity: float
    category: str  # "excavation", "concrete", "masonry", etc.
    trade: str  # "civil", "electrical", "plumbing", etc.
    measurement_standard: MeasurementStandard
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    client_id: str
    measurement_standard: MeasurementStandard
    status: ProjectStatus = ProjectStatus.DRAFT
    drawings: List[Drawing] = []
    boq_items: List[BOQItem] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    bidding_deadline: Optional[datetime] = None
    estimated_cost: Optional[float] = None
    estimated_man_hours: Optional[float] = None

class BidItem(BaseModel):
    boq_item_id: str
    rate: float
    total: float

class Bid(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    contractor_id: str
    contractor_name: str
    contractor_company: str
    items: List[BidItem]
    total_amount: float
    status: BidStatus = BidStatus.DRAFT
    rank: Optional[int] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class BidEvaluation(BaseModel):
    project_id: str
    bids: List[Bid]
    winning_bid_id: str
    evaluation_date: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None

class TradePackage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    trade_name: str  # "structural", "electrical", "plumbing", "mechanical", "civil", "drywall"
    trade_description: str
    boq_items: List[BOQItem] = []
    total_estimated_value: Optional[float] = None
    specialist_required: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    bidding_deadline: Optional[datetime] = None
    status: str = "draft"  # "draft", "open_for_bidding", "bidding_closed", "awarded"

class TradeBid(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trade_package_id: str
    project_id: str
    contractor_id: str
    contractor_name: str
    contractor_company: str
    trade_specialization: str
    items: List[BidItem]
    total_amount: float
    status: BidStatus = BidStatus.DRAFT
    rank: Optional[int] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ScheduledEmail(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    email_type: str  # "full_boq", "trade_package", "architect_queries"
    recipient_emails: List[str]
    subject: str
    send_datetime: datetime
    status: str = "scheduled"  # "scheduled", "sent", "failed", "cancelled"
    trade_package_id: Optional[str] = None
    custom_message: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
