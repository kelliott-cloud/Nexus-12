"""
Tests for Marketplace and Artifacts APIs - Iteration 20
Covers:
- POST /api/marketplace/publish - Publish workflow to marketplace
- GET /api/marketplace - Browse global marketplace
- GET /api/marketplace/org/{org_id} - Browse org-scoped marketplace
- GET /api/marketplace/{template_id} - Get marketplace template details
- POST /api/marketplace/{template_id}/import - Import template as new workflow
- POST /api/marketplace/{template_id}/rate - Rate a template
- POST /api/workspaces/{workspace_id}/artifacts - Create artifact
- GET /api/workspaces/{workspace_id}/artifacts - List artifacts
- GET /api/artifacts/{artifact_id} - Get artifact with versions
- PUT /api/artifacts/{artifact_id} - Update artifact (new version)
- POST /api/artifacts/{artifact_id}/pin - Toggle pin
- POST /api/artifacts/{artifact_id}/tag - Add tags
- DELETE /api/artifacts/{artifact_id} - Delete artifact
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "test@nexus.com"
TEST_PASSWORD = "Test1234!"
TEST_WORKSPACE_ID = "ws_c7cf04bf840e"

# Created test data to clean up
created_marketplace_ids = []
created_artifact_ids = []
created_workflow_ids = []


@pytest.fixture(scope="module")
def session():
    """Create an authenticated requests session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    
    # Login via email/password
    login_resp = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    
    # Session cookie is set automatically
    yield s
    
    # Cleanup created test data
    for art_id in created_artifact_ids:
        try:
            s.delete(f"{BASE_URL}/api/artifacts/{art_id}")
        except:
            pass
    
    for wf_id in created_workflow_ids:
        try:
            s.delete(f"{BASE_URL}/api/workflows/{wf_id}")
        except:
            pass


# ============ MARKETPLACE TESTS ============

class TestMarketplaceBrowse:
    """Tests for marketplace browsing endpoints"""
    
    def test_browse_global_marketplace(self, session):
        """GET /api/marketplace returns global marketplace templates"""
        resp = session.get(f"{BASE_URL}/api/marketplace")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "templates" in data
        assert "total" in data
        assert isinstance(data["templates"], list)
        print(f"✓ Global marketplace returned {data['total']} templates")
    
    def test_browse_marketplace_with_category_filter(self, session):
        """GET /api/marketplace with category filter"""
        resp = session.get(f"{BASE_URL}/api/marketplace?category=research")
        assert resp.status_code == 200
        
        data = resp.json()
        for tpl in data["templates"]:
            assert tpl.get("category") == "research", f"Expected research category, got {tpl.get('category')}"
        print(f"✓ Category filter returns {len(data['templates'])} research templates")
    
    def test_browse_marketplace_with_search(self, session):
        """GET /api/marketplace with search filter"""
        resp = session.get(f"{BASE_URL}/api/marketplace?search=research")
        assert resp.status_code == 200
        
        data = resp.json()
        print(f"✓ Search filter returned {len(data['templates'])} templates matching 'research'")
    
    def test_browse_marketplace_sort_options(self, session):
        """GET /api/marketplace supports sort by popular/rating/newest"""
        for sort_option in ["popular", "rating", "newest"]:
            resp = session.get(f"{BASE_URL}/api/marketplace?sort={sort_option}")
            assert resp.status_code == 200, f"Sort by {sort_option} failed: {resp.status_code}"
        print("✓ All sort options (popular, rating, newest) work")
    
    def test_browse_org_marketplace(self, session):
        """GET /api/marketplace/org/{org_id} returns org-scoped templates"""
        test_org_id = "org_test123"
        resp = session.get(f"{BASE_URL}/api/marketplace/org/{test_org_id}")
        assert resp.status_code == 200
        
        data = resp.json()
        assert "templates" in data
        assert "total" in data
        # All returned templates should be org-scoped
        for tpl in data["templates"]:
            assert tpl.get("org_id") == test_org_id or tpl.get("scope") == "org"
        print(f"✓ Org marketplace returned {data['total']} templates for {test_org_id}")


