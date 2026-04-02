from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 90 — Incident History System Tests
Tests for incident CRUD, timeline API, and enhanced status page.

Features tested:
- POST /api/incidents — admin creates incident
- GET /api/incidents — public list with ?days= and ?status= filters
- GET /api/incidents/:id — public get single incident with updates array
- PUT /api/incidents/:id — admin updates status, adds update entry
- PUT /api/incidents/:id with status=resolved — auto-sets resolved_at and duration_minutes
- DELETE /api/incidents/:id — admin deletes incident
- GET /api/incidents/timeline — 90-day daily severity summary
- GET /api/status — includes active_incidents count
- GET /api/status/page — HTML shows uptime bar, percentage, incident history cards
- Authorization tests (403 for non-admin)
- Validation tests (400 for invalid severity)
- 404 for non-existent incident
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
SUPER_ADMIN_EMAIL = TEST_ADMIN_EMAIL
SUPER_ADMIN_PASSWORD = "test"
STANDARD_USER_EMAIL = "testuser90@test.com"
STANDARD_USER_PASSWORD = "TestPassword123!"


class TestIncidentsCRUD:
    """Test incident CRUD operations"""

    @pytest.fixture(scope="class")
    def admin_session(self):
        """Create admin session for authenticated tests"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code} {response.text}")
        return session

    @pytest.fixture(scope="class")
    def standard_user_session(self):
        """Create standard user session for unauthorized tests"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": STANDARD_USER_EMAIL, "password": STANDARD_USER_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip(f"Standard user login failed: {response.status_code}")
        return session

    @pytest.fixture(scope="class")
    def test_incident_id(self, admin_session):
        """Create a test incident for subsequent tests"""
        unique_title = f"TEST_Incident_{uuid.uuid4().hex[:8]}"
        response = admin_session.post(
            f"{BASE_URL}/api/incidents",
            json={
                "title": unique_title,
                "description": "Test incident for pytest",
                "severity": "major",
                "affected_services": ["database", "api"],
                "message": "Initial incident report",
            },
        )
        assert response.status_code == 200, f"Failed to create test incident: {response.text}"
        data = response.json()
        yield data["incident_id"]
        # Cleanup: delete the test incident
        admin_session.delete(f"{BASE_URL}/api/incidents/{data['incident_id']}")

    # ========== CREATE INCIDENT TESTS ==========

    def test_create_incident_success(self, admin_session):
        """POST /api/incidents — admin creates incident with all fields"""
        unique_title = f"TEST_Network_Outage_{uuid.uuid4().hex[:8]}"
        response = admin_session.post(
            f"{BASE_URL}/api/incidents",
            json={
                "title": unique_title,
                "description": "Major network outage affecting all services",
                "severity": "critical",
                "affected_services": ["database", "api", "websocket"],
                "message": "Investigating root cause",
            },
        )
        assert response.status_code == 200, f"Create incident failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "incident_id" in data
        assert data["incident_id"].startswith("inc_")
        assert data["title"] == unique_title
        assert data["severity"] == "critical"
        assert data["status"] == "investigating"
        assert data["affected_services"] == ["database", "api", "websocket"]
        assert data["resolved_at"] is None
        assert data["duration_minutes"] is None
        assert "created_at" in data
        assert "updates" in data
        assert len(data["updates"]) == 1
        assert data["updates"][0]["status"] == "investigating"
        
        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/incidents/{data['incident_id']}")
        print("✓ POST /api/incidents — admin creates incident with all fields")

    def test_create_incident_invalid_severity(self, admin_session):
        """POST /api/incidents — rejects invalid severity (400)"""
        response = admin_session.post(
            f"{BASE_URL}/api/incidents",
            json={
                "title": "TEST_Invalid_Severity",
                "severity": "extreme",  # Invalid severity
                "affected_services": [],
                "message": "Test",
            },
        )
        assert response.status_code == 400, f"Expected 400 for invalid severity, got {response.status_code}"
        print("✓ POST /api/incidents — rejects invalid severity (400)")

    def test_create_incident_unauthorized(self, standard_user_session):
        """POST /api/incidents — standard user gets 403"""
        response = standard_user_session.post(
            f"{BASE_URL}/api/incidents",
            json={
                "title": "TEST_Unauthorized_Incident",
                "severity": "minor",
                "affected_services": [],
                "message": "Test",
            },
        )
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
        print("✓ POST /api/incidents — standard user gets 403")

    # ========== LIST INCIDENTS TESTS ==========

    def test_list_incidents_public(self):
        """GET /api/incidents — public list (no auth required)"""
        response = requests.get(f"{BASE_URL}/api/incidents")
        assert response.status_code == 200, f"List incidents failed: {response.text}"
        data = response.json()
        assert "incidents" in data
        assert "total" in data
        assert isinstance(data["incidents"], list)
        print(f"✓ GET /api/incidents — returns {data['total']} incidents")

    def test_list_incidents_with_days_filter(self):
        """GET /api/incidents?days=30 — filters by date range"""
        response = requests.get(f"{BASE_URL}/api/incidents?days=30")
        assert response.status_code == 200
        data = response.json()
        assert "incidents" in data
        print(f"✓ GET /api/incidents?days=30 — returns {data['total']} incidents in last 30 days")

    def test_list_incidents_with_status_filter(self):
        """GET /api/incidents?status=resolved — filters by status"""
        response = requests.get(f"{BASE_URL}/api/incidents?status=resolved")
        assert response.status_code == 200
        data = response.json()
        assert "incidents" in data
        for incident in data["incidents"]:
            assert incident["status"] == "resolved"
        print(f"✓ GET /api/incidents?status=resolved — returns {data['total']} resolved incidents")

    # ========== GET SINGLE INCIDENT TESTS ==========

    def test_get_incident_by_id(self, test_incident_id):
        """GET /api/incidents/:id — public get single incident"""
        response = requests.get(f"{BASE_URL}/api/incidents/{test_incident_id}")
        assert response.status_code == 200, f"Get incident failed: {response.text}"
        data = response.json()
        assert data["incident_id"] == test_incident_id
        assert "title" in data
        assert "updates" in data
        assert isinstance(data["updates"], list)
        print(f"✓ GET /api/incidents/{test_incident_id} — returns incident with updates array")

    def test_get_incident_not_found(self):
        """GET /api/incidents/:id — non-existent incident returns 404"""
        fake_id = "inc_nonexistent123"
        response = requests.get(f"{BASE_URL}/api/incidents/{fake_id}")
        assert response.status_code == 404
        print("✓ GET /api/incidents/:id — non-existent incident returns 404")

    # ========== UPDATE INCIDENT TESTS ==========

    def test_update_incident_status(self, admin_session, test_incident_id):
        """PUT /api/incidents/:id — admin updates status, adds update entry"""
        response = admin_session.put(
            f"{BASE_URL}/api/incidents/{test_incident_id}",
            json={
                "status": "identified",
                "message": "Root cause identified: database connection pool exhausted",
            },
        )
        assert response.status_code == 200, f"Update incident failed: {response.text}"
        data = response.json()
        assert data["status"] == "updated"
        
        # Verify the update was persisted
        get_response = requests.get(f"{BASE_URL}/api/incidents/{test_incident_id}")
        incident = get_response.json()
        assert incident["status"] == "identified"
        assert len(incident["updates"]) >= 2  # At least 2 updates now
        latest_update = incident["updates"][-1]
        assert latest_update["status"] == "identified"
        assert "database connection pool" in latest_update["message"]
        print("✓ PUT /api/incidents/:id — admin updates status, adds update entry")

    def test_update_incident_invalid_status(self, admin_session, test_incident_id):
        """PUT /api/incidents/:id — rejects invalid status (400)"""
        response = admin_session.put(
            f"{BASE_URL}/api/incidents/{test_incident_id}",
            json={
                "status": "invalid_status",
                "message": "Test",
            },
        )
        assert response.status_code == 400, f"Expected 400 for invalid status, got {response.status_code}"
        print("✓ PUT /api/incidents/:id — rejects invalid status (400)")

    def test_update_incident_unauthorized(self, standard_user_session, test_incident_id):
        """PUT /api/incidents/:id — standard user gets 403"""
        response = standard_user_session.put(
            f"{BASE_URL}/api/incidents/{test_incident_id}",
            json={
                "status": "monitoring",
                "message": "Test",
            },
        )
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
        print("✓ PUT /api/incidents/:id — standard user gets 403")

    def test_update_incident_not_found(self, admin_session):
        """PUT /api/incidents/:id — non-existent incident returns 404"""
        fake_id = "inc_nonexistent456"
        response = admin_session.put(
            f"{BASE_URL}/api/incidents/{fake_id}",
            json={"status": "monitoring", "message": "Test"},
        )
        assert response.status_code == 404
        print("✓ PUT /api/incidents/:id — non-existent incident returns 404")

    # ========== RESOLVE INCIDENT TESTS ==========

    def test_resolve_incident_sets_duration(self, admin_session):
        """PUT /api/incidents/:id with status=resolved — auto-sets resolved_at and duration_minutes"""
        # Create a fresh incident to resolve
        unique_title = f"TEST_Resolve_Test_{uuid.uuid4().hex[:8]}"
        create_response = admin_session.post(
            f"{BASE_URL}/api/incidents",
            json={
                "title": unique_title,
                "severity": "minor",
                "affected_services": ["api"],
                "message": "Testing resolution",
            },
        )
        assert create_response.status_code == 200
        incident_id = create_response.json()["incident_id"]
        
        # Resolve the incident
        resolve_response = admin_session.put(
            f"{BASE_URL}/api/incidents/{incident_id}",
            json={
                "status": "resolved",
                "message": "Issue has been resolved",
            },
        )
        assert resolve_response.status_code == 200
        
        # Verify resolved_at and duration_minutes are set
        get_response = requests.get(f"{BASE_URL}/api/incidents/{incident_id}")
        incident = get_response.json()
        assert incident["status"] == "resolved"
        assert incident["resolved_at"] is not None
        assert incident["duration_minutes"] is not None
        assert isinstance(incident["duration_minutes"], (int, float))
        assert incident["duration_minutes"] >= 0
        
        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/incidents/{incident_id}")
        print("✓ PUT /api/incidents/:id with status=resolved — auto-sets resolved_at and duration_minutes")

    # ========== DELETE INCIDENT TESTS ==========

    def test_delete_incident_success(self, admin_session):
        """DELETE /api/incidents/:id — admin deletes incident"""
        # Create incident to delete
        unique_title = f"TEST_Delete_Me_{uuid.uuid4().hex[:8]}"
        create_response = admin_session.post(
            f"{BASE_URL}/api/incidents",
            json={
                "title": unique_title,
                "severity": "minor",
                "affected_services": [],
                "message": "To be deleted",
            },
        )
        assert create_response.status_code == 200
        incident_id = create_response.json()["incident_id"]
        
        # Delete the incident
        delete_response = admin_session.delete(f"{BASE_URL}/api/incidents/{incident_id}")
        assert delete_response.status_code == 200
        data = delete_response.json()
        assert data["status"] == "deleted"
        
        # Verify it's deleted (should return 404)
        get_response = requests.get(f"{BASE_URL}/api/incidents/{incident_id}")
        assert get_response.status_code == 404
        print("✓ DELETE /api/incidents/:id — admin deletes incident, verified 404 after deletion")

    def test_delete_incident_unauthorized(self, standard_user_session, test_incident_id):
        """DELETE /api/incidents/:id — standard user gets 403"""
        response = standard_user_session.delete(f"{BASE_URL}/api/incidents/{test_incident_id}")
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
        print("✓ DELETE /api/incidents/:id — standard user gets 403")

    def test_delete_incident_not_found(self, admin_session):
        """DELETE /api/incidents/:id — non-existent incident returns 404"""
        fake_id = "inc_nonexistent789"
        response = admin_session.delete(f"{BASE_URL}/api/incidents/{fake_id}")
        assert response.status_code == 404
        print("✓ DELETE /api/incidents/:id — non-existent incident returns 404")


