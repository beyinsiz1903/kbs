from fastapi import FastAPI, APIRouter, HTTPException, Query, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone
from cryptography.fernet import Fernet
import base64
import hashlib

from models import (
    Hotel, Guest, CheckIn, Submission, SubmissionStatus, GuestType,
    AuditAction, AgentStatus, KBSSimulationMode,
    HotelCreate, GuestCreate, CheckInCreate, SubmissionCorrection, KBSModeUpdate,
    HotelOnboardingUpdate, KbsConfigUpdate,
    serialize_doc, utcnow
)
from validators import validate_guest_data, generate_fingerprint
from kbs_simulator import set_simulation_mode, get_simulation_mode, clear_processed_ids
from agent_runtime import AgentManager
from audit import log_audit_event, get_audit_trail, get_audit_stats
from auth import (
    get_current_user, get_optional_user, require_role,
    check_hotel_access, filter_by_hotel_access,
    hash_password, verify_password, create_access_token,
    seed_default_admin, LoginRequest, UserCreate, UserUpdate, PasswordChange, TokenResponse
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'kbs_bridge_system')]

# Create the main app
app = FastAPI(title="KBS Bridge Management System", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Agent Manager
agent_manager = AgentManager(db)

# Encryption for credential vault
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", None)
if not ENCRYPTION_KEY:
    # Derive a key from JWT secret for simplicity
    key_bytes = hashlib.sha256(os.environ.get("JWT_SECRET_KEY", "kbs-bridge-secret-key-change-in-production-2024").encode()).digest()
    ENCRYPTION_KEY = base64.urlsafe_b64encode(key_bytes)
_fernet = Fernet(ENCRYPTION_KEY)

def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret value."""
    return _fernet.encrypt(plaintext.encode()).decode()

def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a secret value."""
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except Exception:
        return "***decryption_error***"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============= STARTUP / SHUTDOWN =============

@app.on_event("startup")
async def startup():
    """Initialize database indexes and start agents for active hotels."""
    # Create indexes
    await db.hotels.create_index("id", unique=True)
    await db.guests.create_index("id", unique=True)
    await db.guests.create_index("hotel_id")
    await db.checkins.create_index("id", unique=True)
    await db.checkins.create_index("hotel_id")
    await db.submissions.create_index("id", unique=True)
    await db.submissions.create_index("hotel_id")
    await db.submissions.create_index("status")
    await db.submissions.create_index("fingerprint")
    await db.submissions.create_index([("hotel_id", 1), ("status", 1)])
    await db.attempts.create_index("submission_id")
    await db.audit_events.create_index([("hotel_id", 1), ("created_at", -1)])
    await db.agent_states.create_index("hotel_id", unique=True)
    await db.users.create_index("id", unique=True)
    await db.users.create_index("email", unique=True)
    await db.kbs_configs.create_index("hotel_id", unique=True)
    
    # Seed default admin
    await seed_default_admin(db)
    
    # Start agents for all active hotels
    async for hotel in db.hotels.find({"is_active": True}):
        try:
            await agent_manager.start_agent(hotel["id"])
            logger.info(f"Started agent for hotel: {hotel['name']}")
        except Exception as e:
            logger.error(f"Failed to start agent for hotel {hotel['id']}: {e}")
    
    logger.info("KBS Bridge Management System started")


@app.on_event("shutdown")
async def shutdown():
    """Clean shutdown of all agents and DB."""
    await agent_manager.stop_all()
    client.close()
    logger.info("KBS Bridge Management System stopped")


# ============= HEALTH CHECK =============

@api_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": utcnow().isoformat(),
        "agents": agent_manager.get_all_status()
    }


# ============= AUTHENTICATION =============

@api_router.post("/auth/login")
async def login(request: LoginRequest):
    """Authenticate user and return JWT token."""
    user = await db.users.find_one({"email": request.email, "is_active": True})
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Gecersiz e-posta veya sifre / Invalid email or password"
        )
    
    try:
        if not verify_password(request.password, user.get("password_hash", "")):
            raise HTTPException(
                status_code=401,
                detail="Gecersiz e-posta veya sifre / Invalid email or password"
            )
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Gecersiz e-posta veya sifre / Invalid email or password"
        )
    token = create_access_token(
        user_id=user["id"],
        email=user["email"],
        role=user["role"],
        hotel_ids=user.get("hotel_ids", [])
    )
    
    # Log successful login for KVKK compliance
    await log_audit_event(db, "system", AuditAction.LOGIN_SUCCESS, "user", user["id"],
                         {"email": user["email"], "role": user["role"]}, actor=user["email"])
    
    user_data = {
        "id": user["id"],
        "email": user["email"],
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "role": user["role"],
        "hotel_ids": user.get("hotel_ids", [])
    }
    
    return {"access_token": token, "token_type": "bearer", "user": user_data}


@api_router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current user info."""
    db_user = await db.users.find_one({"id": user["user_id"]}, {"_id": 0, "password_hash": 0})
    if not db_user:
        raise HTTPException(status_code=404, detail="Kullanici bulunamadi / User not found")
    return serialize_doc(db_user)


@api_router.post("/auth/change-password")
async def change_password(data: PasswordChange, user: dict = Depends(get_current_user)):
    """Change current user's password."""
    db_user = await db.users.find_one({"id": user["user_id"]})
    if not db_user or not verify_password(data.current_password, db_user["password_hash"]):
        raise HTTPException(status_code=400, detail="Mevcut sifre yanlis / Current password incorrect")
    
    await db.users.update_one(
        {"id": user["user_id"]},
        {"$set": {"password_hash": hash_password(data.new_password), "updated_at": utcnow().isoformat()}}
    )
    return {"message": "Sifre degistirildi / Password changed"}


# ============= USER MANAGEMENT (Admin only) =============

@api_router.get("/users")
async def list_users(user: dict = Depends(require_role("admin"))):
    """List all users (admin only)."""
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(200)
    return [serialize_doc(u) for u in users]


@api_router.post("/users")
async def create_user(data: UserCreate, user: dict = Depends(require_role("admin"))):
    """Create a new user (admin only)."""
    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Bu e-posta zaten kullaniliyor / Email already in use")
    
    if data.role not in ["admin", "hotel_manager", "front_desk"]:
        raise HTTPException(status_code=400, detail="Gecersiz rol / Invalid role")
    
    new_user = {
        "id": str(uuid.uuid4()),
        "email": data.email,
        "password_hash": hash_password(data.password),
        "first_name": data.first_name,
        "last_name": data.last_name,
        "role": data.role,
        "hotel_ids": data.hotel_ids,
        "is_active": True,
        "created_at": utcnow().isoformat(),
        "updated_at": utcnow().isoformat()
    }
    await db.users.insert_one(new_user)
    
    result = {k: v for k, v in new_user.items() if k not in ["_id", "password_hash"]}
    return serialize_doc(result)


@api_router.put("/users/{user_id}")
async def update_user(user_id: str, data: UserUpdate, user: dict = Depends(require_role("admin"))):
    """Update a user (admin only)."""
    update_fields = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not update_fields:
        raise HTTPException(status_code=400, detail="Guncelleme verisi yok / No update data")
    
    update_fields["updated_at"] = utcnow().isoformat()
    await db.users.update_one({"id": user_id}, {"$set": update_fields})
    
    updated = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    return serialize_doc(updated)


