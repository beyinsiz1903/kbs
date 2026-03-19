"""KBS Bridge Management System - Core Flow POC Test Script.

Tests all core user stories:
1. Check-in event → queued KBS submission
2. TC Kimlik and Passport validation (separate)
3. Agent heartbeat, queue processing, SOAP/XML send
4. Retry with exponential backoff → quarantine
5. Toggle KBS modes: unavailable, timeout, duplicate, validation fail, delayed ack
6. Duplicate prevention via fingerprint
7. Manual correction and requeue
8. Audit trail verification
"""

import requests
import time
import json
import sys

BASE_URL = "http://localhost:8001/api"

# Test data
HOTEL_DATA = {
    "name": "Grand Istanbul Hotel",
    "tax_number": "1234567890",
    "city": "Istanbul",
    "address": "Taksim Meydani No:1, Beyoglu",
    "kbs_institution_code": "IST-2024-0001"
}

# Valid TC Kimlik: 10000000146 (passes checksum)
TC_GUEST = {
    "guest_type": "tc_citizen",
    "tc_kimlik_no": "10000000146",
    "first_name": "Ahmet",
    "last_name": "Yilmaz",
    "birth_date": "1985-03-15",
    "phone": "+905551234567"
}

FOREIGN_GUEST = {
    "guest_type": "foreign",
    "passport_no": "AB123456",
    "first_name": "John",
    "last_name": "Smith",
    "birth_date": "1990-07-22",
    "nationality": "American",
    "passport_country": "US",
    "passport_expiry": "2028-12-31"
}

# Invalid test data
INVALID_TC_GUEST = {
    "guest_type": "tc_citizen",
    "tc_kimlik_no": "12345678901",  # Invalid checksum
    "first_name": "Invalid",
    "last_name": "User"
}

INVALID_PASSPORT_GUEST = {
    "guest_type": "foreign",
    "passport_no": "AB",  # Too short
    "first_name": "Bad",
    "last_name": "Passport",
    "nationality": "Unknown",
    "passport_country": "XX"
}

results = []
hotel_id = None


def log_test(name, passed, details=""):
    status = "PASS" if passed else "FAIL"
    results.append({"name": name, "passed": passed, "details": details})
    print(f"  [{status}] {name}" + (f" - {details}" if details else ""))


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ============================================================
# TEST 1: Setup - Create Hotel
# ============================================================
def test_create_hotel():
    global hotel_id
    section("TEST 1: Hotel Creation")
    
    r = requests.post(f"{BASE_URL}/hotels", json=HOTEL_DATA)
    if r.status_code == 200:
        hotel_id = r.json()["id"]
        log_test("Create hotel", True, f"id={hotel_id}")
    else:
        log_test("Create hotel", False, r.text)
        return False
    
    # Verify hotel in list
    r = requests.get(f"{BASE_URL}/hotels")
    hotels = r.json()
    found = any(h["id"] == hotel_id for h in hotels)
    log_test("Hotel appears in list", found)
    
    return True


# ============================================================
# TEST 2: TC Citizen Validation + Check-in → Queue
# ============================================================
def test_tc_checkin():
    global hotel_id
    section("TEST 2: TC Citizen Check-in → KBS Queue")
    
    # Create TC guest
    tc_data = {**TC_GUEST, "hotel_id": hotel_id}
    r = requests.post(f"{BASE_URL}/guests", json=tc_data)
    if r.status_code != 200:
        log_test("Create TC guest", False, r.text)
        return
    tc_guest_id = r.json()["id"]
    log_test("Create TC citizen guest", True, f"id={tc_guest_id}")
    
    # Check-in
    checkin_data = {
        "hotel_id": hotel_id,
        "guest_id": tc_guest_id,
        "room_number": "101",
        "check_in_date": "2026-03-19",
        "check_out_date": "2026-03-22",
        "number_of_guests": 1
    }
    r = requests.post(f"{BASE_URL}/checkins", json=checkin_data)
    if r.status_code != 200:
        log_test("TC check-in", False, r.text)
        return
    
    result = r.json()
    log_test("TC check-in created", True)
    log_test("Submission auto-created", "submission" in result)
    log_test("Submission status is 'queued'", result.get("submission", {}).get("status") == "queued")
    log_test("Not duplicate", result.get("duplicate") == False)
    
    return result.get("submission", {}).get("id")


