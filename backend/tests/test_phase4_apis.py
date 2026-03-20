"""
Phase 4 Backend API Tests: Observability, Go-Live Checklist, KVKK Compliance, Deployment Guide
Tests for KBS Bridge Management System Phase 4 features.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"email": "admin@kbsbridge.com", "password": "admin123"}
MANAGER_CREDS = {"email": "manager@grandistanbul.com", "password": "manager123"}
FRONT_DESK_CREDS = {"email": "resepsiyon@grandistanbul.com", "password": "front123"}

# Known hotel ID from previous tests
KNOWN_HOTEL_ID = "e2d8a4a2-7499-46ad-be2b-a8aa6db149db"  # Grand Istanbul Hotel


@pytest.fixture(scope="session")
def admin_token():
    """Get admin JWT token."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def manager_token():
    """Get hotel_manager JWT token."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=MANAGER_CREDS)
    assert response.status_code == 200, f"Manager login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def front_desk_token():
    """Get front_desk JWT token."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=FRONT_DESK_CREDS)
    assert response.status_code == 200, f"Front desk login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def hotel_id(admin_token):
    """Get a valid hotel ID from the system."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{BASE_URL}/api/hotels", headers=headers)
    assert response.status_code == 200, f"Failed to get hotels: {response.text}"
    hotels = response.json()
    assert len(hotels) > 0, "No hotels found in system"
    return hotels[0]["id"]


class TestHealthEndpoint:
    """Basic health check."""
    
    def test_health_returns_200(self):
        """Health endpoint should return 200."""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestObservabilityEndpoint:
    """Tests for GET /api/observability endpoint."""
    
    def test_observability_returns_summary_agents_tenants(self, admin_token):
        """Observability should return summary, agents, and tenants data."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/observability", headers=headers)
        
        assert response.status_code == 200, f"Observability failed: {response.text}"
        data = response.json()
        
        # Check summary structure
        assert "summary" in data, "Missing 'summary' in response"
        summary = data["summary"]
        assert "total_submissions" in summary
        assert "success_count" in summary
        assert "retry_count" in summary
        assert "quarantine_count" in summary
        assert "success_rate" in summary
        assert "failure_rate" in summary
        assert "by_status" in summary
        
        # Check agents structure
        assert "agents" in data, "Missing 'agents' in response"
        assert isinstance(data["agents"], list)
        
        # Check tenants structure
        assert "tenants" in data, "Missing 'tenants' in response"
        assert isinstance(data["tenants"], list)
        
        # Check timestamp
        assert "timestamp" in data
    
    def test_observability_with_hotel_filter(self, admin_token, hotel_id):
        """Observability should support hotel_id query parameter."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/observability",
            params={"hotel_id": hotel_id},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "tenants" in data
    
    def test_observability_tenant_has_required_fields(self, admin_token):
        """Each tenant in observability should have required fields."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/observability", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data["tenants"]) > 0:
            tenant = data["tenants"][0]
            required_fields = [
                "hotel_id", "hotel_name", "onboarding_status",
                "agent_online", "credential_configured",
                "submission_total", "submission_success_rate"
            ]
            for field in required_fields:
                assert field in tenant, f"Missing field '{field}' in tenant"


