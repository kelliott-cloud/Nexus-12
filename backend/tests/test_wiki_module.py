"""
Wiki/Docs Module - Backend API Tests for Iteration 52
Tests: Wiki CRUD, versioning, hierarchy, search, AI access, pin/unpin
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials and workspace
TEST_EMAIL = "test@test.com"
TEST_PASSWORD = "test123"
TEST_WORKSPACE_ID = "ws_f6ec6355bb18"

# Existing pages from context
EXISTING_PAGE_GETTING_STARTED = "wp_83adc2fe0869"
EXISTING_PAGE_API_REFERENCE = "wp_d39f75b89f58"  # child of Getting Started
EXISTING_PAGE_DEPLOYMENT = "wp_2e07a5888913"


class TestWikiModule:
    """Wiki/Docs Backend API Tests"""

    @pytest.fixture(scope="class")
    def session(self):
        """Create authenticated session with cookies"""
        s = requests.Session()
        response = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return s

    # =====================
    # WIKI LIST ENDPOINT
    # =====================
    
    def test_wiki_list_pages(self, session):
        """GET /workspaces/{ws}/wiki returns pages list"""
        response = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "pages" in data, "Response missing 'pages' key"
        assert isinstance(data["pages"], list), "Pages should be a list"
        # Validate page structure
        if len(data["pages"]) > 0:
            page = data["pages"][0]
            assert "page_id" in page, "Page missing page_id"
            assert "title" in page, "Page missing title"
        print(f"Found {len(data['pages'])} wiki pages")

    def test_wiki_list_with_search(self, session):
        """Wiki search query parameter filters pages"""
        # Search for "Getting Started" - should find existing page
        response = session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki?search=Getting"
        )
        assert response.status_code == 200
        data = response.json()
        assert "pages" in data
        # Should find at least the Getting Started page
        titles = [p["title"] for p in data["pages"]]
        assert any("Getting" in t or "getting" in t for t in titles), f"Search didn't find expected page. Found: {titles}"
        print(f"Search 'Getting' found: {titles}")

    def test_wiki_list_search_no_results(self, session):
        """Search with non-existent term returns empty list"""
        unique_search = f"NonExistentPage_{uuid.uuid4().hex[:8]}"
        response = session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki?search={unique_search}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["pages"] == [], f"Expected empty results, got: {data['pages']}"

    # =====================
    # WIKI CREATE ENDPOINT
    # =====================

    def test_wiki_create_page(self, session):
        """POST /workspaces/{ws}/wiki creates page"""
        unique_title = f"TEST_Page_{uuid.uuid4().hex[:8]}"
        response = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki",
            json={
                "title": unique_title,
                "content": "# Test Content\n\nThis is a test page for iteration 52.",
                "parent_id": None,
                "icon": "📝"
            }
        )
        assert response.status_code == 200, f"Failed to create page: {response.text}"
        data = response.json()
        assert "page_id" in data, "Response missing page_id"
        assert data["title"] == unique_title, "Title mismatch"
        assert data["version"] == 1, "Initial version should be 1"
        assert data["word_count"] > 0, "Word count should be calculated"
        assert data["pinned"] == False, "New pages should not be pinned"
        print(f"Created page: {data['page_id']}")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{data['page_id']}")

    def test_wiki_create_page_with_parent(self, session):
        """POST creates page with parent_id for hierarchy"""
        unique_title = f"TEST_ChildPage_{uuid.uuid4().hex[:8]}"
        response = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki",
            json={
                "title": unique_title,
                "content": "Child page content",
                "parent_id": EXISTING_PAGE_GETTING_STARTED,
                "icon": ""
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["parent_id"] == EXISTING_PAGE_GETTING_STARTED, "Parent ID not set correctly"
        print(f"Created child page with parent: {EXISTING_PAGE_GETTING_STARTED}")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{data['page_id']}")

    def test_wiki_create_page_validation(self, session):
        """Create page with empty title should fail"""
        response = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki",
            json={
                "title": "",
                "content": "Some content",
            }
        )
        assert response.status_code in [400, 422], f"Expected validation error, got {response.status_code}"

    # =====================
    # WIKI GET SINGLE PAGE
    # =====================

    def test_wiki_get_page(self, session):
        """GET /workspaces/{ws}/wiki/{page_id} returns page with children"""
        response = session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{EXISTING_PAGE_GETTING_STARTED}"
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["page_id"] == EXISTING_PAGE_GETTING_STARTED
        assert "title" in data
        assert "content" in data
        assert "version" in data
        assert "children" in data, "Response should include children array"
        assert isinstance(data["children"], list), "Children should be a list"
        print(f"Page '{data['title']}' has {len(data['children'])} children")

    def test_wiki_get_page_not_found(self, session):
        """GET returns 404 for non-existent page"""
        response = session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/wp_nonexistent123"
        )
        assert response.status_code == 404

    # =====================
    # WIKI UPDATE ENDPOINT
    # =====================

    def test_wiki_update_page_creates_version(self, session):
        """PUT /workspaces/{ws}/wiki/{page_id} updates and creates version"""
        # Create a test page first
        create_response = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki",
            json={"title": f"TEST_UpdateTest_{uuid.uuid4().hex[:8]}", "content": "Initial content"}
        )
        assert create_response.status_code == 200
        page_id = create_response.json()["page_id"]
        initial_version = create_response.json()["version"]
        
        # Update the page content
        update_response = session.put(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{page_id}",
            json={"content": "Updated content for version test"}
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        updated_data = update_response.json()
        assert updated_data["version"] == initial_version + 1, "Version should increment on content change"
        assert updated_data["content"] == "Updated content for version test"
        print(f"Version incremented: {initial_version} -> {updated_data['version']}")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{page_id}")

    def test_wiki_update_title_no_version(self, session):
        """Update title only should NOT increment version"""
        # Create a test page
        create_response = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki",
            json={"title": f"TEST_TitleOnly_{uuid.uuid4().hex[:8]}", "content": "Some content"}
        )
        page_id = create_response.json()["page_id"]
        initial_version = create_response.json()["version"]
        
        # Update only the title
        update_response = session.put(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{page_id}",
            json={"title": "TEST_NewTitle"}
        )
        assert update_response.status_code == 200
        # Version should stay same (content didn't change)
        assert update_response.json()["version"] == initial_version, "Version should not change for title-only update"
        print(f"Title-only update kept version at: {initial_version}")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{page_id}")

    def test_wiki_pin_unpin_page(self, session):
        """PUT with pinned field toggles pin status"""
        # Create test page
        create_response = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki",
            json={"title": f"TEST_PinTest_{uuid.uuid4().hex[:8]}", "content": "Pin test"}
        )
        page_id = create_response.json()["page_id"]
        assert create_response.json()["pinned"] == False
        
        # Pin the page
        pin_response = session.put(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{page_id}",
            json={"pinned": True}
        )
        assert pin_response.status_code == 200
        assert pin_response.json()["pinned"] == True
        print(f"Pinned page: {page_id}")
        
        # Unpin the page
        unpin_response = session.put(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{page_id}",
            json={"pinned": False}
        )
        assert unpin_response.status_code == 200
        assert unpin_response.json()["pinned"] == False
        print(f"Unpinned page: {page_id}")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{page_id}")

    # =====================
    # WIKI DELETE ENDPOINT
    # =====================

    def test_wiki_delete_page_soft_delete(self, session):
        """DELETE /workspaces/{ws}/wiki/{page_id} soft deletes and unparents children"""
        # Create parent page
        parent_response = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki",
            json={"title": f"TEST_Parent_{uuid.uuid4().hex[:8]}", "content": "Parent"}
        )
        parent_id = parent_response.json()["page_id"]
        
        # Create child page
        child_response = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki",
            json={"title": f"TEST_Child_{uuid.uuid4().hex[:8]}", "content": "Child", "parent_id": parent_id}
        )
        child_id = child_response.json()["page_id"]
        
        # Delete parent
        delete_response = session.delete(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{parent_id}"
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["deleted"] == True
        
        # Parent should be deleted (not found)
        get_parent = session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{parent_id}"
        )
        assert get_parent.status_code == 404
        
        # Child should be orphaned (parent_id = None)
        get_child = session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{child_id}"
        )
        assert get_child.status_code == 200
        assert get_child.json()["parent_id"] is None, "Child should be unparented after parent deletion"
        print(f"Deleted parent {parent_id}, child {child_id} orphaned successfully")
        
        # Cleanup child
        session.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{child_id}")

    # =====================
    # WIKI VERSION HISTORY
    # =====================

    def test_wiki_get_history(self, session):
        """GET /workspaces/{ws}/wiki/{page_id}/history returns versions"""
        # Create page and make updates to create history
        create_response = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki",
            json={"title": f"TEST_History_{uuid.uuid4().hex[:8]}", "content": "Version 1"}
        )
        page_id = create_response.json()["page_id"]
        
        # Update to create version 2
        session.put(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{page_id}",
            json={"content": "Version 2 content"}
        )
        
        # Update to create version 3
        session.put(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{page_id}",
            json={"content": "Version 3 content"}
        )
        
        # Get history
        history_response = session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{page_id}/history"
        )
        assert history_response.status_code == 200, f"Failed: {history_response.text}"
        data = history_response.json()
        assert "versions" in data, "Response missing 'versions'"
        assert len(data["versions"]) == 3, f"Expected 3 versions, got {len(data['versions'])}"
        
        # Versions should be sorted descending (newest first)
        versions = [v["version"] for v in data["versions"]]
        assert versions == [3, 2, 1], f"Versions not sorted correctly: {versions}"
        
        # Validate version structure
        for v in data["versions"]:
            assert "version_id" in v
            assert "page_id" in v
            assert "version" in v
            assert "title" in v
            assert "content" in v
            assert "author_name" in v
            assert "created_at" in v
        print(f"History has {len(data['versions'])} versions: {versions}")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{page_id}")

    def test_wiki_get_specific_version(self, session):
        """GET /workspaces/{ws}/wiki/{page_id}/version/{v} returns specific version"""
        # Create page
        create_response = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki",
            json={"title": f"TEST_SpecificVersion_{uuid.uuid4().hex[:8]}", "content": "Initial"}
        )
        page_id = create_response.json()["page_id"]
        
        # Update to create version 2
        session.put(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{page_id}",
            json={"content": "Second version content"}
        )
        
        # Get version 1
        v1_response = session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{page_id}/version/1"
        )
        assert v1_response.status_code == 200
        assert v1_response.json()["version"] == 1
        assert v1_response.json()["content"] == "Initial"
        
        # Get version 2
        v2_response = session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{page_id}/version/2"
        )
        assert v2_response.status_code == 200
        assert v2_response.json()["version"] == 2
        assert v2_response.json()["content"] == "Second version content"
        print(f"Retrieved v1 and v2 successfully")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{page_id}")

    # =====================
    # WIKI AI UPDATE
    # =====================

    def test_wiki_ai_update_create(self, session):
        """POST /workspaces/{ws}/wiki/ai-update creates new page"""
        unique_title = f"TEST_AI_Page_{uuid.uuid4().hex[:8]}"
        response = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/ai-update",
            json={
                "title": unique_title,
                "content": "# AI Generated\n\nThis page was created by an AI agent.",
                "agent_name": "TestBot"
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["action"] == "created"
        assert data["version"] == 1
        assert "page_id" in data
        print(f"AI created page: {data['page_id']}, action: {data['action']}")
        
        # Verify the page exists
        get_response = session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{data['page_id']}"
        )
        assert get_response.status_code == 200
        page_data = get_response.json()
        assert page_data["title"] == unique_title
        assert page_data["created_by_name"] == "TestBot"
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{data['page_id']}")

    def test_wiki_ai_update_existing(self, session):
        """POST /workspaces/{ws}/wiki/ai-update updates existing page by title"""
        unique_title = f"TEST_AI_Update_{uuid.uuid4().hex[:8]}"
        
        # Create page first
        create_response = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/ai-update",
            json={"title": unique_title, "content": "Initial AI content", "agent_name": "Bot1"}
        )
        assert create_response.status_code == 200
        page_id = create_response.json()["page_id"]
        
        # Update with same title
        update_response = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/ai-update",
            json={"title": unique_title, "content": "Updated by AI agent", "agent_name": "Bot2"}
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["action"] == "updated"
        assert data["version"] == 2
        assert data["page_id"] == page_id  # Same page updated
        print(f"AI updated existing page: {page_id}, version: {data['version']}")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{page_id}")

    def test_wiki_ai_update_missing_title(self, session):
        """AI update without title should fail"""
        response = session.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/ai-update",
            json={"content": "Content without title", "agent_name": "TestBot"}
        )
        assert response.status_code == 400

    # =====================
    # PARENT-CHILD HIERARCHY
    # =====================

    def test_wiki_hierarchy_parent_children(self, session):
        """Parent page returns children, child has correct parent_id"""
        # Check existing hierarchy (Getting Started -> API Reference)
        response = session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{EXISTING_PAGE_GETTING_STARTED}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "children" in data
        print(f"Parent '{data['title']}' has children: {[c['title'] for c in data['children']]}")
        
        # Check child page
        child_response = session.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/wiki/{EXISTING_PAGE_API_REFERENCE}"
        )
        assert child_response.status_code == 200
        child_data = child_response.json()
        assert child_data["parent_id"] == EXISTING_PAGE_GETTING_STARTED
        print(f"Child '{child_data['title']}' has parent_id: {child_data['parent_id']}")


# Run if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
