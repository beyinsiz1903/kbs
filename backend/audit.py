"""Audit Trail Module.

Provides immutable, append-only audit logging for all system events.
Supports KVKK compliance requirements for data access tracking.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase
import uuid

from models import AuditAction, utcnow

logger = logging.getLogger(__name__)


async def log_audit_event(
    db: AsyncIOMotorDatabase,
    hotel_id: str,
    action: AuditAction,
    entity_type: str,
    entity_id: str,
    details: Dict[str, Any] = None,
    actor: str = "system",
    ip_address: str = None
) -> str:
    """Log an audit event. Returns the event ID."""
    event = {
        "id": str(uuid.uuid4()),
        "hotel_id": hotel_id,
        "action": action.value,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details or {},
        "actor": actor,
        "ip_address": ip_address,
        "created_at": utcnow().isoformat()
    }
    
    await db.audit_events.insert_one(event)
    logger.debug(f"Audit: {action.value} on {entity_type}/{entity_id} by {actor}")
    return event["id"]


async def get_audit_trail(
    db: AsyncIOMotorDatabase,
    hotel_id: str = None,
    entity_type: str = None,
    entity_id: str = None,
    action: str = None,
    limit: int = 100,
    skip: int = 0
) -> List[dict]:
    """Query audit trail with filters."""
    query = {}
    
    if hotel_id:
        query["hotel_id"] = hotel_id
    if entity_type:
        query["entity_type"] = entity_type
    if entity_id:
        query["entity_id"] = entity_id
    if action:
        query["action"] = action
    
    events = await db.audit_events.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    return events


async def get_audit_stats(
    db: AsyncIOMotorDatabase,
    hotel_id: str = None
) -> Dict[str, Any]:
    """Get audit statistics."""
    query = {}
    if hotel_id:
        query["hotel_id"] = hotel_id
    
    total = await db.audit_events.count_documents(query)
    
    # Count by action type using aggregation
    pipeline = []
    if hotel_id:
        pipeline.append({"$match": {"hotel_id": hotel_id}})
    pipeline.append({"$group": {"_id": "$action", "count": {"$sum": 1}}})
    
    action_counts = {}
    async for doc in db.audit_events.aggregate(pipeline):
        action_counts[doc["_id"]] = doc["count"]
    
    return {
        "total_events": total,
        "by_action": action_counts
    }