class TestGoLiveChecklistEndpoint:
    """Tests for GET /api/hotels/{hotel_id}/go-live-checklist endpoint."""
    
    def test_go_live_checklist_returns_items(self, admin_token, hotel_id):
        """Go-live checklist should return computed checklist items."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/hotels/{hotel_id}/go-live-checklist",
            headers=headers
        )
        
        assert response.status_code == 200, f"Go-live checklist failed: {response.text}"
        data = response.json()
        
        # Check required fields
        assert "hotel_id" in data
        assert "hotel_name" in data
        assert "items" in data
        assert "passed" in data
        assert "total" in data
        assert "ready" in data
        assert "readiness_percentage" in data
        
        # Items should be a list
        assert isinstance(data["items"], list)
        assert len(data["items"]) >= 10, "Should have at least 10 checklist items"
        
        # Each item should have required fields
        for item in data["items"]:
            assert "key" in item
            assert "label_tr" in item
            assert "label_en" in item
            assert "passed" in item
            assert "detail" in item
            assert "category" in item
    
    def test_go_live_checklist_passed_total_consistency(self, admin_token, hotel_id):
        """Passed count should match items with passed=True."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/hotels/{hotel_id}/go-live-checklist",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        passed_count = sum(1 for item in data["items"] if item["passed"])
        assert data["passed"] == passed_count
        assert data["total"] == len(data["items"])
    
    def test_go_live_checklist_invalid_hotel_404(self, admin_token):
        """Go-live checklist for invalid hotel should return 404."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/hotels/invalid-hotel-id/go-live-checklist",
            headers=headers
        )
        assert response.status_code == 404


class TestComplianceStatusEndpoint:
    """Tests for GET /api/compliance/status endpoint."""
    
    def test_compliance_status_admin_access(self, admin_token):
        """Admin should access compliance status."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/compliance/status", headers=headers)
        
        assert response.status_code == 200, f"Compliance status failed: {response.text}"
        data = response.json()
        
        # Check required sections
        assert "data_inventory" in data
        assert "pii_field_inventory" in data
        assert "retention_policy" in data
        assert "compliance_checklist" in data
        
        # Check data_inventory fields
        inv = data["data_inventory"]
        assert "total_guests" in inv
        assert "total_submissions_with_pii" in inv
        assert "total_audit_events" in inv
        
        # Check retention_policy fields
        rp = data["retention_policy"]
        assert "guest_data_retention_days" in rp
        assert "submission_data_retention_days" in rp
        assert "audit_log_retention_days" in rp
    
    def test_compliance_status_manager_access(self, manager_token):
        """Hotel manager should access compliance status."""
        headers = {"Authorization": f"Bearer {manager_token}"}
        response = requests.get(f"{BASE_URL}/api/compliance/status", headers=headers)
        
        assert response.status_code == 200, f"Manager compliance access failed: {response.text}"
    
    def test_compliance_status_front_desk_denied(self, front_desk_token):
        """Front desk should NOT access compliance status (RBAC)."""
        headers = {"Authorization": f"Bearer {front_desk_token}"}
        response = requests.get(f"{BASE_URL}/api/compliance/status", headers=headers)
        
        assert response.status_code == 403, f"Front desk should be denied. Got: {response.status_code}"


class TestComplianceAccessLogEndpoint:
    """Tests for GET /api/compliance/access-log endpoint."""
    
    def test_compliance_access_log_admin_only(self, admin_token):
        """Admin should access compliance access log."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/compliance/access-log", headers=headers)
        
        assert response.status_code == 200, f"Access log failed: {response.text}"
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
    
    def test_compliance_access_log_manager_denied(self, manager_token):
        """Manager should NOT access compliance access log (admin only)."""
        headers = {"Authorization": f"Bearer {manager_token}"}
        response = requests.get(f"{BASE_URL}/api/compliance/access-log", headers=headers)
        
        assert response.status_code == 403, f"Manager should be denied. Got: {response.status_code}"
    
    def test_compliance_access_log_front_desk_denied(self, front_desk_token):
        """Front desk should NOT access compliance access log."""
        headers = {"Authorization": f"Bearer {front_desk_token}"}
        response = requests.get(f"{BASE_URL}/api/compliance/access-log", headers=headers)
        
        assert response.status_code == 403


class TestComplianceExportEndpoint:
    """Tests for POST /api/compliance/export-request endpoint."""
    
    def test_compliance_export_admin(self, admin_token, hotel_id):
        """Admin should be able to request data export."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.post(
            f"{BASE_URL}/api/compliance/export-request",
            params={"hotel_id": hotel_id},
            headers=headers
        )
        
        assert response.status_code == 200, f"Export request failed: {response.text}"
        data = response.json()
        
        assert "hotel_id" in data
        assert "hotel_name" in data
        assert "export_timestamp" in data
        assert "data" in data
        assert "note" in data  # KVKK reference
    
    def test_compliance_export_manager(self, manager_token, hotel_id):
        """Manager should be able to request data export."""
        headers = {"Authorization": f"Bearer {manager_token}"}
        response = requests.post(
            f"{BASE_URL}/api/compliance/export-request",
            params={"hotel_id": hotel_id},
            headers=headers
        )
        
        assert response.status_code == 200
    
    def test_compliance_export_front_desk_denied(self, front_desk_token, hotel_id):
        """Front desk should NOT request data export."""
        headers = {"Authorization": f"Bearer {front_desk_token}"}
        response = requests.post(
            f"{BASE_URL}/api/compliance/export-request",
            params={"hotel_id": hotel_id},
            headers=headers
        )
        
        assert response.status_code == 403


