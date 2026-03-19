"""Simulated KBS Bridge Agent Runtime.

This module simulates the behavior of a local bridge agent that would
run as a Windows/Linux service at each hotel location.

It processes the submission queue, sends to KBS, handles retries
with exponential backoff, and manages quarantine.
"""
import asyncio
import random
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from models import SubmissionStatus, AgentStatus, AuditAction, utcnow
from kbs_simulator import send_to_kbs, get_simulation_mode
from audit import log_audit_event

logger = logging.getLogger(__name__)


class BridgeAgentRuntime:
    """Simulated bridge agent that processes the KBS submission queue."""
    
    def __init__(self, db: AsyncIOMotorDatabase, hotel_id: str):
        self.db = db
        self.hotel_id = hotel_id
        self.is_running = False
        self.is_online = True
        self._task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        # Configuration
        self.config = {
            "max_retries": 5,
            "retry_base_delay": 2,
            "retry_max_delay": 60,  # Reduced for demo
            "batch_size": 10,
            "heartbeat_interval": 15,
            "queue_poll_interval": 3
        }
    
    async def start(self):
        """Start the agent runtime."""
        if self.is_running:
            return
        
        self.is_running = True
        self.is_online = True
        
        # Initialize agent state in DB
        await self._update_agent_state(AgentStatus.ONLINE)
        
        # Start background tasks
        self._task = asyncio.create_task(self._process_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        await log_audit_event(self.db, self.hotel_id, AuditAction.AGENT_ONLINE,
                            "agent", self.hotel_id, {"message": "Agent started"})
        
        logger.info(f"Bridge agent started for hotel {self.hotel_id}")
    
    async def stop(self):
        """Stop the agent runtime."""
        self.is_running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        await self._update_agent_state(AgentStatus.OFFLINE)
        await log_audit_event(self.db, self.hotel_id, AuditAction.AGENT_OFFLINE,
                            "agent", self.hotel_id, {"message": "Agent stopped"})
        
        logger.info(f"Bridge agent stopped for hotel {self.hotel_id}")
    
    async def set_online(self, online: bool):
        """Toggle agent online/offline mode."""
        self.is_online = online
        status = AgentStatus.ONLINE if online else AgentStatus.OFFLINE
        await self._update_agent_state(status)
        
        action = AuditAction.AGENT_ONLINE if online else AuditAction.AGENT_OFFLINE
        await log_audit_event(self.db, self.hotel_id, action,
                            "agent", self.hotel_id, 
                            {"message": f"Agent {'online' if online else 'offline'}"})
    
    async def _process_loop(self):
        """Main processing loop - picks up queued submissions and sends to KBS."""
        while self.is_running:
            try:
                if not self.is_online:
                    await asyncio.sleep(self.config["queue_poll_interval"])
                    continue
                
                # Fetch queued or retrying submissions
                now = utcnow()
                submissions = await self.db.submissions.find({
                    "hotel_id": self.hotel_id,
                    "status": {"$in": [
                        SubmissionStatus.QUEUED.value,
                        SubmissionStatus.RETRYING.value
                    ]},
                    "$or": [
                        {"next_retry_at": None},
                        {"next_retry_at": {"$lte": now.isoformat()}}
                    ]
                }).sort("created_at", 1).limit(self.config["batch_size"]).to_list(self.config["batch_size"])
                
                for submission in submissions:
                    if not self.is_running or not self.is_online:
                        break
                    await self._process_submission(submission)
                
                await asyncio.sleep(self.config["queue_poll_interval"])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Agent processing error: {e}")
                await asyncio.sleep(5)
    
    async def _process_submission(self, submission: dict):
        """Process a single submission - send to KBS and handle response."""
        submission_id = submission["id"]
        attempt_number = submission.get("attempt_count", 0) + 1
        
        try:
            # Update status to SENDING
            await self.db.submissions.update_one(
                {"id": submission_id},
                {"$set": {
                    "status": SubmissionStatus.SENDING.value,
                    "updated_at": utcnow().isoformat()
                }}
            )
            
            await log_audit_event(self.db, self.hotel_id, AuditAction.SENT_TO_KBS,
                                "submission", submission_id,
                                {"attempt": attempt_number})
            
            # Get hotel KBS config
            hotel = await self.db.hotels.find_one({"id": self.hotel_id})
            kbs_institution_code = hotel.get("kbs_institution_code", "") if hotel else ""
            
            # Prepare submission data for KBS
            kbs_data = {
                "idempotency_key": submission.get("idempotency_key"),
                "guest_data": submission.get("guest_data", {}),
                "kbs_institution_code": kbs_institution_code,
                "checkin_date": submission.get("guest_data", {}).get("check_in_date", ""),
                "room_number": submission.get("guest_data", {}).get("room_number", "")
            }
            
            # Send to simulated KBS
            start_time = datetime.now(timezone.utc)
            success, response_xml, metadata = await send_to_kbs(kbs_data)
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            
            # Record attempt
            attempt = {
                "id": str(asyncio.get_event_loop().time()).replace(".", "")[-12:],
                "submission_id": submission_id,
                "hotel_id": self.hotel_id,
                "attempt_number": attempt_number,
                "status": "success" if success else "failed",
                "request_xml": metadata.get("request_xml", ""),
                "response_xml": response_xml,
                "error_code": metadata.get("error_code"),
                "error_message": metadata.get("error_message"),
                "duration_ms": duration_ms,
                "created_at": utcnow().isoformat()
            }
            await self.db.attempts.insert_one(attempt)
            
            if success:
                # SUCCESS - update submission
                await self.db.submissions.update_one(
                    {"id": submission_id},
                    {"$set": {
                        "status": SubmissionStatus.ACKED.value,
                        "kbs_reference_id": metadata.get("reference_id"),
                        "kbs_response_code": "SUCCESS",
                        "kbs_response_message": "Bildirim basariyla alindi",
                        "attempt_count": attempt_number,
                        "completed_at": utcnow().isoformat(),
                        "updated_at": utcnow().isoformat()
                    }}
                )
                
                await log_audit_event(self.db, self.hotel_id, AuditAction.KBS_ACK,
                                    "submission", submission_id,
                                    {"reference_id": metadata.get("reference_id"),
                                     "attempt": attempt_number})
                
                # Update daily counters
                await self.db.agent_states.update_one(
                    {"hotel_id": self.hotel_id},
                    {"$inc": {"processed_today": 1}}
                )
                
                logger.info(f"Submission {submission_id} ACKED (attempt {attempt_number})")
                
            else:
                # FAILURE - determine if retryable
                retryable = metadata.get("retryable", True)
                error_code = metadata.get("error_code", "UNKNOWN")
                error_message = metadata.get("error_message", "Bilinmeyen hata")
                
                if not retryable or attempt_number >= submission.get("max_retries", self.config["max_retries"]):
                    # QUARANTINE
                    quarantine_reason = f"Max retries exceeded" if retryable else f"Non-retryable error: {error_code}"
                    
                    await self.db.submissions.update_one(
                        {"id": submission_id},
                        {"$set": {
                            "status": SubmissionStatus.QUARANTINED.value,
                            "attempt_count": attempt_number,
                            "last_error": error_message,
                            "quarantine_reason": quarantine_reason,
                            "kbs_response_code": error_code,
                            "kbs_response_message": error_message,
                            "updated_at": utcnow().isoformat()
                        }}
                    )
                    
                    await log_audit_event(self.db, self.hotel_id, AuditAction.QUARANTINED,
                                        "submission", submission_id,
                                        {"reason": quarantine_reason,
                                         "error_code": error_code,
                                         "attempt": attempt_number})
                    
                    await self.db.agent_states.update_one(
                        {"hotel_id": self.hotel_id},
                        {"$inc": {"failed_today": 1}}
                    )
                    
                    logger.warning(f"Submission {submission_id} QUARANTINED: {quarantine_reason}")
                    
                else:
                    # RETRY with exponential backoff + jitter
                    base_delay = self.config["retry_base_delay"]
                    max_delay = self.config["retry_max_delay"]
                    delay = min(base_delay * (2 ** (attempt_number - 1)), max_delay)
                    jitter = random.uniform(0, delay * 0.3)
                    total_delay = delay + jitter
                    
                    next_retry = utcnow() + timedelta(seconds=total_delay)
                    
                    await self.db.submissions.update_one(
                        {"id": submission_id},
                        {"$set": {
                            "status": SubmissionStatus.RETRYING.value,
                            "attempt_count": attempt_number,
                            "last_error": error_message,
                            "next_retry_at": next_retry.isoformat(),
                            "kbs_response_code": error_code,
                            "kbs_response_message": error_message,
                            "updated_at": utcnow().isoformat()
                        }}
                    )
                    
                    await log_audit_event(self.db, self.hotel_id, AuditAction.RETRY_SCHEDULED,
                                        "submission", submission_id,
                                        {"attempt": attempt_number,
                                         "next_retry_at": next_retry.isoformat(),
                                         "delay_seconds": total_delay})
                    
                    logger.info(f"Submission {submission_id} RETRYING in {total_delay:.1f}s (attempt {attempt_number})")
        
        except Exception as e:
            logger.error(f"Error processing submission {submission_id}: {e}")
            # Mark as retrying on unexpected errors
            await self.db.submissions.update_one(
                {"id": submission_id},
                {"$set": {
                    "status": SubmissionStatus.RETRYING.value,
                    "last_error": str(e),
                    "attempt_count": attempt_number,
                    "updated_at": utcnow().isoformat()
                }}
            )
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat updates."""
        while self.is_running:
            try:
                # Count queue size
                queue_size = await self.db.submissions.count_documents({
                    "hotel_id": self.hotel_id,
                    "status": {"$in": [
                        SubmissionStatus.PENDING.value,
                        SubmissionStatus.QUEUED.value,
                        SubmissionStatus.RETRYING.value,
                        SubmissionStatus.SENDING.value
                    ]}
                })
                
                status = AgentStatus.ONLINE if self.is_online else AgentStatus.OFFLINE
                
                await self.db.agent_states.update_one(
                    {"hotel_id": self.hotel_id},
                    {"$set": {
                        "status": status.value,
                        "last_heartbeat": utcnow().isoformat(),
                        "queue_size": queue_size,
                        "updated_at": utcnow().isoformat()
                    }},
                    upsert=True
                )
                
                await asyncio.sleep(self.config["heartbeat_interval"])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(5)
    
    async def _update_agent_state(self, status: AgentStatus):
        """Update agent state in database."""
        await self.db.agent_states.update_one(
            {"hotel_id": self.hotel_id},
            {"$set": {
                "hotel_id": self.hotel_id,
                "status": status.value,
                "last_heartbeat": utcnow().isoformat(),
                "updated_at": utcnow().isoformat(),
                "config": self.config
            }},
            upsert=True
        )
    
    def get_status(self) -> dict:
        """Get current agent status."""
        return {
            "hotel_id": self.hotel_id,
            "is_running": self.is_running,
            "is_online": self.is_online,
            "config": self.config
        }


# ============= Agent Manager =============

class AgentManager:
    """Manages bridge agent instances for multiple hotels."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.agents: Dict[str, BridgeAgentRuntime] = {}
    
    async def start_agent(self, hotel_id: str) -> BridgeAgentRuntime:
        """Start or get agent for a hotel."""
        if hotel_id in self.agents:
            agent = self.agents[hotel_id]
            if not agent.is_running:
                await agent.start()
            return agent
        
        agent = BridgeAgentRuntime(self.db, hotel_id)
        
        # Load hotel config
        hotel = await self.db.hotels.find_one({"id": hotel_id})
        if hotel and hotel.get("agent_config"):
            agent.config.update(hotel["agent_config"])
        
        await agent.start()
        self.agents[hotel_id] = agent
        return agent
    
    async def stop_agent(self, hotel_id: str):
        """Stop agent for a hotel."""
        if hotel_id in self.agents:
            await self.agents[hotel_id].stop()
            del self.agents[hotel_id]
    
    async def toggle_agent(self, hotel_id: str, online: bool):
        """Toggle agent online/offline."""
        if hotel_id in self.agents:
            await self.agents[hotel_id].set_online(online)
    
    def get_agent(self, hotel_id: str) -> Optional[BridgeAgentRuntime]:
        """Get agent instance."""
        return self.agents.get(hotel_id)
    
    async def stop_all(self):
        """Stop all agents."""
        for hotel_id in list(self.agents.keys()):
            await self.stop_agent(hotel_id)
    
    def get_all_status(self) -> dict:
        """Get status of all agents."""
        return {
            hotel_id: agent.get_status()
            for hotel_id, agent in self.agents.items()
        }
