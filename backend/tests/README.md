# Nexus Test Suite Organization
#
# Run all core regression tests:
#   python -m pytest tests/test_core_regression.py -x -q
#
# Run by domain:
#   Auth:       test_core_regression.py (register, login, password validation, email verification)
#   Messaging:  test_core_regression.py (send, retrieve, XSS sanitization)
#   Projects:   test_projects_module.py, test_plm_phase1_features.py
#   Code Repo:  test_code_repo.py, test_ai_repo_tools.py
#   Wiki:       test_wiki_module.py
#   Billing:    test_advanced_billing.py
#   Admin:      test_core_regression.py (admin 403 checks), test_admin_bugs.py
#   RBAC:       test_platform_roles.py, test_rbac_files_notifications.py
#   AI Tools:   test_ai_tools_mentions.py, test_ai_skills.py
#   Reporting:  test_iteration69_reporting_engine.py
#   i18n:       test_i18n_language.py
#
# Core regression (16 tests covering critical paths):
#   test_core_regression.py
#
# Legacy iteration tests (kept for reference):
#   test_iteration*.py