# ============= HOTEL MANAGEMENT =============

@api_router.post("/hotels")
async def create_hotel(hotel_data: HotelCreate):
    hotel = Hotel(**hotel_data.model_dump())
    doc = hotel.model_dump()
    # Serialize datetimes
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    await db.hotels.insert_one(doc)
    
    # Start agent for this hotel
    await agent_manager.start_agent(hotel.id)
    
    await log_audit_event(db, hotel.id, AuditAction.CHECKIN_CREATED, "hotel", hotel.id,
                         {"name": hotel.name}, actor="system")
    
    return serialize_doc(doc)


@api_router.get("/hotels")
async def list_hotels():
    hotels = await db.hotels.find({}, {"_id": 0}).to_list(100)
    return [serialize_doc(h) for h in hotels]


@api_router.get("/hotels/{hotel_id}")
async def get_hotel(hotel_id: str):
    hotel = await db.hotels.find_one({"id": hotel_id}, {"_id": 0})
    if not hotel:
        raise HTTPException(status_code=404, detail="Otel bulunamadi / Hotel not found")
    return serialize_doc(hotel)


# ============= HOTEL ONBOARDING =============

@api_router.put("/hotels/{hotel_id}/onboarding")
async def update_hotel_onboarding(hotel_id: str, data: HotelOnboardingUpdate):
    """Update hotel onboarding wizard data."""
    hotel = await db.hotels.find_one({"id": hotel_id})
    if not hotel:
        raise HTTPException(status_code=404, detail="Otel bulunamadi / Hotel not found")
    
    update_fields = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not update_fields:
        raise HTTPException(status_code=400, detail="Guncelleme verisi yok / No update data")
    
    update_fields["updated_at"] = utcnow().isoformat()
    
    await db.hotels.update_one({"id": hotel_id}, {"$set": update_fields})
    
    await log_audit_event(db, hotel_id, AuditAction.CHECKIN_CREATED, "hotel", hotel_id,
                         {"action": "onboarding_update", "fields": list(update_fields.keys())}, actor="system")
    
    updated = await db.hotels.find_one({"id": hotel_id}, {"_id": 0})
    return serialize_doc(updated)


@api_router.post("/hotels/{hotel_id}/integration/test")
async def test_hotel_integration(hotel_id: str):
    """Test hotel's KBS integration connectivity (simulated)."""
    hotel = await db.hotels.find_one({"id": hotel_id})
    if not hotel:
        raise HTTPException(status_code=404, detail="Otel bulunamadi / Hotel not found")
    
    config = await db.kbs_configs.find_one({"hotel_id": hotel_id})
    
    # Simulated connection test
    import random
    success = random.random() > 0.2  # 80% success rate for simulation
    
    test_result = {
        "success": success,
        "timestamp": utcnow().isoformat(),
        "details": {
            "endpoint_reachable": success,
            "auth_valid": success,
            "test_submission_sent": success,
            "response_time_ms": random.randint(50, 500) if success else None,
        },
        "message": "Baglanti basarili / Connection successful" if success else "Baglanti basarisiz / Connection failed - check credentials and endpoint"
    }
    
    # Update config with test result
    if config:
        await db.kbs_configs.update_one(
            {"hotel_id": hotel_id},
            {"$set": {
                "last_connection_test": utcnow().isoformat(),
                "last_connection_success": success,
                "last_connection_error": None if success else "Simulated connection failure",
                "updated_at": utcnow().isoformat()
            }}
        )
    
    # Update onboarding status if testing
    if success and hotel.get("onboarding_status") in ["testing", "credentials_pending"]:
        await db.hotels.update_one(
            {"id": hotel_id},
            {"$set": {"onboarding_status": "active", "updated_at": utcnow().isoformat()}}
        )
    
    return test_result


# ============= CREDENTIAL VAULT (KBS Integration Config) =============

@api_router.get("/hotels/{hotel_id}/kbs-config")
async def get_kbs_config(hotel_id: str):
    """Get KBS integration config for a hotel (secrets are masked)."""
    config = await db.kbs_configs.find_one({"hotel_id": hotel_id}, {"_id": 0})
    if not config:
        return {"hotel_id": hotel_id, "configured": False}
    
    result = serialize_doc(config)
    # Mask the encrypted secret
    if result.get("encrypted_secret"):
        result["has_secret"] = True
        result["encrypted_secret"] = "********"
    else:
        result["has_secret"] = False
    
    result["configured"] = True
    return result


@api_router.put("/hotels/{hotel_id}/kbs-config")
async def update_kbs_config(hotel_id: str, data: KbsConfigUpdate):
    """Update KBS integration credentials for a hotel."""
    hotel = await db.hotels.find_one({"id": hotel_id})
    if not hotel:
        raise HTTPException(status_code=404, detail="Otel bulunamadi / Hotel not found")
    
    update_fields = {}
    for k, v in data.model_dump(exclude_none=True).items():
        if k == "secret" and v:
            # Encrypt the secret before storage
            update_fields["encrypted_secret"] = encrypt_secret(v)
        else:
            update_fields[k] = v
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="Guncelleme verisi yok / No update data")
    
    update_fields["updated_at"] = utcnow().isoformat()
    
    existing = await db.kbs_configs.find_one({"hotel_id": hotel_id})
    if existing:
        await db.kbs_configs.update_one({"hotel_id": hotel_id}, {"$set": update_fields})
    else:
        update_fields["id"] = str(uuid.uuid4())
        update_fields["hotel_id"] = hotel_id
        update_fields["created_at"] = utcnow().isoformat()
        await db.kbs_configs.insert_one(update_fields)
    
    # Update hotel onboarding status
    if hotel.get("onboarding_status") in ["not_started", "in_progress"]:
        await db.hotels.update_one(
            {"id": hotel_id},
            {"$set": {"onboarding_status": "credentials_pending", "updated_at": utcnow().isoformat()}}
        )
    
    await log_audit_event(db, hotel_id, AuditAction.CHECKIN_CREATED, "hotel", hotel_id,
                         {"action": "kbs_config_update", "fields": [k for k in update_fields.keys() if k != "encrypted_secret"]},
                         actor="system")
    
    # Return masked config
    return await get_kbs_config(hotel_id)


# ============= HOTEL HEALTH =============

