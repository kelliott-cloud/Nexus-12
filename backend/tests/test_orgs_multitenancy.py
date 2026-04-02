from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Test suite for Multi-Tenant Organization System in Nexus
Tests: Organization registration, slug validation, org-specific login,
       org dashboard, org admin panel (members/billing/analytics),
       platform admin organizations tab
"""
import pytest
import requests
import os
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ============ Fixtures ============

@pytest.fixture(scope="session")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="session")
def super_admin_session(api_client):
    """Super admin session (TEST_ADMIN_EMAIL)"""
    token = "Fp_kWAvgxh8krRP-eEhEicsB06MwP3UtRkzlM66fMVA"
    api_client.headers.update({"Authorization": f"Bearer {token}"})
    return api_client

@pytest.fixture(scope="session")
def acme_admin_token():
    """Acme org admin session token (john@acme.com)"""
    return "vv3CYjbDFAF-xGR9uaGbRHUOnXteVJdr-4QNkBRD2W8"

@pytest.fixture(scope="session")
def acme_org_id():
    """Acme organization ID"""
    return "org_b3f03aa50399"

@pytest.fixture
def unique_slug():
    """Generate unique slug for testing"""
    return f"test-{uuid.uuid4().hex[:8]}"


# ============ Slug Validation Tests ============

class TestSlugValidation:
    """Tests for POST /api/orgs/check-slug endpoint"""
    
    def test_check_slug_available(self, api_client, unique_slug):
        """Test that a unique slug is available"""
        response = api_client.post(f"{BASE_URL}/api/orgs/check-slug", json={"slug": unique_slug})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["available"] is True, f"Expected slug '{unique_slug}' to be available"
        print(f"✓ Slug '{unique_slug}' is available")

    def test_check_slug_existing_taken(self, api_client):
        """Test that existing slug 'acme-corp' is unavailable"""
        response = api_client.post(f"{BASE_URL}/api/orgs/check-slug", json={"slug": "acme-corp"})
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False, "Expected 'acme-corp' to be taken"
        print("✓ Existing slug 'acme-corp' is unavailable as expected")

    def test_reserved_slug_admin(self, api_client):
        """Test that reserved slug 'admin' is rejected"""
        response = api_client.post(f"{BASE_URL}/api/orgs/check-slug", json={"slug": "admin"})
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False, "Expected 'admin' to be unavailable (reserved)"
        assert data.get("reason") == "Reserved"
        print("✓ Reserved slug 'admin' correctly rejected")

    def test_reserved_slug_api(self, api_client):
        """Test that reserved slug 'api' is rejected"""
        response = api_client.post(f"{BASE_URL}/api/orgs/check-slug", json={"slug": "api"})
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False, "Expected 'api' to be unavailable (reserved)"
        print("✓ Reserved slug 'api' correctly rejected")

    def test_reserved_slug_auth(self, api_client):
        """Test that reserved slug 'auth' is rejected"""
        response = api_client.post(f"{BASE_URL}/api/orgs/check-slug", json={"slug": "auth"})
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False, "Expected 'auth' to be unavailable (reserved)"
        print("✓ Reserved slug 'auth' correctly rejected")

    def test_invalid_slug_format(self, api_client):
        """Test invalid slug format (special chars, too short, etc)"""
        # Note: Backend lowercases slugs, so UPPERCASE becomes valid after lowercase conversion
        # Test truly invalid formats that violate the pattern
        invalid_slugs = ["with spaces", "dot.char", "a"]  # "a" is too short (min 2 chars)
        for slug in invalid_slugs:
            response = api_client.post(f"{BASE_URL}/api/orgs/check-slug", json={"slug": slug})
            assert response.status_code == 200
            data = response.json()
            assert data["available"] is False, f"Expected '{slug}' to be invalid"
        print("✓ Invalid slug formats correctly rejected")


# ============ Organization Registration Tests ============

class TestOrgRegistration:
    """Tests for POST /api/orgs/register endpoint"""
    
    def test_register_org_creates_all_resources(self, api_client, unique_slug):
        """Test org registration creates org + admin user + session"""
        payload = {
            "name": f"Test Company {unique_slug}",
            "slug": unique_slug,
            "admin_name": "Test Admin",
            "admin_email": f"admin-{unique_slug}@test.com",
            "admin_password": "Test1234!"
        }
        response = api_client.post(f"{BASE_URL}/api/orgs/register", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify all required fields returned
        assert "org_id" in data, "Missing org_id in response"
        assert "slug" in data, "Missing slug in response"
        assert "name" in data, "Missing name in response"
        assert "user_id" in data, "Missing user_id in response"
        assert "session_token" in data, "Missing session_token in response"
        
        assert data["slug"] == unique_slug
        assert data["name"] == payload["name"]
        assert len(data["session_token"]) > 20, "Session token too short"
        
        print(f"✓ Organization '{unique_slug}' created successfully with admin user and session")
        return data

    def test_register_org_reserved_slug_rejected(self, api_client):
        """Test that reserved slugs are rejected on registration"""
        payload = {
            "name": "Admin Company",
            "slug": "admin",
            "admin_name": "Admin",
            "admin_email": f"admin-test-{uuid.uuid4().hex[:6]}@test.com",
            "admin_password": "Test1234!"
        }
        response = api_client.post(f"{BASE_URL}/api/orgs/register", json=payload)
        assert response.status_code == 400, f"Expected 400 for reserved slug, got {response.status_code}"
        assert "reserved" in response.json().get("detail", "").lower()
        print("✓ Registration with reserved slug 'admin' correctly rejected")

    def test_register_org_duplicate_email_rejected(self, api_client, unique_slug):
        """Test that duplicate email on registration is rejected"""
        payload = {
            "name": "Duplicate Email Test",
            "slug": unique_slug,
            "admin_name": "John",
            "admin_email": "john@acme.com",  # Existing email
            "admin_password": "Test1234!"
        }
        response = api_client.post(f"{BASE_URL}/api/orgs/register", json=payload)
        assert response.status_code == 400, f"Expected 400 for duplicate email, got {response.status_code}"
        assert "already registered" in response.json().get("detail", "").lower()
        print("✓ Registration with existing email correctly rejected")


# ============ Org Public Info Tests ============

class TestOrgBySlug:
    """Tests for GET /api/orgs/by-slug/{slug} endpoint"""
    
    def test_get_org_by_slug_success(self, api_client):
        """Test getting existing org by slug returns org info"""
        response = api_client.get(f"{BASE_URL}/api/orgs/by-slug/acme-corp")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["slug"] == "acme-corp"
        assert "name" in data
        assert "org_id" in data
        assert "member_count" in data
        assert data["member_count"] >= 1
        print(f"✓ Get org by slug returns: {data['name']} with {data['member_count']} member(s)")

    def test_get_org_by_nonexistent_slug(self, api_client):
        """Test getting non-existent org returns 404"""
        response = api_client.get(f"{BASE_URL}/api/orgs/by-slug/nonexistent-org-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        assert "not found" in response.json().get("detail", "").lower()
        print("✓ Non-existent org slug correctly returns 404")


# ============ Org Membership Tests ============

class TestOrgMembership:
    """Tests for /api/orgs/my-orgs and org membership endpoints"""
    
    def test_get_my_orgs_as_acme_admin(self, api_client, acme_admin_token):
        """Test that org admin can get their organizations"""
        headers = {"Authorization": f"Bearer {acme_admin_token}"}
        response = api_client.get(f"{BASE_URL}/api/orgs/my-orgs", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "organizations" in data
        orgs = data["organizations"]
        
        # Acme admin should belong to acme-corp
        acme_org = next((o for o in orgs if o["slug"] == "acme-corp"), None)
        assert acme_org is not None, "Acme admin should belong to acme-corp"
        assert acme_org["org_role"] == "org_owner"
        print(f"✓ Acme admin belongs to {len(orgs)} org(s), is org_owner of acme-corp")


# ============ Org Workspaces Tests ============

class TestOrgWorkspaces:
    """Tests for org-scoped workspaces"""
    
    def test_get_org_workspaces(self, api_client, acme_admin_token, acme_org_id):
        """Test getting org workspaces"""
        headers = {"Authorization": f"Bearer {acme_admin_token}"}
        response = api_client.get(f"{BASE_URL}/api/orgs/{acme_org_id}/workspaces", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "workspaces" in data
        print(f"✓ Acme org has {len(data['workspaces'])} workspace(s)")

    def test_create_org_workspace(self, api_client, acme_admin_token, acme_org_id):
        """Test creating a workspace in an organization"""
        headers = {"Authorization": f"Bearer {acme_admin_token}"}
        ws_name = f"Test Workspace {uuid.uuid4().hex[:6]}"
        payload = {
            "name": ws_name,
            "description": "Test workspace for multi-tenancy testing"
        }
        response = api_client.post(f"{BASE_URL}/api/orgs/{acme_org_id}/workspaces", json=payload, headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["name"] == ws_name
        assert data["org_id"] == acme_org_id
        assert "workspace_id" in data
        print(f"✓ Created workspace '{ws_name}' in org {acme_org_id}")


# ============ Org Members Management Tests ============

class TestOrgMembers:
    """Tests for org members management endpoints"""
    
    def test_get_org_members(self, api_client, acme_admin_token, acme_org_id):
        """Test getting org members list"""
        headers = {"Authorization": f"Bearer {acme_admin_token}"}
        response = api_client.get(f"{BASE_URL}/api/orgs/{acme_org_id}/members", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "members" in data
        assert "total" in data
        
        # Should have at least the owner
        members = data["members"]
        owner = next((m for m in members if m["org_role"] == "org_owner"), None)
        assert owner is not None, "Organization should have an owner"
        print(f"✓ Org {acme_org_id} has {data['total']} member(s)")

    def test_invite_member_user_not_found(self, api_client, acme_admin_token, acme_org_id):
        """Test inviting a non-existent user returns 404"""
        headers = {"Authorization": f"Bearer {acme_admin_token}"}
        payload = {
            "email": f"nonexistent-{uuid.uuid4().hex[:8]}@test.com",
            "org_role": "org_member"
        }
        response = api_client.post(f"{BASE_URL}/api/orgs/{acme_org_id}/members", json=payload, headers=headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        assert "not found" in response.json().get("detail", "").lower()
        print("✓ Inviting non-existent user correctly returns 404")

    def test_invite_member_invalid_role(self, api_client, acme_admin_token, acme_org_id):
        """Test inviting with invalid role returns 400"""
        headers = {"Authorization": f"Bearer {acme_admin_token}"}
        payload = {
            "email": "testuser@test.com",
            "org_role": "org_owner"  # Cannot invite as owner
        }
        response = api_client.post(f"{BASE_URL}/api/orgs/{acme_org_id}/members", json=payload, headers=headers)
        assert response.status_code == 400, f"Expected 400 for invalid role, got {response.status_code}"
        print("✓ Inviting with invalid role 'org_owner' correctly rejected")


# ============ Org Role Change Tests ============

class TestOrgRoleChange:
    """Tests for changing org member roles"""
    
    def test_cannot_change_owner_role(self, api_client, acme_admin_token, acme_org_id):
        """Test that org owner's role cannot be changed"""
        headers = {"Authorization": f"Bearer {acme_admin_token}"}
        
        # First get the owner's user_id
        members_response = api_client.get(f"{BASE_URL}/api/orgs/{acme_org_id}/members", headers=headers)
        members = members_response.json()["members"]
        owner = next((m for m in members if m["org_role"] == "org_owner"), None)
        
        if owner:
            # Try to change owner's role
            payload = {"org_role": "org_admin"}
            response = api_client.put(
                f"{BASE_URL}/api/orgs/{acme_org_id}/members/{owner['user_id']}/role",
                json=payload,
                headers=headers
            )
            assert response.status_code == 400, f"Expected 400, got {response.status_code}"
            assert "owner" in response.json().get("detail", "").lower()
            print("✓ Cannot change org owner's role (correctly rejected with 400)")
        else:
            pytest.skip("No owner found to test role change")


