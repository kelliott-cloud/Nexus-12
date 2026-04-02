"""
Comprehensive tests for RBAC, File Upload, and Notification features.
Tests cover:
- RBAC: Role-Based Access Control for workspaces
- File Upload: Upload/download files to channels and task sessions
- Notifications: User notification system for AI responses
"""
import pytest
import requests
import os
import io
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable not set")

# Test credentials from MongoDB seed data
OWNER_SESSION_TOKEN = "test_session_rbac_1772554836138"
OWNER_USER_ID = "test-user-rbac-1772554836138"
MEMBER_SESSION_TOKEN = "test_session_rbac2_1772554836138" 
MEMBER_USER_ID = "test-user-rbac2-1772554836138"
WORKSPACE_ID = "ws_testrbac_1772554836138"
CHANNEL_ID = "ch_testrbac_1772554836138"


@pytest.fixture
def owner_client():
    """Session with owner auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OWNER_SESSION_TOKEN}"
    })
    return session


@pytest.fixture
def member_client():
    """Session with member auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MEMBER_SESSION_TOKEN}"
    })
    return session


@pytest.fixture
def unauthenticated_client():
    """Session without auth"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ============== RBAC TESTS ==============

class TestRBACMembers:
    """Test RBAC member management endpoints"""
    
    def test_get_workspace_members(self, owner_client):
        """GET /api/workspaces/{id}/members returns workspace members with roles"""
        response = owner_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/members")
        assert response.status_code == 200
        
        data = response.json()
        assert "members" in data
        assert "count" in data
        assert data["count"] >= 1
        
        # Find owner in members
        owner_member = next((m for m in data["members"] if m["user_id"] == OWNER_USER_ID), None)
        assert owner_member is not None
        assert owner_member["role"] == "admin"
        assert owner_member["is_owner"] == True
    
    def test_get_workspace_members_requires_auth(self, unauthenticated_client):
        """GET /api/workspaces/{id}/members requires authentication"""
        response = unauthenticated_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/members")
        assert response.status_code == 401
    
    def test_invite_member_by_email(self, owner_client):
        """POST /api/workspaces/{id}/members/invite sends invitation by email"""
        response = owner_client.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/members/invite",
            json={
                "email": "test.rbac.member.1772554836138@example.com",
                "role": "user"
            }
        )
        # Should be 200 (added) since user exists
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] in ["added", "pending"]
    
    def test_invite_member_invalid_role(self, owner_client):
        """POST /api/workspaces/{id}/members/invite rejects invalid role"""
        response = owner_client.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/members/invite",
            json={
                "email": "newinvitee@example.com",
                "role": "superadmin"  # Invalid role
            }
        )
        assert response.status_code == 400
    
    def test_invite_member_requires_admin(self, member_client):
        """POST /api/workspaces/{id}/members/invite requires admin permission"""
        response = member_client.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/members/invite",
            json={
                "email": "anotherinvitee@example.com",
                "role": "user"
            }
        )
        assert response.status_code == 403


class TestRBACInviteLinks:
    """Test RBAC invite link endpoints"""
    
    def test_create_invite_link(self, owner_client):
        """POST /api/workspaces/{id}/invite-link creates shareable invite link"""
        response = owner_client.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/invite-link",
            json={
                "role": "user",
                "expires_hours": 24,
                "max_uses": 10
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "link_code" in data
        assert len(data["link_code"]) == 16
        assert data["role"] == "user"
        assert data["max_uses"] == 10
        
        # Store for other tests
        TestRBACInviteLinks.link_code = data["link_code"]
    
    def test_create_invite_link_observer_role(self, owner_client):
        """POST /api/workspaces/{id}/invite-link can create observer invite"""
        response = owner_client.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/invite-link",
            json={
                "role": "observer",
                "expires_hours": None,  # Never expires
                "max_uses": None  # Unlimited
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["role"] == "observer"
    
    def test_create_invite_link_admin_not_allowed(self, owner_client):
        """POST /api/workspaces/{id}/invite-link rejects admin role"""
        response = owner_client.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/invite-link",
            json={"role": "admin"}
        )
        assert response.status_code == 400
    
    def test_get_invite_info(self, owner_client):
        """GET /api/invites/{code} returns invite info preview"""
        # Create a link first
        create_resp = owner_client.post(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/invite-link",
            json={"role": "user"}
        )
        link_code = create_resp.json()["link_code"]
        
        # Get invite info
        response = owner_client.get(f"{BASE_URL}/api/invites/{link_code}")
        assert response.status_code == 200
        
        data = response.json()
        assert "workspace_name" in data
        assert data["workspace_name"] == "Test RBAC Workspace"
        assert data["role"] == "user"
        assert "is_member" in data
    
    def test_get_invite_info_invalid_code(self, owner_client):
        """GET /api/invites/{code} returns 404 for invalid code"""
        response = owner_client.get(f"{BASE_URL}/api/invites/invalidcode12345")
        assert response.status_code == 404


class TestRBACRoleManagement:
    """Test RBAC role update and member removal"""
    
    def test_update_member_role(self, owner_client):
        """PUT /api/workspaces/{id}/members/{user_id}/role updates member role"""
        response = owner_client.put(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/members/{MEMBER_USER_ID}/role",
            json={"role": "observer"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "updated"
        assert data["role"] == "observer"
        
        # Change back to user
        owner_client.put(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/members/{MEMBER_USER_ID}/role",
            json={"role": "user"}
        )
    
    def test_update_owner_role_fails(self, owner_client):
        """PUT /api/workspaces/{id}/members/{user_id}/role cannot change owner role"""
        response = owner_client.put(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/members/{OWNER_USER_ID}/role",
            json={"role": "observer"}
        )
        assert response.status_code == 400
    
    def test_get_my_role(self, owner_client):
        """GET /api/workspaces/{id}/my-role returns current user's role and permissions"""
        response = owner_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/my-role")
        assert response.status_code == 200
        
        data = response.json()
        assert data["role"] == "admin"
        assert "permissions" in data
        assert "invite_members" in data["permissions"]
        assert "manage_roles" in data["permissions"]
    
    def test_get_my_role_as_member(self, member_client):
        """GET /api/workspaces/{id}/my-role returns member role correctly"""
        response = member_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/my-role")
        assert response.status_code == 200
        
        data = response.json()
        assert data["role"] in ["user", "observer", "admin"]
        assert "permissions" in data