# ============================================================
# TEST 3: Foreign National Validation + Check-in
# ============================================================
def test_foreign_checkin():
    global hotel_id
    section("TEST 3: Foreign National Check-in → KBS Queue")
    
    # Create foreign guest
    fg_data = {**FOREIGN_GUEST, "hotel_id": hotel_id}
    r = requests.post(f"{BASE_URL}/guests", json=fg_data)
    if r.status_code != 200:
        log_test("Create foreign guest", False, r.text)
        return
    fg_guest_id = r.json()["id"]
    log_test("Create foreign guest (passport)", True, f"id={fg_guest_id}")
    
    # Check-in
    checkin_data = {
        "hotel_id": hotel_id,
        "guest_id": fg_guest_id,
        "room_number": "202",
        "check_in_date": "2026-03-19",
        "check_out_date": "2026-03-21"
    }
    r = requests.post(f"{BASE_URL}/checkins", json=checkin_data)
    if r.status_code != 200:
        log_test("Foreign check-in", False, r.text)
        return
    
    result = r.json()
    log_test("Foreign check-in created", True)
    log_test("Submission auto-created", "submission" in result)
    log_test("Guest type is 'foreign'", result.get("submission", {}).get("guest_type") == "foreign")
    
    return result.get("submission", {}).get("id")


# ============================================================
# TEST 4: Invalid Data Rejection
# ============================================================
def test_invalid_data():
    global hotel_id
    section("TEST 4: Invalid Data Rejection")
    
    # Invalid TC Kimlik
    inv_tc = {**INVALID_TC_GUEST, "hotel_id": hotel_id}
    r = requests.post(f"{BASE_URL}/guests", json=inv_tc)
    inv_tc_id = r.json()["id"]
    
    checkin_data = {
        "hotel_id": hotel_id,
        "guest_id": inv_tc_id,
        "room_number": "999",
        "check_in_date": "2026-03-19"
    }
    r = requests.post(f"{BASE_URL}/checkins", json=checkin_data)
    log_test("Invalid TC Kimlik rejected", r.status_code == 400, 
             r.json().get("detail", "") if r.status_code == 400 else f"Got {r.status_code}")
    
    # Invalid Passport
    inv_pp = {**INVALID_PASSPORT_GUEST, "hotel_id": hotel_id}
    r = requests.post(f"{BASE_URL}/guests", json=inv_pp)
    inv_pp_id = r.json()["id"]
    
    checkin_data["guest_id"] = inv_pp_id
    checkin_data["room_number"] = "998"
    r = requests.post(f"{BASE_URL}/checkins", json=checkin_data)
    log_test("Invalid passport rejected", r.status_code == 400,
             r.json().get("detail", "") if r.status_code == 400 else f"Got {r.status_code}")


# ============================================================
# TEST 5: Agent Processing - Normal Success
# ============================================================
def test_agent_success():
    section("TEST 5: Agent Processes Queue → KBS Success")
    
    # Ensure KBS is in normal mode
    requests.post(f"{BASE_URL}/kbs/simulation", json={"mode": "normal"})
    
    # Wait for agent to process
    print("  Waiting for agent to process submissions (8s)...")
    time.sleep(8)
    
    # Check submissions
    r = requests.get(f"{BASE_URL}/submissions", params={"hotel_id": hotel_id})
    subs = r.json()["items"]
    
    acked = [s for s in subs if s["status"] == "acked"]
    log_test("At least one submission ACKED", len(acked) > 0, f"{len(acked)} acked")
    
    if acked:
        sub = acked[0]
        log_test("KBS reference ID assigned", sub.get("kbs_reference_id") is not None,
                sub.get("kbs_reference_id", "none"))
        
        # Check attempts
        r = requests.get(f"{BASE_URL}/submissions/{sub['id']}")
        detail = r.json()
        log_test("Attempt recorded", len(detail.get("attempts", [])) > 0)
        log_test("Audit trail exists", len(detail.get("audit_trail", [])) > 0)
        
        if detail.get("attempts"):
            att = detail["attempts"][0]
            log_test("Request XML present", att.get("request_xml") is not None and len(att.get("request_xml", "")) > 0)
            log_test("Response XML present", att.get("response_xml") is not None and len(att.get("response_xml", "")) > 0)


