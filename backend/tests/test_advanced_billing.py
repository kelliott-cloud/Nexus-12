"""
Test Suite: Advanced Billing System (routes_billing_advanced.py)
Tests for: Invoices, Statements, Payment History, Org Billing, Cost Allocation, Plan Management, Notifications

Endpoints Tested:
- GET /api/billing/account — billing account with address, plan, credits
- PUT /api/billing/account/address — update billing address + tax ID
- POST /api/billing/invoices/generate — generate monthly invoice
- GET /api/billing/invoices — list invoices
- GET /api/billing/invoices/{id} — invoice detail
- GET /api/billing/invoices/{id}/export?format=csv — export invoice CSV
- GET /api/billing/payments — payment history
- GET /api/billing/usage-summary — 3-month credit usage summary
- POST /api/billing/change-plan — change plan with history
- GET /api/billing/plan-history — plan change history
- GET /api/billing/notifications — billing alerts
- GET /api/orgs/{org}/billing/account — org billing account
- PUT /api/orgs/{org}/billing/address — org billing address
- PUT /api/orgs/{org}/billing/spending-limit — set spending limit
- POST /api/orgs/{org}/billing/contacts — add billing contact
- GET /api/orgs/{org}/billing/cost-allocation — workspace cost breakdown
- GET /api/orgs/{org}/billing/invoices — org invoices
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_EMAIL = "testmention@test.com"
TEST_USER_PASSWORD = "Test1234!"
ORG_ADMIN_EMAIL = "admin@urtech.org"
ORG_ADMIN_PASSWORD = "Test1234!"
TEST_ORG_ID = "org_cba36eb8305f"


class TestAdvancedBillingUserAccount:
    """User billing account tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Create authenticated session for test user"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        # Login
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        return session
    
    def test_get_billing_account(self, auth_session):
        """GET /api/billing/account — returns billing account with address, plan, credits"""
        resp = auth_session.get(f"{BASE_URL}/api/billing/account")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Validate structure
        assert "account" in data, "Missing 'account' field"
        assert "plan" in data, "Missing 'plan' field"
        
        # Validate account fields
        account = data["account"]
        assert "user_id" in account, "Account missing user_id"
        assert "billing_address" in account, "Account missing billing_address"
        
        print(f"✓ Billing account retrieved - plan: {data['plan']}")
    
    def test_update_billing_address(self, auth_session):
        """PUT /api/billing/account/address — updates billing address + tax ID"""
        unique_suffix = uuid.uuid4().hex[:6]
        address_data = {
            "line1": f"TEST_123 Main St {unique_suffix}",
            "line2": "Suite 100",
            "city": "San Francisco",
            "state": "CA",
            "postal_code": "94105",
            "country": "USA",
            "tax_id": f"TAX-{unique_suffix}",
            "company_name": f"TEST_Company_{unique_suffix}"
        }
        
        # Update address
        resp = auth_session.put(f"{BASE_URL}/api/billing/account/address", json=address_data)
        assert resp.status_code == 200, f"Update failed: {resp.text}"
        
        data = resp.json()
        assert "message" in data, "Missing success message"
        
        # Verify update by fetching account
        verify_resp = auth_session.get(f"{BASE_URL}/api/billing/account")
        assert verify_resp.status_code == 200
        account = verify_resp.json()["account"]
        
        assert account.get("billing_address", {}).get("city") == "San Francisco", "Address not persisted"
        print(f"✓ Billing address updated and verified")


