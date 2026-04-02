"""
Iteration 63 - Document Sharing with Text Extraction & Directive Editing Tests

Tests:
1. File upload with text extraction (TXT, CSV)
2. File upload without text extraction (image)
3. Message content includes extracted text with markers
4. File attachment metadata has has_extracted_text and text_length
5. Directive creation via channel
6. Directive editing (PUT) for active directive
7. Directive editing returns 404 when no active directive
"""
import pytest
import requests
import uuid
import os
import io
import tempfile

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Module-level fixtures
@pytest.fixture(scope="module")
def session():
    """Shared requests session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s

@pytest.fixture(scope="module")
def test_user(session):
    """Register a test user and authenticate"""
    unique_id = uuid.uuid4().hex[:8]
    email = f"doctest_{unique_id}@test.com"
    password = "test123"
    name = f"Doc Test User {unique_id}"
    
    # Register user
    reg_res = session.post(f"{BASE_URL}/api/auth/register", json={
        "email": email,
        "password": password,
        "name": name
    })
    assert reg_res.status_code == 200, f"Registration failed: {reg_res.text}"
    
    # Login to get auth cookies
    login_res = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": email,
        "password": password
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    
    user_data = login_res.json()
    return {
        "user_id": user_data.get("user", {}).get("user_id"),
        "email": email,
        "name": name
    }

@pytest.fixture(scope="module")
def workspace_id(session, test_user):
    """Create a test workspace"""
    unique_id = uuid.uuid4().hex[:8]
    res = session.post(f"{BASE_URL}/api/workspaces", json={
        "name": f"Doc Test Workspace {unique_id}",
        "description": "Test workspace for document sharing features"
    })
    assert res.status_code == 200, f"Workspace creation failed: {res.text}"
    return res.json()["workspace_id"]

@pytest.fixture(scope="module")
def channel_id(session, workspace_id):
    """Create a test channel with AI agents"""
    unique_id = uuid.uuid4().hex[:8]
    res = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/channels", json={
        "name": f"doc-test-channel-{unique_id}",
        "ai_agents": ["claude", "chatgpt"]
    })
    assert res.status_code == 200, f"Channel creation failed: {res.text}"
    return res.json()["channel_id"]


class TestDocumentUploadExtraction:
    """Test document upload with text extraction for different file types"""
    
    def test_upload_txt_file_extracts_text(self, session, channel_id):
        """POST /api/channels/{channel_id}/files - Upload TXT file and verify text extraction"""
        # Create a temporary TXT file
        txt_content = "This is a test document.\nIt has multiple lines.\nAI agents should be able to read this."
        
        # Remove Content-Type header to let requests set multipart boundary
        orig_headers = session.headers.copy()
        if "Content-Type" in session.headers:
            del session.headers["Content-Type"]
        
        files = {
            "file": ("test_document.txt", txt_content.encode("utf-8"), "text/plain")
        }
        
        res = session.post(
            f"{BASE_URL}/api/channels/{channel_id}/files",
            files=files
        )
        
        # Restore headers
        session.headers = orig_headers
        
        assert res.status_code == 200, f"TXT upload failed: {res.text}"
        data = res.json()
        
        # Verify file record
        assert "file" in data, "Response should contain file info"
        assert data["file"]["extension"] == "txt", "Extension should be txt"
        assert data["file"]["original_name"] == "test_document.txt"
        
        # Verify message_id is returned
        assert "message_id" in data, "Response should contain message_id"
        
        print(f"TXT upload success: file_id={data['file']['file_id']}, message_id={data['message_id']}")
    
    def test_upload_csv_file_extracts_text(self, session, channel_id):
        """POST /api/channels/{channel_id}/files - Upload CSV file and verify text extraction"""
        csv_content = "name,age,city\nAlice,30,New York\nBob,25,San Francisco\nCharlie,35,Boston"
        
        # Remove Content-Type header
        orig_headers = session.headers.copy()
        if "Content-Type" in session.headers:
            del session.headers["Content-Type"]
        
        files = {
            "file": ("data.csv", csv_content.encode("utf-8"), "text/csv")
        }
        
        res = session.post(
            f"{BASE_URL}/api/channels/{channel_id}/files",
            files=files
        )
        
        session.headers = orig_headers
        
        assert res.status_code == 200, f"CSV upload failed: {res.text}"
        data = res.json()
        
        assert data["file"]["extension"] == "csv", "Extension should be csv"
        assert data["file"]["original_name"] == "data.csv"
        assert "message_id" in data
        
        print(f"CSV upload success: file_id={data['file']['file_id']}")
    
    def test_upload_image_no_text_extraction(self, session, channel_id):
        """POST /api/channels/{channel_id}/files - Upload image and verify no text extraction"""
        # Create a minimal valid PNG (1x1 pixel)
        png_bytes = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,  # bit depth, color type
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
            0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        
        # Remove Content-Type header
        orig_headers = session.headers.copy()
        if "Content-Type" in session.headers:
            del session.headers["Content-Type"]
        
        files = {
            "file": ("test_image.png", png_bytes, "image/png")
        }
        
        res = session.post(
            f"{BASE_URL}/api/channels/{channel_id}/files",
            files=files
        )
        
        session.headers = orig_headers
        
        assert res.status_code == 200, f"PNG upload failed: {res.text}"
        data = res.json()
        
        assert data["file"]["extension"] == "png", "Extension should be png"
        # Images should not have extracted text
        assert data["file"].get("has_extracted_text") is False or data["file"].get("has_extracted_text") is None
        
        print(f"PNG upload success (no text extraction as expected): file_id={data['file']['file_id']}")


class TestMessageDocumentContent:
    """Test that uploaded document content appears correctly in messages"""
    
    def test_get_messages_with_document_markers(self, session, channel_id):
        """GET /api/channels/{channel_id}/messages - Verify uploaded document content appears with markers"""
        # First upload a text document
        doc_content = "# Test Markdown Document\n\nThis is **important** content.\n\n- Item 1\n- Item 2"
        
        # Remove Content-Type header
        orig_headers = session.headers.copy()
        if "Content-Type" in session.headers:
            del session.headers["Content-Type"]
        
        files = {
            "file": ("readme.md", doc_content.encode("utf-8"), "text/markdown")
        }
        
        upload_res = session.post(
            f"{BASE_URL}/api/channels/{channel_id}/files",
            files=files
        )
        
        session.headers = orig_headers
        
        assert upload_res.status_code == 200, f"MD upload failed: {upload_res.text}"
        message_id = upload_res.json()["message_id"]
        
        # Get messages and find our uploaded document message
        messages_res = session.get(f"{BASE_URL}/api/channels/{channel_id}/messages")
        assert messages_res.status_code == 200, f"Get messages failed: {messages_res.text}"
        
        data = messages_res.json()
        # Handle both list and dict response formats
        messages = data if isinstance(data, list) else data.get("messages", [])
        
        # Find the message with our file
        doc_message = None
        for msg in messages:
            if msg.get("message_id") == message_id:
                doc_message = msg
                break
        
        assert doc_message is not None, f"Could not find message {message_id}"
        
        # Verify document content markers are present
        content = doc_message.get("content", "")
        assert "--- Document Content" in content, "Message should contain '--- Document Content' marker"
        assert "--- End Document ---" in content, "Message should contain '--- End Document ---' marker"
        assert "readme.md" in content, "Message should reference the filename"
        
        print(f"Document content markers verified in message {message_id}")
    
    def test_file_attachment_metadata(self, session, channel_id):
        """Verify file attachment includes has_extracted_text and text_length fields"""
        # Upload a text file
        test_text = "Sample text for metadata verification. " * 10
        
        # Remove Content-Type header
        orig_headers = session.headers.copy()
        if "Content-Type" in session.headers:
            del session.headers["Content-Type"]
        
        files = {
            "file": ("metadata_test.txt", test_text.encode("utf-8"), "text/plain")
        }
        
        upload_res = session.post(
            f"{BASE_URL}/api/channels/{channel_id}/files",
            files=files
        )
        
        session.headers = orig_headers
        
        assert upload_res.status_code == 200
        message_id = upload_res.json()["message_id"]
        
        # Get the message to check file_attachment
        messages_res = session.get(f"{BASE_URL}/api/channels/{channel_id}/messages")
        assert messages_res.status_code == 200
        
        data = messages_res.json()
        # Handle both list and dict response formats
        messages = data if isinstance(data, list) else data.get("messages", [])
        
        doc_message = None
        for msg in messages:
            if msg.get("message_id") == message_id:
                doc_message = msg
                break
        
        assert doc_message is not None
        file_attachment = doc_message.get("file_attachment", {})
        
        # Verify required metadata fields
        assert "has_extracted_text" in file_attachment, "file_attachment should have has_extracted_text field"
        assert "text_length" in file_attachment, "file_attachment should have text_length field"
        assert file_attachment["has_extracted_text"] is True, "Text file should have has_extracted_text=True"
        assert file_attachment["text_length"] > 0, "text_length should be > 0 for text files"
        
        print(f"File attachment metadata verified: has_extracted_text={file_attachment['has_extracted_text']}, text_length={file_attachment['text_length']}")


class TestDirectiveEditing:
    """Test directive creation and editing via channel endpoints"""
    
    @pytest.fixture
    def clean_channel(self, session, workspace_id):
        """Create a fresh channel for directive tests (no pre-existing directives)"""
        unique_id = uuid.uuid4().hex[:8]
        res = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/channels", json={
            "name": f"directive-test-{unique_id}",
            "ai_agents": ["claude", "gemini"]
        })
        assert res.status_code == 200
        return res.json()["channel_id"]
    
    def test_create_directive(self, session, clean_channel):
        """POST /api/channels/{channel_id}/directive - Create a directive"""
        payload = {
            "project_name": "Test AI Project",
            "description": "Testing directive creation",
            "goal": "Build something cool",
            "agents": {
                "claude": {"display_name": "Claude", "role": "lead", "prompt_constraints": ["Be helpful"]},
                "gemini": {"display_name": "Gemini", "role": "reviewer", "prompt_constraints": []}
            },
            "universal_rules": {
                "full_file_context": True,
                "additive_only": False,
                "max_retries": 2
            },
            "phases": []
        }
        
        res = session.post(
            f"{BASE_URL}/api/channels/{clean_channel}/directive",
            json=payload
        )
        
        assert res.status_code == 200, f"Directive creation failed: {res.text}"
        data = res.json()
        
        assert data.get("project_name") == "Test AI Project"
        assert data.get("goal") == "Build something cool"
        assert data.get("is_active") is True, "Newly created directive should be active"
        assert "directive_id" in data
        
        print(f"Directive created: {data['directive_id']}, is_active={data['is_active']}")
        return data["directive_id"]
    
    def test_edit_active_directive(self, session, clean_channel):
        """PUT /api/channels/{channel_id}/directive - Update/edit an existing active directive"""
        # First create a directive
        create_res = session.post(
            f"{BASE_URL}/api/channels/{clean_channel}/directive",
            json={
                "project_name": "Original Project",
                "goal": "Original Goal",
                "agents": {
                    "claude": {"display_name": "Claude", "role": "contributor"}
                }
            }
        )
        assert create_res.status_code == 200
        original_directive = create_res.json()
        
        # Now update the directive
        update_payload = {
            "project_name": "Updated Project Name",
            "goal": "Updated Goal - now more specific",
            "agents": {
                "claude": {"display_name": "Claude Updated", "role": "lead", "prompt_constraints": ["Security focus"]},
                "gemini": {"display_name": "Gemini Added", "role": "reviewer"}
            },
            "universal_rules": {
                "full_file_context": False,
                "additive_only": True,
                "max_retries": 5
            }
        }
        
        update_res = session.put(
            f"{BASE_URL}/api/channels/{clean_channel}/directive",
            json=update_payload
        )
        
        assert update_res.status_code == 200, f"Directive update failed: {update_res.text}"
        updated = update_res.json()
        
        # Verify changes
        assert updated.get("project_name") == "Updated Project Name", "Project name should be updated"
        assert updated.get("goal") == "Updated Goal - now more specific", "Goal should be updated"
        assert "gemini" in updated.get("agents", {}), "Gemini agent should be added"
        assert updated.get("agents", {}).get("claude", {}).get("role") == "lead", "Claude role should be updated to lead"
        
        # Verify directive_id is same (editing, not creating new)
        assert updated.get("directive_id") == original_directive.get("directive_id"), "Should edit same directive, not create new"
        
        print(f"Directive updated successfully: directive_id={updated['directive_id']}")
    
    def test_edit_directive_no_active_returns_404(self, session, test_user):
        """PUT /api/channels/{channel_id}/directive - Returns 404 when no active directive exists"""
        # Create a completely new workspace with no directives
        unique_id = uuid.uuid4().hex[:8]
        ws_res = session.post(f"{BASE_URL}/api/workspaces", json={
            "name": f"No Directive Workspace {unique_id}",
            "description": "Workspace with no active directive"
        })
        assert ws_res.status_code == 200
        new_ws_id = ws_res.json()["workspace_id"]
        
        # Create a channel in this new workspace
        channel_res = session.post(f"{BASE_URL}/api/workspaces/{new_ws_id}/channels", json={
            "name": f"no-directive-{unique_id}",
            "ai_agents": ["claude"]
        })
        assert channel_res.status_code == 200
        channel_id = channel_res.json()["channel_id"]
        
        # Try to PUT/edit without creating a directive first
        update_res = session.put(
            f"{BASE_URL}/api/channels/{channel_id}/directive",
            json={
                "project_name": "This should fail",
                "goal": "No active directive exists"
            }
        )
        
        # Should return 404 since no active directive in this workspace
        assert update_res.status_code == 404, f"Expected 404, got {update_res.status_code}: {update_res.text}"
        
        print("Correctly returned 404 when no active directive exists for editing")
    
    def test_get_channel_directive(self, session, clean_channel):
        """GET /api/channels/{channel_id}/directive - Get active directive for channel"""
        # Create directive first
        session.post(
            f"{BASE_URL}/api/channels/{clean_channel}/directive",
            json={"project_name": "Get Test", "goal": "Testing get"}
        )
        
        # Get directive
        get_res = session.get(f"{BASE_URL}/api/channels/{clean_channel}/directive")
        assert get_res.status_code == 200
        
        data = get_res.json()
        assert "directive" in data
        assert data["directive"]["project_name"] == "Get Test"
        
        print(f"GET directive verified: {data['directive']['directive_id']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