# ============================================================
# TEST 6: Agent Heartbeat
# ============================================================
def test_agent_heartbeat():
    section("TEST 6: Agent Heartbeat")
    
    r = requests.get(f"{BASE_URL}/agents/{hotel_id}")
    data = r.json()
    
    state = data.get("state")
    runtime = data.get("runtime")
    
    log_test("Agent state exists", state is not None)
    if state:
        log_test("Agent status is online", state.get("status") == "online")
        log_test("Last heartbeat recorded", state.get("last_heartbeat") is not None)
    
    if runtime:
        log_test("Agent runtime is running", runtime.get("is_running") == True)
        log_test("Agent runtime is online", runtime.get("is_online") == True)


# ============================================================
# TEST 7: KBS Unavailable → Retries → Quarantine
# ============================================================
def test_kbs_unavailable():
    section("TEST 7: KBS Unavailable → Retries → Quarantine")
    
    # Set KBS to unavailable
    r = requests.post(f"{BASE_URL}/kbs/simulation", json={"mode": "unavailable"})
    log_test("Set KBS unavailable", r.status_code == 200)
    
    # Create a new guest and check-in
    guest_data = {
        "hotel_id": hotel_id,
        "guest_type": "tc_citizen",
        "tc_kimlik_no": "10000000146",
        "first_name": "Retry",
        "last_name": "Test",
        "birth_date": "1990-01-01"
    }
    r = requests.post(f"{BASE_URL}/guests", json=guest_data)
    guest_id = r.json()["id"]
    
    checkin_data = {
        "hotel_id": hotel_id,
        "guest_id": guest_id,
        "room_number": "303",
        "check_in_date": "2026-03-20"  # Different date to avoid fingerprint dup
    }
    r = requests.post(f"{BASE_URL}/checkins", json=checkin_data)
    sub_id = r.json().get("submission", {}).get("id")
    log_test("New submission queued during KBS outage", sub_id is not None)
    
    # Wait for retries (reduced delays for demo)
    print("  Waiting for retry attempts (15s)...")
    time.sleep(15)
    
    # Check submission state
    r = requests.get(f"{BASE_URL}/submissions/{sub_id}")
    detail = r.json()
    sub = detail.get("submission", {})
    attempts = detail.get("attempts", [])
    
    log_test("Multiple attempts made", len(attempts) > 1, f"{len(attempts)} attempts")
    log_test("Status is retrying or quarantined", 
             sub.get("status") in ["retrying", "quarantined"],
             f"status={sub.get('status')}")
    
    # Now restore KBS and let it succeed
    requests.post(f"{BASE_URL}/kbs/simulation", json={"mode": "normal"})
    
    # If retrying, wait for success
    if sub.get("status") == "retrying":
        print("  KBS restored, waiting for successful retry (10s)...")
        time.sleep(10)
        r = requests.get(f"{BASE_URL}/submissions/{sub_id}")
        sub = r.json().get("submission", {})
        log_test("Submission eventually ACKED after KBS restored", 
                sub.get("status") == "acked",
                f"status={sub.get('status')}")
    
    return sub_id


# ============================================================
# TEST 8: KBS Validation Fail (Non-retryable)
# ============================================================
def test_kbs_validation_fail():
    section("TEST 8: KBS Validation Fail → Quarantine (Non-retryable)")
    
    # Set KBS to validation fail mode
    requests.post(f"{BASE_URL}/kbs/simulation", json={"mode": "validation_fail"})
    
    guest_data = {
        "hotel_id": hotel_id,
        "guest_type": "foreign",
        "passport_no": "XY999888",
        "first_name": "Validation",
        "last_name": "FailTest",
        "nationality": "German",
        "passport_country": "DE",
        "passport_expiry": "2029-01-01",
        "birth_date": "1988-05-20"
    }
    r = requests.post(f"{BASE_URL}/guests", json=guest_data)
    guest_id = r.json()["id"]
    
    checkin_data = {
        "hotel_id": hotel_id,
        "guest_id": guest_id,
        "room_number": "404",
        "check_in_date": "2026-03-21"
    }
    r = requests.post(f"{BASE_URL}/checkins", json=checkin_data)
    sub_id = r.json().get("submission", {}).get("id")
    
    print("  Waiting for KBS validation fail processing (8s)...")
    time.sleep(8)
    
    r = requests.get(f"{BASE_URL}/submissions/{sub_id}")
    sub = r.json().get("submission", {})
    
    log_test("Submission quarantined on validation fail", 
             sub.get("status") == "quarantined",
             f"status={sub.get('status')}, reason={sub.get('quarantine_reason')}")
    log_test("Non-retryable error recognized", 
             "Non-retryable" in (sub.get("quarantine_reason") or ""),
             sub.get("quarantine_reason"))
    
    # Reset KBS
    requests.post(f"{BASE_URL}/kbs/simulation", json={"mode": "normal"})
    
    return sub_id


