"""
Test iteration 36 - Repository, Integration Settings, Per-Tenant Encryption, Support Queues, Ticket Attachments
Tests for:
- Repository: File upload, list, search, folders, preview, update, delete
- Integration Settings: Admin platform-level + Org-level overrides
- Per-Tenant Encryption: Encryption status + key generation
- Support Queues: 8 ticket type queues with counts
- Ticket Attachments: Upload and list attachments
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ORG_ID = "org_cba36eb8305f"

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    # Don't set default Content-Type - requests will set appropriate header for each request type
    # JSON requests will need Content-Type set explicitly
    # Login with org admin credentials
    resp = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@urtech.org", 
        "password": "Test1234!"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return s


class TestRepository:
    """Repository: Org-level file store with indexing, search, preview"""

    uploaded_file_id = None

    def test_upload_file_text(self, session):
        """POST /api/orgs/{org}/repository/upload - Upload text file with indexing"""
        files = {"file": ("TEST_readme.txt", b"This is a test file content for indexing.", "text/plain")}
        data = {"folder": "/docs", "description": "Test text file"}
        resp = session.post(f"{BASE_URL}/api/orgs/{ORG_ID}/repository/upload", files=files, data=data)
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        result = resp.json()
        assert result["filename"] == "TEST_readme.txt"
        assert result["preview_type"] == "text"
        assert result["folder"] == "/docs"
        assert "file_id" in result
        TestRepository.uploaded_file_id = result["file_id"]
        print(f"Uploaded file: {result['file_id']}")

    def test_upload_file_image(self, session):
        """POST /api/orgs/{org}/repository/upload - Upload image file"""
        # Create minimal PNG bytes
        png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        files = {"file": ("TEST_image.png", png_bytes, "image/png")}
        resp = session.post(f"{BASE_URL}/api/orgs/{ORG_ID}/repository/upload", files=files, data={"folder": "/images"})
        assert resp.status_code == 200
        result = resp.json()
        assert result["preview_type"] == "image"
        print(f"Uploaded image: {result['file_id']}")

    def test_list_repository(self, session):
        """GET /api/orgs/{org}/repository - List files"""
        resp = session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/repository")
        assert resp.status_code == 200
        result = resp.json()
        assert "files" in result
        assert "total" in result
        print(f"Repository has {result['total']} files")

    def test_list_repository_with_search(self, session):
        """GET /api/orgs/{org}/repository?search= - Search files"""
        resp = session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/repository", params={"search": "test"})
        assert resp.status_code == 200
        result = resp.json()
        assert "files" in result
        print(f"Search 'test' found {result['total']} files")

    def test_list_repository_with_folder_filter(self, session):
        """GET /api/orgs/{org}/repository?folder= - Filter by folder"""
        resp = session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/repository", params={"folder": "/docs"})
        assert resp.status_code == 200
        result = resp.json()
        assert "files" in result
        print(f"Folder /docs has {result['total']} files")

    def test_list_repository_with_preview_type_filter(self, session):
        """GET /api/orgs/{org}/repository?preview_type= - Filter by preview type"""
        resp = session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/repository", params={"preview_type": "text"})
        assert resp.status_code == 200
        result = resp.json()
        assert "files" in result
        print(f"Preview type 'text' has {result['total']} files")

    def test_get_file_preview(self, session):
        """GET /api/repository/{id}/preview - Get file metadata + preview data"""
        if not TestRepository.uploaded_file_id:
            pytest.skip("No uploaded file")
        resp = session.get(f"{BASE_URL}/api/repository/{TestRepository.uploaded_file_id}/preview")
        assert resp.status_code == 200
        result = resp.json()
        assert "file" in result
        assert "preview" in result
        # For text files, preview should have 'text' key
        assert result["preview"]["type"] == "text"
        assert "text" in result["preview"]
        print(f"Preview data: type={result['preview']['type']}")

    def test_get_folders(self, session):
        """GET /api/orgs/{org}/repository/folders - Folder aggregation with counts"""
        resp = session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/repository/folders")
        assert resp.status_code == 200
        result = resp.json()
        assert "folders" in result
        for folder in result["folders"]:
            assert "folder" in folder
            assert "count" in folder
            assert "size_bytes" in folder
        print(f"Folders: {result['folders']}")

    def test_update_file(self, session):
        """PUT /api/repository/{id} - Update tags, folder, description"""
        if not TestRepository.uploaded_file_id:
            pytest.skip("No uploaded file")
        resp = session.put(f"{BASE_URL}/api/repository/{TestRepository.uploaded_file_id}",
            json={"tags": ["test", "documentation"], "description": "Updated description", "folder": "/updated"})
        assert resp.status_code == 200
        result = resp.json()
        assert result["tags"] == ["test", "documentation"]
        assert result["description"] == "Updated description"
        assert result["folder"] == "/updated"
        print("File updated successfully")

    def test_delete_file(self, session):
        """DELETE /api/repository/{id} - Delete file + data"""
        if not TestRepository.uploaded_file_id:
            pytest.skip("No uploaded file")
        resp = session.delete(f"{BASE_URL}/api/repository/{TestRepository.uploaded_file_id}")
        assert resp.status_code == 200
        result = resp.json()
        assert result["message"] == "Deleted"
        # Verify it's gone
        resp2 = session.get(f"{BASE_URL}/api/repository/{TestRepository.uploaded_file_id}/preview")
        assert resp2.status_code == 404
        print("File deleted successfully")


class TestIntegrationSettings:
    """Integration Settings: Admin + Org-level API key management"""

    def test_get_platform_integrations(self, session):
        """GET /api/admin/integrations - Lists 13 integration keys with configured status"""
        resp = session.get(f"{BASE_URL}/api/admin/integrations")
        assert resp.status_code == 200
        result = resp.json()
        assert "integrations" in result
        assert len(result["integrations"]) == 13
        # Check structure
        for integ in result["integrations"]:
            assert "key" in integ
            assert "name" in integ
            assert "provider" in integ
            assert "category" in integ
            assert "configured" in integ
        print(f"Platform has {len(result['integrations'])} integration keys")

    def test_set_platform_integration(self, session):
        """POST /api/admin/integrations - Set platform-level key"""
        # Set a test key
        resp = session.post(f"{BASE_URL}/api/admin/integrations", json={
            "key": "SENDGRID_API_KEY",
            "value": "TEST_sg_api_key_12345"
        })
        assert resp.status_code == 200
        result = resp.json()
        assert result["key"] == "SENDGRID_API_KEY"
        assert result["configured"] == True
        print("Platform integration key set")

    def test_set_platform_integration_invalid_key(self, session):
        """POST /api/admin/integrations - Reject invalid key name"""
        resp = session.post(f"{BASE_URL}/api/admin/integrations", json={
            "key": "INVALID_KEY_NAME",
            "value": "some_value"
        })
        assert resp.status_code == 400
        print("Invalid key correctly rejected")

    def test_get_org_integrations(self, session):
        """GET /api/orgs/{org}/integrations - Lists org-level overrides"""
        resp = session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/integrations")
        assert resp.status_code == 200
        result = resp.json()
        assert "integrations" in result
        for integ in result["integrations"]:
            assert "key" in integ
            assert "has_override" in integ
            assert "using" in integ  # "org" or "platform"
        print(f"Org has {len(result['integrations'])} integration config entries")

    def test_set_org_integration(self, session):
        """POST /api/orgs/{org}/integrations - Set org-level key (encrypted)"""
        resp = session.post(f"{BASE_URL}/api/orgs/{ORG_ID}/integrations", json={
            "key": "RESEND_API_KEY",
            "value": "TEST_org_resend_key"
        })
        assert resp.status_code == 200
        result = resp.json()
        assert result["key"] == "RESEND_API_KEY"
        assert result["configured"] == True
        print("Org integration key set (encrypted)")

    def test_verify_org_override(self, session):
        """Verify org integration shows override"""
        resp = session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/integrations")
        assert resp.status_code == 200
        result = resp.json()
        resend = next((i for i in result["integrations"] if i["key"] == "RESEND_API_KEY"), None)
        assert resend is not None
        assert resend["has_override"] == True
        assert resend["using"] == "org"
        print("Org override verified")

    def test_remove_org_integration(self, session):
        """DELETE /api/orgs/{org}/integrations/{key} - Remove override"""
        resp = session.delete(f"{BASE_URL}/api/orgs/{ORG_ID}/integrations/RESEND_API_KEY")
        assert resp.status_code == 200
        result = resp.json()
        assert "removed" in result["message"].lower() or "fallback" in result["message"].lower()
        print("Org integration override removed")


class TestPerTenantEncryption:
    """Per-Tenant Encryption: Org-specific encryption keys"""

    def test_get_encryption_status(self, session):
        """GET /api/orgs/{org}/encryption-status - Shows encryption level"""
        resp = session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/encryption-status")
        assert resp.status_code == 200
        result = resp.json()
        assert "org_id" in result
        assert "has_dedicated_key" in result
        assert "encryption_level" in result
        assert result["encryption_level"] in ["tenant-isolated", "platform-shared"]
        print(f"Encryption level: {result['encryption_level']}")

    def test_generate_encryption_key(self, session):
        """POST /api/orgs/{org}/encryption/generate-key - Generate per-tenant Fernet key"""
        resp = session.post(f"{BASE_URL}/api/orgs/{ORG_ID}/encryption/generate-key")
        assert resp.status_code == 200
        result = resp.json()
        assert result["org_id"] == ORG_ID
        assert result["encryption_level"] == "tenant-isolated"
        # Status can be "generated" (first time) or "already_exists" (subsequent)
        assert result["status"] in ["generated", "already_exists"]
        print(f"Encryption key status: {result['status']}")

    def test_verify_encryption_status_after_key(self, session):
        """Verify encryption status shows tenant-isolated after key generation"""
        resp = session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/encryption-status")
        assert resp.status_code == 200
        result = resp.json()
        assert result["has_dedicated_key"] == True
        assert result["encryption_level"] == "tenant-isolated"
        assert result["created_at"] is not None
        print("Encryption status confirmed: tenant-isolated")


class TestSupportQueues:
    """Support Queues: Ticket type queues with counts"""

    def test_get_support_queues(self, session):
        """GET /api/support/queues - Returns 8 ticket type queues with counts"""
        resp = session.get(f"{BASE_URL}/api/support/queues")
        assert resp.status_code == 200
        result = resp.json()
        assert "queues" in result
        queues = result["queues"]
        # Should have 8 ticket types
        queue_names = [q["queue"] for q in queues]
        expected_types = ["bug", "enhancement", "question", "billing", "general_support", "incident", "feature_request", "access_request"]
        for expected in expected_types:
            assert expected in queue_names, f"Missing queue: {expected}"
        # Each queue should have count and urgent fields
        for q in queues:
            assert "queue" in q
            assert "count" in q
            assert "urgent" in q
        print(f"Support queues: {len(queues)} types")

    def test_get_queue_tickets_billing(self, session):
        """GET /api/support/queues/{type} - Returns tickets in billing queue"""
        resp = session.get(f"{BASE_URL}/api/support/queues/billing")
        assert resp.status_code == 200
        result = resp.json()
        assert result["queue"] == "billing"
        assert "tickets" in result
        assert "total" in result
        print(f"Billing queue has {result['total']} open tickets")

    def test_get_queue_tickets_bug(self, session):
        """GET /api/support/queues/{type} - Returns tickets in bug queue"""
        resp = session.get(f"{BASE_URL}/api/support/queues/bug")
        assert resp.status_code == 200
        result = resp.json()
        assert result["queue"] == "bug"
        assert "tickets" in result
        print(f"Bug queue has {result['total']} open tickets")


class TestTicketAttachments:
    """Ticket Attachments: Upload and list attachments"""

    ticket_id = None

    def test_create_billing_ticket(self, session):
        """POST /api/support/tickets - Create billing ticket"""
        resp = session.post(f"{BASE_URL}/api/support/tickets", json={
            "subject": "TEST_Billing inquiry",
            "description": "Test billing ticket for attachment testing",
            "ticket_type": "billing",
            "priority": "medium"
        })
        assert resp.status_code == 200
        result = resp.json()
        assert result["ticket_type"] == "billing"
        TestTicketAttachments.ticket_id = result["ticket_id"]
        print(f"Created billing ticket: {result['ticket_id']}")

    def test_upload_attachment(self, session):
        """POST /api/support/tickets/{id}/attachments - Upload file attachment"""
        if not TestTicketAttachments.ticket_id:
            pytest.skip("No ticket created")
        files = {"file": ("TEST_screenshot.png", b"fake_png_data_for_testing", "image/png")}
        resp = session.post(f"{BASE_URL}/api/support/tickets/{TestTicketAttachments.ticket_id}/attachments", files=files)
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        result = resp.json()
        assert result["ticket_id"] == TestTicketAttachments.ticket_id
        assert result["filename"] == "TEST_screenshot.png"
        assert "attachment_id" in result
        assert "size" in result
        print(f"Uploaded attachment: {result['attachment_id']}")

    def test_upload_second_attachment(self, session):
        """POST /api/support/tickets/{id}/attachments - Upload another attachment"""
        if not TestTicketAttachments.ticket_id:
            pytest.skip("No ticket created")
        files = {"file": ("TEST_log.txt", b"Error log content for debugging...", "text/plain")}
        resp = session.post(f"{BASE_URL}/api/support/tickets/{TestTicketAttachments.ticket_id}/attachments", files=files)
        assert resp.status_code == 200
        result = resp.json()
        assert result["filename"] == "TEST_log.txt"
        print(f"Uploaded second attachment: {result['attachment_id']}")

    def test_list_attachments(self, session):
        """GET /api/support/tickets/{id}/attachments - List attachments"""
        if not TestTicketAttachments.ticket_id:
            pytest.skip("No ticket created")
        resp = session.get(f"{BASE_URL}/api/support/tickets/{TestTicketAttachments.ticket_id}/attachments")
        assert resp.status_code == 200
        result = resp.json()
        assert isinstance(result, list)
        assert len(result) >= 2
        for att in result:
            assert "attachment_id" in att
            assert "filename" in att
            assert "size" in att
            assert "data" not in att  # Data should be excluded from list
        print(f"Ticket has {len(result)} attachments")

    def test_billing_ticket_in_billing_queue(self, session):
        """Verify billing ticket appears in billing queue"""
        resp = session.get(f"{BASE_URL}/api/support/queues/billing")
        assert resp.status_code == 200
        result = resp.json()
        ticket_ids = [t["ticket_id"] for t in result["tickets"]]
        assert TestTicketAttachments.ticket_id in ticket_ids
        print("Billing ticket found in billing queue")


class TestCleanup:
    """Cleanup test data"""

    def test_cleanup_test_files(self, session):
        """Delete TEST_ prefixed repository files"""
        resp = session.get(f"{BASE_URL}/api/orgs/{ORG_ID}/repository", params={"search": "TEST_"})
        if resp.status_code == 200:
            files = resp.json().get("files", [])
            for f in files:
                session.delete(f"{BASE_URL}/api/repository/{f['file_id']}")
            print(f"Cleaned up {len(files)} TEST_ repository files")

    def test_cleanup_test_tickets(self, session):
        """Delete TEST_ prefixed tickets"""
        # Get all tickets and filter TEST_ ones
        resp = session.get(f"{BASE_URL}/api/support/tickets", params={"search": "TEST_", "limit": 100})
        if resp.status_code == 200:
            tickets = resp.json().get("tickets", [])
            for t in tickets:
                # Close the ticket (can't delete via API, so update status)
                session.put(f"{BASE_URL}/api/support/tickets/{t['ticket_id']}", json={"status": "closed"})
            print(f"Closed {len(tickets)} TEST_ tickets")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