class TestInvoices:
    """Invoice management tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert resp.status_code == 200
        return session
    
    def test_list_invoices(self, auth_session):
        """GET /api/billing/invoices — lists invoices"""
        resp = auth_session.get(f"{BASE_URL}/api/billing/invoices")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "invoices" in data, "Missing invoices field"
        assert isinstance(data["invoices"], list), "Invoices should be a list"
        
        print(f"✓ Listed {len(data['invoices'])} invoices")
    
    def test_generate_invoice_different_month(self, auth_session):
        """POST /api/billing/invoices/generate — generates monthly invoice with line items, credits, overage"""
        # Generate invoice for a different month (2026-01 to avoid existing 2026-03)
        test_month = "2026-01"
        resp = auth_session.post(f"{BASE_URL}/api/billing/invoices/generate", json={
            "month": test_month
        })
        assert resp.status_code == 200, f"Generate failed: {resp.text}"
        
        invoice = resp.json()
        
        # Validate invoice structure
        assert "invoice_id" in invoice, "Missing invoice_id"
        assert "period" in invoice, "Missing period"
        assert invoice["period"] == test_month, f"Expected period {test_month}"
        assert "plan" in invoice, "Missing plan"
        assert "credits_allocated" in invoice, "Missing credits_allocated"
        assert "credits_used" in invoice, "Missing credits_used"
        assert "total" in invoice, "Missing total"
        assert "line_items" in invoice, "Missing line_items"
        
        # Store invoice_id for subsequent tests
        TestInvoices.generated_invoice_id = invoice["invoice_id"]
        print(f"✓ Invoice generated: {invoice['invoice_id']} for {test_month}, total: ${invoice['total']}")
        return invoice["invoice_id"]
    
    def test_generate_invoice_idempotent(self, auth_session):
        """Test that invoice generation is idempotent - calling twice returns existing"""
        test_month = "2026-01"
        
        # First call
        resp1 = auth_session.post(f"{BASE_URL}/api/billing/invoices/generate", json={
            "month": test_month
        })
        assert resp1.status_code == 200
        invoice1 = resp1.json()
        
        # Second call for same month
        resp2 = auth_session.post(f"{BASE_URL}/api/billing/invoices/generate", json={
            "month": test_month
        })
        assert resp2.status_code == 200
        invoice2 = resp2.json()
        
        # Should be same invoice
        assert invoice1["invoice_id"] == invoice2["invoice_id"], "Idempotency broken - different invoice IDs"
        print(f"✓ Invoice generation is idempotent")
    
    def test_get_invoice_detail(self, auth_session):
        """GET /api/billing/invoices/{id} — returns full invoice detail"""
        # First ensure we have an invoice
        resp = auth_session.get(f"{BASE_URL}/api/billing/invoices")
        invoices = resp.json().get("invoices", [])
        
        if not invoices:
            # Generate one
            gen_resp = auth_session.post(f"{BASE_URL}/api/billing/invoices/generate", json={"month": "2026-02"})
            assert gen_resp.status_code == 200
            invoice_id = gen_resp.json()["invoice_id"]
        else:
            invoice_id = invoices[0]["invoice_id"]
        
        # Get detail
        resp = auth_session.get(f"{BASE_URL}/api/billing/invoices/{invoice_id}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        invoice = resp.json()
        assert invoice["invoice_id"] == invoice_id
        assert "billing_address" in invoice, "Missing billing_address in detail"
        assert "due_date" in invoice, "Missing due_date"
        
        print(f"✓ Invoice detail retrieved: {invoice_id}")
    
    def test_get_invoice_not_found(self, auth_session):
        """GET /api/billing/invoices/{id} — returns 404 for non-existent invoice"""
        resp = auth_session.get(f"{BASE_URL}/api/billing/invoices/inv_nonexistent123")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("✓ Non-existent invoice returns 404")
    
    def test_export_invoice_csv(self, auth_session):
        """GET /api/billing/invoices/{id}/export?format=csv — exports invoice as CSV"""
        # Get an existing invoice
        resp = auth_session.get(f"{BASE_URL}/api/billing/invoices")
        invoices = resp.json().get("invoices", [])
        
        if not invoices:
            pytest.skip("No invoices to export")
        
        invoice_id = invoices[0]["invoice_id"]
        
        # Export as CSV
        resp = auth_session.get(f"{BASE_URL}/api/billing/invoices/{invoice_id}/export?format=csv")
        assert resp.status_code == 200, f"Export failed: {resp.text}"
        
        data = resp.json()
        assert "content" in data, "Missing CSV content"
        assert "format" in data, "Missing format field"
        assert data["format"] == "csv", f"Expected csv format, got {data['format']}"
        assert "filename" in data, "Missing filename"
        
        # Verify CSV content has expected structure
        csv_content = data["content"]
        assert "Invoice" in csv_content, "CSV missing Invoice header"
        assert "Total" in csv_content, "CSV missing Total"
        
        print(f"✓ Invoice exported as CSV: {data['filename']}")
    
    def test_export_invoice_json(self, auth_session):
        """GET /api/billing/invoices/{id}/export?format=json — exports invoice as JSON"""
        resp = auth_session.get(f"{BASE_URL}/api/billing/invoices")
        invoices = resp.json().get("invoices", [])
        
        if not invoices:
            pytest.skip("No invoices to export")
        
        invoice_id = invoices[0]["invoice_id"]
        
        # Export as JSON (default)
        resp = auth_session.get(f"{BASE_URL}/api/billing/invoices/{invoice_id}/export")
        assert resp.status_code == 200
        
        # Should return full invoice object
        data = resp.json()
        assert "invoice_id" in data, "Export JSON missing invoice_id"
        print("✓ Invoice exported as JSON")


class TestPayments:
    """Payment history tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert resp.status_code == 200
        return session
    
    def test_list_payments(self, auth_session):
        """GET /api/billing/payments — lists payment history"""
        resp = auth_session.get(f"{BASE_URL}/api/billing/payments")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "payments" in data, "Missing payments field"
        assert isinstance(data["payments"], list), "Payments should be a list"
        
        print(f"✓ Listed {len(data['payments'])} payments")


