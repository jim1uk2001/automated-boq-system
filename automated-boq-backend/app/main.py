from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import List, Optional
import io
from datetime import datetime, timedelta

from .models import *
from .schemas import *
from .database import db
from .auth import *
from .services.drawing_processor import DrawingProcessor
from .services.boq_generator import BOQGenerator
from .services.excel_generator import ExcelGenerator
from .services.cost_estimator import CostEstimator, Currency
from .services.trade_package_generator import TradePackageGenerator
import io

app = FastAPI(
    title="Bojim BOQ Production Software",
    description="Automated construction procurement system with BOQ generation and bidding portal",
    version="1.0.0"
)

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

drawing_processor = DrawingProcessor()
boq_generator = BOQGenerator()
excel_generator = ExcelGenerator()
cost_estimator = CostEstimator()
trade_package_generator = TradePackageGenerator()

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "Bojim BOQ Production Software"}

@app.post("/auth/login")
async def login(email: str = Form(...), password: str = Form(...)):
    """Login endpoint"""
    user = db.get_user_by_email(email)
    if not user:
        role = "client" if "client" in email else "contractor"
        user = User(
            email=email,
            name=email.split("@")[0].title(),
            role=role,
            company=f"{role.title()} Company"
        )
        db.create_user(user)
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "user": user}

@app.post("/auth/register", response_model=UserResponse)
async def register(user_data: UserCreate):
    """Register new user"""
    existing_user = db.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(
        email=user_data.email,
        name=user_data.name,
        role=user_data.role,
        company=user_data.company
    )
    db.create_user(user)
    return user

@app.post("/projects", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_client)
):
    """Create a new project"""
    project = Project(
        name=project_data.name,
        description=project_data.description,
        client_id=current_user.id,
        measurement_standard=project_data.measurement_standard
    )
    db.create_project(project)
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        measurement_standard=project.measurement_standard,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        bidding_deadline=project.bidding_deadline
    )

@app.get("/projects", response_model=List[ProjectResponse])
async def get_projects(current_user: User = Depends(get_current_user)):
    """Get projects for current user"""
    if current_user.role == "client":
        projects = db.get_projects_by_client(current_user.id)
    else:
        projects = [p for p in db.projects.values() if p.status in [ProjectStatus.READY_FOR_BIDDING, ProjectStatus.BIDDING_OPEN]]
    
    return [
        ProjectResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            measurement_standard=p.measurement_standard,
            status=p.status,
            created_at=p.created_at,
            updated_at=p.updated_at,
            bidding_deadline=p.bidding_deadline,
            drawings_count=len(db.get_drawings_by_project(p.id)),
            boq_items_count=len(db.get_boq_items_by_project(p.id))
        )
        for p in projects
    ]

@app.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, current_user: User = Depends(get_current_user)):
    """Get project details"""
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role == "client" and project.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        measurement_standard=project.measurement_standard,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        bidding_deadline=project.bidding_deadline,
        drawings_count=len(db.get_drawings_by_project(project.id)),
        boq_items_count=len(db.get_boq_items_by_project(project.id))
    )

@app.post("/projects/{project_id}/drawings/upload")
async def upload_drawings(
    project_id: str,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_client)
):
    """Upload and process drawings"""
    project = db.get_project(project_id)
    if not project or project.client_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    
    uploaded_drawings = []
    
    for file in files:
        file_extension = file.filename.split('.')[-1].lower()
        if file_extension not in ['pdf', 'dwg', 'dxf']:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_extension}")
        
        drawing = Drawing(
            project_id=project_id,
            filename=file.filename,
            file_path=f"/uploads/{file.filename}",  # In production, use proper file storage
            file_type=file_extension
        )
        db.create_drawing(drawing)
        
        try:
            file_content = await file.read()
            processing_result = await drawing_processor.process_drawing(drawing, file_content)
            
            drawing.processed = True
            drawing.processing_status = "completed"
            drawing.processed_at = datetime.utcnow()
            
            if processing_result.get('drawing_type'):
                drawing.drawing_type = DrawingType(processing_result['drawing_type'])
            
            if processing_result.get('scale_info'):
                drawing.scale = processing_result['scale_info']
            
            if processing_result.get('quality_assessment'):
                quality_data = processing_result['quality_assessment']
                drawing.quality_score = quality_data.get('quality_score', 0)
                drawing.quality_issues = quality_data.get('issues', [])
            
            if processing_result.get('architect_queries'):
                drawing.architect_queries = processing_result['architect_queries']
            
            db.update_drawing(drawing)
            
            uploaded_drawings.append({
                "drawing": drawing,
                "processing_result": processing_result
            })
            
        except Exception as e:
            drawing.processing_status = "failed"
            drawing.error_message = str(e)
            db.update_drawing(drawing)
            uploaded_drawings.append({
                "drawing": drawing,
                "error": str(e)
            })
    
    return {"uploaded_drawings": len(uploaded_drawings), "drawings": uploaded_drawings}