# ============== FILE UPLOAD TESTS ==============

class TestFileUpload:
    """Test file upload/download endpoints"""
    
    def test_upload_file_to_channel(self, owner_client):
        """POST /api/channels/{id}/files uploads file to channel"""
        # Create a test file
        test_content = b"Hello, this is a test file for RBAC testing!"
        files = {
            'file': ('test_file.txt', io.BytesIO(test_content), 'text/plain')
        }
        
        # Need to remove Content-Type header for multipart upload
        headers = {"Authorization": f"Bearer {OWNER_SESSION_TOKEN}"}
        
        response = requests.post(
            f"{BASE_URL}/api/channels/{CHANNEL_ID}/files",
            files=files,
            headers=headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "file" in data
        assert data["file"]["original_name"] == "test_file.txt"
        assert data["file"]["file_size"] == len(test_content)
        assert "message_id" in data
        assert "download_url" in data
        
        # Store file_id for other tests
        TestFileUpload.uploaded_file_id = data["file"]["file_id"]
    
    def test_upload_file_too_large(self, owner_client):
        """POST /api/channels/{id}/files rejects files > 25MB"""
        # Create content > 25MB
        large_content = b"x" * (26 * 1024 * 1024)  # 26MB
        files = {'file': ('large_file.txt', io.BytesIO(large_content), 'text/plain')}
        headers = {"Authorization": f"Bearer {OWNER_SESSION_TOKEN}"}
        
        response = requests.post(
            f"{BASE_URL}/api/channels/{CHANNEL_ID}/files",
            files=files,
            headers=headers
        )
        assert response.status_code == 400
        assert "too large" in response.json().get("detail", "").lower()
    
    def test_upload_disallowed_file_type(self, owner_client):
        """POST /api/channels/{id}/files rejects disallowed file types"""
        files = {'file': ('malware.exe', io.BytesIO(b"bad stuff"), 'application/octet-stream')}
        headers = {"Authorization": f"Bearer {OWNER_SESSION_TOKEN}"}
        
        response = requests.post(
            f"{BASE_URL}/api/channels/{CHANNEL_ID}/files",
            files=files,
            headers=headers
        )
        assert response.status_code == 400
        assert "not allowed" in response.json().get("detail", "").lower()
    
    def test_get_file_info(self, owner_client):
        """GET /api/files/{id} returns file metadata"""
        file_id = getattr(TestFileUpload, 'uploaded_file_id', None)
        if not file_id:
            pytest.skip("No file uploaded in previous test")
        
        response = owner_client.get(f"{BASE_URL}/api/files/{file_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["file_id"] == file_id
        assert data["original_name"] == "test_file.txt"
        assert "file_size" in data
        assert "mime_type" in data
    
    def test_download_file(self, owner_client):
        """GET /api/files/{id}/download downloads file"""
        file_id = getattr(TestFileUpload, 'uploaded_file_id', None)
        if not file_id:
            pytest.skip("No file uploaded in previous test")
        
        # Download returns file content
        response = requests.get(
            f"{BASE_URL}/api/files/{file_id}/download",
            headers={"Authorization": f"Bearer {OWNER_SESSION_TOKEN}"}
        )
        assert response.status_code == 200
        assert b"Hello, this is a test file" in response.content
    
    def test_list_channel_files(self, owner_client):
        """GET /api/channels/{id}/files lists channel files"""
        response = owner_client.get(f"{BASE_URL}/api/channels/{CHANNEL_ID}/files")
        assert response.status_code == 200
        
        data = response.json()
        assert "files" in data
        assert "count" in data
        # Should have at least the file we uploaded
        assert data["count"] >= 1
    
    def test_list_workspace_files(self, owner_client):
        """GET /api/workspaces/{id}/files lists all workspace files"""
        response = owner_client.get(f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/files")
        assert response.status_code == 200
        
        data = response.json()
        assert "files" in data
        assert "count" in data
        assert "total_size" in data
        assert "total_size_mb" in data
    
    def test_delete_file(self, owner_client):
        """DELETE /api/files/{id} deletes file"""
        # Upload a file to delete
        test_content = b"File to be deleted"
        files = {'file': ('delete_me.txt', io.BytesIO(test_content), 'text/plain')}
        headers = {"Authorization": f"Bearer {OWNER_SESSION_TOKEN}"}
        
        upload_resp = requests.post(
            f"{BASE_URL}/api/channels/{CHANNEL_ID}/files",
            files=files,
            headers=headers
        )
        file_id = upload_resp.json()["file"]["file_id"]
        
        # Delete the file
        response = owner_client.delete(f"{BASE_URL}/api/files/{file_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
        
        # Verify file is gone
        get_resp = owner_client.get(f"{BASE_URL}/api/files/{file_id}")
        assert get_resp.status_code == 404


# ============== NOTIFICATION TESTS ==============

class TestNotifications:
    """Test notification endpoints"""
    
    def test_get_notifications(self, owner_client):
        """GET /api/notifications returns user notifications"""
        response = owner_client.get(f"{BASE_URL}/api/notifications")
        assert response.status_code == 200
        
        data = response.json()
        assert "notifications" in data
        assert "unread_count" in data
        assert isinstance(data["notifications"], list)
    
    def test_get_notifications_unread_only(self, owner_client):
        """GET /api/notifications?unread_only=true filters unread"""
        response = owner_client.get(f"{BASE_URL}/api/notifications?unread_only=true")
        assert response.status_code == 200
        
        data = response.json()
        assert "notifications" in data
        # All returned should be unread
        for notif in data["notifications"]:
            assert notif["read"] == False
    
    def test_mark_all_notifications_read(self, owner_client):
        """PUT /api/notifications/read-all marks all as read"""
        response = owner_client.put(f"{BASE_URL}/api/notifications/read-all")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "updated"
        assert "count" in data
    
    def test_get_notification_settings(self, owner_client):
        """GET /api/notifications/settings returns preferences"""
        response = owner_client.get(f"{BASE_URL}/api/notifications/settings")
        assert response.status_code == 200
        
        data = response.json()
        assert "ai_responses" in data
        assert "task_updates" in data
        assert "sound_enabled" in data
    
    def test_update_notification_settings(self, owner_client):
        """PUT /api/notifications/settings updates preferences"""
        response = owner_client.put(
            f"{BASE_URL}/api/notifications/settings",
            json={
                "ai_responses": True,
                "sound_enabled": False
            }
        )
        assert response.status_code == 200
        assert response.json()["status"] == "updated"
    
    def test_notifications_require_auth(self, unauthenticated_client):
        """GET /api/notifications requires authentication"""
        response = unauthenticated_client.get(f"{BASE_URL}/api/notifications")
        assert response.status_code == 401


class TestNotificationCRUD:
    """Test notification create/read/update/delete operations"""
    
    @pytest.fixture(autouse=True)
    def setup_notification(self, owner_client):
        """Create a test notification via MongoDB"""
        # We can't easily create notifications via API (they're created by events)
        # But we can test mark read and delete operations on existing ones
        pass
    
    def test_mark_notification_read_not_found(self, owner_client):
        """PUT /api/notifications/{id}/read returns 404 for non-existent"""
        response = owner_client.put(f"{BASE_URL}/api/notifications/nonexistent123/read")
        assert response.status_code == 404
    
    def test_delete_notification_not_found(self, owner_client):
        """DELETE /api/notifications/{id} returns 404 for non-existent"""
        response = owner_client.delete(f"{BASE_URL}/api/notifications/nonexistent123")
        assert response.status_code == 404


# ============== INTEGRATION TESTS ==============

class TestRBACFileIntegration:
    """Test RBAC permissions for file operations"""
    
    def test_observer_cannot_upload_files(self, owner_client, member_client):
        """Observer role cannot upload files"""
        # Set member to observer role
        owner_client.put(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/members/{MEMBER_USER_ID}/role",
            json={"role": "observer"}
        )
        
        # Try to upload as observer
        test_content = b"Observer trying to upload"
        files = {'file': ('observer_test.txt', io.BytesIO(test_content), 'text/plain')}
        
        response = requests.post(
            f"{BASE_URL}/api/channels/{CHANNEL_ID}/files",
            files=files,
            headers={"Authorization": f"Bearer {MEMBER_SESSION_TOKEN}"}
        )
        assert response.status_code == 403
        
        # Reset member role back to user
        owner_client.put(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/members/{MEMBER_USER_ID}/role",
            json={"role": "user"}
        )
    
    def test_user_can_upload_files(self, owner_client):
        """User role can upload files"""
        # Make sure member is user role
        owner_client.put(
            f"{BASE_URL}/api/workspaces/{WORKSPACE_ID}/members/{MEMBER_USER_ID}/role",
            json={"role": "user"}
        )
        
        test_content = b"User uploading file"
        files = {'file': ('user_upload.txt', io.BytesIO(test_content), 'text/plain')}
        
        response = requests.post(
            f"{BASE_URL}/api/channels/{CHANNEL_ID}/files",
            files=files,
            headers={"Authorization": f"Bearer {MEMBER_SESSION_TOKEN}"}
        )
        assert response.status_code == 200


# ============== HEALTH CHECK ==============

class TestHealth:
    """Basic health check"""
    
    def test_api_health(self):
        """GET /api/health returns ok"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
