"""test_workspaces.py — Workspace CRUD regression tests."""
import requests
import pytest
import uuid


class TestWorkspaceCRUD:
    """Test workspace create, read, update, delete."""

    def test_list_workspaces(self, api_url, auth_headers):
        resp = requests.get(f"{api_url}/api/workspaces", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_create_workspace(self, api_url, auth_headers):
        name = f"CI Test WS {uuid.uuid4().hex[:6]}"
        resp = requests.post(f"{api_url}/api/workspaces", headers=auth_headers, json={
            "name": name, "description": "CI test workspace"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("name") == name
        assert "workspace_id" in data

    def test_get_workspace(self, api_url, auth_headers):
        # Create then get
        name = f"CI Get WS {uuid.uuid4().hex[:6]}"
        create = requests.post(f"{api_url}/api/workspaces", headers=auth_headers, json={"name": name})
        ws_id = create.json().get("workspace_id")
        resp = requests.get(f"{api_url}/api/workspaces/{ws_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json().get("name") == name

    def test_update_workspace(self, api_url, auth_headers):
        name = f"CI Update WS {uuid.uuid4().hex[:6]}"
        create = requests.post(f"{api_url}/api/workspaces", headers=auth_headers, json={"name": name})
        ws_id = create.json().get("workspace_id")
        resp = requests.put(f"{api_url}/api/workspaces/{ws_id}", headers=auth_headers, json={
            "name": f"{name} Updated", "description": "Updated desc"
        })
        assert resp.status_code == 200

    def test_get_nonexistent_workspace(self, api_url, auth_headers):
        resp = requests.get(f"{api_url}/api/workspaces/ws_nonexistent999", headers=auth_headers)
        assert resp.status_code in (403, 404)


class TestWorkspaceMembers:
    """Test workspace member operations."""

    def test_list_members(self, api_url, auth_headers):
        # Get first workspace
        ws_list = requests.get(f"{api_url}/api/workspaces", headers=auth_headers).json()
        if not ws_list:
            pytest.skip("No workspaces available")
        ws_id = ws_list[0]["workspace_id"]
        resp = requests.get(f"{api_url}/api/workspaces/{ws_id}/members", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "members" in data or isinstance(data, list)
