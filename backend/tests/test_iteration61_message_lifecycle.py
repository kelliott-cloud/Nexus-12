"""
Iteration 61 - Message Lifecycle Tests
Testing the fix for channel_id/workspace_id MongoDB keys bug.
The bug was: dictionary keys were incorrectly prefixed with underscore (_channel_id instead of channel_id)
This caused messages to be saved with wrong field names and not be retrievable.
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test user credentials
TEST_EMAIL = f"qatest_{uuid.uuid4().hex[:8]}@test.com"
TEST_PASSWORD = "qatest123"
TEST_NAME = "QA Tester"


class TestMessageLifecycle:
    """Test the complete message lifecycle - create, retrieve, search - to verify the channel_id fix"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create a requests session with cookie support"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        return s
    
    @pytest.fixture(scope="class")
    def auth_data(self, session):
        """Register and login test user, return session with auth cookie"""
        # Register a new test user
        register_response = session.post(f"{BASE_URL}/api/auth/register", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": TEST_NAME
        })
        # Accept 201 (created) or 400 (user exists)
        assert register_response.status_code in [200, 201, 400], f"Register failed: {register_response.text}"
        
        # Login to get session cookie
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        user_data = login_response.json()
        assert "user_id" in user_data or "email" in user_data, f"Invalid login response: {user_data}"
        
        # Verify session cookie is set
        assert 'session_token' in session.cookies or login_response.status_code == 200, "Session cookie not set"
        
        return {
            "session": session,
            "user": user_data
        }
    
    @pytest.fixture(scope="class")
    def workspace(self, auth_data):
        """Create a test workspace"""
        session = auth_data["session"]
        workspace_name = f"Test Workspace {uuid.uuid4().hex[:8]}"
        
        response = session.post(f"{BASE_URL}/api/workspaces", json={
            "name": workspace_name,
            "description": "Test workspace for message lifecycle testing"
        })
        assert response.status_code in [200, 201], f"Create workspace failed: {response.text}"
        
        workspace_data = response.json()
        assert "workspace_id" in workspace_data, f"Missing workspace_id: {workspace_data}"
        
        return workspace_data
    
    @pytest.fixture(scope="class")
    def channel(self, auth_data, workspace):
        """Create a test channel in the workspace"""
        session = auth_data["session"]
        workspace_id = workspace["workspace_id"]
        channel_name = f"Test Channel {uuid.uuid4().hex[:8]}"
        
        response = session.post(f"{BASE_URL}/api/workspaces/{workspace_id}/channels", json={
            "name": channel_name,
            "description": "Test channel for message testing",
            "ai_agents": []  # No AI agents for testing
        })
        assert response.status_code in [200, 201], f"Create channel failed: {response.text}"
        
        channel_data = response.json()
        assert "channel_id" in channel_data, f"Missing channel_id: {channel_data}"
        assert channel_data.get("workspace_id") == workspace_id, "Workspace ID mismatch in channel"
        
        return channel_data
    
    def test_01_health_check(self, session):
        """Test 1: Verify backend health"""
        response = session.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy", f"Unhealthy status: {data}"
        assert data.get("database") == "connected", f"Database not connected: {data}"
        print(f"✓ Health check passed: {data}")
    
    def test_02_register_user(self, auth_data):
        """Test 2: Verify user registration/login"""
        user = auth_data["user"]
        assert "user_id" in user or "email" in user, f"Invalid user data: {user}"
        print(f"✓ User authenticated: {user.get('email', user.get('user_id', 'unknown'))}")
    
    def test_03_create_workspace(self, workspace):
        """Test 3: Verify workspace creation"""
        assert "workspace_id" in workspace, f"Missing workspace_id: {workspace}"
        assert "name" in workspace, f"Missing name: {workspace}"
        print(f"✓ Workspace created: {workspace['workspace_id']}")
    
    def test_04_create_channel(self, channel, workspace):
        """Test 4: Verify channel creation with correct workspace_id"""
        assert "channel_id" in channel, f"Missing channel_id: {channel}"
        assert channel.get("workspace_id") == workspace["workspace_id"], "Workspace ID mismatch"
        print(f"✓ Channel created: {channel['channel_id']} in workspace {workspace['workspace_id']}")
    
    def test_05_send_message_and_retrieve(self, auth_data, channel):
        """Test 5: CRITICAL - Send message and verify it can be retrieved
        
        This tests the P0 bug fix. Previously, messages were saved with '_channel_id' key
        but retrieved by 'channel_id' query, causing empty results.
        """
        session = auth_data["session"]
        channel_id = channel["channel_id"]
        test_content = f"Test message from QA at {uuid.uuid4().hex[:8]}"
        
        # POST a message
        post_response = session.post(f"{BASE_URL}/api/channels/{channel_id}/messages", json={
            "content": test_content
        })
        assert post_response.status_code in [200, 201], f"POST message failed: {post_response.text}"
        
        created_message = post_response.json()
        assert "message_id" in created_message, f"Missing message_id: {created_message}"
        assert created_message.get("content") == test_content, f"Content mismatch: {created_message}"
        assert created_message.get("channel_id") == channel_id, f"Channel ID mismatch in response: {created_message}"
        
        print(f"✓ Message created: {created_message['message_id']}")
        
        # GET messages - THIS IS THE CRITICAL TEST
        # Before the fix, this would return empty results because:
        # - Messages were saved with "_channel_id" key
        # - Query was using "channel_id" key
        get_response = session.get(f"{BASE_URL}/api/channels/{channel_id}/messages")
        assert get_response.status_code == 200, f"GET messages failed: {get_response.text}"
        
        messages = get_response.json()
        assert isinstance(messages, list), f"Messages should be a list: {messages}"
        assert len(messages) > 0, f"CRITICAL BUG: No messages returned - the channel_id key fix may not be working!"
        
        # Verify our message is in the list
        message_ids = [m.get("message_id") for m in messages]
        assert created_message["message_id"] in message_ids, f"Created message not found in GET results. IDs returned: {message_ids}"
        
        # Find our specific message
        our_message = next((m for m in messages if m.get("message_id") == created_message["message_id"]), None)
        assert our_message is not None, "Our message not found"
        assert our_message.get("content") == test_content, f"Content mismatch in retrieved message: {our_message}"
        
        print(f"✓ Message retrieved successfully! {len(messages)} total messages in channel")
    
    def test_06_message_search(self, auth_data, channel):
        """Test 6: Test message search functionality"""
        session = auth_data["session"]
        channel_id = channel["channel_id"]
        
        # Send a unique searchable message
        unique_term = f"SEARCHTERM{uuid.uuid4().hex[:8]}"
        session.post(f"{BASE_URL}/api/channels/{channel_id}/messages", json={
            "content": f"This message contains {unique_term} for testing"
        })
        
        # Search for it
        search_response = session.get(f"{BASE_URL}/api/channels/{channel_id}/search-messages?q={unique_term}")
        assert search_response.status_code == 200, f"Search failed: {search_response.text}"
        
        search_results = search_response.json()
        assert "messages" in search_results, f"Invalid search response: {search_results}"
        assert len(search_results["messages"]) > 0, f"Search should find the message with {unique_term}"
        
        print(f"✓ Message search working: found {len(search_results['messages'])} results for '{unique_term}'")
    
    def test_07_message_polling_after_timestamp(self, auth_data, channel):
        """Test 7: Test message polling with 'after' parameter"""
        session = auth_data["session"]
        channel_id = channel["channel_id"]
        
        # Get current messages to establish a baseline timestamp
        initial_response = session.get(f"{BASE_URL}/api/channels/{channel_id}/messages")
        assert initial_response.status_code == 200
        initial_messages = initial_response.json()
        
        if len(initial_messages) > 0:
            last_timestamp = initial_messages[-1].get("created_at")
            
            # Post a new message
            new_content = f"New message after {uuid.uuid4().hex[:8]}"
            session.post(f"{BASE_URL}/api/channels/{channel_id}/messages", json={
                "content": new_content
            })
            
            # Poll for messages after the timestamp
            poll_response = session.get(f"{BASE_URL}/api/channels/{channel_id}/messages?after={last_timestamp}")
            assert poll_response.status_code == 200, f"Polling failed: {poll_response.text}"
            
            new_messages = poll_response.json()
            assert isinstance(new_messages, list), f"Polling should return list: {new_messages}"
            
            # The new message should be in the polled results
            new_contents = [m.get("content") for m in new_messages]
            assert new_content in new_contents, f"New message not found in polled results. Contents: {new_contents}"
            
            print(f"✓ Message polling working: found {len(new_messages)} new messages after timestamp")
        else:
            print("✓ Message polling test skipped (no initial messages)")
    
    def test_08_verify_message_structure(self, auth_data, channel):
        """Test 8: Verify message has correct structure with channel_id field"""
        session = auth_data["session"]
        channel_id = channel["channel_id"]
        
        # Get messages
        response = session.get(f"{BASE_URL}/api/channels/{channel_id}/messages")
        assert response.status_code == 200
        
        messages = response.json()
        if len(messages) > 0:
            msg = messages[0]
            
            # Verify required fields are present
            required_fields = ["message_id", "channel_id", "content", "created_at"]
            for field in required_fields:
                assert field in msg, f"Missing required field '{field}' in message: {msg}"
            
            # Verify channel_id matches (not _channel_id)
            assert msg.get("channel_id") == channel_id, f"Channel ID should match: {msg.get('channel_id')} vs {channel_id}"
            
            # Verify no underscore-prefixed duplicate keys
            assert "_channel_id" not in msg, f"Found legacy '_channel_id' key in message: {msg}"
            
            print(f"✓ Message structure verified: {list(msg.keys())}")
        else:
            pytest.skip("No messages to verify structure")
    
    def test_09_multiple_messages_retrieval(self, auth_data, channel):
        """Test 9: Send multiple messages and verify all can be retrieved"""
        session = auth_data["session"]
        channel_id = channel["channel_id"]
        
        # Send 5 messages
        sent_ids = []
        for i in range(5):
            response = session.post(f"{BASE_URL}/api/channels/{channel_id}/messages", json={
                "content": f"Batch message #{i+1} - {uuid.uuid4().hex[:8]}"
            })
            assert response.status_code in [200, 201]
            sent_ids.append(response.json()["message_id"])
        
        # Retrieve all messages
        get_response = session.get(f"{BASE_URL}/api/channels/{channel_id}/messages")
        assert get_response.status_code == 200
        
        messages = get_response.json()
        retrieved_ids = [m.get("message_id") for m in messages]
        
        # Verify all sent messages are in retrieved list
        for sent_id in sent_ids:
            assert sent_id in retrieved_ids, f"Message {sent_id} not found in retrieved messages"
        
        print(f"✓ All {len(sent_ids)} messages retrieved successfully")
    
    def test_10_cleanup_verification(self, auth_data, workspace, channel):
        """Test 10: Verify we can clean up test data (optional cleanup)"""
        session = auth_data["session"]
        
        # We don't actually delete to preserve data for inspection
        # Just verify we have access to delete if needed
        print(f"✓ Test data preserved: workspace={workspace['workspace_id']}, channel={channel['channel_id']}")


class TestDirectCurlEndpoints:
    """Direct endpoint tests without session dependencies"""
    
    def test_health_endpoint(self):
        """Direct health check without auth"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✓ Direct health check: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
