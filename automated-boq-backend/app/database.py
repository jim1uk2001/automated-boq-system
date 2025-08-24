from typing import Dict, List, Optional, Any
import uuid
from datetime import datetime
from .models import User, Project, Drawing, BOQItem, Bid, BidEvaluation, TradePackage, TradeBid, ScheduledEmail

class InMemoryDatabase:
    """In-memory database for proof of concept"""
    
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.projects: Dict[str, Project] = {}
        self.drawings: Dict[str, Drawing] = {}
        self.boq_items: Dict[str, BOQItem] = {}
        self.bids: Dict[str, Bid] = {}
        self.bid_evaluations: Dict[str, BidEvaluation] = {}
        self.trade_packages: Dict[str, TradePackage] = {}
        self.trade_bids: Dict[str, TradeBid] = {}
        self.scheduled_emails: Dict[str, ScheduledEmail] = {}
        self._sample_data_created = False
    
    def _ensure_sample_data(self):
        """Create sample users for testing if not already created"""
        if self._sample_data_created:
            print(f"DEBUG: Sample data already created, {len(self.users)} users in database")
            return
            
        print("DEBUG: Creating sample data...")
        from .auth import get_password_hash
        
        client = User(
            id="bf4881b9-f7bd-4307-bd77-ad46cdd4ef6b",  # Fixed ID to match existing tokens
            email="mcguirejim@yahoo.com",
            name="Jim McGuire",
            password=get_password_hash("password123"),
            role="client",
            company="ABC Construction Ltd"
        )
        print(f"DEBUG: Created client user with ID: {client.id}")
        self.users[client.id] = client
        
        contractor1 = User(
            id="contractor1-fixed-id-12345",  # Fixed ID
            email="contractor1@example.com",
            name="Mike Builder",
            password=get_password_hash("password123"),
            role="contractor",
            company="BuildCorp Ltd"
        )
        self.users[contractor1.id] = contractor1
        
        contractor2 = User(
            id="contractor2-fixed-id-67890",  # Fixed ID
            email="contractor2@example.com",
            name="Sarah Constructor",
            password=get_password_hash("password123"),
            role="contractor",
            company="ConstructCo Inc"
        )
        self.users[contractor2.id] = contractor2
        
        self._sample_data_created = True
        print(f"DEBUG: Sample data creation complete. Total users: {len(self.users)}")
        for user_id, user in self.users.items():
            print(f"DEBUG: User {user_id}: {user.email} ({user.role})")
    
    def create_user(self, user: User) -> User:
        self.users[user.id] = user
        return user
    
    def get_user(self, user_id: str) -> Optional[User]:
        self._ensure_sample_data()
        return self.users.get(user_id)
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        self._ensure_sample_data()
        for user in self.users.values():
            if user.email == email:
                return user
        return None
    
    def get_users_by_role(self, role: str) -> List[User]:
        return [user for user in self.users.values() if user.role == role]
    
    def create_project(self, project: Project) -> Project:
        self.projects[project.id] = project
        return project
    
    def get_project(self, project_id: str) -> Optional[Project]:
        return self.projects.get(project_id)
    
    def get_projects_by_client(self, client_id: str) -> List[Project]:
        return [project for project in self.projects.values() if project.client_id == client_id]
    
    def update_project(self, project: Project) -> Project:
        project.updated_at = datetime.utcnow()
        self.projects[project.id] = project
        return project
    
    def create_drawing(self, drawing: Drawing) -> Drawing:
        self.drawings[drawing.id] = drawing
        return drawing
    
    def get_drawing(self, drawing_id: str) -> Optional[Drawing]:
        return self.drawings.get(drawing_id)
    
    def get_drawings_by_project(self, project_id: str) -> List[Drawing]:
        return [drawing for drawing in self.drawings.values() if drawing.project_id == project_id]
    
    def update_drawing(self, drawing: Drawing) -> Drawing:
        self.drawings[drawing.id] = drawing
        return drawing
    
    def create_boq_item(self, boq_item: BOQItem) -> BOQItem:
        self.boq_items[boq_item.id] = boq_item
        return boq_item
    
    def get_boq_items_by_project(self, project_id: str) -> List[BOQItem]:
        return [item for item in self.boq_items.values() if item.project_id == project_id]
    
    def bulk_create_boq_items(self, boq_items: List[BOQItem]) -> List[BOQItem]:
        for item in boq_items:
            self.boq_items[item.id] = item
        return boq_items
    
    def create_bid(self, bid: Bid) -> Bid:
        self.bids[bid.id] = bid
        return bid
    
    def get_bid(self, bid_id: str) -> Optional[Bid]:
        return self.bids.get(bid_id)
    
    def get_bids_by_project(self, project_id: str) -> List[Bid]:
        return [bid for bid in self.bids.values() if bid.project_id == project_id]
    
    def get_bids_by_contractor(self, contractor_id: str) -> List[Bid]:
        return [bid for bid in self.bids.values() if bid.contractor_id == contractor_id]
    
    def update_bid(self, bid: Bid) -> Bid:
        self.bids[bid.id] = bid
        return bid
    
    def create_bid_evaluation(self, evaluation: BidEvaluation) -> BidEvaluation:
        self.bid_evaluations[evaluation.project_id] = evaluation
        return evaluation
    
    def get_bid_evaluation(self, project_id: str) -> Optional[BidEvaluation]:
        return self.bid_evaluations.get(project_id)
    
    def create_trade_package(self, trade_package: TradePackage) -> TradePackage:
        self.trade_packages[trade_package.id] = trade_package
        return trade_package
    
    def get_trade_packages_by_project(self, project_id: str) -> List[TradePackage]:
        return [tp for tp in self.trade_packages.values() if tp.project_id == project_id]
    
    def get_trade_package(self, trade_package_id: str) -> Optional[TradePackage]:
        return self.trade_packages.get(trade_package_id)
    
    def update_trade_package(self, trade_package: TradePackage) -> TradePackage:
        self.trade_packages[trade_package.id] = trade_package
        return trade_package
    
    def create_trade_bid(self, trade_bid: TradeBid) -> TradeBid:
        self.trade_bids[trade_bid.id] = trade_bid
        return trade_bid
    
    def get_trade_bids_by_package(self, trade_package_id: str) -> List[TradeBid]:
        return [tb for tb in self.trade_bids.values() if tb.trade_package_id == trade_package_id]
    
    def get_trade_bids_by_contractor(self, contractor_id: str) -> List[TradeBid]:
        return [tb for tb in self.trade_bids.values() if tb.contractor_id == contractor_id]
    
    def get_trade_bid(self, trade_bid_id: str) -> Optional[TradeBid]:
        return self.trade_bids.get(trade_bid_id)
    
    def create_scheduled_email(self, scheduled_email: ScheduledEmail) -> ScheduledEmail:
        self.scheduled_emails[scheduled_email.id] = scheduled_email
        return scheduled_email
    
    def get_scheduled_email(self, email_id: str) -> Optional[ScheduledEmail]:
        return self.scheduled_emails.get(email_id)
    
    def get_scheduled_emails_by_project(self, project_id: str) -> List[ScheduledEmail]:
        return [email for email in self.scheduled_emails.values() if email.project_id == project_id]
    
    def get_scheduled_emails_by_user(self, user_id: str) -> List[ScheduledEmail]:
        return [email for email in self.scheduled_emails.values() if email.created_by == user_id]
    
    def update_scheduled_email(self, scheduled_email: ScheduledEmail) -> ScheduledEmail:
        self.scheduled_emails[scheduled_email.id] = scheduled_email
        return scheduled_email
    
    def get_pending_scheduled_emails(self) -> List[ScheduledEmail]:
        return [email for email in self.scheduled_emails.values() if email.status == "scheduled"]

db = InMemoryDatabase()
