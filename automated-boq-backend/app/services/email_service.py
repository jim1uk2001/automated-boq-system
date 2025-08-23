import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
import threading
import time
from ..models import Project, Drawing
from ..database import db
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"  # Configurable
        self.smtp_port = 587
        self.sender_email = None  # To be configured
        self.sender_password = None  # To be configured
        self.scheduler_running = False
        self.scheduled_emails = []
        
    def configure_smtp(self, smtp_server: str, smtp_port: int, sender_email: str, sender_password: str):
        """Configure SMTP settings"""
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        
    def create_boq_email(self, 
                        project: Project, 
                        recipient_emails: List[str],
                        excel_content: bytes,
                        filename: str,
                        email_type: str = "full_boq",
                        trade_name: Optional[str] = None,
                        custom_message: Optional[str] = None) -> MIMEMultipart:
        """Create professional BOQ email with Excel attachment"""
        
        msg = MIMEMultipart()
        msg['From'] = self.sender_email
        msg['To'] = ", ".join(recipient_emails)
        
        if email_type == "trade_package" and trade_name:
            msg['Subject'] = f"BOQ - {project.name} - {trade_name.title()} Trade Package"
            email_body = self._get_trade_package_email_template(project, trade_name, custom_message)
        else:
            msg['Subject'] = f"BOQ - {project.name} - Complete Bill of Quantities"
            email_body = self._get_full_boq_email_template(project, custom_message)
        
        msg.attach(MIMEText(email_body, 'html'))
        
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(excel_content)
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename= {filename}'
        )
        msg.attach(part)
        
        return msg
    
    def _get_full_boq_email_template(self, project: Project, custom_message: Optional[str] = None) -> str:
        """Generate professional email template for full BOQ"""
        drawings = db.get_drawings_by_project(project.id)
        drawing_list = ""
        
        if drawings:
            drawing_list = "<h3>Drawing Register:</h3><ul>"
            for drawing in drawings:
                revision = f" (Rev. {drawing.revision_number})" if drawing.revision_number else ""
                drawing_list += f"<li>{drawing.drawing_title or drawing.filename}{revision}</li>"
            drawing_list += "</ul>"
        
        custom_section = f"<p><strong>Additional Notes:</strong><br>{custom_message}</p>" if custom_message else ""
        
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #4472C4; color: white; padding: 20px; text-align: center;">
                    <h1 style="margin: 0;">Bojim BOQ Production Software</h1>
                    <p style="margin: 5px 0 0 0;">Professional Bill of Quantities</p>
                </div>
                
                <div style="padding: 20px; background-color: #f8f9fa;">
                    <h2 style="color: #4472C4;">Project: {project.name}</h2>
                    <p><strong>Description:</strong> {project.description or 'N/A'}</p>
                    <p><strong>Measurement Standard:</strong> {project.measurement_standard.value}</p>
                    <p><strong>Generated:</strong> {datetime.utcnow().strftime('%d %B %Y at %H:%M UTC')}</p>
                    
                    {drawing_list}
                    
                    <h3>BOQ Details:</h3>
                    <p>Please find attached the complete Bill of Quantities for this project. The Excel file contains:</p>
                    <ul>
                        <li>Complete itemized quantities with descriptions</li>
                        <li>Protected cells (only rate/price columns are editable)</li>
                        <li>Automatic calculation formulas</li>
                        <li>Drawing register with revision tracking</li>
                        <li>Measurement standard compliance ({project.measurement_standard.value})</li>
                    </ul>
                    
                    {custom_section}
                    
                    <div style="background-color: #e7f3ff; padding: 15px; border-left: 4px solid #4472C4; margin: 20px 0;">
                        <h4 style="margin-top: 0; color: #4472C4;">Instructions for Bidders:</h4>
                        <ol>
                            <li>Enter your rates in the designated price columns only</li>
                            <li>Do not modify quantities or descriptions</li>
                            <li>Ensure all rates include materials, labor, and overheads</li>
                            <li>Submit your completed BOQ by the specified deadline</li>
                        </ol>
                    </div>
                    
                    <p style="margin-top: 30px;">
                        <strong>For technical support or queries, please contact our team.</strong><br>
                        Generated by Bojim BOQ Production Software
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _get_trade_package_email_template(self, project: Project, trade_name: str, custom_message: Optional[str] = None) -> str:
        """Generate professional email template for trade package BOQ"""
        custom_section = f"<p><strong>Additional Notes:</strong><br>{custom_message}</p>" if custom_message else ""
        
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #4472C4; color: white; padding: 20px; text-align: center;">
                    <h1 style="margin: 0;">Bojim BOQ Production Software</h1>
                    <p style="margin: 5px 0 0 0;">{trade_name.title()} Trade Package</p>
                </div>
                
                <div style="padding: 20px; background-color: #f8f9fa;">
                    <h2 style="color: #4472C4;">Project: {project.name}</h2>
                    <h3 style="color: #d63384;">Trade: {trade_name.title()}</h3>
                    <p><strong>Description:</strong> {project.description or 'N/A'}</p>
                    <p><strong>Measurement Standard:</strong> {project.measurement_standard.value}</p>
                    <p><strong>Generated:</strong> {datetime.utcnow().strftime('%d %B %Y at %H:%M UTC')}</p>
                    
                    <h3>Trade Package Details:</h3>
                    <p>Please find attached the Bill of Quantities for the <strong>{trade_name.title()}</strong> trade package. This specialized BOQ contains:</p>
                    <ul>
                        <li>Items specific to {trade_name} trade only</li>
                        <li>Protected cells (only rate/price columns are editable)</li>
                        <li>Automatic calculation formulas</li>
                        <li>Trade-specific measurement standards</li>
                        <li>Independent procurement capability</li>
                    </ul>
                    
                    {custom_section}
                    
                    <div style="background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0;">
                        <h4 style="margin-top: 0; color: #856404;">Trade-Specific Instructions:</h4>
                        <ol>
                            <li>This BOQ contains only {trade_name} trade items</li>
                            <li>Ensure your rates reflect current market conditions</li>
                            <li>Include all specialist equipment and materials</li>
                            <li>Consider coordination with other trades</li>
                        </ol>
                    </div>
                    
                    <p style="margin-top: 30px;">
                        <strong>For technical support or queries, please contact our team.</strong><br>
                        Generated by Bojim BOQ Production Software
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
    
    async def send_email_now(self, msg: MIMEMultipart) -> bool:
        """Send email immediately"""
        try:
            if not self.sender_email or not self.sender_password:
                logger.error("Email credentials not configured")
                return False
                
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.sender_email, self.sender_password)
                text = msg.as_string()
                server.sendmail(self.sender_email, msg['To'].split(", "), text)
                
            logger.info(f"Email sent successfully to {msg['To']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False
    
    def schedule_email(self, 
                      msg: MIMEMultipart, 
                      send_datetime: datetime,
                      email_id: str,
                      project_id: str) -> str:
        """Schedule email for future delivery"""
        scheduled_email = {
            'id': email_id,
            'project_id': project_id,
            'message': msg,
            'send_datetime': send_datetime,
            'status': 'scheduled',
            'created_at': datetime.utcnow()
        }
        
        self.scheduled_emails.append(scheduled_email)
        
        if not self.scheduler_running:
            self._start_email_scheduler()
            
        logger.info(f"Email scheduled for {send_datetime} with ID {email_id}")
        return email_id
    
    def _start_email_scheduler(self):
        """Start background email scheduler"""
        if self.scheduler_running:
            return
            
        self.scheduler_running = True
        
        def scheduler_loop():
            while self.scheduler_running:
                current_time = datetime.utcnow()
                emails_to_send = []
                
                for email in self.scheduled_emails[:]:
                    if email['status'] == 'scheduled' and email['send_datetime'] <= current_time:
                        emails_to_send.append(email)
                        email['status'] = 'sending'
                
                for email in emails_to_send:
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        success = loop.run_until_complete(self.send_email_now(email['message']))
                        loop.close()
                        
                        if success:
                            email['status'] = 'sent'
                            email['sent_at'] = datetime.utcnow()
                            logger.info(f"Scheduled email {email['id']} sent successfully")
                        else:
                            email['status'] = 'failed'
                            logger.error(f"Failed to send scheduled email {email['id']}")
                            
                    except Exception as e:
                        email['status'] = 'failed'
                        logger.error(f"Error sending scheduled email {email['id']}: {str(e)}")
                
                time.sleep(60)  # Check every minute
        
        scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
        scheduler_thread.start()
        logger.info("Email scheduler started")
    
    def get_scheduled_emails(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of scheduled emails"""
        if project_id:
            return [email for email in self.scheduled_emails if email['project_id'] == project_id]
        return self.scheduled_emails
    
    def cancel_scheduled_email(self, email_id: str) -> bool:
        """Cancel a scheduled email"""
        for email in self.scheduled_emails:
            if email['id'] == email_id and email['status'] == 'scheduled':
                email['status'] = 'cancelled'
                logger.info(f"Scheduled email {email_id} cancelled")
                return True
        return False

email_service = EmailService()