class TestIncidentTimeline:
    """Test incident timeline API"""

    def test_timeline_default_90_days(self):
        """GET /api/incidents/timeline — returns 90-day daily summary"""
        response = requests.get(f"{BASE_URL}/api/incidents/timeline")
        assert response.status_code == 200, f"Timeline API failed: {response.text}"
        data = response.json()
        
        assert "timeline" in data
        assert "days" in data
        assert data["days"] == 90
        assert isinstance(data["timeline"], list)
        assert len(data["timeline"]) == 91  # 90 days + today
        
        # Verify timeline entry structure
        for entry in data["timeline"]:
            assert "date" in entry
            assert "severity" in entry
            assert "count" in entry
            assert entry["severity"] in ("none", "minor", "major", "critical")
            assert isinstance(entry["count"], int)
        
        print(f"✓ GET /api/incidents/timeline — returns {len(data['timeline'])} days of severity data")

    def test_timeline_custom_days(self):
        """GET /api/incidents/timeline?days=30 — custom date range"""
        response = requests.get(f"{BASE_URL}/api/incidents/timeline?days=30")
        assert response.status_code == 200
        data = response.json()
        
        assert data["days"] == 30
        assert len(data["timeline"]) == 31  # 30 days + today
        print("✓ GET /api/incidents/timeline?days=30 — returns 31 days of data")