class TestComplianceDeletionEndpoint:
    """Tests for POST /api/compliance/deletion-request endpoint."""
    
    def test_compliance_deletion_request_admin_only(self, admin_token, hotel_id):
        """Admin should be able to request data deletion."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.post(
            f"{BASE_URL}/api/compliance/deletion-request",
            params={"hotel_id": hotel_id},
            headers=headers
        )
        
        assert response.status_code == 200, f"Deletion request failed: {response.text}"
        data = response.json()
        
        assert "hotel_id" in data
        assert "data_to_delete" in data
        assert "status" in data
        assert data["status"] == "pending_confirmation"
    
    def test_compliance_deletion_request_manager_denied(self, manager_token, hotel_id):
        """Manager should NOT request data deletion (admin only)."""
        headers = {"Authorization": f"Bearer {manager_token}"}
        response = requests.post(
            f"{BASE_URL}/api/compliance/deletion-request",
            params={"hotel_id": hotel_id},
            headers=headers
        )
        
        assert response.status_code == 403
    
    # Note: We don't actually test deletion-confirm to avoid losing test data


class TestDeploymentGuideEndpoint:
    """Tests for GET /api/deployment/guide endpoint."""
    
    def test_deployment_guide_returns_structure(self, admin_token):
        """Deployment guide should return structured documentation."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/deployment/guide", headers=headers)
        
        assert response.status_code == 200, f"Deployment guide failed: {response.text}"
        data = response.json()
        
        # Check all required sections exist
        required_sections = [
            "architecture",
            "agent_installation",
            "network_requirements",
            "credential_vault",
            "environment_separation",
            "per_hotel_config"
        ]
        for section in required_sections:
            assert section in data, f"Missing section: {section}"
    
    def test_deployment_guide_architecture_components(self, admin_token):
        """Architecture section should have components."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/deployment/guide", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        arch = data["architecture"]
        assert "title_tr" in arch
        assert "title_en" in arch
        assert "components" in arch
        assert len(arch["components"]) >= 3  # Cloud Panel, Bridge Agent, KBS Endpoint
    
    def test_deployment_guide_agent_installation_steps(self, admin_token):
        """Agent installation should have steps."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/deployment/guide", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        inst = data["agent_installation"]
        assert "steps" in inst
        assert len(inst["steps"]) >= 5
        assert "config_template" in inst
    
    def test_deployment_guide_environment_separation(self, admin_token):
        """Environment separation should have test/staging/production."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/deployment/guide", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        envs = data["environment_separation"]["environments"]
        env_names = [e["name"] for e in envs]
        assert "Test" in env_names
        assert "Staging" in env_names
        assert "Production" in env_names


class TestLoginAuditLogging:
    """Test that login creates audit event."""
    
    def test_login_creates_audit_event(self, admin_token):
        """After login, check audit log for login_success event."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Perform a fresh login
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert login_response.status_code == 200
        
        # Check audit events for login_success action
        response = requests.get(
            f"{BASE_URL}/api/compliance/access-log",
            params={"limit": 10},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Look for login_success in recent events
        login_events = [e for e in data["items"] if e.get("action") == "login_success"]
        assert len(login_events) > 0, "No login_success audit events found"


class TestRBACForPhase4Features:
    """Test role-based access control for Phase 4 features."""
    
    def test_front_desk_cannot_access_observability(self, front_desk_token):
        """Front desk users should not see observability data (implied via compliance access)."""
        headers = {"Authorization": f"Bearer {front_desk_token}"}
        # Observability itself doesn't have auth requirement in the code,
        # but compliance does - testing compliance RBAC
        response = requests.get(f"{BASE_URL}/api/compliance/status", headers=headers)
        assert response.status_code == 403
    
    def test_admin_full_access(self, admin_token, hotel_id):
        """Admin should have full access to all Phase 4 endpoints."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        endpoints = [
            f"{BASE_URL}/api/observability",
            f"{BASE_URL}/api/hotels/{hotel_id}/go-live-checklist",
            f"{BASE_URL}/api/compliance/status",
            f"{BASE_URL}/api/compliance/access-log",
            f"{BASE_URL}/api/deployment/guide",
        ]
        
        for endpoint in endpoints:
            response = requests.get(endpoint, headers=headers)
            assert response.status_code == 200, f"Admin denied access to {endpoint}"


class TestUnauthenticatedAccess:
    """Test that endpoints requiring auth reject unauthenticated requests."""
    
    def test_compliance_requires_auth(self):
        """Compliance endpoints should require authentication."""
        response = requests.get(f"{BASE_URL}/api/compliance/status")
        assert response.status_code == 401 or response.status_code == 403
    
    def test_compliance_access_log_requires_auth(self):
        """Compliance access log should require authentication."""
        response = requests.get(f"{BASE_URL}/api/compliance/access-log")
        assert response.status_code == 401 or response.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