class TestMarketplaceTemplateDetails:
    """Tests for getting marketplace template details"""
    
    def test_get_template_details(self, session):
        """GET /api/marketplace/{template_id} returns template details"""
        # First get a template from marketplace
        browse_resp = session.get(f"{BASE_URL}/api/marketplace")
        assert browse_resp.status_code == 200
        templates = browse_resp.json()["templates"]
        
        if len(templates) == 0:
            pytest.skip("No templates in marketplace to test")
        
        template_id = templates[0]["marketplace_id"]
        resp = session.get(f"{BASE_URL}/api/marketplace/{template_id}")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["marketplace_id"] == template_id
        assert "name" in data
        assert "category" in data
        assert "difficulty" in data
        assert "nodes" in data or "node_count" in data
        print(f"✓ Got template details for {template_id}: {data['name']}")
    
    def test_get_nonexistent_template(self, session):
        """GET /api/marketplace/{template_id} returns 404 for nonexistent"""
        resp = session.get(f"{BASE_URL}/api/marketplace/mkt_nonexistent123")
        assert resp.status_code == 404
        print("✓ Nonexistent template returns 404")


class TestMarketplacePublish:
    """Tests for publishing workflows to marketplace"""
    
    def test_publish_workflow_to_marketplace(self, session):
        """POST /api/marketplace/publish creates a marketplace template from workflow"""
        # First create a test workflow with nodes
        create_wf_resp = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/workflows", json={
            "name": f"TEST_PublishTest_{uuid.uuid4().hex[:6]}",
            "description": "Workflow for publish testing"
        })
        assert create_wf_resp.status_code == 200, f"Create workflow failed: {create_wf_resp.text}"
        workflow = create_wf_resp.json()
        workflow_id = workflow["workflow_id"]
        created_workflow_ids.append(workflow_id)
        
        # Add nodes to the workflow
        node1_resp = session.post(f"{BASE_URL}/api/workflows/{workflow_id}/nodes", json={
            "type": "input",
            "label": "Test Input"
        })
        assert node1_resp.status_code == 200
        
        node2_resp = session.post(f"{BASE_URL}/api/workflows/{workflow_id}/nodes", json={
            "type": "ai_agent",
            "label": "Test AI Agent"
        })
        assert node2_resp.status_code == 200
        
        # Now publish to marketplace
        publish_resp = session.post(f"{BASE_URL}/api/marketplace/publish", json={
            "workflow_id": workflow_id,
            "name": f"TEST_Marketplace_Template_{uuid.uuid4().hex[:6]}",
            "description": "Test template for marketplace testing",
            "category": "development",
            "difficulty": "beginner",
            "estimated_time": "5-10 min",
            "scope": "global"
        })
        assert publish_resp.status_code == 200, f"Publish failed: {publish_resp.text}"
        
        template = publish_resp.json()
        created_marketplace_ids.append(template["marketplace_id"])
        
        assert "marketplace_id" in template
        assert template["category"] == "development"
        assert template["difficulty"] == "beginner"
        assert template["node_count"] >= 2
        assert "nodes" in template
        print(f"✓ Published workflow to marketplace: {template['marketplace_id']}")
        return template["marketplace_id"]
    
    def test_publish_empty_workflow_fails(self, session):
        """POST /api/marketplace/publish fails for workflow without nodes"""
        # Create workflow without nodes
        create_wf_resp = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/workflows", json={
            "name": f"TEST_EmptyWorkflow_{uuid.uuid4().hex[:6]}"
        })
        assert create_wf_resp.status_code == 200
        workflow_id = create_wf_resp.json()["workflow_id"]
        created_workflow_ids.append(workflow_id)
        
        # Try to publish empty workflow
        publish_resp = session.post(f"{BASE_URL}/api/marketplace/publish", json={
            "workflow_id": workflow_id,
            "name": "Empty Workflow Template"
        })
        assert publish_resp.status_code == 400, f"Expected 400 for empty workflow, got {publish_resp.status_code}"
        print("✓ Publishing empty workflow correctly returns 400")
    
    def test_publish_nonexistent_workflow_fails(self, session):
        """POST /api/marketplace/publish fails for nonexistent workflow"""
        publish_resp = session.post(f"{BASE_URL}/api/marketplace/publish", json={
            "workflow_id": "wf_nonexistent123",
            "name": "Test Template"
        })
        assert publish_resp.status_code == 404
        print("✓ Publishing nonexistent workflow returns 404")


