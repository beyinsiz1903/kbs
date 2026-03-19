#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime

class KBSBridgeAPITester:
    def __init__(self, base_url="https://kbs-reporting-hub.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.hotel_id = None
        self.guest_id = None
        self.checkin_id = None
        self.submission_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.api_base}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, params=params, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Response: {error_detail}")
                except:
                    print(f"   Response: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health endpoint"""
        return self.run_test("Health Check", "GET", "health", 200)

    def test_create_hotel(self):
        """Test creating a hotel"""
        hotel_data = {
            "name": "Test Grand Hotel",
            "tax_number": "1234567890",
            "city": "Istanbul",
            "address": "Taksim Square No:1",
            "kbs_institution_code": "TEST-2024-001"
        }
        success, response = self.run_test("Create Hotel", "POST", "hotels", 200, hotel_data)
        if success and response.get('id'):
            self.hotel_id = response['id']
            print(f"   Hotel ID: {self.hotel_id}")
        return success, response

    def test_list_hotels(self):
        """Test listing hotels"""
        return self.run_test("List Hotels", "GET", "hotels", 200)

    def test_get_hotel(self):
        """Test getting specific hotel"""
        if not self.hotel_id:
            print("❌ Skipping - No hotel ID available")
            return False, {}
        return self.run_test("Get Hotel", "GET", f"hotels/{self.hotel_id}", 200)

    def test_create_tc_guest(self):
        """Test creating a TC citizen guest"""
        if not self.hotel_id:
            print("❌ Skipping - No hotel ID available")
            return False, {}
            
        guest_data = {
            "hotel_id": self.hotel_id,
            "guest_type": "tc_citizen",
            "tc_kimlik_no": "10000000146",
            "first_name": "Test",
            "last_name": "User",
            "birth_date": "1990-01-01",
            "phone": "+905551234567",
            "email": "test@example.com"
        }
        success, response = self.run_test("Create TC Guest", "POST", "guests", 200, guest_data)
        if success and response.get('id'):
            self.guest_id = response['id']
            print(f"   Guest ID: {self.guest_id}")
        return success, response

    def test_create_foreign_guest(self):
        """Test creating a foreign guest"""
        if not self.hotel_id:
            print("❌ Skipping - No hotel ID available")
            return False, {}
            
        guest_data = {
            "hotel_id": self.hotel_id,
            "guest_type": "foreign",
            "passport_no": "AB123456",
            "nationality": "American",
            "passport_country": "US",
            "passport_expiry": "2025-12-31",
            "first_name": "John",
            "last_name": "Smith"
        }
        success, response = self.run_test("Create Foreign Guest", "POST", "guests", 200, guest_data)
        return success, response

    def test_list_guests(self):
        """Test listing guests"""
        params = {"hotel_id": self.hotel_id} if self.hotel_id else None
        return self.run_test("List Guests", "GET", "guests", 200, params=params)

    def test_create_checkin(self):
        """Test creating a check-in"""
        if not self.hotel_id or not self.guest_id:
            print("❌ Skipping - No hotel ID or guest ID available")
            return False, {}
            
        checkin_data = {
            "hotel_id": self.hotel_id,
            "guest_id": self.guest_id,
            "room_number": "101",
            "check_in_date": "2024-01-15",
            "check_out_date": "2024-01-17",
            "number_of_guests": 1
        }
        success, response = self.run_test("Create Check-in", "POST", "checkins", 200, checkin_data)
        if success and response.get('checkin', {}).get('id'):
            self.checkin_id = response['checkin']['id']
            print(f"   Check-in ID: {self.checkin_id}")
        if success and response.get('submission', {}).get('id'):
            self.submission_id = response['submission']['id']
            print(f"   Submission ID: {self.submission_id}")
        return success, response

    def test_list_checkins(self):
        """Test listing check-ins"""
        params = {"hotel_id": self.hotel_id} if self.hotel_id else None
        return self.run_test("List Check-ins", "GET", "checkins", 200, params=params)

    def test_list_submissions(self):
        """Test listing submissions"""
        params = {"hotel_id": self.hotel_id} if self.hotel_id else None
        return self.run_test("List Submissions", "GET", "submissions", 200, params=params)

    def test_get_submission_detail(self):
        """Test getting submission detail"""
        if not self.submission_id:
            print("❌ Skipping - No submission ID available")
            return False, {}
        return self.run_test("Get Submission Detail", "GET", f"submissions/{self.submission_id}", 200)

    def test_list_agents(self):
        """Test listing agents"""
        return self.run_test("List Agents", "GET", "agents", 200)

    def test_get_agent_status(self):
        """Test getting agent status"""
        if not self.hotel_id:
            print("❌ Skipping - No hotel ID available")
            return False, {}
        return self.run_test("Get Agent Status", "GET", f"agents/{self.hotel_id}", 200)

    def test_toggle_agent(self):
        """Test toggling agent online/offline"""
        if not self.hotel_id:
            print("❌ Skipping - No hotel ID available")
            return False, {}
        
        # Test toggle offline
        success1, response1 = self.run_test("Toggle Agent Offline", "POST", f"agents/{self.hotel_id}/toggle", 200, params={"online": "false"})
        
        # Test toggle back online
        success2, response2 = self.run_test("Toggle Agent Online", "POST", f"agents/{self.hotel_id}/toggle", 200, params={"online": "true"})
        
        return success1 and success2, response2

    def test_kbs_simulation_control(self):
        """Test KBS simulation control"""
        # Get current mode
        success1, response1 = self.run_test("Get KBS Mode", "GET", "kbs/simulation", 200)
        
        # Set unavailable mode
        kbs_data = {
            "mode": "unavailable",
            "error_rate": 0.0,
            "delay_seconds": 0.0
        }
        success2, response2 = self.run_test("Set KBS Unavailable", "POST", "kbs/simulation", 200, kbs_data)
        
        # Reset to normal
        success3, response3 = self.run_test("Reset KBS Mode", "POST", "kbs/simulation/reset", 200)
        
        return success1 and success2 and success3, response3

    def test_get_metrics(self):
        """Test getting metrics/dashboard data"""
        return self.run_test("Get Metrics", "GET", "metrics", 200)

    def test_audit_trail(self):
        """Test audit trail"""
        params = {"hotel_id": self.hotel_id, "limit": 10} if self.hotel_id else {"limit": 10}
        return self.run_test("Get Audit Trail", "GET", "audit", 200, params=params)

    def test_filter_submissions_by_status(self):
        """Test filtering submissions by status"""
        params = {"status": "acked", "limit": 5}
        return self.run_test("Filter Submissions by Status", "GET", "submissions", 200, params=params)

def main():
    print("🚀 Starting KBS Bridge Management System API Tests")
    print("=" * 60)
    
    tester = KBSBridgeAPITester()
    
    # Core functionality tests
    test_sequence = [
        ("Health Check", tester.test_health_check),
        ("Create Hotel", tester.test_create_hotel),
        ("List Hotels", tester.test_list_hotels),
        ("Get Hotel", tester.test_get_hotel),
        ("Create TC Guest", tester.test_create_tc_guest),
        ("Create Foreign Guest", tester.test_create_foreign_guest),
        ("List Guests", tester.test_list_guests),
        ("Create Check-in & Submission", tester.test_create_checkin),
        ("List Check-ins", tester.test_list_checkins),
        ("List Submissions", tester.test_list_submissions),
        ("Get Submission Detail", tester.test_get_submission_detail),
        ("Filter Submissions by Status", tester.test_filter_submissions_by_status),
        ("List Agents", tester.test_list_agents),
        ("Get Agent Status", tester.test_get_agent_status),
        ("Toggle Agent", tester.test_toggle_agent),
        ("KBS Simulation Control", tester.test_kbs_simulation_control),
        ("Get Metrics", tester.test_get_metrics),
        ("Audit Trail", tester.test_audit_trail),
    ]
    
    print(f"Running {len(test_sequence)} test scenarios...")
    
    for test_name, test_func in test_sequence:
        try:
            test_func()
        except Exception as e:
            print(f"❌ {test_name} - Unexpected error: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Tests completed: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        failed = tester.tests_run - tester.tests_passed
        print(f"⚠️  {failed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())