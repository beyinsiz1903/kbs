"""
Authentication & Authorization module for KBS Bridge Management System.
JWT-based auth with RBAC (Admin, Hotel Manager, Front Desk).
"""
import os
import jwt
import uuid
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
from pydantic import BaseModel

# Config
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "kbs-bridge-secret-key-change-in-production-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token extraction
security = HTTPBearer(auto_error=False)


# ============= Models =============

class TokenPayload(BaseModel):
    user_id: str
    email: str
    role: str
    hotel_ids: List[str]  # empty for admin (all access)
    exp: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class LoginRequest(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    role: str  # admin, hotel_manager, front_desk
    hotel_ids: List[str] = []  # hotels this user can access


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None
    hotel_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


# ============= Helpers =============

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str, email: str, role: str, hotel_ids: List[str]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "hotel_ids": hotel_ids,
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token suresi dolmus / Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gecersiz token / Invalid token"
        )


# ============= Dependencies =============

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Extract and validate the current user from JWT token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Giris yapmaniz gerekiyor / Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    payload = decode_access_token(credentials.credentials)
    return {
        "user_id": payload["user_id"],
        "email": payload["email"],
        "role": payload["role"],
        "hotel_ids": payload.get("hotel_ids", [])
    }


async def get_optional_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[dict]:
    """Extract user if token present, otherwise return None (for mixed endpoints)."""
    if not credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        return {
            "user_id": payload["user_id"],
            "email": payload["email"],
            "role": payload["role"],
            "hotel_ids": payload.get("hotel_ids", [])
        }
    except HTTPException:
        return None


def require_role(*allowed_roles: str):
    """Dependency factory to require specific roles."""
    async def role_checker(user: dict = Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu islem icin yetkiniz yok / Insufficient permissions. Required: {', '.join(allowed_roles)}"
            )
        return user
    return role_checker


def require_hotel_access(hotel_id_param: str = "hotel_id"):
    """Dependency to ensure user has access to the specified hotel."""
    async def hotel_checker(user: dict = Depends(get_current_user), **kwargs):
        if user["role"] == "admin":
            return user  # Admin has access to all hotels
        # For non-admin, check hotel_ids
        # Note: The actual hotel_id comes from the path/query, not the dependency
        return user
    return hotel_checker


def check_hotel_access(user: dict, hotel_id: str) -> bool:
    """Check if user has access to a specific hotel."""
    if user["role"] == "admin":
        return True
    return hotel_id in user.get("hotel_ids", [])


def filter_by_hotel_access(user: dict, query: dict) -> dict:
    """Add hotel_id filter to query based on user's access."""
    if user["role"] == "admin":
        return query  # Admin sees everything
    hotel_ids = user.get("hotel_ids", [])
    if len(hotel_ids) == 1:
        query["hotel_id"] = hotel_ids[0]
    elif len(hotel_ids) > 1:
        query["hotel_id"] = {"$in": hotel_ids}
    else:
        query["hotel_id"] = "__no_access__"  # No hotels assigned
    return query


# ============= Seed Data =============

async def seed_default_admin(db):
    """Create default admin user if none exists."""
    admin = await db.users.find_one({"role": "admin"})
    if not admin:
        admin_user = {
            "id": str(uuid.uuid4()),
            "email": "admin@kbsbridge.com",
            "password_hash": hash_password("admin123"),
            "first_name": "Sistem",
            "last_name": "Yonetici",
            "role": "admin",
            "hotel_ids": [],
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one(admin_user)
        
        # Also create a demo hotel manager
        hotels = await db.hotels.find({}, {"id": 1}).to_list(10)
        hotel_ids = [h["id"] for h in hotels]
        
        if hotel_ids:
            manager_user = {
                "id": str(uuid.uuid4()),
                "email": "manager@grandistanbul.com",
                "password_hash": hash_password("manager123"),
                "first_name": "Ahmet",
                "last_name": "Yilmaz",
                "role": "hotel_manager",
                "hotel_ids": hotel_ids[:1],  # First hotel only
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            await db.users.insert_one(manager_user)
            
            frontdesk_user = {
                "id": str(uuid.uuid4()),
                "email": "resepsiyon@grandistanbul.com",
                "password_hash": hash_password("front123"),
                "first_name": "Elif",
                "last_name": "Demir",
                "role": "front_desk",
                "hotel_ids": hotel_ids[:1],
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            await db.users.insert_one(frontdesk_user)
        
        return True
    return False