class TestMarketplaceImport:
    """Tests for importing marketplace templates"""
    
    def test_import_template_creates_workflow(self, session):
        """POST /api/marketplace/{template_id}/import creates new workflow from template"""
        # Get a template to import
        browse_resp = session.get(f"{BASE_URL}/api/marketplace")
        assert browse_resp.status_code == 200
        templates = browse_resp.json()["templates"]
        
        if len(templates) == 0:
            pytest.skip("No templates in marketplace to import")
        
        template_id = templates[0]["marketplace_id"]
        
        # Import the template
        import_resp = session.post(f"{BASE_URL}/api/marketplace/{template_id}/import?workspace_id={TEST_WORKSPACE_ID}")
        assert import_resp.status_code == 200, f"Import failed: {import_resp.text}"
        
        workflow = import_resp.json()
        created_workflow_ids.append(workflow["workflow_id"])
        
        assert "workflow_id" in workflow
        assert workflow["workspace_id"] == TEST_WORKSPACE_ID
        assert "nodes" in workflow
        assert "edges" in workflow
        print(f"✓ Imported template {template_id} as workflow {workflow['workflow_id']}")
        print(f"  - {len(workflow['nodes'])} nodes, {len(workflow['edges'])} edges created")
    
    def test_import_increments_usage_count(self, session):
        """POST /api/marketplace/{template_id}/import increments usage_count"""
        # Get a template
        browse_resp = session.get(f"{BASE_URL}/api/marketplace")
        templates = browse_resp.json()["templates"]
        
        if len(templates) == 0:
            pytest.skip("No templates in marketplace")
        
        template_id = templates[0]["marketplace_id"]
        
        # Get initial usage count
        initial_resp = session.get(f"{BASE_URL}/api/marketplace/{template_id}")
        initial_usage = initial_resp.json().get("usage_count", 0)
        
        # Import
        import_resp = session.post(f"{BASE_URL}/api/marketplace/{template_id}/import?workspace_id={TEST_WORKSPACE_ID}")
        assert import_resp.status_code == 200
        created_workflow_ids.append(import_resp.json()["workflow_id"])
        
        # Check usage count increased
        after_resp = session.get(f"{BASE_URL}/api/marketplace/{template_id}")
        after_usage = after_resp.json().get("usage_count", 0)
        
        assert after_usage == initial_usage + 1, f"Usage count didn't increment: {initial_usage} -> {after_usage}"
        print(f"✓ Import incremented usage count: {initial_usage} -> {after_usage}")
    
    def test_import_without_workspace_id_fails(self, session):
        """POST /api/marketplace/{template_id}/import without workspace_id returns 400"""
        browse_resp = session.get(f"{BASE_URL}/api/marketplace")
        templates = browse_resp.json()["templates"]
        
        if len(templates) == 0:
            pytest.skip("No templates in marketplace")
        
        template_id = templates[0]["marketplace_id"]
        
        # Import without workspace_id
        import_resp = session.post(f"{BASE_URL}/api/marketplace/{template_id}/import")
        assert import_resp.status_code == 400, f"Expected 400, got {import_resp.status_code}"
        print("✓ Import without workspace_id returns 400")