# ============================================================
# TEST 9: Manual Correction + Requeue
# ============================================================
def test_manual_correction(quarantined_sub_id):
    section("TEST 9: Manual Correction + Requeue")
    
    if not quarantined_sub_id:
        log_test("Quarantined submission available", False, "No quarantined sub from previous test")
        return
    
    # Correct the submission
    correction = {
        "first_name": "Corrected",
        "last_name": "Guest"
    }
    r = requests.post(f"{BASE_URL}/submissions/{quarantined_sub_id}/correct", json=correction)
    log_test("Correction applied", r.status_code == 200, r.json().get("message", ""))
    
    if r.status_code == 200:
        corrections = r.json().get("corrections", {})
        log_test("Correction details returned", len(corrections) > 0, str(corrections))
    
    # Verify it's requeued
    r = requests.get(f"{BASE_URL}/submissions/{quarantined_sub_id}")
    sub = r.json().get("submission", {})
    log_test("Submission requeued after correction", sub.get("status") == "queued")
    
    # Wait for processing
    print("  Waiting for reprocessing (8s)...")
    time.sleep(8)
    
    r = requests.get(f"{BASE_URL}/submissions/{quarantined_sub_id}")
    sub = r.json().get("submission", {})
    log_test("Corrected submission ACKED", sub.get("status") == "acked",
             f"status={sub.get('status')}")


# ============================================================
# TEST 10: Duplicate Prevention
# ============================================================
def test_duplicate_prevention():
    section("TEST 10: Duplicate Prevention")
    
    # Create guest with same data as TC_GUEST and same checkin date
    guest_data = {**TC_GUEST, "hotel_id": hotel_id}
    r = requests.post(f"{BASE_URL}/guests", json=guest_data)
    dup_guest_id = r.json()["id"]
    
    checkin_data = {
        "hotel_id": hotel_id,
        "guest_id": dup_guest_id,
        "room_number": "505",
        "check_in_date": "2026-03-19"  # Same date as TEST 2
    }
    r = requests.post(f"{BASE_URL}/checkins", json=checkin_data)
    result = r.json()
    
    log_test("Duplicate detected", result.get("duplicate") == True,
             result.get("message", ""))


# ============================================================
# TEST 11: Agent Offline Mode
# ============================================================
def test_agent_offline():
    section("TEST 11: Agent Offline Mode")
    
    # Toggle agent offline
    r = requests.post(f"{BASE_URL}/agents/{hotel_id}/toggle", params={"online": False})
    log_test("Agent set to offline", r.status_code == 200)
    
    # Create submission while offline
    guest_data = {
        "hotel_id": hotel_id,
        "guest_type": "tc_citizen",
        "tc_kimlik_no": "10000000146",
        "first_name": "Offline",
        "last_name": "Queue",
        "birth_date": "1995-12-25"
    }
    r = requests.post(f"{BASE_URL}/guests", json=guest_data)
    guest_id = r.json()["id"]
    
    checkin_data = {
        "hotel_id": hotel_id,
        "guest_id": guest_id,
        "room_number": "606",
        "check_in_date": "2026-03-25"
    }
    r = requests.post(f"{BASE_URL}/checkins", json=checkin_data)
    sub_id = r.json().get("submission", {}).get("id")
    
    time.sleep(5)
    
    # Should still be queued (agent is offline)
    r = requests.get(f"{BASE_URL}/submissions/{sub_id}")
    sub = r.json().get("submission", {})
    log_test("Submission stays queued while agent offline", sub.get("status") == "queued")
    
    # Toggle back online
    r = requests.post(f"{BASE_URL}/agents/{hotel_id}/toggle", params={"online": True})
    log_test("Agent set back to online", r.status_code == 200)
    
    print("  Waiting for queued submission to process (8s)...")
    time.sleep(8)
    
    r = requests.get(f"{BASE_URL}/submissions/{sub_id}")
    sub = r.json().get("submission", {})
    log_test("Submission processed after agent online", sub.get("status") == "acked",
             f"status={sub.get('status')}")


