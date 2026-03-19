from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import uuid


# ============= ENUMS =============

class SubmissionStatus(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    QUEUED = "queued"
    SENDING = "sending"
    ACKED = "acked"
    FAILED = "failed"
    RETRYING = "retrying"
    QUARANTINED = "quarantined"


class GuestType(str, Enum):
    TC_CITIZEN = "tc_citizen"
    FOREIGN = "foreign"


class KBSErrorCode(str, Enum):
    SUCCESS = "KBS_SUCCESS"
    VALIDATION_FAIL = "KBS_VALIDATION_FAIL"
    DUPLICATE_REJECT = "KBS_DUPLICATE_REJECT"
    TIMEOUT = "KBS_TIMEOUT"
    UNAVAILABLE = "KBS_UNAVAILABLE"
    DELAYED_ACK = "KBS_DELAYED_ACK"
    INTERNAL_ERROR = "KBS_INTERNAL_ERROR"


class UserRole(str, Enum):
    ADMIN = "admin"
    HOTEL_MANAGER = "hotel_manager"
    FRONT_DESK = "front_desk"


class AgentStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"


class AuditAction(str, Enum):
    CHECKIN_CREATED = "checkin_created"
    SUBMISSION_CREATED = "submission_created"
    VALIDATION_SUCCESS = "validation_success"
    VALIDATION_FAILED = "validation_failed"
    QUEUED = "queued"
    SENT_TO_KBS = "sent_to_kbs"
    KBS_ACK = "kbs_ack"
    KBS_FAIL = "kbs_fail"
    RETRY_SCHEDULED = "retry_scheduled"
    QUARANTINED = "quarantined"
    MANUAL_CORRECTION = "manual_correction"
    REQUEUED = "requeued"
    AGENT_HEARTBEAT = "agent_heartbeat"
    AGENT_OFFLINE = "agent_offline"
    AGENT_ONLINE = "agent_online"


# ============= MODELS =============

def utcnow():
    return datetime.now(timezone.utc)


class Hotel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    tax_number: str
    city: str
    address: str
    kbs_institution_code: str = ""
    ip_whitelist: List[str] = Field(default_factory=list)
    agent_config: Dict[str, Any] = Field(default_factory=lambda: {
        "max_retries": 5,
        "retry_base_delay": 2,
        "retry_max_delay": 300,
        "batch_size": 10,
        "heartbeat_interval": 30,
        "queue_poll_interval": 5
    })
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Guest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hotel_id: str
    guest_type: GuestType
    # TC Citizen fields
    tc_kimlik_no: Optional[str] = None
    first_name: str
    last_name: str
    birth_date: Optional[str] = None
    # Foreign national fields
    passport_no: Optional[str] = None
    nationality: Optional[str] = None
    passport_country: Optional[str] = None
    passport_expiry: Optional[str] = None
    # Common
    phone: Optional[str] = None
    email: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class CheckIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hotel_id: str
    guest_id: str
    room_number: str
    check_in_date: str
    check_out_date: Optional[str] = None
    number_of_guests: int = 1
    created_at: datetime = Field(default_factory=utcnow)
    created_by: Optional[str] = None


class Submission(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hotel_id: str
    guest_id: str
    checkin_id: str
    idempotency_key: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: SubmissionStatus = SubmissionStatus.PENDING
    guest_type: GuestType = GuestType.TC_CITIZEN
    # Snapshot of guest data at submission time
    guest_data: Dict[str, Any] = Field(default_factory=dict)
    # KBS response data
    kbs_reference_id: Optional[str] = None
    kbs_response_code: Optional[str] = None
    kbs_response_message: Optional[str] = None
    # Processing
    attempt_count: int = 0
    max_retries: int = 5
    next_retry_at: Optional[datetime] = None
    last_error: Optional[str] = None
    quarantine_reason: Optional[str] = None
    # Timestamps
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    completed_at: Optional[datetime] = None
    # For duplicate prevention
    fingerprint: Optional[str] = None


class Attempt(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    submission_id: str
    hotel_id: str
    attempt_number: int
    status: str  # success, failed, timeout, error
    request_xml: Optional[str] = None
    response_xml: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=utcnow)


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hotel_id: str
    action: AuditAction
    entity_type: str  # submission, guest, checkin, agent
    entity_id: str
    details: Dict[str, Any] = Field(default_factory=dict)
    actor: Optional[str] = None  # user or system
    ip_address: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class AgentState(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hotel_id: str
    status: AgentStatus = AgentStatus.OFFLINE
    last_heartbeat: Optional[datetime] = None
    queue_size: int = 0
    processed_today: int = 0
    failed_today: int = 0
    version: str = "1.0.0"
    ip_address: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    password_hash: str
    first_name: str
    last_name: str
    role: UserRole
    hotel_id: Optional[str] = None  # None for admin (all hotels)
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)


# ============= KBS Simulation Settings =============

class KBSSimulationMode(str, Enum):
    NORMAL = "normal"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    DELAYED_ACK = "delayed_ack"
    DUPLICATE_REJECT = "duplicate_reject"
    VALIDATION_FAIL = "validation_fail"
    RANDOM_ERRORS = "random_errors"


class KBSSimulationConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    hotel_id: str = "global"
    mode: KBSSimulationMode = KBSSimulationMode.NORMAL
    error_rate: float = 0.0  # 0-1, used in random_errors mode
    delay_seconds: float = 0.0  # used in delayed_ack mode
    updated_at: datetime = Field(default_factory=utcnow)


# ============= API Request/Response Models =============

class GuestCreate(BaseModel):
    hotel_id: str
    guest_type: GuestType
    tc_kimlik_no: Optional[str] = None
    first_name: str
    last_name: str
    birth_date: Optional[str] = None
    passport_no: Optional[str] = None
    nationality: Optional[str] = None
    passport_country: Optional[str] = None
    passport_expiry: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class CheckInCreate(BaseModel):
    hotel_id: str
    guest_id: str
    room_number: str
    check_in_date: str
    check_out_date: Optional[str] = None
    number_of_guests: int = 1


class HotelCreate(BaseModel):
    name: str
    tax_number: str
    city: str
    address: str
    kbs_institution_code: str = ""


class SubmissionCorrection(BaseModel):
    tc_kimlik_no: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[str] = None
    passport_no: Optional[str] = None
    nationality: Optional[str] = None
    passport_country: Optional[str] = None
    passport_expiry: Optional[str] = None


class KBSModeUpdate(BaseModel):
    mode: KBSSimulationMode
    error_rate: float = 0.0
    delay_seconds: float = 0.0


def serialize_doc(doc: dict) -> dict:
    """Serialize MongoDB document for JSON response."""
    if doc is None:
        return None
    result = {}
    for key, value in doc.items():
        if key == "_id":
            continue
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = serialize_doc(value)
        elif isinstance(value, list):
            result[key] = [serialize_doc(v) if isinstance(v, dict) else v.isoformat() if isinstance(v, datetime) else v for v in value]
        else:
            result[key] = value
    return result
