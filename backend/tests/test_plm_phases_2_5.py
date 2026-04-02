"""
PLM Phases 2-5 Backend Tests
Phase 2: Sprints, Burndown, Dependencies, Milestones, Gantt Data
Phase 3: Programs, Portfolios, Portfolio Health
Phase 4: Time Tracking, Timesheets, Automation Rules, Recurring Tasks
Phase 5: Custom Fields, Custom Values, Field Templates, PLM Config
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPLMPhases2To5:
    """Test all PLM Phase 2-5 endpoints"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Authenticated session"""
        s = requests.Session()
        login_resp = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testmention@test.com",
            "password": "Test1234!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        return s
    
    @pytest.fixture(scope="class")
    def test_data(self):
        """Test data IDs"""
        return {
            "workspace_id": "ws_bd1750012bfd",
            "project_id": "proj_4e216147ec29",
            "task_id": "ptask_d0ae46fddc58",
            "sprint_id": "spr_261dd587a5b4"
        }
    
    # =====================================================
    # PHASE 2 - SPRINTS
    # =====================================================
    
    def test_create_sprint(self, session, test_data):
        """POST /api/projects/{id}/sprints creates sprint with goal/dates/status"""
        today = datetime.now().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        
        resp = session.post(f"{BASE_URL}/api/projects/{test_data['project_id']}/sprints", json={
            "name": "TEST_Sprint_Phase2",
            "goal": "Test Phase 2 features",
            "start_date": today,
            "end_date": end_date
        })
        assert resp.status_code == 200, f"Create sprint failed: {resp.text}"
        data = resp.json()
        
        # Verify response fields
        assert "sprint_id" in data
        assert data["name"] == "TEST_Sprint_Phase2"
        assert data["goal"] == "Test Phase 2 features"
        assert data["start_date"] == today
        assert data["end_date"] == end_date
        assert data["status"] == "planning"  # Default status
        
        # Store for later tests
        test_data["test_sprint_id"] = data["sprint_id"]
        print(f"✓ Created sprint: {data['sprint_id']}")
    
    def test_list_sprints_with_counts(self, session, test_data):
        """GET /api/projects/{id}/sprints lists with task_count and total_points"""
        resp = session.get(f"{BASE_URL}/api/projects/{test_data['project_id']}/sprints")
        assert resp.status_code == 200, f"List sprints failed: {resp.text}"
        data = resp.json()
        
        assert "sprints" in data
        assert isinstance(data["sprints"], list)
        
        # Find our test sprint and verify count fields exist
        for sprint in data["sprints"]:
            assert "task_count" in sprint, "Missing task_count field"
            assert "total_points" in sprint, "Missing total_points field"
            assert "tasks_done" in sprint, "Missing tasks_done field"
        
        print(f"✓ Listed {len(data['sprints'])} sprints with task counts")
    
    def test_assign_tasks_to_sprint(self, session, test_data):
        """POST /api/sprints/{id}/tasks assigns tasks to sprint"""
        sprint_id = test_data.get("test_sprint_id") or test_data["sprint_id"]
        
        resp = session.post(f"{BASE_URL}/api/sprints/{sprint_id}/tasks", json={
            "task_ids": [test_data["task_id"]]
        })
        assert resp.status_code == 200, f"Assign tasks failed: {resp.text}"
        data = resp.json()
        
        assert "assigned" in data
        print(f"✓ Assigned tasks to sprint, count: {data['assigned']}")
    
    def test_get_sprint_board(self, session, test_data):
        """GET /api/sprints/{id}/board returns tasks grouped by status"""
        sprint_id = test_data.get("test_sprint_id") or test_data["sprint_id"]
        
        resp = session.get(f"{BASE_URL}/api/sprints/{sprint_id}/board")
        assert resp.status_code == 200, f"Get board failed: {resp.text}"
        data = resp.json()
        
        assert "board" in data
        assert "todo" in data["board"]
        assert "in_progress" in data["board"]
        assert "review" in data["board"]
        assert "done" in data["board"]
        assert "sprint" in data
        
        print(f"✓ Sprint board has columns: {list(data['board'].keys())}")
    
    def test_get_burndown(self, session, test_data):
        """GET /api/sprints/{id}/burndown returns points/tasks remaining"""
        sprint_id = test_data.get("test_sprint_id") or test_data["sprint_id"]
        
        resp = session.get(f"{BASE_URL}/api/sprints/{sprint_id}/burndown")
        assert resp.status_code == 200, f"Get burndown failed: {resp.text}"
        data = resp.json()
        
        # Verify burndown response structure
        assert "sprint_id" in data
        assert "total_points" in data
        assert "done_points" in data
        assert "remaining_points" in data
        assert "tasks_total" in data
        assert "tasks_done" in data
        
        # Verify math consistency
        assert data["remaining_points"] == data["total_points"] - data["done_points"]
        
        print(f"✓ Burndown data: total_points={data['total_points']}, remaining={data['remaining_points']}")
    
    # =====================================================
    # PHASE 2 - DEPENDENCIES
    # =====================================================
    
    def test_create_dependency(self, session, test_data):
        """POST /api/tasks/dependencies creates dependency link"""
        # First create a second task to create dependency between
        create_task_resp = session.post(f"{BASE_URL}/api/projects/{test_data['project_id']}/tasks", json={
            "title": "TEST_Task_Blocking",
            "description": "Blocking task for dependency test"
        })
        assert create_task_resp.status_code == 200, f"Create task failed: {create_task_resp.text}"
        blocking_task = create_task_resp.json()
        test_data["blocking_task_id"] = blocking_task["task_id"]
        
        # Create dependency: blocking_task blocks existing task
        resp = session.post(f"{BASE_URL}/api/tasks/dependencies", json={
            "blocked_task_id": test_data["task_id"],
            "blocking_task_id": blocking_task["task_id"],
            "dependency_type": "finish_to_start"
        })
        assert resp.status_code == 200, f"Create dependency failed: {resp.text}"
        data = resp.json()
        
        assert "dependency_id" in data
        assert data["blocked_task_id"] == test_data["task_id"]
        assert data["blocking_task_id"] == blocking_task["task_id"]
        assert data["dependency_type"] == "finish_to_start"
        
        test_data["dependency_id"] = data["dependency_id"]
        print(f"✓ Created dependency: {data['dependency_id']}")
    
    def test_get_task_dependencies(self, session, test_data):
        """GET /api/tasks/{id}/dependencies returns blocks and blocked_by"""
        resp = session.get(f"{BASE_URL}/api/tasks/{test_data['task_id']}/dependencies")
        assert resp.status_code == 200, f"Get dependencies failed: {resp.text}"
        data = resp.json()
        
        assert "blocks" in data
        assert "blocked_by" in data
        assert isinstance(data["blocks"], list)
        assert isinstance(data["blocked_by"], list)
        
        # Our test task should be blocked by the blocking task
        assert len(data["blocked_by"]) >= 1, "Expected at least one blocked_by dependency"
        
        print(f"✓ Task dependencies: blocks={len(data['blocks'])}, blocked_by={len(data['blocked_by'])}")
    
    def test_create_dependency_self_blocked(self, session, test_data):
        """Verify task cannot depend on itself"""
        resp = session.post(f"{BASE_URL}/api/tasks/dependencies", json={
            "blocked_task_id": test_data["task_id"],
            "blocking_task_id": test_data["task_id"],
            "dependency_type": "finish_to_start"
        })
        assert resp.status_code == 400, "Should reject self-dependency"
        print("✓ Self-dependency correctly rejected")
    
    # =====================================================
    # PHASE 2 - MILESTONES
    # =====================================================
    
    def test_create_milestone(self, session, test_data):
        """POST /api/projects/{id}/milestones creates milestone"""
        target_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        resp = session.post(f"{BASE_URL}/api/projects/{test_data['project_id']}/milestones", json={
            "name": "TEST_Milestone_Phase2",
            "target_date": target_date,
            "description": "Test milestone for Phase 2"
        })
        assert resp.status_code == 200, f"Create milestone failed: {resp.text}"
        data = resp.json()
        
        assert "milestone_id" in data
        assert data["name"] == "TEST_Milestone_Phase2"
        assert data["target_date"] == target_date
        assert data["status"] == "pending"
        
        test_data["milestone_id"] = data["milestone_id"]
        print(f"✓ Created milestone: {data['milestone_id']}")
    
    def test_list_milestones_with_counts(self, session, test_data):
        """GET /api/projects/{id}/milestones lists with task counts"""
        resp = session.get(f"{BASE_URL}/api/projects/{test_data['project_id']}/milestones")
        assert resp.status_code == 200, f"List milestones failed: {resp.text}"
        data = resp.json()
        
        assert "milestones" in data
        assert isinstance(data["milestones"], list)
        
        # Verify count fields exist on milestones
        for ms in data["milestones"]:
            assert "task_count" in ms, "Missing task_count field"
            assert "tasks_done" in ms, "Missing tasks_done field"
        
        print(f"✓ Listed {len(data['milestones'])} milestones with counts")
    
    # =====================================================
    # PHASE 2 - GANTT DATA
    # =====================================================
    
    def test_get_gantt_data(self, session, test_data):
        """GET /api/projects/{id}/gantt returns tasks+milestones+deps"""
        resp = session.get(f"{BASE_URL}/api/projects/{test_data['project_id']}/gantt")
        assert resp.status_code == 200, f"Get Gantt failed: {resp.text}"
        data = resp.json()
        
        assert "tasks" in data
        assert "milestones" in data
        assert "dependencies" in data
        assert isinstance(data["tasks"], list)
        assert isinstance(data["milestones"], list)
        assert isinstance(data["dependencies"], list)
        
        print(f"✓ Gantt data: {len(data['tasks'])} tasks, {len(data['milestones'])} milestones, {len(data['dependencies'])} deps")
    
    # =====================================================
    # PHASE 3 - PROGRAMS
    # =====================================================
    
    def test_create_program(self, session, test_data):
        """POST /api/workspaces/{ws}/programs creates program"""
        resp = session.post(f"{BASE_URL}/api/workspaces/{test_data['workspace_id']}/programs", json={
            "name": "TEST_Program_Phase3",
            "description": "Test program for Phase 3"
        })
        assert resp.status_code == 200, f"Create program failed: {resp.text}"
        data = resp.json()
        
        assert "program_id" in data
        assert data["name"] == "TEST_Program_Phase3"
        assert data["status"] == "active"
        assert "project_ids" in data
        
        test_data["program_id"] = data["program_id"]
        print(f"✓ Created program: {data['program_id']}")
    
    def test_list_programs(self, session, test_data):
        """GET /api/workspaces/{ws}/programs lists programs"""
        resp = session.get(f"{BASE_URL}/api/workspaces/{test_data['workspace_id']}/programs")
        assert resp.status_code == 200, f"List programs failed: {resp.text}"
        data = resp.json()
        
        assert "programs" in data
        assert isinstance(data["programs"], list)
        
        # Verify project_count field
        for p in data["programs"]:
            assert "project_count" in p
        
        print(f"✓ Listed {len(data['programs'])} programs")
    
    def test_add_project_to_program(self, session, test_data):
        """POST /api/programs/{id}/projects adds project to program"""
        resp = session.post(f"{BASE_URL}/api/programs/{test_data['program_id']}/projects", json={
            "project_id": test_data["project_id"]
        })
        assert resp.status_code == 200, f"Add project failed: {resp.text}"
        data = resp.json()
        
        assert test_data["project_id"] in data.get("project_ids", [])
        print(f"✓ Added project to program")
    
    # =====================================================
    # PHASE 3 - PORTFOLIOS
    # =====================================================
    
    def test_create_portfolio(self, session, test_data):
        """POST /api/portfolios creates portfolio"""
        resp = session.post(f"{BASE_URL}/api/portfolios", json={
            "name": "TEST_Portfolio_Phase3",
            "description": "Test portfolio for Phase 3"
        })
        assert resp.status_code == 200, f"Create portfolio failed: {resp.text}"
        data = resp.json()
        
        assert "portfolio_id" in data
        assert data["name"] == "TEST_Portfolio_Phase3"
        assert data["status"] == "active"
        
        test_data["portfolio_id"] = data["portfolio_id"]
        print(f"✓ Created portfolio: {data['portfolio_id']}")
    
    def test_list_portfolios(self, session, test_data):
        """GET /api/portfolios lists portfolios"""
        resp = session.get(f"{BASE_URL}/api/portfolios")
        assert resp.status_code == 200, f"List portfolios failed: {resp.text}"
        data = resp.json()
        
        assert "portfolios" in data
        assert isinstance(data["portfolios"], list)
        print(f"✓ Listed {len(data['portfolios'])} portfolios")
    
    def test_add_program_to_portfolio(self, session, test_data):
        """POST /api/portfolios/{id}/programs adds program to portfolio"""
        resp = session.post(f"{BASE_URL}/api/portfolios/{test_data['portfolio_id']}/programs", json={
            "program_id": test_data["program_id"]
        })
        assert resp.status_code == 200, f"Add program failed: {resp.text}"
        data = resp.json()
        
        assert test_data["program_id"] in data.get("program_ids", [])
        print(f"✓ Added program to portfolio")
    
    def test_get_portfolio_health(self, session, test_data):
        """GET /api/portfolios/{id}/health returns completion rate and health color"""
        resp = session.get(f"{BASE_URL}/api/portfolios/{test_data['portfolio_id']}/health")
        assert resp.status_code == 200, f"Get health failed: {resp.text}"
        data = resp.json()
        
        # Verify health response structure
        assert "portfolio" in data
        assert "programs" in data
        assert "projects" in data
        assert "total_tasks" in data
        assert "done_tasks" in data
        assert "overdue_tasks" in data
        assert "completion_rate" in data
        assert "health" in data
        
        # Verify health color is valid
        assert data["health"] in ["green", "yellow", "red"], f"Invalid health color: {data['health']}"
        
        print(f"✓ Portfolio health: {data['health']}, completion_rate={data['completion_rate']}%")
    
    # =====================================================
    # PHASE 4 - TIME TRACKING
    # =====================================================
    
    def test_log_time_entry(self, session, test_data):
        """POST /api/time-entries logs time with hours/description"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        resp = session.post(f"{BASE_URL}/api/time-entries", json={
            "task_id": test_data["task_id"],
            "hours": 2.5,
            "description": "TEST_Time_Entry_Phase4",
            "date": today
        })
        assert resp.status_code == 200, f"Log time failed: {resp.text}"
        data = resp.json()
        
        assert "entry_id" in data
        assert data["hours"] == 2.5
        assert data["description"] == "TEST_Time_Entry_Phase4"
        assert data["date"] == today
        assert data["task_id"] == test_data["task_id"]
        
        test_data["time_entry_id"] = data["entry_id"]
        print(f"✓ Logged time entry: {data['entry_id']}, {data['hours']} hours")
    
    def test_get_task_time_entries(self, session, test_data):
        """GET /api/tasks/{id}/time-entries returns entries with total_hours"""
        resp = session.get(f"{BASE_URL}/api/tasks/{test_data['task_id']}/time-entries")
        assert resp.status_code == 200, f"Get time entries failed: {resp.text}"
        data = resp.json()
        
        assert "entries" in data
        assert "total_hours" in data
        assert isinstance(data["entries"], list)
        assert isinstance(data["total_hours"], (int, float))
        
        print(f"✓ Task has {len(data['entries'])} time entries, total: {data['total_hours']} hours")
    
    def test_get_my_timesheet(self, session, test_data):
        """GET /api/my-timesheet returns user's timesheet with by_day breakdown"""
        resp = session.get(f"{BASE_URL}/api/my-timesheet")
        assert resp.status_code == 200, f"Get timesheet failed: {resp.text}"
        data = resp.json()
        
        assert "entries" in data
        assert "total_hours" in data
        assert "by_day" in data
        assert isinstance(data["entries"], list)
        assert isinstance(data["by_day"], dict)
        
        print(f"✓ Timesheet: {len(data['entries'])} entries, total: {data['total_hours']} hours")
    
    def test_get_my_timesheet_with_dates(self, session, test_data):
        """GET /api/my-timesheet with date range filters"""
        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        resp = session.get(f"{BASE_URL}/api/my-timesheet?start_date={week_ago}&end_date={today}")
        assert resp.status_code == 200, f"Get timesheet with dates failed: {resp.text}"
        data = resp.json()
        
        assert "entries" in data
        assert "total_hours" in data
        print(f"✓ Timesheet with date filter: {data['total_hours']} hours")
    
    # =====================================================
    # PHASE 4 - AUTOMATION RULES
    # =====================================================
    
    def test_create_automation_rule(self, session, test_data):
        """POST /api/projects/{id}/automations creates automation rule"""
        resp = session.post(f"{BASE_URL}/api/projects/{test_data['project_id']}/automations", json={
            "name": "TEST_Automation_Phase4",
            "trigger_event": "task.status_changed",
            "conditions": {"old_status": "todo", "new_status": "in_progress"},
            "actions": [{"type": "set_field", "field": "priority", "value": "high"}],
            "enabled": True
        })
        assert resp.status_code == 200, f"Create automation failed: {resp.text}"
        data = resp.json()
        
        assert "rule_id" in data
        assert data["name"] == "TEST_Automation_Phase4"
        assert data["trigger_event"] == "task.status_changed"
        assert data["enabled"] == True
        assert "conditions" in data
        assert "actions" in data
        
        test_data["automation_rule_id"] = data["rule_id"]
        print(f"✓ Created automation rule: {data['rule_id']}")
    
    def test_list_automations(self, session, test_data):
        """GET /api/projects/{id}/automations lists automation rules"""
        resp = session.get(f"{BASE_URL}/api/projects/{test_data['project_id']}/automations")
        assert resp.status_code == 200, f"List automations failed: {resp.text}"
        data = resp.json()
        
        assert "automations" in data
        assert isinstance(data["automations"], list)
        print(f"✓ Listed {len(data['automations'])} automation rules")
    
    def test_get_automation_triggers(self, session, test_data):
        """GET /api/automations/triggers returns 7 triggers and 6 actions"""
        resp = session.get(f"{BASE_URL}/api/automations/triggers")
        assert resp.status_code == 200, f"Get triggers failed: {resp.text}"
        data = resp.json()
        
        assert "triggers" in data
        assert "actions" in data
        assert isinstance(data["triggers"], list)
        assert isinstance(data["actions"], list)
        
        # Verify 7 triggers
        assert len(data["triggers"]) == 7, f"Expected 7 triggers, got {len(data['triggers'])}"
        
        # Verify 6 actions
        assert len(data["actions"]) == 6, f"Expected 6 actions, got {len(data['actions'])}"
        
        # Verify trigger structure
        trigger_keys = [t["key"] for t in data["triggers"]]
        expected_triggers = ["task.status_changed", "task.assigned", "task.due_soon", "task.overdue", "task.created", "sprint.completed", "milestone.reached"]
        for expected in expected_triggers:
            assert expected in trigger_keys, f"Missing trigger: {expected}"
        
        print(f"✓ Found {len(data['triggers'])} triggers and {len(data['actions'])} actions")
    
    # =====================================================
    # PHASE 4 - RECURRING TASKS
    # =====================================================
    
    def test_create_recurring_task(self, session, test_data):
        """POST /api/projects/{id}/recurring-tasks creates recurring task config"""
        start_date = datetime.now().strftime("%Y-%m-%d")
        
        resp = session.post(f"{BASE_URL}/api/projects/{test_data['project_id']}/recurring-tasks", json={
            "template": {
                "title": "TEST_Recurring_Task",
                "description": "Auto-created recurring task",
                "priority": "medium"
            },
            "interval_days": 7,
            "start_date": start_date
        })
        assert resp.status_code == 200, f"Create recurring task failed: {resp.text}"
        data = resp.json()
        
        assert "recurring_id" in data
        assert data["interval_days"] == 7
        assert data["next_creation"] == start_date
        assert data["enabled"] == True
        assert "template" in data
        
        test_data["recurring_task_id"] = data["recurring_id"]
        print(f"✓ Created recurring task config: {data['recurring_id']}")
    
    def test_list_recurring_tasks(self, session, test_data):
        """GET /api/projects/{id}/recurring-tasks lists configs"""
        resp = session.get(f"{BASE_URL}/api/projects/{test_data['project_id']}/recurring-tasks")
        assert resp.status_code == 200, f"List recurring tasks failed: {resp.text}"
        data = resp.json()
        
        assert "recurring_tasks" in data
        assert isinstance(data["recurring_tasks"], list)
        print(f"✓ Listed {len(data['recurring_tasks'])} recurring task configs")
    
    # =====================================================
    # PHASE 5 - CUSTOM FIELDS
    # =====================================================
    
    def test_create_custom_field_dropdown(self, session, test_data):
        """POST /api/projects/{id}/custom-fields creates dropdown field"""
        resp = session.post(f"{BASE_URL}/api/projects/{test_data['project_id']}/custom-fields", json={
            "name": "TEST_Environment",
            "field_type": "dropdown",
            "options": ["Development", "Staging", "Production"],
            "required": False
        })
        assert resp.status_code == 200, f"Create dropdown field failed: {resp.text}"
        data = resp.json()
        
        assert "field_id" in data
        assert data["name"] == "TEST_Environment"
        assert data["field_type"] == "dropdown"
        assert data["options"] == ["Development", "Staging", "Production"]
        
        test_data["custom_field_dropdown_id"] = data["field_id"]
        print(f"✓ Created dropdown custom field: {data['field_id']}")
    
    def test_create_custom_field_text(self, session, test_data):
        """POST /api/projects/{id}/custom-fields creates text field"""
        resp = session.post(f"{BASE_URL}/api/projects/{test_data['project_id']}/custom-fields", json={
            "name": "TEST_External_Link",
            "field_type": "text",
            "required": False
        })
        assert resp.status_code == 200, f"Create text field failed: {resp.text}"
        data = resp.json()
        
        assert data["field_type"] == "text"
        test_data["custom_field_text_id"] = data["field_id"]
        print(f"✓ Created text custom field: {data['field_id']}")
    
    def test_create_custom_field_number(self, session, test_data):
        """POST /api/projects/{id}/custom-fields creates number field"""
        resp = session.post(f"{BASE_URL}/api/projects/{test_data['project_id']}/custom-fields", json={
            "name": "TEST_Story_Points_Custom",
            "field_type": "number",
            "default_value": "0"
        })
        assert resp.status_code == 200, f"Create number field failed: {resp.text}"
        data = resp.json()
        
        assert data["field_type"] == "number"
        test_data["custom_field_number_id"] = data["field_id"]
        print(f"✓ Created number custom field: {data['field_id']}")
    
    def test_list_custom_fields(self, session, test_data):
        """GET /api/projects/{id}/custom-fields lists fields"""
        resp = session.get(f"{BASE_URL}/api/projects/{test_data['project_id']}/custom-fields")
        assert resp.status_code == 200, f"List custom fields failed: {resp.text}"
        data = resp.json()
        
        assert "fields" in data
        assert isinstance(data["fields"], list)
        print(f"✓ Listed {len(data['fields'])} custom fields")
    
    # =====================================================
    # PHASE 5 - CUSTOM VALUES ON TASKS
    # =====================================================
    
    def test_set_custom_field_value(self, session, test_data):
        """POST /api/tasks/{id}/custom-values sets custom field value on task"""
        field_id = test_data.get("custom_field_dropdown_id")
        
        resp = session.post(f"{BASE_URL}/api/tasks/{test_data['task_id']}/custom-values", json={
            "field_id": field_id,
            "value": "Production"
        })
        assert resp.status_code == 200, f"Set custom value failed: {resp.text}"
        data = resp.json()
        
        assert data["task_id"] == test_data["task_id"]
        assert data["field_id"] == field_id
        assert data["value"] == "Production"
        
        print(f"✓ Set custom field value: {field_id}=Production")
    
    def test_get_custom_field_values(self, session, test_data):
        """GET /api/tasks/{id}/custom-values reads custom field values"""
        resp = session.get(f"{BASE_URL}/api/tasks/{test_data['task_id']}/custom-values")
        assert resp.status_code == 200, f"Get custom values failed: {resp.text}"
        data = resp.json()
        
        assert isinstance(data, dict)
        # Should have our set value
        field_id = test_data.get("custom_field_dropdown_id")
        if field_id:
            assert field_id in data, f"Expected field {field_id} in custom values"
            assert data[field_id] == "Production"
        
        print(f"✓ Got custom field values: {len(data)} fields")
    
    # =====================================================
    # PHASE 5 - FIELD TEMPLATES
    # =====================================================
    
    def test_save_field_template(self, session, test_data):
        """POST /api/projects/{id}/field-templates saves current fields as template"""
        resp = session.post(f"{BASE_URL}/api/projects/{test_data['project_id']}/field-templates", json={
            "name": "TEST_Template_Phase5"
        })
        assert resp.status_code == 200, f"Save template failed: {resp.text}"
        data = resp.json()
        
        assert "template_id" in data
        assert data["name"] == "TEST_Template_Phase5"
        assert "fields" in data
        assert isinstance(data["fields"], list)
        
        test_data["field_template_id"] = data["template_id"]
        print(f"✓ Saved field template: {data['template_id']} with {len(data['fields'])} fields")
    
    def test_list_field_templates(self, session, test_data):
        """GET /api/field-templates lists templates"""
        resp = session.get(f"{BASE_URL}/api/field-templates")
        assert resp.status_code == 200, f"List templates failed: {resp.text}"
        data = resp.json()
        
        assert "templates" in data
        assert isinstance(data["templates"], list)
        print(f"✓ Listed {len(data['templates'])} field templates")
    
    # =====================================================
    # PHASE 5 - PLM CONFIG
    # =====================================================
    
    def test_get_plm_config(self, session, test_data):
        """GET /api/plm-config returns all PLM configuration options"""
        resp = session.get(f"{BASE_URL}/api/plm-config")
        assert resp.status_code == 200, f"Get PLM config failed: {resp.text}"
        data = resp.json()
        
        # Verify all config sections present
        assert "sprint_statuses" in data
        assert "dependency_types" in data
        assert "milestone_statuses" in data
        assert "custom_field_types" in data
        assert "portfolio_health_levels" in data
        
        # Verify values
        assert data["sprint_statuses"] == ["planning", "active", "completed"]
        assert "finish_to_start" in data["dependency_types"]
        assert data["custom_field_types"] == ["text", "number", "date", "dropdown", "checkbox", "url"]
        assert data["portfolio_health_levels"] == ["green", "yellow", "red"]
        
        print(f"✓ PLM Config: {len(data['custom_field_types'])} field types, {len(data['dependency_types'])} dep types")
    
    # =====================================================
    # CLEANUP
    # =====================================================
    
    def test_cleanup_test_data(self, session, test_data):
        """Clean up test-created data"""
        cleanup_count = 0
        
        # Delete test sprint
        if test_sprint_id := test_data.get("test_sprint_id"):
            resp = session.delete(f"{BASE_URL}/api/sprints/{test_sprint_id}")
            if resp.status_code == 200:
                cleanup_count += 1
        
        # Delete test dependency
        if dep_id := test_data.get("dependency_id"):
            resp = session.delete(f"{BASE_URL}/api/dependencies/{dep_id}")
            if resp.status_code == 200:
                cleanup_count += 1
        
        # Delete test milestone
        if ms_id := test_data.get("milestone_id"):
            resp = session.delete(f"{BASE_URL}/api/milestones/{ms_id}")
            if resp.status_code == 200:
                cleanup_count += 1
        
        # Delete test program
        if prog_id := test_data.get("program_id"):
            resp = session.delete(f"{BASE_URL}/api/programs/{prog_id}")
            if resp.status_code == 200:
                cleanup_count += 1
        
        # Delete test automation
        if rule_id := test_data.get("automation_rule_id"):
            resp = session.delete(f"{BASE_URL}/api/automations/{rule_id}")
            if resp.status_code == 200:
                cleanup_count += 1
        
        # Delete test time entry
        if entry_id := test_data.get("time_entry_id"):
            resp = session.delete(f"{BASE_URL}/api/time-entries/{entry_id}")
            if resp.status_code == 200:
                cleanup_count += 1
        
        # Delete test custom fields
        for field_key in ["custom_field_dropdown_id", "custom_field_text_id", "custom_field_number_id"]:
            if field_id := test_data.get(field_key):
                resp = session.delete(f"{BASE_URL}/api/custom-fields/{field_id}")
                if resp.status_code == 200:
                    cleanup_count += 1
        
        # Delete blocking task
        if blocking_task_id := test_data.get("blocking_task_id"):
            resp = session.delete(f"{BASE_URL}/api/tasks/{blocking_task_id}")
            if resp.status_code == 200:
                cleanup_count += 1
        
        print(f"✓ Cleaned up {cleanup_count} test resources")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
