from fastapi import FastAPI, APIRouter, HTTPException, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone

from models import (
    Hotel, Guest, CheckIn, Submission, SubmissionStatus, GuestType,
    AuditAction, AgentStatus, KBSSimulationMode,
    HotelCreate, GuestCreate, CheckInCreate, SubmissionCorrection, KBSModeUpdate,
    serialize_doc, utcnow
)
from validators import validate_guest_data, generate_fingerprint
from kbs_simulator import set_simulation_mode, get_simulation_mode, clear_processed_ids
from agent_runtime import AgentManager
from audit import log_audit_event, get_audit_trail, get_audit_stats

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
    
    # Don't delete hotels - keep them for demo
    
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