class TestUsageSummary:
    """Usage summary tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert resp.status_code == 200
        return session
    
    def test_get_usage_summary(self, auth_session):
        """GET /api/billing/usage-summary — returns 3-month credit usage summary"""
        resp = auth_session.get(f"{BASE_URL}/api/billing/usage-summary")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "summaries" in data, "Missing summaries field"
        
        summaries = data["summaries"]
        assert isinstance(summaries, list), "Summaries should be a list"
        assert len(summaries) == 3, f"Expected 3 months, got {len(summaries)}"
        
        # Validate summary structure
        for summary in summaries:
            assert "month" in summary, "Missing month"
            assert "allocated" in summary, "Missing allocated"
            assert "used" in summary, "Missing used"
        
        print(f"✓ Usage summary retrieved for {len(summaries)} months")
    
    def test_get_usage_summary_custom_months(self, auth_session):
        """GET /api/billing/usage-summary?months=6 — custom month range"""
        resp = auth_session.get(f"{BASE_URL}/api/billing/usage-summary?months=6")
        assert resp.status_code == 200
        
        data = resp.json()
        summaries = data["summaries"]
        assert len(summaries) == 6, f"Expected 6 months, got {len(summaries)}"
        print(f"✓ Usage summary retrieved for 6 months")


class TestPlanManagement:
    """Plan change and history tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert resp.status_code == 200
        return session
    
    def test_get_plan_history(self, auth_session):
        """GET /api/billing/plan-history — lists plan changes"""
        resp = auth_session.get(f"{BASE_URL}/api/billing/plan-history")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "history" in data, "Missing history field"
        assert isinstance(data["history"], list), "History should be a list"
        
        print(f"✓ Plan history retrieved: {len(data['history'])} changes")
    
    def test_change_plan_invalid(self, auth_session):
        """POST /api/billing/change-plan — invalid plan returns 400"""
        resp = auth_session.post(f"{BASE_URL}/api/billing/change-plan", json={
            "plan": "invalid_plan"
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("✓ Invalid plan change rejected with 400")
    
    def test_change_plan_same_plan(self, auth_session):
        """POST /api/billing/change-plan — changing to same plan returns 400"""
        # First get current plan
        account_resp = auth_session.get(f"{BASE_URL}/api/billing/account")
        current_plan = account_resp.json().get("plan", "pro")  # User is on pro plan
        
        resp = auth_session.post(f"{BASE_URL}/api/billing/change-plan", json={
            "plan": current_plan
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print(f"✓ Same plan change rejected (already on {current_plan})")
    
    def test_change_plan_downgrade(self, auth_session):
        """POST /api/billing/change-plan — downgrade from pro to free"""
        # Get current plan first
        account_resp = auth_session.get(f"{BASE_URL}/api/billing/account")
        current_plan = account_resp.json().get("plan", "pro")
        
        if current_plan == "free":
            # Upgrade to pro first
            resp = auth_session.post(f"{BASE_URL}/api/billing/change-plan", json={"plan": "pro"})
            assert resp.status_code == 200
        
        # Now downgrade to free
        resp = auth_session.post(f"{BASE_URL}/api/billing/change-plan", json={
            "plan": "free"
        })
        assert resp.status_code == 200, f"Downgrade failed: {resp.text}"
        
        data = resp.json()
        assert "change_id" in data, "Missing change_id"
        assert data["new_plan"] == "free", "Plan not changed to free"
        assert data["status"] == "active", "Status should be active"
        
        print(f"✓ Plan changed from {data['old_plan']} to {data['new_plan']}")
        
        # Restore to pro for other tests
        restore_resp = auth_session.post(f"{BASE_URL}/api/billing/change-plan", json={"plan": "pro"})
        assert restore_resp.status_code == 200
        print("✓ Plan restored to pro")


class TestBillingNotifications:
    """Billing notifications tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert resp.status_code == 200
        return session
    
    def test_get_billing_notifications(self, auth_session):
        """GET /api/billing/notifications — returns billing alerts"""
        resp = auth_session.get(f"{BASE_URL}/api/billing/notifications")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "notifications" in data, "Missing notifications field"
        assert isinstance(data["notifications"], list), "Notifications should be a list"
        
        # If there are notifications, validate structure
        for notif in data["notifications"]:
            assert "type" in notif, "Missing notification type"
            assert "title" in notif, "Missing notification title"
            assert "message" in notif, "Missing notification message"
        
        print(f"✓ Billing notifications retrieved: {len(data['notifications'])} alerts")


class TestOrgBilling:
    """Organization billing tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Auth session for org admin"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ORG_ADMIN_EMAIL,
            "password": ORG_ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Org admin login failed: {resp.text}"
        return session
    
    def test_get_org_billing_account(self, auth_session):
        """GET /api/orgs/{org}/billing/account — org billing account with contacts, spending limit"""
        resp = auth_session.get(f"{BASE_URL}/api/orgs/{TEST_ORG_ID}/billing/account")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "org_id" in data, "Missing org_id"
        assert data["org_id"] == TEST_ORG_ID, "Wrong org_id"
        assert "billing_address" in data, "Missing billing_address"
        assert "billing_contacts" in data, "Missing billing_contacts"
        assert "spending_limit_usd" in data, "Missing spending_limit_usd"
        assert "alert_threshold_pct" in data, "Missing alert_threshold_pct"
        
        print(f"✓ Org billing account retrieved for {TEST_ORG_ID}")
    
    def test_update_org_billing_address(self, auth_session):
        """PUT /api/orgs/{org}/billing/address — org billing address"""
        unique_suffix = uuid.uuid4().hex[:6]
        address_data = {
            "line1": f"TEST_456 Corporate Blvd {unique_suffix}",
            "line2": "Floor 20",
            "city": "New York",
            "state": "NY",
            "postal_code": "10001",
            "country": "USA",
            "tax_id": f"ORG-TAX-{unique_suffix}",
            "company_name": f"TEST_OrgCompany_{unique_suffix}"
        }
        
        resp = auth_session.put(f"{BASE_URL}/api/orgs/{TEST_ORG_ID}/billing/address", json=address_data)
        assert resp.status_code == 200, f"Update failed: {resp.text}"
        
        # Verify
        verify_resp = auth_session.get(f"{BASE_URL}/api/orgs/{TEST_ORG_ID}/billing/account")
        assert verify_resp.status_code == 200
        account = verify_resp.json()
        assert account.get("billing_address", {}).get("city") == "New York", "Address not persisted"
        
        print("✓ Org billing address updated and verified")
    
    def test_set_org_spending_limit(self, auth_session):
        """PUT /api/orgs/{org}/billing/spending-limit — set monthly spending limit + alert threshold"""
        limit_data = {
            "monthly_limit_usd": 5000.00,
            "alert_threshold_pct": 75
        }
        
        resp = auth_session.put(f"{BASE_URL}/api/orgs/{TEST_ORG_ID}/billing/spending-limit", json=limit_data)
        assert resp.status_code == 200, f"Set limit failed: {resp.text}"
        
        # Verify
        verify_resp = auth_session.get(f"{BASE_URL}/api/orgs/{TEST_ORG_ID}/billing/account")
        account = verify_resp.json()
        assert account.get("spending_limit_usd") == 5000.00, "Spending limit not persisted"
        assert account.get("alert_threshold_pct") == 75, "Alert threshold not persisted"
        
        print("✓ Org spending limit set: $5000 with 75% alert threshold")
    
    def test_add_billing_contact(self, auth_session):
        """POST /api/orgs/{org}/billing/contacts — add billing contact"""
        unique_suffix = uuid.uuid4().hex[:6]
        contact_data = {
            "email": f"TEST_billing_{unique_suffix}@example.com",
            "name": f"Test Billing Contact {unique_suffix}",
            "role": "finance"
        }
        
        resp = auth_session.post(f"{BASE_URL}/api/orgs/{TEST_ORG_ID}/billing/contacts", json=contact_data)
        assert resp.status_code == 200, f"Add contact failed: {resp.text}"
        
        # Verify contact was added
        verify_resp = auth_session.get(f"{BASE_URL}/api/orgs/{TEST_ORG_ID}/billing/account")
        account = verify_resp.json()
        contacts = account.get("billing_contacts", [])
        
        # Find our added contact
        found = any(c.get("email") == contact_data["email"] for c in contacts)
        assert found, "Billing contact not added"
        
        print(f"✓ Billing contact added: {contact_data['email']}")
    
    def test_get_cost_allocation(self, auth_session):
        """GET /api/orgs/{org}/billing/cost-allocation — per-workspace cost breakdown"""
        resp = auth_session.get(f"{BASE_URL}/api/orgs/{TEST_ORG_ID}/billing/cost-allocation")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "allocations" in data, "Missing allocations field"
        assert "total_credits" in data, "Missing total_credits"
        assert isinstance(data["allocations"], list), "Allocations should be a list"
        
        # Allocations may be empty if no workspaces have analytics data
        for alloc in data["allocations"]:
            assert "workspace_id" in alloc, "Missing workspace_id"
            assert "workspace_name" in alloc, "Missing workspace_name"
            assert "estimated_credits" in alloc, "Missing estimated_credits"
        
        print(f"✓ Cost allocation retrieved: {len(data['allocations'])} workspaces, {data['total_credits']} total credits")
    
    def test_get_org_invoices(self, auth_session):
        """GET /api/orgs/{org}/billing/invoices — org invoices"""
        resp = auth_session.get(f"{BASE_URL}/api/orgs/{TEST_ORG_ID}/billing/invoices")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "invoices" in data, "Missing invoices field"
        assert isinstance(data["invoices"], list), "Invoices should be a list"
        
        print(f"✓ Org invoices retrieved: {len(data['invoices'])} invoices")


class TestAuthRequired:
    """Test that endpoints require authentication"""
    
    def test_billing_account_requires_auth(self):
        """Billing account requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/billing/account")
        assert resp.status_code in [401, 403], f"Expected auth error, got {resp.status_code}"
        print("✓ /billing/account requires authentication")
    
    def test_invoices_requires_auth(self):
        """Invoices list requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/billing/invoices")
        assert resp.status_code in [401, 403], f"Expected auth error, got {resp.status_code}"
        print("✓ /billing/invoices requires authentication")
    
    def test_org_billing_requires_auth(self):
        """Org billing requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/orgs/{TEST_ORG_ID}/billing/account")
        assert resp.status_code in [401, 403], f"Expected auth error, got {resp.status_code}"
        print("✓ /orgs/{org}/billing/account requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