# ============ Org Billing Tests ============

class TestOrgBilling:
    """Tests for GET /api/orgs/{org_id}/billing endpoint"""
    
    def test_get_org_billing(self, api_client, acme_admin_token, acme_org_id):
        """Test getting org billing info shows plans"""
        headers = {"Authorization": f"Bearer {acme_admin_token}"}
        response = api_client.get(f"{BASE_URL}/api/orgs/{acme_org_id}/billing", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "plan" in data
        assert "plans" in data
        assert "member_count" in data
        
        # Verify plan structure
        plans = data["plans"]
        assert "free" in plans
        assert "pro" in plans
        assert "enterprise" in plans
        
        # Verify plan details
        free_plan = plans["free"]
        assert free_plan["price"] == 0
        assert free_plan["max_members"] == 5
        assert free_plan["max_workspaces"] == 3
        
        pro_plan = plans["pro"]
        assert pro_plan["price"] == 49
        assert pro_plan["max_members"] == 25
        assert pro_plan["max_workspaces"] == 20
        
        enterprise_plan = plans["enterprise"]
        assert enterprise_plan["price"] == 199
        assert enterprise_plan["max_members"] == -1  # unlimited
        assert enterprise_plan["max_workspaces"] == -1  # unlimited
        
        print(f"✓ Org billing: Current plan={data['plan']}, member_count={data['member_count']}")


# ============ Org Analytics Tests ============

class TestOrgAnalytics:
    """Tests for GET /api/orgs/{org_id}/admin/analytics endpoint"""
    
    def test_get_org_analytics(self, api_client, acme_admin_token, acme_org_id):
        """Test getting org analytics returns usage data"""
        headers = {"Authorization": f"Bearer {acme_admin_token}"}
        response = api_client.get(f"{BASE_URL}/api/orgs/{acme_org_id}/admin/analytics", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "total_messages" in data
        assert "ai_messages" in data
        assert "model_usage" in data
        # Note: workspaces/channels only returned if there are org workspaces with data
        # Empty orgs return {total_messages: 0, ai_messages: 0, model_usage: {}, daily_activity: []}
        
        print(f"✓ Org analytics: {data['total_messages']} total messages, {data['ai_messages']} AI messages")


# ============ Org Admin Stats Tests ============

class TestOrgAdminStats:
    """Tests for GET /api/orgs/{org_id}/admin/stats endpoint"""
    
    def test_get_org_admin_stats(self, api_client, acme_admin_token, acme_org_id):
        """Test getting org admin stats"""
        headers = {"Authorization": f"Bearer {acme_admin_token}"}
        response = api_client.get(f"{BASE_URL}/api/orgs/{acme_org_id}/admin/stats", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "members" in data
        assert "workspaces" in data
        assert "channels" in data
        assert "messages" in data
        assert "plan" in data
        
        print(f"✓ Org admin stats: {data['members']} members, {data['workspaces']} workspaces")


# ============ Platform Admin Organizations Tests ============

class TestPlatformAdminOrgs:
    """Tests for platform admin GET /api/admin/organizations endpoint"""
    
    def test_platform_admin_get_all_orgs(self, super_admin_session):
        """Test platform admin can get all organizations"""
        response = super_admin_session.get(f"{BASE_URL}/api/admin/organizations")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "organizations" in data
        assert "total" in data
        
        orgs = data["organizations"]
        # Check that each org has required fields
        for org in orgs:
            assert "org_id" in org
            assert "name" in org
            assert "slug" in org
            assert "member_count" in org
            assert "workspace_count" in org
        
        # Find acme-corp
        acme = next((o for o in orgs if o["slug"] == "acme-corp"), None)
        assert acme is not None, "acme-corp should be in org list"
        
        print(f"✓ Platform admin can list all {data['total']} organization(s)")

    def test_non_admin_cannot_get_all_orgs(self, api_client, acme_admin_token):
        """Test non-platform-admin cannot access all orgs"""
        headers = {"Authorization": f"Bearer {acme_admin_token}"}
        response = api_client.get(f"{BASE_URL}/api/admin/organizations", headers=headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✓ Non-platform-admin correctly denied access to all organizations")


# ============ Auth Access Control Tests ============

class TestOrgAccessControl:
    """Tests for org access control"""
    
    def test_unauthenticated_cannot_get_my_orgs(self, api_client):
        """Test unauthenticated user cannot get my orgs"""
        # Clear any auth header
        client = requests.Session()
        client.headers.update({"Content-Type": "application/json"})
        response = client.get(f"{BASE_URL}/api/orgs/my-orgs")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthenticated user correctly denied access to /orgs/my-orgs")

    def test_non_member_cannot_access_org_workspaces(self, super_admin_session, acme_org_id):
        """Test non-member cannot access org workspaces"""
        # Super admin is not a member of acme org
        response = super_admin_session.get(f"{BASE_URL}/api/orgs/{acme_org_id}/workspaces")
        assert response.status_code == 403, f"Expected 403 for non-member, got {response.status_code}"
        print("✓ Non-member correctly denied access to org workspaces")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