class TestMarketplaceRating:
    """Tests for rating marketplace templates"""
    
    def test_rate_template(self, session):
        """POST /api/marketplace/{template_id}/rate submits rating"""
        browse_resp = session.get(f"{BASE_URL}/api/marketplace")
        templates = browse_resp.json()["templates"]
        
        if len(templates) == 0:
            pytest.skip("No templates in marketplace")
        
        template_id = templates[0]["marketplace_id"]
        
        # Rate the template
        rate_resp = session.post(f"{BASE_URL}/api/marketplace/{template_id}/rate", json={"rating": 5})
        assert rate_resp.status_code == 200, f"Rating failed: {rate_resp.text}"
        
        data = rate_resp.json()
        assert "avg_rating" in data
        assert "rating_count" in data
        assert data["rating_count"] >= 1
        print(f"✓ Rated template {template_id}: avg_rating={data['avg_rating']}, count={data['rating_count']}")
    
    def test_update_existing_rating(self, session):
        """POST /api/marketplace/{template_id}/rate updates existing rating"""
        browse_resp = session.get(f"{BASE_URL}/api/marketplace")
        templates = browse_resp.json()["templates"]
        
        if len(templates) == 0:
            pytest.skip("No templates in marketplace")
        
        template_id = templates[0]["marketplace_id"]
        
        # Rate with 3 stars
        session.post(f"{BASE_URL}/api/marketplace/{template_id}/rate", json={"rating": 3})
        
        # Update to 4 stars
        rate_resp = session.post(f"{BASE_URL}/api/marketplace/{template_id}/rate", json={"rating": 4})
        assert rate_resp.status_code == 200
        print("✓ Updating existing rating works")
    
    def test_invalid_rating_value(self, session):
        """POST /api/marketplace/{template_id}/rate rejects invalid ratings"""
        browse_resp = session.get(f"{BASE_URL}/api/marketplace")
        templates = browse_resp.json()["templates"]
        
        if len(templates) == 0:
            pytest.skip("No templates in marketplace")
        
        template_id = templates[0]["marketplace_id"]
        
        # Rating out of range
        resp = session.post(f"{BASE_URL}/api/marketplace/{template_id}/rate", json={"rating": 6})
        assert resp.status_code == 422, f"Expected 422 for invalid rating, got {resp.status_code}"
        
        resp = session.post(f"{BASE_URL}/api/marketplace/{template_id}/rate", json={"rating": 0})
        assert resp.status_code == 422
        print("✓ Invalid ratings (0, 6) correctly rejected with 422")


# ============ ARTIFACTS TESTS ============

