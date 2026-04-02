"""
Workflow API Tests - Phase 1 Workflow Engine Testing
Tests: Templates, Workflow CRUD, Node CRUD, Edge CRUD, Canvas Save
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "test@nexus.com"
TEST_PASSWORD = "Test1234!"

# Existing workspace and workflows
TEST_WORKSPACE_ID = "ws_c7cf04bf840e"
EXISTING_WORKFLOW_ID = "wf_55ad235a0a37"
BLANK_WORKFLOW_ID = "wf_3b4980ca126e"


@pytest.fixture(scope="module")
def session():
    """Create authenticated session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    
    # Login
    res = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert res.status_code == 200, f"Login failed: {res.text}"
    print(f"Login successful for {TEST_EMAIL}")
    return s


class TestWorkflowTemplates:
    """Test template endpoints"""
    
    def test_list_templates(self, session):
        """GET /api/templates - should return seeded templates"""
        res = session.get(f"{BASE_URL}/api/templates")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        templates = res.json()
        assert isinstance(templates, list), "Expected list of templates"
        assert len(templates) >= 4, f"Expected at least 4 templates, got {len(templates)}"
        
        # Verify template structure
        for tpl in templates:
            assert "template_id" in tpl
            assert "name" in tpl
            assert "description" in tpl
            assert "category" in tpl
            assert "nodes" in tpl or "node_definitions" in tpl
        
        # Check for expected templates
        template_ids = [t["template_id"] for t in templates]
        assert "tpl_research_synthesis" in template_ids, "Missing Research Synthesis template"
        assert "tpl_content_production" in template_ids, "Missing Content Production template"
        assert "tpl_code_review" in template_ids, "Missing Code Review template"
        assert "tpl_competitive_analysis" in template_ids, "Missing Competitive Analysis template"
        print(f"Found {len(templates)} templates")
    
    def test_get_single_template(self, session):
        """GET /api/templates/{template_id}"""
        res = session.get(f"{BASE_URL}/api/templates/tpl_research_synthesis")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        tpl = res.json()
        assert tpl["template_id"] == "tpl_research_synthesis"
        assert tpl["name"] == "Research Synthesis Pipeline"
        assert "nodes" in tpl
        assert len(tpl["nodes"]) >= 4, f"Expected at least 4 nodes in template"
        print(f"Template: {tpl['name']} with {len(tpl['nodes'])} nodes")
    
    def test_get_nonexistent_template(self, session):
        """GET /api/templates/{invalid_id} - should return 404"""
        res = session.get(f"{BASE_URL}/api/templates/nonexistent_template")
        assert res.status_code == 404


