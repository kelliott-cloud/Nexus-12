#!/usr/bin/env python3
"""
Nexus Phase 2 API Testing
Tests new authentication, billing, tasks, reports, and sharing features
"""

import requests
import sys
import uuid
import json
from datetime import datetime

class NexusPhase2Tester:
    def __init__(self):
        self.base_url = "https://ai-chat-recovery.preview.emergentagent.com"
        self.api_url = f"{self.base_url}/api"
        self.session = requests.Session()  # Use session to maintain cookies
        self.user_data = None
        self.workspace_id = None
        self.channel_id = None
        self.reset_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def log_test(self, name, success, details=None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name}")
            if details:
                print(f"   {details}")
            self.failed_tests.append({"name": name, "details": details})

    def make_request(self, method, endpoint, data=None, expected_status=200, headers=None):
        """Make HTTP request and return response"""
        url = f"{self.api_url}{endpoint}"
        req_headers = {'Content-Type': 'application/json'}
        
        if headers:
            req_headers.update(headers)

        try:
            if method == 'GET':
                resp = self.session.get(url, headers=req_headers, timeout=15)
            elif method == 'POST':
                resp = self.session.post(url, json=data, headers=req_headers, timeout=15)
            elif method == 'PUT':
                resp = self.session.put(url, json=data, headers=req_headers, timeout=15)
            elif method == 'DELETE':
                resp = self.session.delete(url, headers=req_headers, timeout=15)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = resp.status_code == expected_status
            try:
                response_data = resp.json()
            except:
                response_data = {"text": resp.text}

            return success, resp.status_code, response_data, resp

        except Exception as e:
            return False, 0, {"error": str(e)}, None

    def test_email_registration(self):
        """Test email/password registration"""
        print(f"\n🧪 Testing Email Registration...")
        
        # Generate unique test user
        test_id = uuid.uuid4().hex[:8]
        test_email = f"test_{test_id}@example.com"
        test_name = f"Test User {test_id}"
        test_password = "TestPass123!"
        
        self.user_data = {
            "email": test_email,
            "password": test_password,
            "name": test_name
        }
        
        success, status, data, resp = self.make_request(
            'POST', '/auth/register',
            data={
                "email": test_email,
                "password": test_password,
                "name": test_name
            }
        )
        
        if success:
            # Extract session token from cookies if available
            if resp and 'set-cookie' in resp.headers:
                print(f"   Session cookie set successfully")
            self.log_test("Email Registration", True, f"User created: {test_email}")
        else:
            self.log_test("Email Registration", False, f"Status {status}: {data}")
        
        return success

    def test_email_login(self):
        """Test email/password login"""
        print(f"\n🧪 Testing Email Login...")
        
        if not self.user_data:
            self.log_test("Email Login", False, "No user data available")
            return False
            
        success, status, data, resp = self.make_request(
            'POST', '/auth/login',
            data={
                "email": self.user_data["email"],
                "password": self.user_data["password"]
            }
        )
        
        if success:
            # For API testing with session cookies, we need to handle auth differently
            # The session token is httpOnly so we can't extract it directly
            self.log_test("Email Login", True, "Login successful")
        else:
            self.log_test("Email Login", False, f"Status {status}: {data}")
        
        return success

    def test_forgot_password(self):
        """Test forgot password flow"""
        print(f"\n🧪 Testing Forgot Password...")
        
        if not self.user_data:
            self.log_test("Forgot Password", False, "No user data available")
            return False
            
        success, status, data, _ = self.make_request(
            'POST', '/auth/forgot-password',
            data={"email": self.user_data["email"]}
        )
        
        if success and "reset_token" in data:
            self.reset_token = data["reset_token"]
            self.log_test("Forgot Password", True, f"Reset token received: {self.reset_token[:10]}...")
        else:
            self.log_test("Forgot Password", False, f"Status {status}: {data}")
        
        return success

    def test_reset_password(self):
        """Test password reset"""
        print(f"\n🧪 Testing Password Reset...")
        
        if not self.reset_token:
            self.log_test("Password Reset", False, "No reset token available")
            return False
            
        new_password = "NewTestPass456!"
        success, status, data, _ = self.make_request(
            'POST', '/auth/reset-password',
            data={
                "token": self.reset_token,
                "new_password": new_password
            }
        )
        
        if success:
            self.user_data["password"] = new_password
            self.log_test("Password Reset", True, "Password reset successfully")
        else:
            self.log_test("Password Reset", False, f"Status {status}: {data}")
        
        return success

    def test_oauth_stubs(self):
        """Test OAuth stub endpoints (should return 501)"""
        print(f"\n🧪 Testing OAuth Stubs...")
        
        oauth_tests = [
            ("Microsoft OAuth", "/auth/microsoft"),
            ("Meta OAuth", "/auth/meta")
        ]
        
        for name, endpoint in oauth_tests:
            success, status, data, _ = self.make_request('POST', endpoint, expected_status=501)
            if success:
                self.log_test(f"{name} Stub", True, f"Correctly returns 501: {data.get('detail', 'N/A')}")
            else:
                self.log_test(f"{name} Stub", False, f"Expected 501, got {status}")

    def test_billing_plans(self):
        """Test billing plans endpoint"""
        print(f"\n🧪 Testing Billing Plans...")
        
        success, status, data, _ = self.make_request('GET', '/billing/plans')
        
        if success:
            required_plans = ["free", "pro", "enterprise"]
            missing_plans = [p for p in required_plans if p not in data]
            
            if not missing_plans:
                self.log_test("Billing Plans", True, f"All plans found: {list(data.keys())}")
                
                # Validate plan structure
                for plan_id, plan in data.items():
                    required_fields = ["name", "price", "features"]
                    missing_fields = [f for f in required_fields if f not in plan]
                    if missing_fields:
                        self.log_test(f"Plan {plan_id} Structure", False, f"Missing fields: {missing_fields}")
                    else:
                        self.log_test(f"Plan {plan_id} Structure", True)
            else:
                self.log_test("Billing Plans", False, f"Missing plans: {missing_plans}")
        else:
            self.log_test("Billing Plans", False, f"Status {status}: {data}")
        
        return success

    def test_subscription_info(self):
        """Test subscription info (requires auth)"""
        print(f"\n🧪 Testing Subscription Info...")
        
        success, status, data, _ = self.make_request('GET', '/billing/subscription')
        
        if success:
            required_fields = ["plan", "plan_info", "usage"]
            missing_fields = [f for f in required_fields if f not in data]
            
            if not missing_fields:
                self.log_test("Subscription Info", True, f"Plan: {data.get('plan')}")
            else:
                self.log_test("Subscription Info", False, f"Missing fields: {missing_fields}")
        else:
            self.log_test("Subscription Info", False, f"Status {status}: {data}")
        
        return success

    def test_stripe_checkout(self):
        """Test Stripe checkout creation"""
        print(f"\n🧪 Testing Stripe Checkout...")
        
        success, status, data, _ = self.make_request(
            'POST', '/billing/checkout',
            data={
                "plan_id": "pro",
                "origin_url": self.base_url
            }
        )
        
        if success and "url" in data:
            self.log_test("Stripe Checkout", True, f"Checkout URL created: {data['url'][:50]}...")
        else:
            self.log_test("Stripe Checkout", False, f"Status {status}: {data}")
        
        return success

    def test_paypal_stub(self):
        """Test PayPal stub (should return 501)"""
        print(f"\n🧪 Testing PayPal Stub...")
        
        success, status, data, _ = self.make_request('POST', '/billing/paypal', expected_status=501)
        
        if success:
            self.log_test("PayPal Stub", True, f"Correctly returns 501: {data.get('detail', 'N/A')}")
        else:
            self.log_test("PayPal Stub", False, f"Expected 501, got {status}")

    def setup_workspace_and_channel(self):
        """Setup workspace and channel for task/sharing tests"""
        print(f"\n🧪 Setting up Workspace and Channel...")
        
        # Create workspace
        ws_name = f"Test Workspace {uuid.uuid4().hex[:6]}"
        success, status, workspace, _ = self.make_request(
            'POST', '/workspaces',
            data={
                "name": ws_name,
                "description": "Test workspace for Phase 2 features"
            }
        )
        
        if not success:
            self.log_test("Workspace Setup", False, f"Failed to create workspace: {status}")
            return False
            
        self.workspace_id = workspace.get("workspace_id")
        if not self.workspace_id:
            self.log_test("Workspace Setup", False, "No workspace_id in response")
            return False
            
        # Create channel
        success, status, channel, _ = self.make_request(
            'POST', f'/workspaces/{self.workspace_id}/channels',
            data={
                "name": "test-channel",
                "description": "Test channel for Phase 2",
                "ai_agents": ["claude", "chatgpt"]
            }
        )
        
        if success:
            self.channel_id = channel.get("channel_id")
            self.log_test("Workspace & Channel Setup", True, f"WS: {self.workspace_id}, CH: {self.channel_id}")
            return True
        else:
            self.log_test("Channel Setup", False, f"Failed to create channel: {status}")
            return False

    def test_task_operations(self):
        """Test task CRUD operations"""
        print(f"\n🧪 Testing Task Operations...")
        
        if not self.workspace_id:
            self.log_test("Task Operations", False, "No workspace available")
            return False
        
        # Create task
        task_data = {
            "title": "Test Task Phase 2",
            "description": "Testing task management APIs",
            "status": "todo",
            "assigned_to": "claude",
            "assigned_type": "ai",
            "channel_id": self.channel_id or ""
        }
        
        success, status, task, _ = self.make_request(
            'POST', f'/workspaces/{self.workspace_id}/tasks',
            data=task_data
        )
        
        if not success:
            self.log_test("Create Task", False, f"Status {status}")
            return False
            
        task_id = task.get("task_id")
        if not task_id:
            self.log_test("Create Task", False, "No task_id in response")
            return False
            
        self.log_test("Create Task", True, f"Task created: {task_id}")
        
        # Get tasks
        success, status, tasks, _ = self.make_request('GET', f'/workspaces/{self.workspace_id}/tasks')
        if success:
            self.log_test("Get Tasks", True, f"Found {len(tasks)} tasks")
        else:
            self.log_test("Get Tasks", False, f"Status {status}")
        
        # Update task
        success, status, updated_task, _ = self.make_request(
            'PUT', f'/tasks/{task_id}',
            data={"status": "in_progress"}
        )
        if success:
            self.log_test("Update Task", True, f"Status: {updated_task.get('status')}")
        else:
            self.log_test("Update Task", False, f"Status {status}")
        
        # Delete task
        success, status, _, _ = self.make_request('DELETE', f'/tasks/{task_id}')
        if success:
            self.log_test("Delete Task", True)
        else:
            self.log_test("Delete Task", False, f"Status {status}")
        
        return True

    def test_reports(self):
        """Test workspace reports"""
        print(f"\n🧪 Testing Reports...")
        
        if not self.workspace_id:
            self.log_test("Reports", False, "No workspace available")
            return False
        
        success, status, reports, _ = self.make_request('GET', f'/workspaces/{self.workspace_id}/reports')
        
        if success:
            required_keys = ["agent_stats", "task_stats", "total_messages", "channels_count"]
            missing_keys = [k for k in required_keys if k not in reports]
            
            if not missing_keys:
                self.log_test("Reports", True, f"All report sections present")
                
                # Validate task stats structure
                task_stats = reports.get("task_stats", {})
                expected_statuses = ["todo", "in_progress", "done", "total"]
                if all(status in task_stats for status in expected_statuses):
                    self.log_test("Task Stats Structure", True)
                else:
                    self.log_test("Task Stats Structure", False, f"Missing task statuses")
            else:
                self.log_test("Reports", False, f"Missing keys: {missing_keys}")
        else:
            self.log_test("Reports", False, f"Status {status}: {reports}")
        
        return success

    def test_sharing_features(self):
        """Test sharing and replay functionality"""
        print(f"\n🧪 Testing Sharing Features...")
        
        if not self.channel_id:
            self.log_test("Sharing Features", False, "No channel available")
            return False
        
        # Create share
        share_data = {
            "is_public": True,
            "expires_in_days": 7
        }
        
        success, status, share, _ = self.make_request(
            'POST', f'/channels/{self.channel_id}/share',
            data=share_data
        )
        
        if not success:
            self.log_test("Create Share", False, f"Status {status}")
            return False
            
        share_id = share.get("share_id")
        if not share_id:
            self.log_test("Create Share", False, "No share_id in response")
            return False
            
        self.log_test("Create Share", True, f"Share created: {share_id}")
        
        # Get share info
        success, status, share_info, _ = self.make_request('GET', f'/shares/{share_id}')
        if success:
            required_fields = ["share_id", "is_public", "views", "created_at"]
            missing_fields = [f for f in required_fields if f not in share_info]
            if not missing_fields:
                self.log_test("Get Share Info", True)
            else:
                self.log_test("Get Share Info", False, f"Missing fields: {missing_fields}")
        else:
            self.log_test("Get Share Info", False, f"Status {status}")
        
        # Test replay (no auth needed for public shares)
        success, status, replay, _ = self.make_request('POST', f'/replay/{share_id}')
        if success:
            required_keys = ["channel", "workspace", "messages", "share"]
            missing_keys = [k for k in required_keys if k not in replay]
            if not missing_keys:
                self.log_test("Replay Access", True, f"All replay data present")
            else:
                self.log_test("Replay Access", False, f"Missing keys: {missing_keys}")
        else:
            self.log_test("Replay Access", False, f"Status {status}")
        
        # Test private share
        private_share_data = {
            "is_public": False,
            "password": "test123",
            "expires_in_days": 3
        }
        
        success, status, private_share, _ = self.make_request(
            'POST', f'/channels/{self.channel_id}/share',
            data=private_share_data
        )
        
        if success:
            private_share_id = private_share.get("share_id")
            self.log_test("Create Private Share", True, f"Private share: {private_share_id}")
            
            # Test replay with wrong password
            success, status, _, _ = self.make_request(
                'POST', f'/replay/{private_share_id}',
                data={"password": "wrong"},
                expected_status=403
            )
            if success:
                self.log_test("Private Share Security", True, "Correctly rejects wrong password")
            else:
                self.log_test("Private Share Security", False, f"Expected 403, got {status}")
                
            # Test replay with correct password
            success, status, _, _ = self.make_request(
                'POST', f'/replay/{private_share_id}',
                data={"password": "test123"}
            )
            if success:
                self.log_test("Private Share Access", True, "Correct password works")
            else:
                self.log_test("Private Share Access", False, f"Status {status}")
        else:
            self.log_test("Create Private Share", False, f"Status {status}")
        
        return True

    def print_summary(self):
        """Print test summary"""
        print(f"\n{'='*70}")
        print(f"📊 NEXUS PHASE 2 TEST SUMMARY")
        print(f"{'='*70}")
        print(f"Tests run: {self.tests_run}")
        print(f"Tests passed: {self.tests_passed}")
        print(f"Tests failed: {len(self.failed_tests)}")
        
        if self.tests_run > 0:
            success_rate = (self.tests_passed / self.tests_run) * 100
            print(f"Success rate: {success_rate:.1f}%")
        
        if self.failed_tests:
            print(f"\n❌ FAILED TESTS:")
            for i, test in enumerate(self.failed_tests, 1):
                print(f"   {i}. {test['name']}")
                if test['details']:
                    print(f"      {test['details']}")
        else:
            print(f"\n🎉 All Phase 2 tests passed!")
        
        return len(self.failed_tests) == 0

def main():
    """Main test runner"""
    print("🚀 Starting Nexus Phase 2 API Testing")
    print("="*70)
    print("Testing: Auth, Billing, Tasks, Reports, Sharing")
    print()
    
    tester = NexusPhase2Tester()
    
    # Authentication Tests
    print("🔐 AUTHENTICATION TESTS")
    tester.test_email_registration()
    tester.test_email_login()
    tester.test_forgot_password()
    tester.test_reset_password()
    tester.test_oauth_stubs()
    
    # Billing Tests
    print("\n💰 BILLING TESTS")
    tester.test_billing_plans()
    tester.test_subscription_info()
    tester.test_stripe_checkout()
    tester.test_paypal_stub()
    
    # Workspace/Channel Setup for remaining tests
    tester.setup_workspace_and_channel()
    
    # Task Management Tests
    print("\n📋 TASK MANAGEMENT TESTS")
    tester.test_task_operations()
    
    # Reports Tests
    print("\n📊 REPORTS TESTS")
    tester.test_reports()
    
    # Sharing Tests
    print("\n🔗 SHARING TESTS")
    tester.test_sharing_features()
    
    # Print final summary
    success = tester.print_summary()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())