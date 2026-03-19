"""Simulated KBS (Kimlik Bildirme Sistemi) SOAP/XML Service.

This module simulates the Turkish Identity Reporting System's SOAP endpoint
with realistic request/response patterns, error codes, and failure scenarios.
"""
import asyncio
import random
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional
from lxml import etree


# ============= SOAP/XML Templates =============

SOAP_REQUEST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:kbs="http://kbs.egm.gov.tr/bildirim">
    <soap:Header>
        <kbs:Authentication>
            <kbs:InstitutionCode>{institution_code}</kbs:InstitutionCode>
            <kbs:Timestamp>{timestamp}</kbs:Timestamp>
        </kbs:Authentication>
    </soap:Header>
    <soap:Body>
        <kbs:KimlikBildirim>
            <kbs:BildirimId>{bildirim_id}</kbs:BildirimId>
            <kbs:MisafirTipi>{guest_type}</kbs:MisafirTipi>
            {identity_block}
            <kbs:Ad>{first_name}</kbs:Ad>
            <kbs:Soyad>{last_name}</kbs:Soyad>
            <kbs:DogumTarihi>{birth_date}</kbs:DogumTarihi>
            <kbs:GirisTarihi>{checkin_date}</kbs:GirisTarihi>
            <kbs:OdaNo>{room_number}</kbs:OdaNo>
        </kbs:KimlikBildirim>
    </soap:Body>
</soap:Envelope>"""

SOAP_RESPONSE_SUCCESS = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:kbs="http://kbs.egm.gov.tr/bildirim">
    <soap:Body>
        <kbs:KimlikBildirimResponse>
            <kbs:Sonuc>BASARILI</kbs:Sonuc>
            <kbs:ReferansNo>{reference_id}</kbs:ReferansNo>
            <kbs:BildirimId>{bildirim_id}</kbs:BildirimId>
            <kbs:Mesaj>Kimlik bildirimi basariyla alindi</kbs:Mesaj>
            <kbs:IslemZamani>{timestamp}</kbs:IslemZamani>
        </kbs:KimlikBildirimResponse>
    </soap:Body>
</soap:Envelope>"""

SOAP_RESPONSE_ERROR = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:kbs="http://kbs.egm.gov.tr/bildirim">
    <soap:Body>
        <soap:Fault>
            <faultcode>{fault_code}</faultcode>
            <faultstring>{fault_string}</faultstring>
            <detail>
                <kbs:HataDetay>
                    <kbs:HataKodu>{error_code}</kbs:HataKodu>
                    <kbs:HataMesaji>{error_message}</kbs:HataMesaji>
                    <kbs:BildirimId>{bildirim_id}</kbs:BildirimId>
                </kbs:HataDetay>
            </detail>
        </soap:Fault>
    </soap:Body>
</soap:Envelope>"""

SOAP_RESPONSE_UNAVAILABLE = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <soap:Fault>
            <faultcode>soap:Server</faultcode>
            <faultstring>Service Temporarily Unavailable</faultstring>
            <detail>
                <kbs:HataDetay xmlns:kbs="http://kbs.egm.gov.tr/bildirim">
                    <kbs:HataKodu>KBS_503</kbs:HataKodu>
                    <kbs:HataMesaji>KBS sistemi gecici olarak kullanim disi. Lutfen daha sonra tekrar deneyin.</kbs:HataMesaji>
                </kbs:HataDetay>
            </detail>
        </soap:Fault>
    </soap:Body>
</soap:Envelope>"""

# ============= KBS Error Definitions =============

KBS_ERRORS = {
    "VALIDATION_FAIL": {
        "fault_code": "soap:Client",
        "fault_string": "Validation Error",
        "error_code": "KBS_400",
        "error_messages": [
            "TC Kimlik numarasi dogrunalanamadi",
            "Pasaport bilgileri eksik veya hatali",
            "Dogum tarihi formati gecersiz",
            "Zorunlu alan eksik: Ad/Soyad"
        ]
    },
    "DUPLICATE_REJECT": {
        "fault_code": "soap:Client",
        "fault_string": "Duplicate Entry",
        "error_code": "KBS_409",
        "error_messages": [
            "Bu misafir icin ayni tarihte bildirim zaten mevcut",
            "Mukerrer bildirim tespit edildi"
        ]
    },
    "INTERNAL_ERROR": {
        "fault_code": "soap:Server",
        "fault_string": "Internal Server Error",
        "error_code": "KBS_500",
        "error_messages": [
            "Sistem hatasi olustu, lutfen tekrar deneyin",
            "Dahili islem hatasi"
        ]
    }
}


# ============= Global simulation state (in-memory) =============
_simulation_config = {
    "mode": "normal",
    "error_rate": 0.0,
    "delay_seconds": 0.0
}

_processed_bildirim_ids = set()  # Track for duplicate detection


def set_simulation_mode(mode: str, error_rate: float = 0.0, delay_seconds: float = 0.0):
    """Update simulation mode."""
    global _simulation_config
    _simulation_config = {
        "mode": mode,
        "error_rate": error_rate,
        "delay_seconds": delay_seconds
    }


def get_simulation_mode() -> Dict[str, Any]:
    """Get current simulation mode."""
    return _simulation_config.copy()


def clear_processed_ids():
    """Clear processed bildirim IDs (for testing)."""
    _processed_bildirim_ids.clear()