@app.post("/projects/{project_id}/generate-boq")
async def generate_boq(
    project_id: str,
    current_user: User = Depends(get_current_client)
):
    """Generate BOQ from processed drawings"""
    project = db.get_project(project_id)
    if not project or project.client_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    
    drawings = db.get_drawings_by_project(project_id)
    processed_drawings = [d for d in drawings if d.processed and d.processing_status == "completed"]
    
    if not processed_drawings:
        raise HTTPException(status_code=400, detail="No processed drawings found")
    
    drawings_data = []
    for drawing in processed_drawings:
        drawings_data.append({
            "drawing_id": drawing.id,
            "drawing_type": drawing.drawing_type.value if drawing.drawing_type else "architectural",
            "elements": [],  # Would contain actual processed elements
            "dimensions": [],
            "text_annotations": []
        })
    
    boq_items = await boq_generator.generate_boq(
        project_id, drawings_data, project.measurement_standard
    )
    
    db.bulk_create_boq_items(boq_items)
    
    project.status = ProjectStatus.READY_FOR_BIDDING
    db.update_project(project)
    
    return {"generated_items": len(boq_items), "boq_items": boq_items}

@app.get("/projects/{project_id}/boq", response_model=List[BOQItemResponse])
async def get_boq(project_id: str, current_user: User = Depends(get_current_user)):
    """Get BOQ items for a project"""
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role == "client" and project.client_id != current_user.id:
        if project.status not in [ProjectStatus.READY_FOR_BIDDING, ProjectStatus.BIDDING_OPEN]:
            raise HTTPException(status_code=403, detail="Not authorized")
    
    boq_items = db.get_boq_items_by_project(project_id)
    return boq_items

