from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .database import db
from .models import User

SECRET_KEY = "bojim-boq-secret-key-2024"  # In production, use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours for development

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[str]:
    """Verify a JWT token and return user ID"""
    try:
        print(f"DEBUG: Verifying token with SECRET_KEY: {SECRET_KEY[:10]}...")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"DEBUG: Token payload: {payload}")
        user_id: str = payload.get("sub")
        if user_id is None:
            print("DEBUG: No 'sub' field in token payload")
            return None
        return user_id
    except JWTError as e:
        print(f"DEBUG: JWT verification error: {e}")
        return None

def authenticate_user(email: str, password: str) -> Optional[User]:
    """Authenticate a user with email and password"""
    user = db.get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user.password if hasattr(user, 'password') else ''):
        return None
    return user

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get the current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    print(f"DEBUG: Received token: {credentials.credentials[:50]}...")
    user_id = verify_token(credentials.credentials)
    print(f"DEBUG: Token verification result: {user_id}")
    
    if user_id is None:
        print("DEBUG: Token verification failed")
        raise credentials_exception
    
    user = db.get_user(user_id)
    print(f"DEBUG: User lookup result: {user.email if user else 'None'}")
    
    if user is None:
        print("DEBUG: User not found in database")
        raise credentials_exception
    
    return user

async def get_current_client(current_user: User = Depends(get_current_user)) -> User:
    """Get current user if they are a client"""
    if current_user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

async def get_current_contractor(current_user: User = Depends(get_current_user)) -> User:
    """Get current user if they are a contractor"""
    if current_user.role != "contractor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user