class TestArtifactCRUD:
    """Tests for artifact CRUD operations"""
    
    def test_create_artifact(self, session):
        """POST /api/workspaces/{workspace_id}/artifacts creates artifact"""
        resp = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/artifacts", json={
            "name": f"TEST_Artifact_{uuid.uuid4().hex[:6]}",
            "content": "This is test artifact content",
            "content_type": "text",
            "tags": ["test", "automated"]
        })
        assert resp.status_code == 200, f"Create artifact failed: {resp.text}"
        
        artifact = resp.json()
        created_artifact_ids.append(artifact["artifact_id"])
        
        assert "artifact_id" in artifact
        assert artifact["name"].startswith("TEST_Artifact_")
        assert artifact["content_type"] == "text"
        assert artifact["version"] == 1
        assert artifact["pinned"] == False
        assert "test" in artifact["tags"]
        print(f"✓ Created artifact: {artifact['artifact_id']}")
        return artifact["artifact_id"]
    
    def test_create_artifact_with_different_types(self, session):
        """POST /api/workspaces/{workspace_id}/artifacts supports all content types"""
        for content_type in ["text", "json", "code", "markdown"]:
            content = '{"key": "value"}' if content_type == "json" else f"Test {content_type} content"
            resp = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/artifacts", json={
                "name": f"TEST_{content_type.upper()}_{uuid.uuid4().hex[:6]}",
                "content": content,
                "content_type": content_type,
                "tags": ["type-test"]
            })
            assert resp.status_code == 200, f"Failed for type {content_type}: {resp.text}"
            created_artifact_ids.append(resp.json()["artifact_id"])
        print("✓ All content types (text, json, code, markdown) work")
    
    def test_list_artifacts(self, session):
        """GET /api/workspaces/{workspace_id}/artifacts lists artifacts"""
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/artifacts")
        assert resp.status_code == 200
        
        data = resp.json()
        assert "artifacts" in data
        assert "total" in data
        assert isinstance(data["artifacts"], list)
        print(f"✓ Listed {data['total']} artifacts")
    
    def test_list_artifacts_with_search(self, session):
        """GET /api/workspaces/{workspace_id}/artifacts supports search"""
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/artifacts?search=TEST_")
        assert resp.status_code == 200
        
        data = resp.json()
        # All results should contain TEST_ in name or tags
        print(f"✓ Search returned {len(data['artifacts'])} artifacts matching 'TEST_'")
    
    def test_list_artifacts_filter_by_type(self, session):
        """GET /api/workspaces/{workspace_id}/artifacts supports content_type filter"""
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/artifacts?content_type=text")
        assert resp.status_code == 200
        
        data = resp.json()
        for art in data["artifacts"]:
            assert art["content_type"] == "text"
        print(f"✓ Type filter returned {len(data['artifacts'])} text artifacts")
    
    def test_list_artifacts_filter_by_pinned(self, session):
        """GET /api/workspaces/{workspace_id}/artifacts supports pinned filter"""
        resp = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/artifacts?pinned=true")
        assert resp.status_code == 200
        
        data = resp.json()
        for art in data["artifacts"]:
            assert art["pinned"] == True
        print(f"✓ Pinned filter returned {len(data['artifacts'])} pinned artifacts")
    
    def test_get_artifact_with_versions(self, session):
        """GET /api/artifacts/{artifact_id} returns artifact with version history"""
        # First create an artifact
        create_resp = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/artifacts", json={
            "name": f"TEST_VersionTest_{uuid.uuid4().hex[:6]}",
            "content": "Version 1 content",
            "content_type": "text"
        })
        artifact_id = create_resp.json()["artifact_id"]
        created_artifact_ids.append(artifact_id)
        
        # Get the artifact
        resp = session.get(f"{BASE_URL}/api/artifacts/{artifact_id}")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["artifact_id"] == artifact_id
        assert "versions" in data
        assert len(data["versions"]) >= 1
        print(f"✓ Got artifact with {len(data['versions'])} version(s)")
    
    def test_get_nonexistent_artifact(self, session):
        """GET /api/artifacts/{artifact_id} returns 404 for nonexistent"""
        resp = session.get(f"{BASE_URL}/api/artifacts/art_nonexistent123")
        assert resp.status_code == 404
        print("✓ Nonexistent artifact returns 404")


class TestArtifactUpdate:
    """Tests for artifact update operations"""
    
    def test_update_artifact_creates_new_version(self, session):
        """PUT /api/artifacts/{artifact_id} with content change creates new version"""
        # Create artifact
        create_resp = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/artifacts", json={
            "name": f"TEST_UpdateTest_{uuid.uuid4().hex[:6]}",
            "content": "Original content",
            "content_type": "text"
        })
        artifact_id = create_resp.json()["artifact_id"]
        created_artifact_ids.append(artifact_id)
        
        # Update content
        update_resp = session.put(f"{BASE_URL}/api/artifacts/{artifact_id}", json={
            "content": "Updated content version 2"
        })
        assert update_resp.status_code == 200
        
        updated = update_resp.json()
        assert updated["version"] == 2
        assert updated["content"] == "Updated content version 2"
        
        # Verify version history
        get_resp = session.get(f"{BASE_URL}/api/artifacts/{artifact_id}")
        versions = get_resp.json()["versions"]
        assert len(versions) >= 2
        print(f"✓ Update created version 2, total versions: {len(versions)}")
    
    def test_update_artifact_name_only(self, session):
        """PUT /api/artifacts/{artifact_id} can update just name without new version"""
        create_resp = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/artifacts", json={
            "name": f"TEST_NameUpdate_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "content_type": "text"
        })
        artifact_id = create_resp.json()["artifact_id"]
        created_artifact_ids.append(artifact_id)
        
        # Update name only
        update_resp = session.put(f"{BASE_URL}/api/artifacts/{artifact_id}", json={
            "name": "TEST_RenamedArtifact"
        })
        assert update_resp.status_code == 200
        
        updated = update_resp.json()
        assert updated["name"] == "TEST_RenamedArtifact"
        assert updated["version"] == 1  # No content change, no new version
        print("✓ Name-only update doesn't create new version")
    
    def test_update_artifact_tags(self, session):
        """PUT /api/artifacts/{artifact_id} can update tags"""
        create_resp = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/artifacts", json={
            "name": f"TEST_TagUpdate_{uuid.uuid4().hex[:6]}",
            "content": "Content",
            "content_type": "text",
            "tags": ["original"]
        })
        artifact_id = create_resp.json()["artifact_id"]
        created_artifact_ids.append(artifact_id)
        
        # Update tags
        update_resp = session.put(f"{BASE_URL}/api/artifacts/{artifact_id}", json={
            "tags": ["updated", "new-tag"]
        })
        assert update_resp.status_code == 200
        
        updated = update_resp.json()
        assert "updated" in updated["tags"]
        assert "new-tag" in updated["tags"]
        print("✓ Tags updated successfully")


