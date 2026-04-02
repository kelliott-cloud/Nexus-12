"""test_channels_messages.py — Channel and message flow regression tests."""
import requests
import pytest
import uuid


class TestChannelCRUD:
    """Test channel operations within workspaces."""

    @pytest.fixture(scope="class")
    def workspace_id(self, api_url, auth_headers):
        name = f"CI Channel WS {uuid.uuid4().hex[:6]}"
        resp = requests.post(f"{api_url}/api/workspaces", headers=auth_headers, json={"name": name})
        return resp.json().get("workspace_id")

    def test_create_channel(self, api_url, auth_headers, workspace_id):
        resp = requests.post(f"{api_url}/api/workspaces/{workspace_id}/channels", headers=auth_headers, json={
            "name": f"ci-channel-{uuid.uuid4().hex[:6]}", "ai_agents": ["claude"]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "channel_id" in data
        assert data.get("name").startswith("ci-channel-")

    def test_list_channels(self, api_url, auth_headers, workspace_id):
        resp = requests.get(f"{api_url}/api/workspaces/{workspace_id}/channels", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_channel_status(self, api_url, auth_headers, workspace_id):
        channels = requests.get(f"{api_url}/api/workspaces/{workspace_id}/channels", headers=auth_headers).json()
        if not channels:
            pytest.skip("No channels")
        ch_id = channels[0]["channel_id"]
        resp = requests.get(f"{api_url}/api/channels/{ch_id}/status", headers=auth_headers)
        assert resp.status_code == 200


class TestMessages:
    """Test message send and retrieve."""

    @pytest.fixture(scope="class")
    def channel_setup(self, api_url, auth_headers):
        name = f"CI Msg WS {uuid.uuid4().hex[:6]}"
        ws = requests.post(f"{api_url}/api/workspaces", headers=auth_headers, json={"name": name}).json()
        ws_id = ws["workspace_id"]
        ch = requests.post(f"{api_url}/api/workspaces/{ws_id}/channels", headers=auth_headers, json={
            "name": f"ci-msg-{uuid.uuid4().hex[:6]}", "ai_agents": []
        }).json()
        return {"workspace_id": ws_id, "channel_id": ch["channel_id"]}

    def test_send_message(self, api_url, auth_headers, channel_setup):
        ch_id = channel_setup["channel_id"]
        resp = requests.post(f"{api_url}/api/channels/{ch_id}/messages", headers=auth_headers, json={
            "content": "CI test message"
        })
        assert resp.status_code == 200

    def test_get_messages(self, api_url, auth_headers, channel_setup):
        ch_id = channel_setup["channel_id"]
        resp = requests.get(f"{api_url}/api/channels/{ch_id}/messages", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_download_transcript(self, api_url, auth_headers, channel_setup):
        ch_id = channel_setup["channel_id"]
        resp = requests.get(f"{api_url}/api/channels/{ch_id}/transcript", headers=auth_headers)
        assert resp.status_code == 200