# ============================================================
# TEST 12: Delayed ACK Mode
# ============================================================
def test_delayed_ack():
    section("TEST 12: KBS Delayed ACK")
    
    requests.post(f"{BASE_URL}/kbs/simulation", json={
        "mode": "delayed_ack",
        "delay_seconds": 2
    })
    
    guest_data = {
        "hotel_id": hotel_id,
        "guest_type": "foreign",
        "passport_no": "FR789012",
        "first_name": "Delayed",
        "last_name": "AckTest",
        "nationality": "French",
        "passport_country": "FR",
        "passport_expiry": "2030-06-15",
        "birth_date": "1992-08-10"
    }
    r = requests.post(f"{BASE_URL}/guests", json=guest_data)
    guest_id = r.json()["id"]
    
    checkin_data = {
        "hotel_id": hotel_id,
        "guest_id": guest_id,
        "room_number": "707",
        "check_in_date": "2026-03-26"
    }
    r = requests.post(f"{BASE_URL}/checkins", json=checkin_data)
    sub_id = r.json().get("submission", {}).get("id")
    
    print("  Waiting for delayed ACK processing (10s)...")
    time.sleep(10)
    
    r = requests.get(f"{BASE_URL}/submissions/{sub_id}")
    sub = r.json().get("submission", {})
    log_test("Delayed ACK still succeeds", sub.get("status") == "acked",
             f"status={sub.get('status')}")
    
    # Reset
    requests.post(f"{BASE_URL}/kbs/simulation", json={"mode": "normal"})


# ============================================================
# TEST 13: Audit Trail Verification
# ============================================================
def test_audit_trail():
    section("TEST 13: Audit Trail Verification")
    
    r = requests.get(f"{BASE_URL}/audit", params={"hotel_id": hotel_id, "limit": 50})
    events = r.json().get("items", [])
    
    log_test("Audit events exist", len(events) > 0, f"{len(events)} events")
    
    # Check for various event types
    actions_found = set(e["action"] for e in events)
    expected_actions = ["checkin_created", "submission_created", "queued", "sent_to_kbs"]
    
    for action in expected_actions:
        log_test(f"Audit action '{action}' found", action in actions_found)
    
    # Check audit stats
    r = requests.get(f"{BASE_URL}/audit/stats", params={"hotel_id": hotel_id})
    stats = r.json()
    log_test("Audit stats available", stats.get("total_events", 0) > 0,
             f"total={stats.get('total_events')}")


# ============================================================
# TEST 14: Metrics Endpoint
# ============================================================
def test_metrics():
    section("TEST 14: Metrics / Dashboard Data")
    
    r = requests.get(f"{BASE_URL}/metrics", params={"hotel_id": hotel_id})
    metrics = r.json()
    
    log_test("Metrics response valid", "submissions" in metrics)
    
    subs = metrics.get("submissions", {})
    log_test("Total submissions tracked", subs.get("total", 0) > 0, f"total={subs.get('total')}")
    log_test("Success rate calculated", subs.get("success_rate") is not None,
             f"rate={subs.get('success_rate')}%")
    
    log_test("Agent status in metrics", len(metrics.get("agents", [])) > 0)
    log_test("KBS simulation info in metrics", "kbs_simulation" in metrics)


# ============================================================
# MAIN
# ============================================================
def main():
    print("\n" + "="*60)
    print("  KBS BRIDGE MANAGEMENT SYSTEM - POC TEST SUITE")
    print("="*60)
    
    # Reset demo data first
    print("\nResetting demo data...")
    requests.post(f"{BASE_URL}/reset-demo")
    time.sleep(1)
    
    # Run all tests
    if not test_create_hotel():
        print("\nFATAL: Hotel creation failed. Cannot proceed.")
        sys.exit(1)
    
    tc_sub_id = test_tc_checkin()
    fg_sub_id = test_foreign_checkin()
    test_invalid_data()
    test_agent_success()
    test_agent_heartbeat()
    unavail_sub_id = test_kbs_unavailable()
    quarantined_sub_id = test_kbs_validation_fail()
    test_manual_correction(quarantined_sub_id)
    test_duplicate_prevention()
    test_agent_offline()
    test_delayed_ack()
    test_audit_trail()
    test_metrics()
    
    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    total = len(results)
    
    print(f"\n  Total: {total}")
    print(f"  Passed: {passed} ({passed/total*100:.0f}%)")
    print(f"  Failed: {failed}")
    
    if failed > 0:
        print(f"\n  FAILED TESTS:")
        for r in results:
            if not r["passed"]:
                print(f"    - {r['name']}: {r['details']}")
    
    print(f"\n  {'ALL TESTS PASSED!' if failed == 0 else 'SOME TESTS FAILED'}")
    print("="*60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