class TestWorkflowCRUD:
    """Test workflow CRUD operations"""
    
    def test_list_workflows(self, session):
        """GET /api/workspaces/{workspace_id}/workflows"""
        res = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/workflows")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        workflows = res.json()
        assert isinstance(workflows, list), "Expected list of workflows"
        
        # Check for existing workflows
        wf_ids = [w["workflow_id"] for w in workflows]
        print(f"Found {len(workflows)} workflows in workspace")
        
        # Verify structure
        for wf in workflows:
            assert "workflow_id" in wf
            assert "workspace_id" in wf
            assert "name" in wf
            assert "status" in wf
            assert "node_count" in wf
    
    def test_create_blank_workflow(self, session):
        """POST /api/workspaces/{workspace_id}/workflows - create blank"""
        res = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/workflows", json={
            "name": "TEST_Blank_Workflow_API",
            "description": "API test workflow"
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        wf = res.json()
        assert "workflow_id" in wf
        assert wf["name"] == "TEST_Blank_Workflow_API"
        assert wf["status"] == "draft"
        assert wf["workspace_id"] == TEST_WORKSPACE_ID
        assert wf.get("nodes", []) == [], "Blank workflow should have no nodes"
        
        print(f"Created blank workflow: {wf['workflow_id']}")
        return wf["workflow_id"]
    
    def test_create_workflow_from_template(self, session):
        """POST /api/workspaces/{workspace_id}/workflows with template_id"""
        res = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/workflows", json={
            "name": "TEST_From_Template_API",
            "description": "Created from template",
            "template_id": "tpl_research_synthesis"
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        wf = res.json()
        assert wf["name"] == "TEST_From_Template_API"
        assert wf["template_id"] == "tpl_research_synthesis"
        assert wf["is_template_instance"] == True
        assert wf["status"] == "active", "Template-based workflow should be active"
        
        # Should have nodes and edges created from template
        nodes = wf.get("nodes", [])
        edges = wf.get("edges", [])
        assert len(nodes) >= 4, f"Expected at least 4 nodes from template, got {len(nodes)}"
        assert len(edges) >= 4, f"Expected at least 4 edges from template, got {len(edges)}"
        
        # Verify node types
        node_types = [n["type"] for n in nodes]
        assert "input" in node_types
        assert "output" in node_types
        assert "ai_agent" in node_types
        
        print(f"Created workflow from template: {wf['workflow_id']} with {len(nodes)} nodes, {len(edges)} edges")
        return wf["workflow_id"]
    
    def test_get_single_workflow(self, session):
        """GET /api/workflows/{workflow_id}"""
        res = session.get(f"{BASE_URL}/api/workflows/{EXISTING_WORKFLOW_ID}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        wf = res.json()
        assert wf["workflow_id"] == EXISTING_WORKFLOW_ID
        assert "nodes" in wf
        assert "edges" in wf
        assert isinstance(wf["nodes"], list)
        assert isinstance(wf["edges"], list)
        print(f"Workflow {wf['name']}: {len(wf['nodes'])} nodes, {len(wf['edges'])} edges")
    
    def test_get_nonexistent_workflow(self, session):
        """GET /api/workflows/{invalid_id} - should return 404"""
        res = session.get(f"{BASE_URL}/api/workflows/nonexistent_workflow")
        assert res.status_code == 404
    
    def test_update_workflow_name(self, session):
        """PUT /api/workflows/{workflow_id} - update name"""
        # First create a test workflow
        create_res = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/workflows", json={
            "name": "TEST_Update_Name_Original",
            "description": "To be updated"
        })
        wf_id = create_res.json()["workflow_id"]
        
        # Update name
        res = session.put(f"{BASE_URL}/api/workflows/{wf_id}", json={
            "name": "TEST_Update_Name_Updated"
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        updated = res.json()
        assert updated["name"] == "TEST_Update_Name_Updated"
        
        # Verify persistence
        get_res = session.get(f"{BASE_URL}/api/workflows/{wf_id}")
        assert get_res.json()["name"] == "TEST_Update_Name_Updated"
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/workflows/{wf_id}")
        print("Workflow name update verified")
    
    def test_update_workflow_status(self, session):
        """PUT /api/workflows/{workflow_id} - update status"""
        # Create test workflow
        create_res = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/workflows", json={
            "name": "TEST_Status_Change",
            "description": "Testing status changes"
        })
        wf_id = create_res.json()["workflow_id"]
        
        # Change from draft to active
        res = session.put(f"{BASE_URL}/api/workflows/{wf_id}", json={"status": "active"})
        assert res.status_code == 200
        assert res.json()["status"] == "active"
        
        # Change to paused
        res = session.put(f"{BASE_URL}/api/workflows/{wf_id}", json={"status": "paused"})
        assert res.status_code == 200
        assert res.json()["status"] == "paused"
        
        # Test invalid status
        res = session.put(f"{BASE_URL}/api/workflows/{wf_id}", json={"status": "invalid_status"})
        assert res.status_code == 400
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/workflows/{wf_id}")
        print("Workflow status update verified")
    
    def test_delete_workflow(self, session):
        """DELETE /api/workflows/{workflow_id}"""
        # Create test workflow
        create_res = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/workflows", json={
            "name": "TEST_Delete_Me",
            "description": "To be deleted"
        })
        wf_id = create_res.json()["workflow_id"]
        
        # Delete
        res = session.delete(f"{BASE_URL}/api/workflows/{wf_id}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        # Verify deleted
        get_res = session.get(f"{BASE_URL}/api/workflows/{wf_id}")
        assert get_res.status_code == 404
        print("Workflow deletion verified")


class TestNodeCRUD:
    """Test node CRUD operations"""
    
    @pytest.fixture
    def test_workflow(self, session):
        """Create a test workflow for node tests"""
        res = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/workflows", json={
            "name": "TEST_Node_CRUD_Workflow",
            "description": "For node testing"
        })
        wf_id = res.json()["workflow_id"]
        yield wf_id
        # Cleanup
        session.delete(f"{BASE_URL}/api/workflows/{wf_id}")
    
    def test_add_node(self, session, test_workflow):
        """POST /api/workflows/{workflow_id}/nodes"""
        res = session.post(f"{BASE_URL}/api/workflows/{test_workflow}/nodes", json={
            "type": "ai_agent",
            "label": "Test AI Agent",
            "ai_model": "chatgpt",
            "system_prompt": "You are a test agent",
            "temperature": 0.5,
            "position_x": 100,
            "position_y": 200
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        node = res.json()
        assert "node_id" in node
        assert node["type"] == "ai_agent"
        assert node["label"] == "Test AI Agent"
        assert node["ai_model"] == "chatgpt"
        assert node["temperature"] == 0.5
        assert node["position_x"] == 100
        assert node["position_y"] == 200
        print(f"Created node: {node['node_id']}")
        return node["node_id"]
    
    def test_add_all_node_types(self, session, test_workflow):
        """Test adding all 6 node types"""
        node_types = ["input", "output", "ai_agent", "human_review", "condition", "merge"]
        
        for ntype in node_types:
            res = session.post(f"{BASE_URL}/api/workflows/{test_workflow}/nodes", json={
                "type": ntype,
                "label": f"Test {ntype}",
                "position_x": 100,
                "position_y": 100
            })
            assert res.status_code == 200, f"Failed to create {ntype} node: {res.text}"
            assert res.json()["type"] == ntype
        
        print(f"All 6 node types created successfully")
    
    def test_add_invalid_node_type(self, session, test_workflow):
        """POST /api/workflows/{workflow_id}/nodes with invalid type"""
        res = session.post(f"{BASE_URL}/api/workflows/{test_workflow}/nodes", json={
            "type": "invalid_type",
            "label": "Invalid Node"
        })
        assert res.status_code == 400
    
    def test_update_node_config(self, session, test_workflow):
        """PUT /api/workflows/{workflow_id}/nodes/{node_id}"""
        # Create a node first
        create_res = session.post(f"{BASE_URL}/api/workflows/{test_workflow}/nodes", json={
            "type": "ai_agent",
            "label": "Original Label",
            "ai_model": "chatgpt"
        })
        node_id = create_res.json()["node_id"]
        
        # Update node config
        res = session.put(f"{BASE_URL}/api/workflows/{test_workflow}/nodes/{node_id}", json={
            "label": "Updated Label",
            "ai_model": "claude",
            "system_prompt": "You are an updated agent",
            "temperature": 0.8,
            "max_tokens": 2048
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        updated = res.json()
        assert updated["label"] == "Updated Label"
        assert updated["ai_model"] == "claude"
        assert updated["system_prompt"] == "You are an updated agent"
        assert updated["temperature"] == 0.8
        assert updated["max_tokens"] == 2048
        print("Node config update verified")
    
    def test_delete_node(self, session, test_workflow):
        """DELETE /api/workflows/{workflow_id}/nodes/{node_id}"""
        # Create a node
        create_res = session.post(f"{BASE_URL}/api/workflows/{test_workflow}/nodes", json={
            "type": "input",
            "label": "To Delete"
        })
        node_id = create_res.json()["node_id"]
        
        # Delete node
        res = session.delete(f"{BASE_URL}/api/workflows/{test_workflow}/nodes/{node_id}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        # Verify workflow doesn't have this node
        wf_res = session.get(f"{BASE_URL}/api/workflows/{test_workflow}")
        node_ids = [n["node_id"] for n in wf_res.json()["nodes"]]
        assert node_id not in node_ids
        print("Node deletion verified")
    
    def test_delete_node_removes_connected_edges(self, session, test_workflow):
        """DELETE node should also delete connected edges"""
        # Create two nodes
        n1_res = session.post(f"{BASE_URL}/api/workflows/{test_workflow}/nodes", json={
            "type": "input", "label": "Source"
        })
        n2_res = session.post(f"{BASE_URL}/api/workflows/{test_workflow}/nodes", json={
            "type": "output", "label": "Target"
        })
        n1_id = n1_res.json()["node_id"]
        n2_id = n2_res.json()["node_id"]
        
        # Create edge between them
        edge_res = session.post(f"{BASE_URL}/api/workflows/{test_workflow}/edges", json={
            "source_node_id": n1_id,
            "target_node_id": n2_id
        })
        edge_id = edge_res.json()["edge_id"]
        
        # Delete source node
        session.delete(f"{BASE_URL}/api/workflows/{test_workflow}/nodes/{n1_id}")
        
        # Verify edge is also deleted
        wf_res = session.get(f"{BASE_URL}/api/workflows/{test_workflow}")
        edge_ids = [e["edge_id"] for e in wf_res.json()["edges"]]
        assert edge_id not in edge_ids, "Edge should be deleted when connected node is deleted"
        print("Deleting node removes connected edges verified")


class TestEdgeCRUD:
    """Test edge CRUD operations"""
    
    @pytest.fixture
    def test_workflow_with_nodes(self, session):
        """Create a test workflow with 2 nodes for edge tests"""
        # Create workflow
        wf_res = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/workflows", json={
            "name": "TEST_Edge_CRUD_Workflow",
            "description": "For edge testing"
        })
        wf_id = wf_res.json()["workflow_id"]
        
        # Create two nodes
        n1_res = session.post(f"{BASE_URL}/api/workflows/{wf_id}/nodes", json={
            "type": "input", "label": "Input Node"
        })
        n2_res = session.post(f"{BASE_URL}/api/workflows/{wf_id}/nodes", json={
            "type": "ai_agent", "label": "AI Node"
        })
        
        yield {
            "workflow_id": wf_id,
            "node1_id": n1_res.json()["node_id"],
            "node2_id": n2_res.json()["node_id"]
        }
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/workflows/{wf_id}")
    
    def test_create_edge(self, session, test_workflow_with_nodes):
        """POST /api/workflows/{workflow_id}/edges"""
        wf_id = test_workflow_with_nodes["workflow_id"]
        n1_id = test_workflow_with_nodes["node1_id"]
        n2_id = test_workflow_with_nodes["node2_id"]
        
        res = session.post(f"{BASE_URL}/api/workflows/{wf_id}/edges", json={
            "source_node_id": n1_id,
            "target_node_id": n2_id,
            "edge_type": "default"
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        edge = res.json()
        assert "edge_id" in edge
        assert edge["source_node_id"] == n1_id
        assert edge["target_node_id"] == n2_id
        print(f"Created edge: {edge['edge_id']}")
        return edge["edge_id"]
    
    def test_delete_edge(self, session, test_workflow_with_nodes):
        """DELETE /api/workflows/{workflow_id}/edges/{edge_id}"""
        wf_id = test_workflow_with_nodes["workflow_id"]
        n1_id = test_workflow_with_nodes["node1_id"]
        n2_id = test_workflow_with_nodes["node2_id"]
        
        # Create edge
        create_res = session.post(f"{BASE_URL}/api/workflows/{wf_id}/edges", json={
            "source_node_id": n1_id,
            "target_node_id": n2_id
        })
        edge_id = create_res.json()["edge_id"]
        
        # Delete edge
        res = session.delete(f"{BASE_URL}/api/workflows/{wf_id}/edges/{edge_id}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        # Verify deleted
        wf_res = session.get(f"{BASE_URL}/api/workflows/{wf_id}")
        edge_ids = [e["edge_id"] for e in wf_res.json()["edges"]]
        assert edge_id not in edge_ids
        print("Edge deletion verified")


class TestCanvasSave:
    """Test batch canvas save"""
    
    @pytest.fixture
    def test_workflow_for_canvas(self, session):
        """Create a workflow with nodes for canvas test"""
        wf_res = session.post(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/workflows", json={
            "name": "TEST_Canvas_Save",
            "description": "For canvas testing"
        })
        wf_id = wf_res.json()["workflow_id"]
        
        # Create 3 nodes
        nodes = []
        for i, ntype in enumerate(["input", "ai_agent", "output"]):
            res = session.post(f"{BASE_URL}/api/workflows/{wf_id}/nodes", json={
                "type": ntype,
                "label": f"{ntype.title()} Node",
                "position_x": 100 + i * 200,
                "position_y": 100
            })
            nodes.append(res.json())
        
        yield {"workflow_id": wf_id, "nodes": nodes}
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/workflows/{wf_id}")
    
    def test_save_canvas_positions(self, session, test_workflow_for_canvas):
        """PUT /api/workflows/{workflow_id}/canvas - save positions"""
        wf_id = test_workflow_for_canvas["workflow_id"]
        nodes = test_workflow_for_canvas["nodes"]
        
        # Update positions via canvas save
        new_positions = [
            {"node_id": nodes[0]["node_id"], "position_x": 50, "position_y": 50},
            {"node_id": nodes[1]["node_id"], "position_x": 250, "position_y": 150},
            {"node_id": nodes[2]["node_id"], "position_x": 450, "position_y": 250}
        ]
        
        res = session.put(f"{BASE_URL}/api/workflows/{wf_id}/canvas", json={
            "nodes": new_positions,
            "edges": []
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        # Verify positions were saved
        wf_res = session.get(f"{BASE_URL}/api/workflows/{wf_id}")
        saved_nodes = {n["node_id"]: n for n in wf_res.json()["nodes"]}
        
        assert saved_nodes[nodes[0]["node_id"]]["position_x"] == 50
        assert saved_nodes[nodes[0]["node_id"]]["position_y"] == 50
        assert saved_nodes[nodes[1]["node_id"]]["position_x"] == 250
        assert saved_nodes[nodes[1]["node_id"]]["position_y"] == 150
        print("Canvas position save verified")
    
    def test_save_canvas_with_edges(self, session, test_workflow_for_canvas):
        """PUT /api/workflows/{workflow_id}/canvas - sync edges"""
        wf_id = test_workflow_for_canvas["workflow_id"]
        nodes = test_workflow_for_canvas["nodes"]
        
        # Create edges via canvas save
        edges = [
            {"source_node_id": nodes[0]["node_id"], "target_node_id": nodes[1]["node_id"]},
            {"source_node_id": nodes[1]["node_id"], "target_node_id": nodes[2]["node_id"]}
        ]
        
        res = session.put(f"{BASE_URL}/api/workflows/{wf_id}/canvas", json={
            "nodes": [{"node_id": n["node_id"], "position_x": n["position_x"], "position_y": n["position_y"]} for n in nodes],
            "edges": edges
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        # Verify edges were created
        wf_res = session.get(f"{BASE_URL}/api/workflows/{wf_id}")
        saved_edges = wf_res.json()["edges"]
        assert len(saved_edges) == 2, f"Expected 2 edges, got {len(saved_edges)}"
        print("Canvas edge save verified")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_workflows(self, session):
        """Delete all TEST_ prefixed workflows"""
        res = session.get(f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/workflows")
        workflows = res.json()
        
        deleted = 0
        for wf in workflows:
            if wf["name"].startswith("TEST_"):
                session.delete(f"{BASE_URL}/api/workflows/{wf['workflow_id']}")
                deleted += 1
        
        print(f"Cleaned up {deleted} test workflows")