@api_router.get("/hotels/{hotel_id}/health")
async def get_hotel_health(hotel_id: str):
    """Get per-hotel health summary."""
    hotel = await db.hotels.find_one({"id": hotel_id}, {"_id": 0})
    if not hotel:
        raise HTTPException(status_code=404, detail="Otel bulunamadi / Hotel not found")
    
    # Agent status
    agent_state = await db.agent_states.find_one({"hotel_id": hotel_id}, {"_id": 0})
    
    # KBS config
    kbs_config = await db.kbs_configs.find_one({"hotel_id": hotel_id}, {"_id": 0})
    
    # Submission stats
    pipeline = [
        {"$match": {"hotel_id": hotel_id}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    status_counts = {}
    async for doc in db.submissions.aggregate(pipeline):
        status_counts[doc["_id"]] = doc["count"]
    
    # Last successful submission
    last_success = await db.submissions.find_one(
        {"hotel_id": hotel_id, "status": "acked"},
        {"_id": 0, "id": 1, "updated_at": 1}
    )
    
    # Last error
    last_error_sub = await db.submissions.find_one(
        {"hotel_id": hotel_id, "status": {"$in": ["failed", "quarantined"]}},
        {"_id": 0, "id": 1, "last_error": 1, "updated_at": 1}
    )
    
    return {
        "hotel": serialize_doc(hotel),
        "agent": {
            "status": agent_state.get("status", "offline") if agent_state else "offline",
            "last_heartbeat": agent_state.get("last_heartbeat") if agent_state else None,
            "queue_size": agent_state.get("queue_size", 0) if agent_state else 0,
            "processed_today": agent_state.get("processed_today", 0) if agent_state else 0,
            "failed_today": agent_state.get("failed_today", 0) if agent_state else 0,
        },
        "integration": {
            "configured": bool(kbs_config),
            "last_connection_test": kbs_config.get("last_connection_test") if kbs_config else None,
            "last_connection_success": kbs_config.get("last_connection_success") if kbs_config else None,
            "environment": kbs_config.get("environment", "test") if kbs_config else None,
        },
        "submissions": {
            "by_status": status_counts,
            "total": sum(status_counts.values()),
            "quarantined": status_counts.get("quarantined", 0),
            "last_successful": serialize_doc(last_success) if last_success else None,
            "last_error": serialize_doc(last_error_sub) if last_error_sub else None,
        },
        "onboarding_status": hotel.get("onboarding_status", "not_started")
    }


# ============= GUEST MANAGEMENT =============

@api_router.post("/guests")
async def create_guest(guest_data: GuestCreate):
    guest = Guest(**guest_data.model_dump())
    doc = guest.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    
    await db.guests.insert_one(doc)
    return serialize_doc(doc)


@api_router.get("/guests")
async def list_guests(hotel_id: str = Query(None)):
    query = {}
    if hotel_id:
        query["hotel_id"] = hotel_id
    guests = await db.guests.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [serialize_doc(g) for g in guests]


@api_router.get("/guests/{guest_id}")
async def get_guest(guest_id: str):
    guest = await db.guests.find_one({"id": guest_id}, {"_id": 0})
    if not guest:
        raise HTTPException(status_code=404, detail="Misafir bulunamadi / Guest not found")
    return serialize_doc(guest)


# ============= CHECK-IN =============

@api_router.post("/checkins")
async def create_checkin(checkin_data: CheckInCreate):
    """Create a check-in and automatically trigger KBS submission."""
    # Verify hotel exists
    hotel = await db.hotels.find_one({"id": checkin_data.hotel_id})
    if not hotel:
        raise HTTPException(status_code=404, detail="Otel bulunamadi / Hotel not found")
    
    # Verify guest exists
    guest = await db.guests.find_one({"id": checkin_data.guest_id})
    if not guest:
        raise HTTPException(status_code=404, detail="Misafir bulunamadi / Guest not found")
    
    # Validate guest data
    guest_data = {k: v for k, v in guest.items() if k != "_id"}
    is_valid, validation_msg = validate_guest_data(guest_data)
    
    if not is_valid:
        await log_audit_event(db, checkin_data.hotel_id, AuditAction.VALIDATION_FAILED,
                            "guest", checkin_data.guest_id,
                            {"error": validation_msg})
        raise HTTPException(status_code=400, detail=validation_msg)
    
    # Create check-in record
    checkin = CheckIn(**checkin_data.model_dump())
    checkin_doc = checkin.model_dump()
    checkin_doc["created_at"] = checkin_doc["created_at"].isoformat()
    await db.checkins.insert_one(checkin_doc)
    
    await log_audit_event(db, checkin_data.hotel_id, AuditAction.CHECKIN_CREATED,
                         "checkin", checkin.id,
                         {"guest_id": checkin_data.guest_id, "room": checkin_data.room_number})
    
    # Generate fingerprint for duplicate prevention
    fingerprint = generate_fingerprint(guest_data, checkin_data.hotel_id, checkin_data.check_in_date)
    
    # Check for duplicate
    existing = await db.submissions.find_one({
        "fingerprint": fingerprint,
        "status": {"$in": [
            SubmissionStatus.ACKED.value,
            SubmissionStatus.QUEUED.value,
            SubmissionStatus.SENDING.value,
            SubmissionStatus.RETRYING.value
        ]}
    })
    
    if existing:
        return {
            "checkin": serialize_doc(checkin_doc),
            "submission": serialize_doc(existing),
            "message": "Mukerrer bildirim tespit edildi, mevcut gonderim kullanilacak / Duplicate detected, using existing submission",
            "duplicate": True
        }
    
    # Create KBS submission
    guest_snapshot = {k: v for k, v in guest_data.items() if k not in ["_id", "created_at"]}
    guest_snapshot["room_number"] = checkin_data.room_number
    guest_snapshot["check_in_date"] = checkin_data.check_in_date
    guest_snapshot["check_out_date"] = checkin_data.check_out_date
    
    # Get hotel max_retries config
    hotel_config = hotel.get("agent_config", {})
    max_retries = hotel_config.get("max_retries", 5)
    
    submission = Submission(
        hotel_id=checkin_data.hotel_id,
        guest_id=checkin_data.guest_id,
        checkin_id=checkin.id,
        status=SubmissionStatus.QUEUED,
        guest_type=GuestType(guest_data.get("guest_type", "tc_citizen")),
        guest_data=guest_snapshot,
        max_retries=max_retries,
        fingerprint=fingerprint
    )
    
    sub_doc = submission.model_dump()
    sub_doc["created_at"] = sub_doc["created_at"].isoformat()
    sub_doc["updated_at"] = sub_doc["updated_at"].isoformat()
    sub_doc["status"] = sub_doc["status"].value if hasattr(sub_doc["status"], 'value') else sub_doc["status"]
    sub_doc["guest_type"] = sub_doc["guest_type"].value if hasattr(sub_doc["guest_type"], 'value') else sub_doc["guest_type"]
    
    await db.submissions.insert_one(sub_doc)
    
    await log_audit_event(db, checkin_data.hotel_id, AuditAction.SUBMISSION_CREATED,
                         "submission", submission.id,
                         {"guest_id": checkin_data.guest_id, "checkin_id": checkin.id})
    
    await log_audit_event(db, checkin_data.hotel_id, AuditAction.VALIDATION_SUCCESS,
                         "submission", submission.id,
                         {"guest_type": guest_data.get("guest_type")})
    
    await log_audit_event(db, checkin_data.hotel_id, AuditAction.QUEUED,
                         "submission", submission.id, {})
    
    # Ensure agent is running
    agent = agent_manager.get_agent(checkin_data.hotel_id)
    if not agent or not agent.is_running:
        await agent_manager.start_agent(checkin_data.hotel_id)
    
    return {
        "checkin": serialize_doc(checkin_doc),
        "submission": serialize_doc(sub_doc),
        "message": "Check-in olusturuldu ve KBS bildirimi kuyruga eklendi / Check-in created and KBS submission queued",
        "duplicate": False
    }


@api_router.get("/checkins")
async def list_checkins(hotel_id: str = Query(None)):
    query = {}
    if hotel_id:
        query["hotel_id"] = hotel_id
    checkins = await db.checkins.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [serialize_doc(c) for c in checkins]


# ============= SUBMISSIONS =============

@api_router.get("/submissions")
async def list_submissions(
    hotel_id: str = Query(None),
    status: str = Query(None),
    limit: int = Query(100),
    skip: int = Query(0)
):
    query = {}
    if hotel_id:
        query["hotel_id"] = hotel_id
    if status:
        query["status"] = status
    
    submissions = await db.submissions.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    total = await db.submissions.count_documents(query)
    
    return {
        "items": [serialize_doc(s) for s in submissions],
        "total": total,
        "limit": limit,
        "skip": skip
    }


@api_router.get("/submissions/{submission_id}")
async def get_submission(submission_id: str):
    submission = await db.submissions.find_one({"id": submission_id}, {"_id": 0})
    if not submission:
        raise HTTPException(status_code=404, detail="Gonderim bulunamadi / Submission not found")
    
    # Get attempts
    attempts = await db.attempts.find(
        {"submission_id": submission_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    # Get audit trail
    audit = await get_audit_trail(db, entity_id=submission_id, entity_type="submission")
    
    return {
        "submission": serialize_doc(submission),
        "attempts": [serialize_doc(a) for a in attempts],
        "audit_trail": audit
    }


@api_router.post("/submissions/{submission_id}/requeue")
async def requeue_submission(submission_id: str):
    """Requeue a quarantined or failed submission."""
    submission = await db.submissions.find_one({"id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Gonderim bulunamadi / Submission not found")
    
    if submission["status"] not in [SubmissionStatus.QUARANTINED.value, SubmissionStatus.FAILED.value]:
        raise HTTPException(status_code=400, 
                          detail="Sadece karantina veya basarisiz gonderimler yeniden kuyrulanabilir / Only quarantined or failed submissions can be requeued")
    
    await db.submissions.update_one(
        {"id": submission_id},
        {"$set": {
            "status": SubmissionStatus.QUEUED.value,
            "attempt_count": 0,
            "next_retry_at": None,
            "last_error": None,
            "quarantine_reason": None,
            "updated_at": utcnow().isoformat()
        }}
    )
    
    await log_audit_event(db, submission["hotel_id"], AuditAction.REQUEUED,
                         "submission", submission_id,
                         {"previous_status": submission["status"]})
    
    return {"message": "Gonderim yeniden kuyruga eklendi / Submission requeued", "status": "queued"}


@api_router.post("/submissions/{submission_id}/correct")
async def correct_submission(submission_id: str, correction: SubmissionCorrection):
    """Apply manual corrections to a quarantined submission."""
    submission = await db.submissions.find_one({"id": submission_id})
    if not submission:
        raise HTTPException(status_code=404, detail="Gonderim bulunamadi / Submission not found")
    
    if submission["status"] != SubmissionStatus.QUARANTINED.value:
        raise HTTPException(status_code=400,
                          detail="Sadece karantina gonderimler duzeltebilir / Only quarantined submissions can be corrected")
    
    # Apply corrections to guest_data snapshot
    guest_data = submission.get("guest_data", {})
    corrections_applied = {}
    
    for field, value in correction.model_dump(exclude_none=True).items():
        if value is not None:
            old_value = guest_data.get(field)
            guest_data[field] = value
            corrections_applied[field] = {"old": old_value, "new": value}
    
    # Re-validate
    is_valid, validation_msg = validate_guest_data(guest_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Duzeltme sonrasi dogrulama hatasi / Validation failed after correction: {validation_msg}")
    
    # Update submission
    await db.submissions.update_one(
        {"id": submission_id},
        {"$set": {
            "guest_data": guest_data,
            "status": SubmissionStatus.QUEUED.value,
            "attempt_count": 0,
            "next_retry_at": None,
            "last_error": None,
            "quarantine_reason": None,
            "updated_at": utcnow().isoformat()
        }}
    )
    
    await log_audit_event(db, submission["hotel_id"], AuditAction.MANUAL_CORRECTION,
                         "submission", submission_id,
                         {"corrections": corrections_applied})
    
    return {
        "message": "Duzeltme uygulandi ve yeniden kuyruga eklendi / Correction applied and requeued",
        "corrections": corrections_applied
    }


# ============= AGENT CONTROL =============

@api_router.get("/agents")
async def list_agents():
    """Get all agent statuses."""
    agents = await db.agent_states.find({}, {"_id": 0}).to_list(100)
    return [serialize_doc(a) for a in agents]


@api_router.get("/agents/{hotel_id}")
async def get_agent_status(hotel_id: str):
    """Get agent status for a hotel."""
    agent_state = await db.agent_states.find_one({"hotel_id": hotel_id}, {"_id": 0})
    runtime_status = agent_manager.get_agent(hotel_id)
    
    return {
        "state": serialize_doc(agent_state) if agent_state else None,
        "runtime": runtime_status.get_status() if runtime_status else None
    }


@api_router.post("/agents/{hotel_id}/toggle")
async def toggle_agent(hotel_id: str, online: bool = Query(True)):
    """Toggle agent online/offline."""
    agent = agent_manager.get_agent(hotel_id)
    if not agent:
        # Try to start it
        await agent_manager.start_agent(hotel_id)
        agent = agent_manager.get_agent(hotel_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent bulunamadi / Agent not found")
    
    await agent_manager.toggle_agent(hotel_id, online)
    
    return {
        "message": f"Agent {'cevrimici' if online else 'cevrimdisi'} / Agent {'online' if online else 'offline'}",
        "status": "online" if online else "offline"
    }


@api_router.post("/agents/{hotel_id}/start")
async def start_agent(hotel_id: str):
    """Start the agent for a hotel."""
    await agent_manager.start_agent(hotel_id)
    return {"message": "Agent baslatildi / Agent started"}


@api_router.post("/agents/{hotel_id}/stop")
async def stop_agent(hotel_id: str):
    """Stop the agent for a hotel."""
    await agent_manager.stop_agent(hotel_id)
    return {"message": "Agent durduruldu / Agent stopped"}


# ============= KBS SIMULATION CONTROL =============

@api_router.get("/kbs/simulation")
async def get_kbs_simulation():
    """Get current KBS simulation mode."""
    return get_simulation_mode()


@api_router.post("/kbs/simulation")
async def set_kbs_simulation(mode_update: KBSModeUpdate):
    """Set KBS simulation mode."""
    set_simulation_mode(
        mode_update.mode.value,
        mode_update.error_rate,
        mode_update.delay_seconds
    )
    return {
        "message": f"KBS simulasyon modu '{mode_update.mode.value}' olarak ayarlandi / KBS simulation mode set to '{mode_update.mode.value}'",
        "config": get_simulation_mode()
    }


@api_router.post("/kbs/simulation/reset")
async def reset_kbs_simulation():
    """Reset KBS simulation to normal mode."""
    set_simulation_mode("normal")
    clear_processed_ids()
    return {"message": "KBS simulasyon sifirlandi / KBS simulation reset", "config": get_simulation_mode()}


# ============= AUDIT TRAIL =============

@api_router.get("/audit")
async def list_audit_events(
    hotel_id: str = Query(None),
    entity_type: str = Query(None),
    entity_id: str = Query(None),
    action: str = Query(None),
    limit: int = Query(100),
    skip: int = Query(0)
):
    events = await get_audit_trail(db, hotel_id, entity_type, entity_id, action, limit, skip)
    return {"items": events, "total": len(events)}


@api_router.get("/audit/stats")
async def audit_statistics(hotel_id: str = Query(None)):
    return await get_audit_stats(db, hotel_id)


# ============= METRICS / DASHBOARD =============

@api_router.get("/metrics")
async def get_metrics(hotel_id: str = Query(None)):
    """Get system-wide or hotel-specific metrics."""
    query = {}
    if hotel_id:
        query["hotel_id"] = hotel_id
    
    # Submission counts by status
    status_pipeline = []
    if hotel_id:
        status_pipeline.append({"$match": {"hotel_id": hotel_id}})
    status_pipeline.append({"$group": {"_id": "$status", "count": {"$sum": 1}}})
    
    status_counts = {}
    async for doc in db.submissions.aggregate(status_pipeline):
        status_counts[doc["_id"]] = doc["count"]
    
    total_submissions = sum(status_counts.values())
    success_count = status_counts.get("acked", 0)
    failed_count = status_counts.get("quarantined", 0)
    pending_count = status_counts.get("queued", 0) + status_counts.get("retrying", 0) + status_counts.get("sending", 0) + status_counts.get("pending", 0)
    
    success_rate = (success_count / total_submissions * 100) if total_submissions > 0 else 0
    failure_rate = (failed_count / total_submissions * 100) if total_submissions > 0 else 0
    
    # Agent statuses
    agent_query = {"hotel_id": hotel_id} if hotel_id else {}
    agents = await db.agent_states.find(agent_query, {"_id": 0}).to_list(100)
    
    return {
        "submissions": {
            "total": total_submissions,
            "by_status": status_counts,
            "success_count": success_count,
            "failed_count": failed_count,
            "pending_count": pending_count,
            "success_rate": round(success_rate, 1),
            "failure_rate": round(failure_rate, 1)
        },
        "agents": [serialize_doc(a) for a in agents],
        "kbs_simulation": get_simulation_mode()
    }


@api_router.get("/metrics/timeline")
async def get_metrics_timeline(hotel_id: str = Query(None), hours: int = Query(24)):
    """Get submission timeline for charts."""
    from datetime import timedelta
    
    since = utcnow() - timedelta(hours=hours)
    
    query = {"created_at": {"$gte": since.isoformat()}}
    if hotel_id:
        query["hotel_id"] = hotel_id
    
    submissions = await db.submissions.find(query, {"_id": 0, "status": 1, "created_at": 1}).to_list(1000)
    
    return {"items": submissions, "since": since.isoformat()}


# ============= OBSERVABILITY =============

@api_router.get("/observability")
async def get_observability(hotel_id: str = Query(None)):
    """Phase 4: Comprehensive observability data for monitoring."""
    from datetime import timedelta

    # 1. Submission stats by status
    status_pipeline = []
    if hotel_id:
        status_pipeline.append({"$match": {"hotel_id": hotel_id}})
    status_pipeline.append({"$group": {"_id": "$status", "count": {"$sum": 1}}})
    status_counts = {}
    async for doc in db.submissions.aggregate(status_pipeline):
        status_counts[doc["_id"]] = doc["count"]

    total = sum(status_counts.values())
    success_count = status_counts.get("acked", 0)
    retry_count = status_counts.get("retrying", 0)
    quarantine_count = status_counts.get("quarantined", 0)
    failed_count = status_counts.get("failed", 0)
    queued_count = status_counts.get("queued", 0) + status_counts.get("sending", 0) + status_counts.get("pending", 0)

    success_rate = round((success_count / total * 100), 1) if total > 0 else 0
    failure_rate = round(((quarantine_count + failed_count) / total * 100), 1) if total > 0 else 0

    # 2. Per-hotel breakdown
    hotel_pipeline = [
        {"$group": {
            "_id": {"hotel_id": "$hotel_id", "status": "$status"},
            "count": {"$sum": 1}
        }}
    ]
    if hotel_id:
        hotel_pipeline.insert(0, {"$match": {"hotel_id": hotel_id}})

    hotel_stats_raw = {}
    async for doc in db.submissions.aggregate(hotel_pipeline):
        hid = doc["_id"]["hotel_id"]
        st = doc["_id"]["status"]
        if hid not in hotel_stats_raw:
            hotel_stats_raw[hid] = {}
        hotel_stats_raw[hid][st] = doc["count"]

    # 3. Agent statuses with heartbeat freshness
    agent_query = {"hotel_id": hotel_id} if hotel_id else {}
    agents_raw = await db.agent_states.find(agent_query, {"_id": 0}).to_list(100)
    now = utcnow()

    agents_health = []
    for ag in agents_raw:
        hb = ag.get("last_heartbeat")
        freshness_seconds = None
        heartbeat_stale = True
        if hb:
            try:
                hb_dt = datetime.fromisoformat(hb.replace("Z", "+00:00")) if isinstance(hb, str) else hb
                freshness_seconds = (now - hb_dt).total_seconds()
                heartbeat_stale = freshness_seconds > 60
            except Exception:
                pass

        agents_health.append({
            "hotel_id": ag.get("hotel_id"),
            "status": ag.get("status", "offline"),
            "last_heartbeat": hb,
            "heartbeat_freshness_seconds": round(freshness_seconds, 1) if freshness_seconds is not None else None,
            "heartbeat_stale": heartbeat_stale,
            "queue_size": ag.get("queue_size", 0),
            "processed_today": ag.get("processed_today", 0),
            "failed_today": ag.get("failed_today", 0),
        })

    # 4. Last successful and failed transmissions per hotel
    hotels_list = await db.hotels.find({} if not hotel_id else {"id": hotel_id}, {"_id": 0, "id": 1, "name": 1, "onboarding_status": 1, "authority_region": 1, "integration_type": 1}).to_list(100)

    tenant_readiness = []
    for h in hotels_list:
        hid = h["id"]
        # Last success
        last_ok = await db.submissions.find_one(
            {"hotel_id": hid, "status": "acked"},
            {"_id": 0, "id": 1, "updated_at": 1},
            sort=[("updated_at", -1)]
        )
        # Last error
        last_err = await db.submissions.find_one(
            {"hotel_id": hid, "status": {"$in": ["failed", "quarantined"]}},
            {"_id": 0, "id": 1, "last_error": 1, "updated_at": 1, "status": 1},
            sort=[("updated_at", -1)]
        )
        # KBS config
        kbs_cfg = await db.kbs_configs.find_one({"hotel_id": hid}, {"_id": 0, "last_connection_test": 1, "last_connection_success": 1})
        # Agent
        ag = next((a for a in agents_health if a["hotel_id"] == hid), None)

        h_stats = hotel_stats_raw.get(hid, {})
        h_total = sum(h_stats.values())
        h_success = h_stats.get("acked", 0)

        tenant_readiness.append({
            "hotel_id": hid,
            "hotel_name": h.get("name"),
            "onboarding_status": h.get("onboarding_status", "not_started"),
            "authority_region": h.get("authority_region"),
            "integration_type": h.get("integration_type"),
            "agent_online": ag["status"] == "online" if ag else False,
            "agent_heartbeat_stale": ag["heartbeat_stale"] if ag else True,
            "credential_configured": bool(kbs_cfg),
            "credential_test_success": kbs_cfg.get("last_connection_success") if kbs_cfg else None,
            "submission_total": h_total,
            "submission_success_rate": round((h_success / h_total * 100), 1) if h_total > 0 else 0,
            "last_successful_transmission": serialize_doc(last_ok) if last_ok else None,
            "last_failed_transmission": serialize_doc(last_err) if last_err else None,
        })

    return {
        "summary": {
            "total_submissions": total,
            "success_count": success_count,
            "retry_count": retry_count,
            "quarantine_count": quarantine_count,
            "queued_count": queued_count,
            "success_rate": success_rate,
            "failure_rate": failure_rate,
            "by_status": status_counts,
        },
        "agents": agents_health,
        "tenants": tenant_readiness,
        "timestamp": now.isoformat(),
    }


# ============= GO-LIVE CHECKLIST =============

@api_router.get("/hotels/{hotel_id}/go-live-checklist")
async def get_go_live_checklist(hotel_id: str):
    """Phase 4: Compute per-hotel go-live readiness checklist."""
    hotel = await db.hotels.find_one({"id": hotel_id}, {"_id": 0})
    if not hotel:
        raise HTTPException(status_code=404, detail="Otel bulunamadi / Hotel not found")

    kbs_cfg = await db.kbs_configs.find_one({"hotel_id": hotel_id}, {"_id": 0})
    agent_state = await db.agent_states.find_one({"hotel_id": hotel_id}, {"_id": 0})

    # Check for test submission success
    test_sub_ok = await db.submissions.find_one(
        {"hotel_id": hotel_id, "status": "acked"}, {"_id": 0, "id": 1}
    )
    # Check retry/quarantine flow
    retry_sub = await db.submissions.find_one(
        {"hotel_id": hotel_id, "status": {"$in": ["retrying", "quarantined"]}}, {"_id": 0, "id": 1}
    )
    requeued_sub = await db.audit_events.find_one(
        {"hotel_id": hotel_id, "action": "requeued"}, {"_id": 0, "id": 1}
    )
    # Check audit trail
    audit_count = await db.audit_events.count_documents({"hotel_id": hotel_id})

    items = [
        {
            "key": "authority_region",
            "label_tr": "Yetki bolgesi (EGM/Jandarma) secildi mi?",
            "label_en": "Authority region (EGM/Jandarma) selected?",
            "passed": bool(hotel.get("authority_region")),
            "detail": hotel.get("authority_region") or "Secilmedi / Not selected",
            "category": "configuration"
        },
        {
            "key": "integration_type",
            "label_tr": "Entegrasyon tipi secildi mi?",
            "label_en": "Integration type selected?",
            "passed": bool(hotel.get("integration_type")),
            "detail": hotel.get("integration_type") or "Secilmedi / Not selected",
            "category": "configuration"
        },
        {
            "key": "contact_info",
            "label_tr": "Yetkili iletisim bilgileri girildi mi?",
            "label_en": "Authorized contact info filled?",
            "passed": bool(hotel.get("authorized_contact_name") and hotel.get("authorized_contact_phone")),
            "detail": hotel.get("authorized_contact_name") or "Girilmedi / Not filled",
            "category": "configuration"
        },
        {
            "key": "static_ip",
            "label_tr": "Sabit IP adresi tanimli mi?",
            "label_en": "Static IP address configured?",
            "passed": bool(hotel.get("static_ip")),
            "detail": hotel.get("static_ip") or "Tanimlanmadi / Not configured",
            "category": "network"
        },
        {
            "key": "credentials",
            "label_tr": "Resmi erisim bilgileri girildi mi?",
            "label_en": "Official access credentials entered?",
            "passed": bool(kbs_cfg and kbs_cfg.get("encrypted_secret")),
            "detail": "Yapilandirildi / Configured" if (kbs_cfg and kbs_cfg.get("encrypted_secret")) else "Girilmedi / Not entered",
            "category": "credentials"
        },
        {
            "key": "credential_test",
            "label_tr": "Baglanti testi basarili mi?",
            "label_en": "Connection test successful?",
            "passed": bool(kbs_cfg and kbs_cfg.get("last_connection_success")),
            "detail": kbs_cfg.get("last_connection_test", "Henuz test yapilmadi / Not tested yet") if kbs_cfg else "Henuz test yapilmadi / Not tested yet",
            "category": "credentials"
        },
        {
            "key": "agent_online",
            "label_tr": "Agent cevrimici mi?",
            "label_en": "Agent online?",
            "passed": bool(agent_state and agent_state.get("status") == "online"),
            "detail": agent_state.get("status", "offline") if agent_state else "offline",
            "category": "agent"
        },
        {
            "key": "test_submission",
            "label_tr": "Test gonderimi basarili mi?",
            "label_en": "Test submission successful?",
            "passed": bool(test_sub_ok),
            "detail": "Basarili / Successful" if test_sub_ok else "Henuz test gonderimi yok / No test submission yet",
            "category": "testing"
        },
        {
            "key": "retry_flow",
            "label_tr": "Retry/Karantina akisi dogrulandi mi?",
            "label_en": "Retry/quarantine flow verified?",
            "passed": bool(retry_sub or requeued_sub),
            "detail": "Dogrulandi / Verified" if (retry_sub or requeued_sub) else "Henuz dogrulanmadi / Not verified yet",
            "category": "testing"
        },
        {
            "key": "audit_trail",
            "label_tr": "Denetim izi gorunuyor mu?",
            "label_en": "Audit trail visible?",
            "passed": audit_count > 0,
            "detail": f"{audit_count} kayit / {audit_count} events",
            "category": "compliance"
        },
    ]

    passed_count = sum(1 for i in items if i["passed"])
    total_count = len(items)

    return {
        "hotel_id": hotel_id,
        "hotel_name": hotel.get("name"),
        "items": items,
        "passed": passed_count,
        "total": total_count,
        "ready": passed_count == total_count,
        "readiness_percentage": round((passed_count / total_count * 100), 1) if total_count > 0 else 0,
    }


# ============= KVKK / COMPLIANCE =============

@api_router.get("/compliance/status")
async def get_compliance_status(user: dict = Depends(require_role("admin", "hotel_manager"))):
    """Phase 4: KVKK compliance overview."""
    # PII data counts
    total_guests = await db.guests.count_documents({})
    total_submissions = await db.submissions.count_documents({})
    total_audit = await db.audit_events.count_documents({})

    # Access log counts (PII access events)
    pii_access_count = await db.audit_events.count_documents({"action": "pii_access"})
    data_export_count = await db.audit_events.count_documents({"action": "data_export_request"})
    data_deletion_count = await db.audit_events.count_documents({"action": "data_deletion_request"})

    # Retention stats
    from datetime import timedelta
    thirty_days_ago = (utcnow() - timedelta(days=30)).isoformat()
    old_submissions = await db.submissions.count_documents({"created_at": {"$lte": thirty_days_ago}})

    # Sensitive field inventory
    pii_fields = [
        {"field": "tc_kimlik_no", "collection": "guests", "classification": "Kritik / Critical", "masked_in_ui": True},
        {"field": "passport_no", "collection": "guests", "classification": "Kritik / Critical", "masked_in_ui": True},
        {"field": "first_name", "collection": "guests", "classification": "Kisisel / Personal", "masked_in_ui": False},
        {"field": "last_name", "collection": "guests", "classification": "Kisisel / Personal", "masked_in_ui": False},
        {"field": "birth_date", "collection": "guests", "classification": "Kisisel / Personal", "masked_in_ui": False},
        {"field": "phone", "collection": "guests", "classification": "Iletisim / Contact", "masked_in_ui": False},
        {"field": "email", "collection": "guests", "classification": "Iletisim / Contact", "masked_in_ui": False},
        {"field": "encrypted_secret", "collection": "kbs_configs", "classification": "Gizli / Secret", "masked_in_ui": True},
        {"field": "password_hash", "collection": "users", "classification": "Gizli / Secret", "masked_in_ui": True},
    ]

    return {
        "data_inventory": {
            "total_guests": total_guests,
            "total_submissions_with_pii": total_submissions,
            "total_audit_events": total_audit,
            "submissions_older_than_30d": old_submissions,
        },
        "access_log_summary": {
            "pii_access_count": pii_access_count,
            "data_export_requests": data_export_count,
            "data_deletion_requests": data_deletion_count,
        },
        "pii_field_inventory": pii_fields,
        "retention_policy": {
            "guest_data_retention_days": 365,
            "submission_data_retention_days": 365,
            "audit_log_retention_days": 730,
            "credential_retention": "Otel silininceye kadar / Until hotel deletion",
            "policy_note": "KVKK Madde 7: Kisisel veriler, islenme amacinin ortadan kalkmasi halinde silinir, yok edilir veya anonim hale getirilir."
        },
        "compliance_checklist": [
            {"item": "PII maskeleme / PII masking", "status": "active", "detail": "TC Kimlik ve Pasaport numaralari UI'da maskelenmis"},
            {"item": "Sifreleme / Encryption at rest", "status": "active", "detail": "Servis kimlik bilgileri Fernet ile sifrelenmis"},
            {"item": "Erisim loglama / Access logging", "status": "active", "detail": "Tum PII erisim olaylari audit trail'e kaydedilir"},
            {"item": "Veri ihracat / Data export", "status": "available", "detail": "Misafir verileri JSON formatinda ihrac edilebilir"},
            {"item": "Veri silme / Data deletion", "status": "available", "detail": "Otel bazli veri silme islemi mevcut"},
            {"item": "Erisim kontrolu / Access control", "status": "active", "detail": "RBAC ile rol bazli erisim kontrolu"},
        ],
        "timestamp": utcnow().isoformat()
    }


@api_router.get("/compliance/access-log")
async def get_compliance_access_log(
    hotel_id: str = Query(None),
    limit: int = Query(50),
    skip: int = Query(0),
    user: dict = Depends(require_role("admin"))
):
    """Phase 4: Access log for PII data access tracking."""
    query = {"action": {"$in": ["pii_access", "credential_access", "login_success", "login_failed", "data_export_request", "data_deletion_request"]}}
    if hotel_id:
        query["hotel_id"] = hotel_id

    events = await db.audit_events.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.audit_events.count_documents(query)

    return {"items": events, "total": total, "limit": limit, "skip": skip}


@api_router.post("/compliance/export-request")
async def request_data_export(
    hotel_id: str = Query(...),
    user: dict = Depends(require_role("admin", "hotel_manager"))
):
    """Phase 4: Request PII data export for a hotel (KVKK Article 11)."""
    hotel = await db.hotels.find_one({"id": hotel_id})
    if not hotel:
        raise HTTPException(status_code=404, detail="Otel bulunamadi / Hotel not found")

    # Log the export request
    await log_audit_event(db, hotel_id, AuditAction.DATA_EXPORT_REQUEST, "hotel", hotel_id,
                         {"requested_by": user["email"], "scope": "all_guest_data"}, actor=user["email"])

    # Collect guest data (masked)
    guests = await db.guests.find({"hotel_id": hotel_id}, {"_id": 0}).to_list(1000)
    submissions = await db.submissions.find({"hotel_id": hotel_id}, {"_id": 0}).to_list(1000)

    # Mask PII in export
    for g in guests:
        if g.get("tc_kimlik_no"):
            g["tc_kimlik_no"] = g["tc_kimlik_no"][:3] + "***" + g["tc_kimlik_no"][-2:]
        if g.get("passport_no"):
            g["passport_no"] = g["passport_no"][:2] + "***" + g["passport_no"][-2:]

    return {
        "hotel_id": hotel_id,
        "hotel_name": hotel.get("name"),
        "export_timestamp": utcnow().isoformat(),
        "requested_by": user["email"],
        "data": {
            "guests": [serialize_doc(g) for g in guests],
            "submissions_count": len(submissions),
        },
        "note": "KVKK Madde 11: Ilgili kisi, kisisel verilerin islenip islenmedigini ogrenme ve islenmisse bilgi talep etme hakkina sahiptir."
    }


@api_router.post("/compliance/deletion-request")
async def request_data_deletion(
    hotel_id: str = Query(...),
    user: dict = Depends(require_role("admin"))
):
    """Phase 4: Request PII data deletion for a hotel (KVKK Article 7)."""
    hotel = await db.hotels.find_one({"id": hotel_id})
    if not hotel:
        raise HTTPException(status_code=404, detail="Otel bulunamadi / Hotel not found")

    # Log the deletion request
    await log_audit_event(db, hotel_id, AuditAction.DATA_DELETION_REQUEST, "hotel", hotel_id,
                         {"requested_by": user["email"], "scope": "all_guest_data"}, actor=user["email"])

    # Count what would be deleted
    guest_count = await db.guests.count_documents({"hotel_id": hotel_id})
    submission_count = await db.submissions.count_documents({"hotel_id": hotel_id})
    checkin_count = await db.checkins.count_documents({"hotel_id": hotel_id})

    return {
        "hotel_id": hotel_id,
        "hotel_name": hotel.get("name"),
        "request_timestamp": utcnow().isoformat(),
        "requested_by": user["email"],
        "data_to_delete": {
            "guests": guest_count,
            "submissions": submission_count,
            "checkins": checkin_count,
        },
        "status": "pending_confirmation",
        "note": "KVKK Madde 7: Silme islemi onay sonrasi geri donusumsuz olarak uygulanacaktir. / Deletion will be irreversible after confirmation."
    }


@api_router.post("/compliance/deletion-confirm")
async def confirm_data_deletion(
    hotel_id: str = Query(...),
    user: dict = Depends(require_role("admin"))
):
    """Phase 4: Confirm and execute PII data deletion for a hotel."""
    hotel = await db.hotels.find_one({"id": hotel_id})
    if not hotel:
        raise HTTPException(status_code=404, detail="Otel bulunamadi / Hotel not found")

    # Execute deletion
    del_guests = await db.guests.delete_many({"hotel_id": hotel_id})
    del_submissions = await db.submissions.delete_many({"hotel_id": hotel_id})
    del_checkins = await db.checkins.delete_many({"hotel_id": hotel_id})
    del_attempts = await db.attempts.delete_many({"hotel_id": hotel_id})

    await log_audit_event(db, hotel_id, AuditAction.DATA_DELETION_REQUEST, "hotel", hotel_id,
                         {"action": "deletion_confirmed", "guests_deleted": del_guests.deleted_count,
                          "submissions_deleted": del_submissions.deleted_count}, actor=user["email"])

    return {
        "hotel_id": hotel_id,
        "deleted": {
            "guests": del_guests.deleted_count,
            "submissions": del_submissions.deleted_count,
            "checkins": del_checkins.deleted_count,
            "attempts": del_attempts.deleted_count,
        },
        "timestamp": utcnow().isoformat(),
        "note": "Veriler geri donusumsuz olarak silindi. Denetim kayitlari korunmaktadir. / Data permanently deleted. Audit records preserved."
    }


# ============= DEPLOYMENT GUIDE =============

@api_router.get("/deployment/guide")
async def get_deployment_guide():
    """Phase 4: Structured deployment guide."""
    return {
        "architecture": {
            "title_tr": "Sistem Mimarisi",
            "title_en": "System Architecture",
            "components": [
                {
                    "name": "Cloud Panel",
                    "description_tr": "Merkezi yonetim paneli. Tum otellerin izlenmesi, kullanici yonetimi ve raporlama buradan yapilir.",
                    "description_en": "Central management panel. All hotel monitoring, user management and reporting is done here.",
                    "deployment": "Cloud (Azure/AWS/GCP)",
                    "tech": "FastAPI + React + MongoDB"
                },
                {
                    "name": "Bridge Agent",
                    "description_tr": "Her otelde yerel olarak calisir. KBS SOAP baglantisini gerceklestirir. Sabit IP uzerinden iletisim kurar.",
                    "description_en": "Runs locally at each hotel. Performs KBS SOAP connection. Communicates over static IP.",
                    "deployment": "On-premise (Windows/Linux service)",
                    "tech": "Python service + SOAP client"
                },
                {
                    "name": "KBS Endpoint",
                    "description_tr": "EGM veya Jandarma KBS SOAP servisi. Resmi devlet altyapisi.",
                    "description_en": "EGM or Jandarma KBS SOAP service. Official government infrastructure.",
                    "deployment": "Government hosted",
                    "tech": "SOAP/XML Web Service"
                }
            ]
        },
        "agent_installation": {
            "title_tr": "Agent Kurulum Rehberi",
            "title_en": "Agent Installation Guide",
            "steps": [
                {"step": 1, "tr": "Otel sunucusuna Python 3.10+ yukleyin", "en": "Install Python 3.10+ on hotel server"},
                {"step": 2, "tr": "Agent paketini indirin ve kurun: pip install kbs-bridge-agent", "en": "Download and install agent package: pip install kbs-bridge-agent"},
                {"step": 3, "tr": "Yapilandirma dosyasini (/etc/kbs-agent/config.yaml) duzenleyin", "en": "Edit configuration file (/etc/kbs-agent/config.yaml)"},
                {"step": 4, "tr": "Servisi baslatip otomatik baslangica ekleyin (systemd/Windows service)", "en": "Start service and enable auto-start (systemd/Windows service)"},
                {"step": 5, "tr": "Cloud panel uzerinden agent durumunu dogrulayin", "en": "Verify agent status from cloud panel"},
            ],
            "config_template": {
                "cloud_panel_url": "https://kbs-bridge.example.com",
                "hotel_id": "<OTEL_ID>",
                "api_key": "<AGENT_API_KEY>",
                "kbs_endpoint": "https://kbs.egm.gov.tr/KBSServis.asmx",
                "heartbeat_interval": 15,
                "queue_poll_interval": 5,
                "max_retries": 5,
                "log_level": "INFO"
            }
        },
        "network_requirements": {
            "title_tr": "Ag Gereksinimleri",
            "title_en": "Network Requirements",
            "items": [
                {"tr": "Sabit IP adresi (EGM/Jandarma whitelist icin zorunlu)", "en": "Static IP address (required for EGM/Jandarma whitelist)"},
                {"tr": "HTTPS 443 port erisimi (cloud panel icin)", "en": "HTTPS port 443 access (for cloud panel)"},
                {"tr": "KBS endpoint erisimi (EGM: kbs.egm.gov.tr / Jandarma: ilgili endpoint)", "en": "KBS endpoint access (EGM: kbs.egm.gov.tr / Jandarma: relevant endpoint)"},
                {"tr": "Firewall kurallari: sadece gerekli portlar acik", "en": "Firewall rules: only required ports open"},
                {"tr": "DNS cozumleme: KBS ve cloud panel domainleri", "en": "DNS resolution: KBS and cloud panel domains"},
            ]
        },
        "credential_vault": {
            "title_tr": "Kimlik Bilgisi Kasasi",
            "title_en": "Credential Vault Protection",
            "items": [
                {"tr": "Servis kimlik bilgileri Fernet simetrik sifreleme ile korunur", "en": "Service credentials protected with Fernet symmetric encryption"},
                {"tr": "Sifreleme anahtari sunucu ortam degiskeninde saklanir", "en": "Encryption key stored in server environment variable"},
                {"tr": "API yanitlarinda sifreler her zaman maskelenir", "en": "Passwords always masked in API responses"},
                {"tr": "e-Devlet sifreleri ASLA sistemde saklanmaz", "en": "e-Devlet passwords are NEVER stored in the system"},
            ]
        },
        "environment_separation": {
            "title_tr": "Ortam Ayirimi",
            "title_en": "Environment Separation",
            "environments": [
                {
                    "name": "Test",
                    "tr": "KBS simulatoru ile entegrasyon testleri. Gercek veri gondermez.",
                    "en": "Integration tests with KBS simulator. Does not send real data.",
                    "config": {"kbs_endpoint": "internal_simulator", "mode": "test"}
                },
                {
                    "name": "Staging",
                    "tr": "EGM/Jandarma test ortamina baglanti. Gercek SOAP ama test verileri.",
                    "en": "Connection to EGM/Jandarma test environment. Real SOAP but test data.",
                    "config": {"kbs_endpoint": "egm_test_endpoint", "mode": "staging"}
                },
                {
                    "name": "Production",
                    "tr": "Canli KBS baglantisi. Gercek kimlik bildirimleri.",
                    "en": "Live KBS connection. Real identity notifications.",
                    "config": {"kbs_endpoint": "kbs.egm.gov.tr", "mode": "production"}
                }
            ]
        },
        "per_hotel_config": {
            "title_tr": "Otel Bazli Yapilandirma Dagitimi",
            "title_en": "Per-Hotel Configuration Distribution",
            "items": [
                {"tr": "Her otel icin benzersiz hotel_id ve api_key uretilir", "en": "Unique hotel_id and api_key generated for each hotel"},
                {"tr": "Onboarding sihirbazi uzerinden yapilandirma tamamlanir", "en": "Configuration completed through onboarding wizard"},
                {"tr": "Agent config dosyasi cloud panelden indirilebilir", "en": "Agent config file downloadable from cloud panel"},
                {"tr": "Yapilandirma degisiklikleri agent restart gerektirir", "en": "Configuration changes require agent restart"},
            ]
        }
    }


# ============= UTILITY =============

@api_router.post("/reset-demo")
async def reset_demo():
    """Reset all data for demo purposes."""
    await db.submissions.delete_many({})
    await db.attempts.delete_many({})
    await db.audit_events.delete_many({})
    await db.checkins.delete_many({})
    await db.guests.delete_many({})
    await db.agent_states.delete_many({})
    
    # Don't delete hotels, users, or kbs_configs - keep them for demo
    
    set_simulation_mode("normal")
    clear_processed_ids()
    
    # Restart all agents
    await agent_manager.stop_all()
    async for hotel in db.hotels.find({"is_active": True}):
        await agent_manager.start_agent(hotel["id"])
    
    return {"message": "Demo verileri sifirlandi / Demo data reset"}


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