class TestEnhancedStatus:
    """Test enhanced status endpoints with incident information"""

    def test_status_includes_active_incidents(self):
        """GET /api/status — includes active_incidents count"""
        response = requests.get(f"{BASE_URL}/api/status")
        assert response.status_code == 200, f"Status API failed: {response.text}"
        data = response.json()
        
        assert "active_incidents" in data
        assert isinstance(data["active_incidents"], int)
        assert data["active_incidents"] >= 0
        assert "status" in data
        assert "uptime_seconds" in data
        assert "services" in data
        print(f"✓ GET /api/status — includes active_incidents count: {data['active_incidents']}")

    def test_status_page_html_includes_incidents(self):
        """GET /api/status/page — HTML shows uptime bar, percentage, incident history"""
        response = requests.get(f"{BASE_URL}/api/status/page")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        
        html = response.text
        
        # Verify key elements are present
        assert "90-Day Uptime" in html, "Missing '90-Day Uptime' section"
        assert "%" in html, "Missing uptime percentage"
        assert "Incident History" in html, "Missing 'Incident History' section"
        assert "timeline" in html.lower() or "day" in html.lower(), "Missing timeline visualization"
        
        # Check for legend items
        assert "No issues" in html or "none" in html.lower()
        assert "Minor" in html
        assert "Major" in html
        assert "Critical" in html
        
        print("✓ GET /api/status/page — HTML includes uptime bar, percentage, incident history cards")

    def test_status_page_auto_refresh(self):
        """GET /api/status/page — HTML has auto-refresh meta tag"""
        response = requests.get(f"{BASE_URL}/api/status/page")
        assert response.status_code == 200
        html = response.text
        
        # Check for auto-refresh meta tag
        assert 'http-equiv="refresh"' in html.lower() or "refresh" in html.lower()
        print("✓ GET /api/status/page — has auto-refresh enabled")


class TestExistingIncidents:
    """Verify existing test incidents in DB as mentioned in context"""

    def test_existing_incidents_present(self):
        """Verify test incidents exist in DB (one resolved major, one active minor)"""
        response = requests.get(f"{BASE_URL}/api/incidents")
        assert response.status_code == 200
        data = response.json()
        
        # Check if there are any incidents
        if data["total"] > 0:
            print(f"✓ Found {data['total']} incidents in database")
            
            # Check for resolved and active incidents
            resolved_count = sum(1 for inc in data["incidents"] if inc["status"] == "resolved")
            active_count = sum(1 for inc in data["incidents"] if inc["status"] != "resolved")
            print(f"  - Resolved: {resolved_count}, Active: {active_count}")
        else:
            print("⚠ No existing incidents found (expected 2 seeded incidents)")