class TestArtifactPinAndTag:
    """Tests for artifact pin and tag operations"""
    
    def test_toggle_pin(self, session):
        """POST /api/artifacts/{artifact_id}/pin toggles pinned state"""
        # Create artifact
        create_resp = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/artifacts", json={
            "name": f"TEST_PinTest_{uuid.uuid4().hex[:6]}",
            "content": "Pin test content",
            "content_type": "text"
        })
        artifact_id = create_resp.json()["artifact_id"]
        created_artifact_ids.append(artifact_id)
        
        # Pin it
        pin_resp = session.post(f"{BASE_URL}/api/artifacts/{artifact_id}/pin")
        assert pin_resp.status_code == 200
        assert pin_resp.json()["pinned"] == True
        
        # Unpin it
        unpin_resp = session.post(f"{BASE_URL}/api/artifacts/{artifact_id}/pin")
        assert unpin_resp.status_code == 200
        assert unpin_resp.json()["pinned"] == False
        print("✓ Pin toggle works correctly")
    
    def test_add_tags(self, session):
        """POST /api/artifacts/{artifact_id}/tag adds tags to artifact"""
        # Create artifact with initial tags
        create_resp = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/artifacts", json={
            "name": f"TEST_TagTest_{uuid.uuid4().hex[:6]}",
            "content": "Tag test content",
            "content_type": "text",
            "tags": ["initial"]
        })
        artifact_id = create_resp.json()["artifact_id"]
        created_artifact_ids.append(artifact_id)
        
        # Add more tags
        tag_resp = session.post(f"{BASE_URL}/api/artifacts/{artifact_id}/tag", json={
            "tags": ["new-tag", "another-tag"]
        })
        assert tag_resp.status_code == 200
        
        tags = tag_resp.json()["tags"]
        assert "initial" in tags  # Original preserved
        assert "new-tag" in tags
        assert "another-tag" in tags
        print(f"✓ Tags added successfully: {tags}")


class TestArtifactDelete:
    """Tests for artifact deletion"""
    
    def test_delete_artifact(self, session):
        """DELETE /api/artifacts/{artifact_id} removes artifact and versions"""
        # Create artifact
        create_resp = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/artifacts", json={
            "name": f"TEST_DeleteTest_{uuid.uuid4().hex[:6]}",
            "content": "To be deleted",
            "content_type": "text"
        })
        artifact_id = create_resp.json()["artifact_id"]
        
        # Delete it
        delete_resp = session.delete(f"{BASE_URL}/api/artifacts/{artifact_id}")
        assert delete_resp.status_code == 200
        
        # Verify it's gone
        get_resp = session.get(f"{BASE_URL}/api/artifacts/{artifact_id}")
        assert get_resp.status_code == 404
        print("✓ Artifact deleted successfully")
    
    def test_delete_nonexistent_artifact(self, session):
        """DELETE /api/artifacts/{artifact_id} returns 404 for nonexistent"""
        resp = session.delete(f"{BASE_URL}/api/artifacts/art_nonexistent123")
        assert resp.status_code == 404
        print("✓ Deleting nonexistent artifact returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