def build_soap_request(submission_data: Dict[str, Any]) -> str:
    """Build a SOAP/XML request from submission data."""
    guest_data = submission_data.get("guest_data", {})
    guest_type = guest_data.get("guest_type", "tc_citizen")
    
    if guest_type == "tc_citizen":
        identity_block = f'<kbs:TCKimlikNo>{guest_data.get("tc_kimlik_no", "")}</kbs:TCKimlikNo>'
    else:
        identity_block = (
            f'<kbs:PasaportNo>{guest_data.get("passport_no", "")}</kbs:PasaportNo>\n'
            f'            <kbs:Uyruk>{guest_data.get("nationality", "")}</kbs:Uyruk>\n'
            f'            <kbs:PasaportUlke>{guest_data.get("passport_country", "")}</kbs:PasaportUlke>'
        )
    
    return SOAP_REQUEST_TEMPLATE.format(
        institution_code=submission_data.get("kbs_institution_code", "UNKNOWN"),
        timestamp=datetime.now(timezone.utc).isoformat(),
        bildirim_id=submission_data.get("idempotency_key", str(uuid.uuid4())),
        guest_type="TC_VATANDAS" if guest_type == "tc_citizen" else "YABANCI_UYRUKLU",
        identity_block=identity_block,
        first_name=guest_data.get("first_name", ""),
        last_name=guest_data.get("last_name", ""),
        birth_date=guest_data.get("birth_date", ""),
        checkin_date=submission_data.get("checkin_date", ""),
        room_number=submission_data.get("room_number", "")
    )


async def send_to_kbs(submission_data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Simulate sending data to KBS SOAP endpoint.
    
    Returns:
        Tuple of (success: bool, response_xml: str, metadata: dict)
    """
    mode = _simulation_config["mode"]
    bildirim_id = submission_data.get("idempotency_key", str(uuid.uuid4()))
    timestamp = datetime.now(timezone.utc).isoformat()
    
    request_xml = build_soap_request(submission_data)
    
    # Simulate network latency
    await asyncio.sleep(random.uniform(0.1, 0.5))
    
    # ---- UNAVAILABLE MODE ----
    if mode == "unavailable":
        return False, SOAP_RESPONSE_UNAVAILABLE, {
            "error_code": "KBS_UNAVAILABLE",
            "error_message": "KBS sistemi kullanim disi",
            "request_xml": request_xml,
            "retryable": True
        }
    
    # ---- TIMEOUT MODE ----
    if mode == "timeout":
        await asyncio.sleep(min(_simulation_config.get("delay_seconds", 10), 10))
        return False, "", {
            "error_code": "KBS_TIMEOUT",
            "error_message": "KBS baglanti zaman asimi",
            "request_xml": request_xml,
            "retryable": True
        }
    
    # ---- DELAYED ACK MODE ----
    if mode == "delayed_ack":
        delay = _simulation_config.get("delay_seconds", 3)
        await asyncio.sleep(min(delay, 5))
        # Still succeeds, just delayed
        reference_id = f"KBS-{uuid.uuid4().hex[:12].upper()}"
        _processed_bildirim_ids.add(bildirim_id)
        response_xml = SOAP_RESPONSE_SUCCESS.format(
            reference_id=reference_id,
            bildirim_id=bildirim_id,
            timestamp=timestamp
        )
        return True, response_xml, {
            "reference_id": reference_id,
            "request_xml": request_xml,
            "delayed": True,
            "delay_seconds": delay
        }
    
    # ---- DUPLICATE REJECT MODE ----
    if mode == "duplicate_reject" or bildirim_id in _processed_bildirim_ids:
        error_info = KBS_ERRORS["DUPLICATE_REJECT"]
        response_xml = SOAP_RESPONSE_ERROR.format(
            fault_code=error_info["fault_code"],
            fault_string=error_info["fault_string"],
            error_code=error_info["error_code"],
            error_message=random.choice(error_info["error_messages"]),
            bildirim_id=bildirim_id
        )
        return False, response_xml, {
            "error_code": "KBS_DUPLICATE_REJECT",
            "error_message": "Mukerrer bildirim",
            "request_xml": request_xml,
            "retryable": False
        }
    
    # ---- VALIDATION FAIL MODE ----
    if mode == "validation_fail":
        error_info = KBS_ERRORS["VALIDATION_FAIL"]
        response_xml = SOAP_RESPONSE_ERROR.format(
            fault_code=error_info["fault_code"],
            fault_string=error_info["fault_string"],
            error_code=error_info["error_code"],
            error_message=random.choice(error_info["error_messages"]),
            bildirim_id=bildirim_id
        )
        return False, response_xml, {
            "error_code": "KBS_VALIDATION_FAIL",
            "error_message": "KBS dogrulama hatasi",
            "request_xml": request_xml,
            "retryable": False
        }
    
    # ---- RANDOM ERRORS MODE ----
    if mode == "random_errors":
        error_rate = _simulation_config.get("error_rate", 0.3)
        if random.random() < error_rate:
            error_type = random.choice(["VALIDATION_FAIL", "DUPLICATE_REJECT", "INTERNAL_ERROR"])
            error_info = KBS_ERRORS[error_type]
            response_xml = SOAP_RESPONSE_ERROR.format(
                fault_code=error_info["fault_code"],
                fault_string=error_info["fault_string"],
                error_code=error_info["error_code"],
                error_message=random.choice(error_info["error_messages"]),
                bildirim_id=bildirim_id
            )
            retryable = error_type == "INTERNAL_ERROR"
            return False, response_xml, {
                "error_code": f"KBS_{error_type}",
                "error_message": error_info["error_messages"][0],
                "request_xml": request_xml,
                "retryable": retryable
            }
    
    # ---- NORMAL / SUCCESS ----
    reference_id = f"KBS-{uuid.uuid4().hex[:12].upper()}"
    _processed_bildirim_ids.add(bildirim_id)
    response_xml = SOAP_RESPONSE_SUCCESS.format(
        reference_id=reference_id,
        bildirim_id=bildirim_id,
        timestamp=timestamp
    )
    return True, response_xml, {
        "reference_id": reference_id,
        "request_xml": request_xml
    }