@app.get("/projects/{project_id}/boq/excel")
async def download_boq_excel(
    project_id: str,
    current_user: User = Depends(get_current_user)
):
    """Download BOQ as Excel file"""
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    boq_items = db.get_boq_items_by_project(project_id)
    if not boq_items:
        raise HTTPException(status_code=404, detail="No BOQ items found")
    
    excel_data = excel_generator.generate_boq_excel(project, boq_items)
    
    return StreamingResponse(
        io.BytesIO(excel_data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=BOQ_{project.name.replace(' ', '_')}.xlsx"}
    )

@app.post("/projects/{project_id}/bids", response_model=BidResponse)
async def submit_bid(
    project_id: str,
    bid_data: BidCreate,
    current_user: User = Depends(get_current_contractor)
):
    """Submit a bid for a project"""
    project = db.get_project(project_id)
    if not project or project.status != ProjectStatus.BIDDING_OPEN:
        raise HTTPException(status_code=400, detail="Project not available for bidding")
    
    existing_bids = db.get_bids_by_contractor(current_user.id)
    existing_bid = next((b for b in existing_bids if b.project_id == project_id), None)
    if existing_bid:
        raise HTTPException(status_code=400, detail="Bid already submitted for this project")
    
    total_amount = 0
    bid_items = []
    boq_items = db.get_boq_items_by_project(project_id)
    boq_dict = {item.id: item for item in boq_items}
    
    for item_data in bid_data.items:
        boq_item = boq_dict.get(item_data.boq_item_id)
        if not boq_item:
            raise HTTPException(status_code=400, detail=f"BOQ item {item_data.boq_item_id} not found")
        
        item_total = boq_item.quantity * item_data.rate
        total_amount += item_total
        
        bid_items.append(BidItem(
            boq_item_id=item_data.boq_item_id,
            rate=item_data.rate,
            total=item_total
        ))
    
    bid = Bid(
        project_id=project_id,
        contractor_id=current_user.id,
        contractor_name=current_user.name,
        contractor_company=current_user.company or "",
        items=bid_items,
        total_amount=total_amount,
        status=BidStatus.SUBMITTED,
        submitted_at=datetime.utcnow()
    )
    
    db.create_bid(bid)
    return bid

@app.get("/projects/{project_id}/bids", response_model=List[BidResponse])
async def get_project_bids(
    project_id: str,
    current_user: User = Depends(get_current_client)
):
    """Get all bids for a project (client only)"""
    project = db.get_project(project_id)
    if not project or project.client_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    
    bids = db.get_bids_by_project(project_id)
    return bids

@app.post("/projects/{project_id}/evaluate-bids", response_model=BidEvaluationResponse)
async def evaluate_bids(
    project_id: str,
    current_user: User = Depends(get_current_client)
):
    """Evaluate and rank all bids for a project"""
    project = db.get_project(project_id)
    if not project or project.client_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    
    bids = db.get_bids_by_project(project_id)
    if not bids:
        raise HTTPException(status_code=400, detail="No bids found for evaluation")
    
    sorted_bids = sorted(bids, key=lambda x: x.total_amount)
    
    for i, bid in enumerate(sorted_bids, 1):
        bid.rank = i
        bid.status = BidStatus.EVALUATED
        db.update_bid(bid)
    
    winning_bid = sorted_bids[0]
    evaluation = BidEvaluation(
        project_id=project_id,
        bids=sorted_bids,
        winning_bid_id=winning_bid.id
    )
    db.create_bid_evaluation(evaluation)
    
    project.status = ProjectStatus.AWARDED
    db.update_project(project)
    
    ranked_bids = [
        {
            "rank": bid.rank,
            "contractor_name": bid.contractor_name,
            "contractor_company": bid.contractor_company,
            "total_amount": bid.total_amount,
            "status": bid.status.value
        }
        for bid in sorted_bids
    ]
    
    return BidEvaluationResponse(
        project_id=project_id,
        winning_bid_id=winning_bid.id,
        winning_contractor=winning_bid.contractor_name,
        winning_amount=winning_bid.total_amount,
        total_bids=len(bids),
        evaluation_date=evaluation.evaluation_date,
        ranked_bids=ranked_bids
    )

@app.get("/projects/{project_id}/estimate", response_model=CostEstimateResponse)
async def get_cost_estimate(
    project_id: str, 
    hourly_rate: Optional[float] = 45.0,
    currency: Currency = Query(Currency.GBP, description="Currency for cost calculation"),
    current_user: User = Depends(get_current_client)
):
    """Get cost estimate for project using advanced algorithms @ configurable hourly rate"""
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    cost_estimator.hourly_rate = hourly_rate
    
    estimate = cost_estimator.estimate_project_cost(project, currency)
    report = cost_estimator.generate_estimate_report(project, currency)
    
    project.estimated_cost = estimate['total_cost']
    project.estimated_man_hours = estimate['total_hours']
    db.update_project(project)
    
    return CostEstimateResponse(
        project_id=project_id,
        total_hours=estimate['total_hours'],
        total_cost=estimate['total_cost'],
        hourly_rate=estimate['hourly_rate'],
        drawing_processing_hours=estimate['drawing_processing_hours'],
        boq_generation_hours=estimate['boq_generation_hours'],
        setup_hours=estimate['setup_hours'],
        standard_multiplier=estimate['standard_multiplier'],
        cost_breakdown=estimate['cost_breakdown'],
        estimate_report=report
    )

@app.post("/projects/{project_id}/quick-estimate")
async def quick_estimate_from_drawings(
    project_id: str,
    hourly_rate: Optional[float] = 45.0,
    currency: Currency = Query(Currency.GBP, description="Currency for cost calculation"),
    current_user: User = Depends(get_current_client)
):
    """Get quick cost estimate immediately after uploading drawings"""
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    drawings = db.get_drawings_by_project(project_id)
    if not drawings:
        raise HTTPException(status_code=400, detail="No drawings found for estimation")
    
    temp_boq_items = []
    for drawing in drawings:
        drawing_type = drawing.drawing_type.value if drawing.drawing_type else "general"
        
        if drawing_type == "architectural":
            temp_boq_items.extend([
                BOQItem(project_id=project_id, item_code="A001", description="Excavation", 
                       unit="m³", quantity=100.0, category="excavation", trade="civil", 
                       measurement_standard=project.measurement_standard),
                BOQItem(project_id=project_id, item_code="A002", description="Concrete", 
                       unit="m³", quantity=50.0, category="concrete", trade="civil", 
                       measurement_standard=project.measurement_standard)
            ])
        elif drawing_type == "structural":
            temp_boq_items.extend([
                BOQItem(project_id=project_id, item_code="S001", description="Steel reinforcement", 
                       unit="kg", quantity=1000.0, category="steel", trade="civil", 
                       measurement_standard=project.measurement_standard),
                BOQItem(project_id=project_id, item_code="S002", description="Structural concrete", 
                       unit="m³", quantity=75.0, category="concrete", trade="civil", 
                       measurement_standard=project.measurement_standard)
            ])
        elif drawing_type == "mep":
            temp_boq_items.extend([
                BOQItem(project_id=project_id, item_code="M001", description="Electrical installation", 
                       unit="m", quantity=200.0, category="electrical", trade="electrical", 
                       measurement_standard=project.measurement_standard),
                BOQItem(project_id=project_id, item_code="M002", description="Plumbing installation", 
                       unit="m", quantity=150.0, category="plumbing", trade="plumbing", 
                       measurement_standard=project.measurement_standard)
            ])
    
    temp_project = Project(
        id=project.id,
        name=project.name,
        description=project.description,
        client_id=project.client_id,
        measurement_standard=project.measurement_standard,
        status=project.status,
        drawings=drawings,
        boq_items=temp_boq_items,
        created_at=project.created_at,
        updated_at=project.updated_at
    )
    
    cost_estimator.hourly_rate = hourly_rate
    
    estimate = cost_estimator.estimate_project_cost(temp_project, currency)
    report = cost_estimator.generate_estimate_report(temp_project, currency)
    
    return {
        "project_id": project_id,
        "estimate_type": "quick_estimate",
        "total_hours": estimate['total_hours'],
        "total_cost": estimate['total_cost'],
        "hourly_rate": estimate['hourly_rate'],
        "drawing_count": len(drawings),
        "estimated_boq_items": len(temp_boq_items),
        "cost_breakdown": estimate['cost_breakdown'],
        "estimate_report": report,
        "note": "This is a preliminary estimate based on drawing analysis. Generate full BOQ for accurate pricing."
    }

@app.get("/my-bids", response_model=List[BidResponse])
async def get_my_bids(current_user: User = Depends(get_current_contractor)):
    """Get contractor's own bids"""
    bids = db.get_bids_by_contractor(current_user.id)
    return bids

@app.get("/projects/{project_id}/drawings/{drawing_id}/queries", response_model=ArchitectQueriesResponse)
async def get_architect_queries(
    project_id: str,
    drawing_id: str,
    current_user: User = Depends(get_current_client)
):
    """Get architect/engineer queries for a specific drawing"""
    project = db.get_project(project_id)
    if not project or project.client_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    
    drawing = db.get_drawing(drawing_id)
    if not drawing or drawing.project_id != project_id:
        raise HTTPException(status_code=404, detail="Drawing not found")
    
    queries = drawing.architect_queries or []
    
    queries_by_category = {}
    high_priority_count = 0
    
    for query in queries:
        category = query.get('category', 'general')
        if category not in queries_by_category:
            queries_by_category[category] = []
        queries_by_category[category].append(query)
        
        if query.get('priority') == 'high':
            high_priority_count += 1
    
    formatted_query_list = _format_queries_for_export(drawing.filename, queries, drawing.quality_score or 0)
    
    return ArchitectQueriesResponse(
        project_id=project_id,
        drawing_id=drawing_id,
        drawing_filename=drawing.filename,
        quality_score=drawing.quality_score or 0,
        total_queries=len(queries),
        high_priority_queries=high_priority_count,
        queries_by_category=queries_by_category,
        formatted_query_list=formatted_query_list
    )

@app.get("/projects/{project_id}/architect-queries-export")
async def export_architect_queries(
    project_id: str,
    current_user: User = Depends(get_current_client)
):
    """Export all architect queries for a project as a downloadable text file"""
    project = db.get_project(project_id)
    if not project or project.client_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    
    drawings = db.get_drawings_by_project(project_id)
    drawings_with_queries = [d for d in drawings if d.architect_queries]
    
    if not drawings_with_queries:
        raise HTTPException(status_code=404, detail="No architect queries found for this project")
    
    export_content = _generate_comprehensive_query_report(project, drawings_with_queries)
    
    return StreamingResponse(
        io.BytesIO(export_content.encode('utf-8')),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=Architect_Queries_{project.name.replace(' ', '_')}.txt"}
    )

def _format_queries_for_export(filename: str, queries: List[Dict[str, Any]], quality_score: int) -> str:
    """Format queries for professional export"""
    if not queries:
        return f"Drawing: {filename}\nQuality Score: {quality_score}/100\nNo queries required - drawing quality is sufficient."
    
    content = f"""DRAWING QUALITY ASSESSMENT AND QUERIES
=====================================

Drawing: {filename}
Quality Score: {quality_score}/100
Total Queries: {len(queries)}

"""
    
    high_priority = [q for q in queries if q.get('priority') == 'high']
    medium_priority = [q for q in queries if q.get('priority') == 'medium']
    low_priority = [q for q in queries if q.get('priority') == 'low']
    
    if high_priority:
        content += "HIGH PRIORITY ISSUES (Immediate Attention Required):\n"
        content += "=" * 55 + "\n\n"
        for i, query in enumerate(high_priority, 1):
            content += f"{i}. {query.get('question', '')}\n"
            content += f"   Category: {query.get('category', '').title()}\n"
            content += f"   Details: {query.get('details', '')}\n"
            content += f"   Action: {query.get('suggested_action', '')}\n\n"
    
    if medium_priority:
        content += "MEDIUM PRIORITY RECOMMENDATIONS:\n"
        content += "=" * 35 + "\n\n"
        for i, query in enumerate(medium_priority, 1):
            content += f"{i}. {query.get('question', '')}\n"
            content += f"   Category: {query.get('category', '').title()}\n"
            content += f"   Details: {query.get('details', '')}\n"
            content += f"   Action: {query.get('suggested_action', '')}\n\n"
    
    if low_priority:
        content += "LOW PRIORITY SUGGESTIONS:\n"
        content += "=" * 27 + "\n\n"
        for i, query in enumerate(low_priority, 1):
            content += f"{i}. {query.get('question', '')}\n"
            content += f"   Category: {query.get('category', '').title()}\n"
            content += f"   Details: {query.get('details', '')}\n"
            content += f"   Action: {query.get('suggested_action', '')}\n\n"
    
    return content

def _generate_comprehensive_query_report(project: Project, drawings_with_queries: List[Drawing]) -> str:
    """Generate comprehensive query report for all project drawings"""
    content = f"""BOJIM BOQ PRODUCTION SOFTWARE
ARCHITECT/ENGINEER QUERY REPORT
===============================

Project: {project.name}
Description: {project.description or 'N/A'}
Measurement Standard: {project.measurement_standard.value}
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

EXECUTIVE SUMMARY
================
Total Drawings Processed: {len(drawings_with_queries)}
Drawings Requiring Attention: {len(drawings_with_queries)}

"""
    
    total_queries = sum(len(d.architect_queries or []) for d in drawings_with_queries)
    high_priority_total = sum(len([q for q in (d.architect_queries or []) if q.get('priority') == 'high']) for d in drawings_with_queries)
    
    content += f"Total Queries Generated: {total_queries}\n"
    content += f"High Priority Issues: {high_priority_total}\n"
    content += f"Average Quality Score: {sum(d.quality_score or 0 for d in drawings_with_queries) / len(drawings_with_queries):.1f}/100\n\n"
    
    content += "DETAILED DRAWING ANALYSIS\n"
    content += "=" * 25 + "\n\n"
    
    for drawing in drawings_with_queries:
        content += _format_queries_for_export(drawing.filename, drawing.architect_queries or [], drawing.quality_score or 0)
        content += "\n" + "=" * 80 + "\n\n"
    
    content += """NEXT STEPS
==========
1. Review all HIGH PRIORITY issues first - these prevent accurate BOQ generation
2. Address MEDIUM PRIORITY recommendations to improve drawing quality
3. Consider LOW PRIORITY suggestions for optimal results
4. Re-upload drawings after making corrections for updated quality assessment

For technical support, please contact the Bojim BOQ Production Software team.
"""
    
    return content

@app.post("/projects/{project_id}/generate-trade-packages", response_model=List[TradePackageResponse])
async def generate_trade_packages(
    project_id: str,
    current_user: User = Depends(get_current_client)
):
    """Generate trade packages from project BOQ items"""
    project = db.get_project(project_id)
    if not project or project.client_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    
    boq_items = db.get_boq_items_by_project(project_id)
    if not boq_items:
        raise HTTPException(status_code=400, detail="No BOQ items found. Generate BOQ first.")
    
    trade_packages = trade_package_generator.generate_trade_packages(project, boq_items)
    
    saved_packages = []
    for package in trade_packages:
        saved_package = db.create_trade_package(package)
        saved_packages.append(saved_package)
    
    return [trade_package_generator.get_trade_package_summary(pkg) for pkg in saved_packages]

@app.get("/projects/{project_id}/trade-packages", response_model=List[TradePackageResponse])
async def get_trade_packages(
    project_id: str,
    current_user: User = Depends(get_current_client)
):
    """Get all trade packages for a project"""
    project = db.get_project(project_id)
    if not project or project.client_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    
    trade_packages = db.get_trade_packages_by_project(project_id)
    return [trade_package_generator.get_trade_package_summary(pkg) for pkg in trade_packages]

@app.get("/projects/{project_id}/trade-packages/{package_id}", response_model=TradePackageDetailResponse)
async def get_trade_package_detail(
    project_id: str,
    package_id: str,
    current_user: User = Depends(get_current_client)
):
    """Get detailed view of a specific trade package"""
    project = db.get_project(project_id)
    if not project or project.client_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    
    trade_package = db.get_trade_package(package_id)
    if not trade_package or trade_package.project_id != project_id:
        raise HTTPException(status_code=404, detail="Trade package not found")
    
    return trade_package_generator.get_trade_package_detail(trade_package)

@app.get("/projects/{project_id}/trade-packages/{package_id}/excel")
async def download_trade_package_excel(
    project_id: str,
    package_id: str,
    current_user: User = Depends(get_current_client)
):
    """Download Excel BOQ for a specific trade package"""
    project = db.get_project(project_id)
    if not project or project.client_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    
    trade_package = db.get_trade_package(package_id)
    if not trade_package or trade_package.project_id != project_id:
        raise HTTPException(status_code=404, detail="Trade package not found")
    
    drawings = db.get_drawings_by_project(project_id)
    excel_content = excel_generator.generate_excel_boq(
        project, 
        trade_package.boq_items,  # Only items for this trade
        drawings
    )
    
    filename = f"BOQ_{project.name}_{trade_package.trade_name}_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    
    return StreamingResponse(
        io.BytesIO(excel_content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
