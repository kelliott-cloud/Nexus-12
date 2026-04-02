import requests
import sys
import os
import json
from datetime import datetime
import subprocess

class NexusAPITester:
    def __init__(self):
        # Get frontend URL from .env
        self.base_url = "https://ai-chat-recovery.preview.emergentagent.com"
        self.api_url = f"{self.base_url}/api"
        self.session_token = None
        self.user_id = None
        self.workspace_id = None
        self.channel_id = None
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        if self.session_token:
            test_headers['Authorization'] = f'Bearer {self.session_token}'
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    resp_data = response.json()
                    print(f"   Response: {json.dumps(resp_data, indent=2)[:200]}...")
                    return True, resp_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def create_test_user_session(self):
        """Create test user and session in MongoDB"""
        print("\n📝 Creating test user and session in MongoDB...")
        
        timestamp = int(datetime.now().timestamp())
        user_id = f"test-user-{timestamp}"
        session_token = f"test_session_{timestamp}"
        
        mongo_command = f"""
        use('test_database');
        var userId = '{user_id}';
        var sessionToken = '{session_token}';
        db.users.insertOne({{
          user_id: userId,
          email: 'test.user.{timestamp}@example.com',
          name: 'Test User {timestamp}',
          picture: 'https://via.placeholder.com/150',
          created_at: new Date().toISOString()
        }});
        db.user_sessions.insertOne({{
          user_id: userId,
          session_token: sessionToken,
          expires_at: new Date(Date.now() + 7*24*60*60*1000).toISOString(),
          created_at: new Date().toISOString()
        }});
        print('Created user: ' + userId);
        print('Session token: ' + sessionToken);
        """
        
        try:
            result = subprocess.run(
                ["mongosh", "--eval", mongo_command], 
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                self.user_id = user_id
                self.session_token = session_token
                print(f"✅ Created test user: {user_id}")
                print(f"✅ Session token: {session_token}")
                return True
            else:
                print(f"❌ MongoDB command failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Error creating test user: {e}")
            return False

    def test_health(self):
        """Test health endpoint"""
        return self.run_test("Health Check", "GET", "/health", 200)

    def test_ai_models(self):
        """Test AI models endpoint"""
        return self.run_test("AI Models", "GET", "/ai-models", 200)

    def test_auth_me_without_token(self):
        """Test auth/me without token (should fail)"""
        temp_token = self.session_token
        self.session_token = None
        success, data = self.run_test("Auth Me (No Token)", "GET", "/auth/me", 401)
        self.session_token = temp_token
        return success, data

    def test_auth_me(self):
        """Test auth/me with valid token"""
        return self.run_test("Auth Me", "GET", "/auth/me", 200)

    def test_workspaces_get(self):
        """Test get workspaces"""
        return self.run_test("Get Workspaces", "GET", "/workspaces", 200)

    def test_workspace_create(self):
        """Test create workspace"""
        data = {
            "name": f"Test Workspace {datetime.now().strftime('%H%M%S')}",
            "description": "Test workspace for API testing"
        }
        success, resp_data = self.run_test("Create Workspace", "POST", "/workspaces", 200, data)
        if success and resp_data.get('workspace_id'):
            self.workspace_id = resp_data['workspace_id']
            print(f"   Saved workspace_id: {self.workspace_id}")
        return success, resp_data

    def test_workspace_get(self):
        """Test get specific workspace"""
        if not self.workspace_id:
            print("❌ No workspace_id available for testing")
            return False, {}
        return self.run_test("Get Workspace", "GET", f"/workspaces/{self.workspace_id}", 200)

    def test_channels_get(self):
        """Test get channels for workspace"""
        if not self.workspace_id:
            print("❌ No workspace_id available for testing")
            return False, {}
        return self.run_test("Get Channels", "GET", f"/workspaces/{self.workspace_id}/channels", 200)

    def test_channel_create(self):
        """Test create channel"""
        if not self.workspace_id:
            print("❌ No workspace_id available for testing")
            return False, {}
        
        data = {
            "name": f"test-channel-{datetime.now().strftime('%H%M%S')}",
            "description": "Test channel for API testing",
            "ai_agents": ["claude", "chatgpt", "deepseek", "grok"]
        }
        success, resp_data = self.run_test("Create Channel", "POST", f"/workspaces/{self.workspace_id}/channels", 200, data)
        if success and resp_data.get('channel_id'):
            self.channel_id = resp_data['channel_id']
            print(f"   Saved channel_id: {self.channel_id}")
        return success, resp_data

    def test_channel_get(self):
        """Test get specific channel"""
        if not self.channel_id:
            print("❌ No channel_id available for testing")
            return False, {}
        return self.run_test("Get Channel", "GET", f"/channels/{self.channel_id}", 200)

    def test_messages_get_empty(self):
        """Test get messages from empty channel"""
        if not self.channel_id:
            print("❌ No channel_id available for testing")
            return False, {}
        return self.run_test("Get Messages (Empty)", "GET", f"/channels/{self.channel_id}/messages", 200)

    def test_message_create(self):
        """Test create message"""
        if not self.channel_id:
            print("❌ No channel_id available for testing")
            return False, {}
        
        data = {
            "content": "Hello AI agents! Let's collaborate on building a simple Python function to calculate fibonacci numbers."
        }
        return self.run_test("Create Message", "POST", f"/channels/{self.channel_id}/messages", 200, data)

    def test_messages_get_with_content(self):
        """Test get messages after creating one"""
        if not self.channel_id:
            print("❌ No channel_id available for testing")
            return False, {}
        return self.run_test("Get Messages (With Content)", "GET", f"/channels/{self.channel_id}/messages", 200)

    def test_collaboration_status(self):
        """Test collaboration status"""
        if not self.channel_id:
            print("❌ No channel_id available for testing")
            return False, {}
        return self.run_test("Collaboration Status", "GET", f"/channels/{self.channel_id}/status", 200)

    def test_trigger_collaboration(self):
        """Test trigger AI collaboration"""
        if not self.channel_id:
            print("❌ No channel_id available for testing")
            return False, {}
        return self.run_test("Trigger Collaboration", "POST", f"/channels/{self.channel_id}/collaborate", 200)

    def test_analytics_endpoint(self):
        """Test analytics endpoint with current workspace"""
        # Test with current workspace first (should have no data but valid response)
        if self.workspace_id:
            success, data = self.run_test("Analytics (New Workspace)", "GET", f"/workspaces/{self.workspace_id}/analytics", 200)
            if success:
                # Should have empty but valid structure
                required_keys = ['overview', 'model_comparison', 'timeline', 'collaboration_patterns']
                for key in required_keys:
                    if key not in data:
                        print(f"❌ Missing key in analytics response: {key}")
                        return False, data
                print(f"✅ New workspace analytics structure valid")
                return True, data
        
        return False, {}

    def test_analytics_models_endpoint(self):
        """Test analytics models detail endpoint"""
        # Test with current workspace
        if self.workspace_id:
            success, data = self.run_test("Analytics Models Detail", "GET", f"/workspaces/{self.workspace_id}/analytics/models", 200)
            if success:
                print(f"✅ Analytics models endpoint working, found {len(data)} records")
                return True, data
        
        return False, {}

    def test_analytics_models_with_filter(self):
        """Test analytics models with agent filter"""
        # Test with existing workspace that has data
        existing_workspace = "ws_23a3470c803d"
        success, data = self.run_test("Analytics Models (Claude Filter)", "GET", f"/workspaces/{existing_workspace}/analytics/models?agent=claude", 200)
        
        if success and data:
            # All records should be for claude
            for record in data:
                if record.get('agent') != 'claude':
                    print(f"❌ Found non-claude record in filtered results: {record.get('agent')}")
                    return False, data
            print(f"✅ Filtered results: {len(data)} claude records")
        
        return success, data

    def test_analytics_existing_data(self):
        """Test analytics with existing data (with longer timeout)"""
        existing_workspace = "ws_23a3470c803d"
        
        # Use longer timeout for this test
        url = f"{self.api_url}/workspaces/{existing_workspace}/analytics"
        test_headers = {'Content-Type': 'application/json'}
        if self.session_token:
            test_headers['Authorization'] = f'Bearer {self.session_token}'

        print(f"\n🔍 Testing Analytics (Existing Data with longer timeout)...")
        print(f"   URL: {url}")
        
        try:
            response = requests.get(url, headers=test_headers, timeout=30)  # Longer timeout
            success = response.status_code == 200
            if success:
                data = response.json()
                required_keys = ['overview', 'model_comparison', 'timeline', 'collaboration_patterns']
                for key in required_keys:
                    if key not in data:
                        print(f"❌ Missing key in analytics response: {key}")
                        return False, data
                
                print(f"✅ Analytics has {len(data.get('model_comparison', []))} models")
                print(f"✅ Overview shows {data.get('overview', {}).get('total_ai_responses', 0)} total responses")
                return True, data
            else:
                print(f"❌ Failed - Status: {response.status_code}")
                return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_tasks_endpoints(self):
        """Test tasks endpoints"""
        if not self.workspace_id:
            print("❌ No workspace_id available for testing tasks")
            return False, {}
        
        # Get existing tasks
        success, data = self.run_test("Get Tasks", "GET", f"/workspaces/{self.workspace_id}/tasks", 200)
        if not success:
            return False, {}
        
        # Create a new task
        task_data = {
            "title": f"Test Task {datetime.now().strftime('%H%M%S')}",
            "description": "Test task for drag and drop",
            "assigned_to": "claude",
            "assigned_type": "ai"
        }
        success, resp_data = self.run_test("Create Task", "POST", f"/workspaces/{self.workspace_id}/tasks", 200, task_data)
        
        if success and resp_data.get('task_id'):
            task_id = resp_data['task_id']
            print(f"   Created task_id: {task_id}")
            
            # Test update task status (simulating drag-drop)
            update_data = {"status": "in_progress"}
            success2, _ = self.run_test("Update Task Status", "PUT", f"/tasks/{task_id}", 200, update_data)
            
            # Test delete task
            success3, _ = self.run_test("Delete Task", "DELETE", f"/tasks/{task_id}", 200)
            
            return success and success2 and success3, resp_data
        
        return success, resp_data

    def test_logout(self):
        """Test logout"""
        return self.run_test("Logout", "POST", "/auth/logout", 200)

    def run_all_tests(self):
        """Run all API tests in sequence"""
        print("🚀 Starting Nexus API Testing...")
        print(f"   Base URL: {self.base_url}")
        print(f"   API URL: {self.api_url}")
        
        # Create test user first
        if not self.create_test_user_session():
            print("❌ Failed to create test user, aborting tests")
            return 1

        # Test basic endpoints
        self.test_health()
        self.test_ai_models()
        
        # Test auth
        self.test_auth_me_without_token()
        self.test_auth_me()
        
        # Test workspaces
        self.test_workspaces_get()
        self.test_workspace_create()
        self.test_workspace_get()
        
        # Test channels
        self.test_channels_get()
        self.test_channel_create() 
        self.test_channel_get()
        
        # Test messages
        self.test_messages_get_empty()
        self.test_message_create()
        self.test_messages_get_with_content()
        
        # Test AI collaboration
        self.test_collaboration_status()
        self.test_trigger_collaboration()
        
        # Test analytics endpoints (Phase 3)
        print("\n🔬 Testing Analytics Endpoints...")
        self.test_analytics_endpoint()
        self.test_analytics_models_endpoint()
        self.test_analytics_models_with_filter()
        self.test_analytics_existing_data()  # Test with longer timeout
        
        # Test tasks endpoints (Phase 3)
        print("\n📋 Testing Tasks Endpoints...")
        self.test_tasks_endpoints()
        
        # Test logout
        self.test_logout()

        # Print summary
        print(f"\n📊 Test Results: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            failed = self.tests_run - self.tests_passed
            print(f"❌ {failed} tests failed")
            return 1

def main():
    tester = NexusAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())