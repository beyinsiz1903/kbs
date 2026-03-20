#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime

class KBSBridgeAPITester:
    def __init__(self, base_url="https://hotel-pms-bridge.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.hotel_id = None
        self.guest_id = None
        self.checkin_id = None
        self.submission_id = None
        self.admin_token = None
        self.manager_token = None
        self.front_desk_token = None
        self.admin_user = None
        self.manager_user = None
        self.front_desk_user = None

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None, token=None):
        """Run a single API test"""
        url = f"{self.api_base}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        # Add authorization header if token provided
        if token:
            headers['Authorization'] = f'Bearer {token}'

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
    
    # ============= PHASE 3: AUTHENTICATION & RBAC TESTS =============
    
    def test_admin_login(self):
        """Test admin login with JWT"""
        login_data = {
            "email": "admin@kbsbridge.com",
            "password": "admin123"
        }
        success, response = self.run_test("Admin Login", "POST", "auth/login", 200, login_data)
        if success and response.get('access_token'):
            self.admin_token = response['access_token']
            self.admin_user = response.get('user', {})
            print(f"   Admin Token: {self.admin_token[:20]}...")
            print(f"   Admin Role: {self.admin_user.get('role')}")
        return success, response
    
    def test_manager_login(self):
        """Test hotel manager login with JWT"""
        login_data = {
            "email": "manager@grandistanbul.com",
            "password": "manager123"
        }
        success, response = self.run_test("Manager Login", "POST", "auth/login", 200, login_data)
        if success and response.get('access_token'):
            self.manager_token = response['access_token']
            self.manager_user = response.get('user', {})
            print(f"   Manager Token: {self.manager_token[:20]}...")
            print(f"   Manager Role: {self.manager_user.get('role')}")
        return success, response
    
    def test_front_desk_login(self):
        """Test front desk login with JWT"""
        login_data = {
            "email": "resepsiyon@grandistanbul.com", 
            "password": "front123"
        }
        success, response = self.run_test("Front Desk Login", "POST", "auth/login", 200, login_data)
        if success and response.get('access_token'):
            self.front_desk_token = response['access_token']
            self.front_desk_user = response.get('user', {})
            print(f"   Front Desk Token: {self.front_desk_token[:20]}...")
            print(f"   Front Desk Role: {self.front_desk_user.get('role')}")
        return success, response
    
    def test_invalid_login(self):
        """Test login with invalid credentials"""
        login_data = {
            "email": "invalid@example.com",
            "password": "wrongpassword"
        }
        return self.run_test("Invalid Login", "POST", "auth/login", 401, login_data)
    
    def test_get_current_user_admin(self):
        """Test /auth/me endpoint with admin token"""
        if not self.admin_token:
            print("❌ Skipping - No admin token available")
            return False, {}
        return self.run_test("Get Current User (Admin)", "GET", "auth/me", 200, token=self.admin_token)
    
    def test_get_current_user_manager(self):
        """Test /auth/me endpoint with manager token"""
        if not self.manager_token:
            print("❌ Skipping - No manager token available")
            return False, {}
        return self.run_test("Get Current User (Manager)", "GET", "auth/me", 200, token=self.manager_token)
    
    def test_unauthorized_access(self):
        """Test accessing protected endpoint without token"""
        return self.run_test("Unauthorized Access", "GET", "auth/me", 401)
    
    # ============= USERS MANAGEMENT (Admin only) =============
    
    def test_list_users_admin(self):
        """Test listing users as admin"""
        if not self.admin_token:
            print("❌ Skipping - No admin token available")
            return False, {}
        return self.run_test("List Users (Admin)", "GET", "users", 200, token=self.admin_token)
    
    def test_list_users_non_admin(self):
        """Test listing users as non-admin (should fail)"""
        if not self.manager_token:
            print("❌ Skipping - No manager token available")  
            return False, {}
        return self.run_test("List Users (Non-Admin)", "GET", "users", 403, token=self.manager_token)
    
    def test_create_user_admin(self):
        """Test creating user as admin"""
        if not self.admin_token:
            print("❌ Skipping - No admin token available")
            return False, {}
        
        user_data = {
            "email": f"test_user_{datetime.now().strftime('%H%M%S')}@test.com",
            "password": "testpass123",
            "first_name": "Test",
            "last_name": "User", 
            "role": "front_desk",
            "hotel_ids": []
        }
        return self.run_test("Create User (Admin)", "POST", "users", 200, user_data, token=self.admin_token)
    
    # ============= HOTEL ONBOARDING TESTS =============
    
    def get_hotel_id(self):
        """Get first available hotel ID"""
        if self.hotel_id:
            return self.hotel_id
            
        success, response = self.run_test("Get Hotels for ID", "GET", "hotels", 200)
        if success and response and len(response) > 0:
            self.hotel_id = response[0]['id']
    def test_hotel_onboarding_update(self):
        """Test hotel onboarding wizard update"""
        hotel_id = self.get_hotel_id()
        if not hotel_id:
            print("❌ Skipping - No hotel ID available")
            return False, {}
        
        onboarding_data = {
            "authority_region": "egm",
            "integration_type": "egm_kbs", 
            "district": "Beyoglu",
            "authorized_contact_name": "Test Contact",
            "authorized_contact_phone": "+905551234567",
            "authorized_contact_email": "contact@test.com",
            "static_ip": "203.0.113.10",
            "kbs_institution_code": "TEST-2024-001",
            "onboarding_step": 2,
            "onboarding_status": "in_progress"
        }
        return self.run_test("Hotel Onboarding Update", "PUT", f"hotels/{hotel_id}/onboarding", 200, onboarding_data)
    
    def test_kbs_config_update(self):
        """Test KBS config/credential vault update"""
        hotel_id = self.get_hotel_id()
        if not hotel_id:
            print("❌ Skipping - No hotel ID available")
            return False, {}
        
        kbs_config_data = {
            "kbs_username": "test_kbs_user",
            "facility_code": "FACILITY001",
            "service_username": "service_user",
            "secret": "test_secret_password",
            "endpoint_url": "https://kbs.egm.gov.tr/ws/submit.asmx",
            "environment": "test",
            "auth_method": "username_password"
        }
        return self.run_test("KBS Config Update", "PUT", f"hotels/{hotel_id}/kbs-config", 200, kbs_config_data)
    
    def test_get_kbs_config(self):
        """Test getting KBS config (secrets should be masked)"""
        hotel_id = self.get_hotel_id()
        if not hotel_id:
            print("❌ Skipping - No hotel ID available")
            return False, {}
        
        success, response = self.run_test("Get KBS Config", "GET", f"hotels/{hotel_id}/kbs-config", 200)
        if success:
            # Verify that secrets are masked
            if response.get('encrypted_secret') == "********":
                print(f"   ✅ Secret properly masked")
            else:
                print(f"   ⚠️ Secret masking may not be working properly")
        return success, response
    
    def test_hotel_integration_test(self):
        """Test hotel integration connectivity test"""
        hotel_id = self.get_hotel_id()
        if not hotel_id:
            print("❌ Skipping - No hotel ID available")
            return False, {}
        
        success, response = self.run_test("Hotel Integration Test", "POST", f"hotels/{hotel_id}/integration/test", 200)
        if success:
            print(f"   Test Result: {response.get('success')}")
            print(f"   Message: {response.get('message')}")
        return success, response
    
    # ============= HOTEL HEALTH PANEL =============
    
    def test_hotel_health_panel(self):
        """Test hotel health panel data"""
        hotel_id = self.get_hotel_id()
        if not hotel_id:
            print("❌ Skipping - No hotel ID available")
            return False, {}
        
        success, response = self.run_test("Hotel Health Panel", "GET", f"hotels/{hotel_id}/health", 200)
        if success:
            # Check that we get expected health data structure
            expected_keys = ['hotel', 'agent', 'integration', 'submissions', 'onboarding_status']
            for key in expected_keys:
                if key in response:
                    print(f"   ✅ {key} data present")
                else:
                    print(f"   ⚠️ {key} data missing")
        return success, response
    
    # ============= ORIGINAL CORE TESTS (from Phase 1) =============
    
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

    def test_get_metrics(self):
        """Test getting metrics/dashboard data"""
        return self.run_test("Get Metrics", "GET", "metrics", 200)
    
    def test_audit_trail(self):
        """Test audit trail"""
        params = {"hotel_id": self.hotel_id, "limit": 10} if self.hotel_id else {"limit": 10}
        return self.run_test("Get Audit Trail", "GET", "audit", 200, params=params)

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
    print("🚀 Starting KBS Bridge Management System Phase 3 API Tests")
    print("=" * 70)
    print("Testing: JWT Auth, RBAC, Hotel Onboarding, Credential Vault, Health Panel")
    print("=" * 70)
    
    tester = KBSBridgeAPITester()
    
    # Phase 3 focused test sequence
    test_sequence = [
        ("Health Check", tester.test_health_check),
        
        # Authentication & RBAC Tests
        ("Admin Login", tester.test_admin_login),
        ("Manager Login", tester.test_manager_login), 
        ("Front Desk Login", tester.test_front_desk_login),
        ("Invalid Login", tester.test_invalid_login),
        ("Get Current User (Admin)", tester.test_get_current_user_admin),
        ("Get Current User (Manager)", tester.test_get_current_user_manager),
        ("Unauthorized Access", tester.test_unauthorized_access),
        
        # RBAC - User Management
        ("List Users (Admin Only)", tester.test_list_users_admin),
        ("List Users (Non-Admin - Should Fail)", tester.test_list_users_non_admin),
        ("Create User (Admin Only)", tester.test_create_user_admin),
        
        # Hotel Onboarding Wizard
        ("Hotel Onboarding Update", tester.test_hotel_onboarding_update),
        
        # Credential Vault
        ("KBS Config Update", tester.test_kbs_config_update),
        ("Get KBS Config (Secrets Masked)", tester.test_get_kbs_config),
        ("Hotel Integration Test", tester.test_hotel_integration_test),
        
        # Hotel Health Panel
        ("Hotel Health Panel", tester.test_hotel_health_panel),
        
        # Supporting APIs
        ("List Hotels", tester.test_list_hotels),
        ("Get Metrics", tester.test_get_metrics),
    ]
    
    print(f"Running {len(test_sequence)} Phase 3 test scenarios...")
    
    for test_name, test_func in test_sequence:
        try:
            test_func()
        except Exception as e:
            print(f"❌ {test_name} - Unexpected error: {e}")
    
    print("\n" + "=" * 70)
    print(f"📊 Phase 3 Tests completed: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All Phase 3 tests passed!")
        return 0
    else:
        failed = tester.tests_run - tester.tests_passed
        print(f"⚠️  {failed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())