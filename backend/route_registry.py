"""Route Registry — Centralized route registration for all API modules.

Extracted from server.py to reduce its size and improve maintainability.
Each route module's register function is called with the shared dependencies.
"""
import logging

logger = logging.getLogger(__name__)


def register_all_routes(app, api_router, db, get_current_user, ws_manager, AI_MODELS=None):
    """Register all route modules. Called once during server startup."""
    
    # --- Core routes (order matters for some) ---
    from routes.routes_health import register_health_routes
    register_health_routes(api_router, db, get_current_user)

    from routes.routes_google_auth import register_google_auth_routes
    register_google_auth_routes(api_router, db, get_current_user)

    from routes.routes_auth_email import register_auth_email_routes
    register_auth_email_routes(api_router, db)

    from routes.routes_mfa import register_mfa_routes
    register_mfa_routes(api_router, db, get_current_user)

    from routes.routes_sso import register_sso_routes
    register_sso_routes(api_router, db, get_current_user)

    from routes.routes_user_prefs import register_user_prefs_routes
    register_user_prefs_routes(api_router, db, get_current_user)

    # --- Workspace / Channel / Message ---
    from routes.routes_workspace_deletion import register_workspace_deletion_routes
    register_workspace_deletion_routes(api_router, db, get_current_user)

    from routes.routes_workspaces import register_workspaces_routes
    register_workspaces_routes(api_router, db, get_current_user)

    from routes.routes_channels import register_channels_routes
    register_channels_routes(api_router, db, get_current_user)

    from routes.routes_messages import register_messages_routes
    register_messages_routes(api_router, db, get_current_user, ws_manager)

    # --- RBAC must come before files (provides check_workspace_permission) ---
    from routes.routes_rbac import register_rbac_routes, check_workspace_permission
    register_rbac_routes(api_router, db, get_current_user)

    from routes.routes_files import register_file_routes
    register_file_routes(api_router, db, get_current_user, check_workspace_permission)

    from routes.routes_wiki import register_wiki_routes
    register_wiki_routes(api_router, db, get_current_user)

    from routes.routes_tasks import register_task_routes
    register_task_routes(api_router, db, get_current_user)

    from routes.routes_projects import register_project_routes
    register_project_routes(api_router, db, get_current_user)

    from routes.routes_task_sessions import register_task_session_routes
    register_task_session_routes(api_router, db, get_current_user, AI_MODELS)

    # --- Members / Org ---
    from routes.routes_orgs import register_org_routes
    register_org_routes(api_router, db, get_current_user)

    from routes.routes_scim import register_scim_routes
    register_scim_routes(api_router, db, get_current_user)

    # --- AI / Agent ---
    from routes.routes_ai_keys import register_ai_key_routes
    register_ai_key_routes(api_router, db, get_current_user)

    from routes.routes_nexus_agents import register_nexus_agent_routes
    register_nexus_agent_routes(api_router, db, get_current_user, AI_MODELS)

    from routes.routes_agent_studio import register_agent_studio_routes
    register_agent_studio_routes(api_router, db, get_current_user, AI_MODELS or {})

    from routes.routes_agent_skills import register_agent_skills_routes
    register_agent_skills_routes(api_router, db, get_current_user)

    from routes.routes_agent_training import register_agent_training_routes
    register_agent_training_routes(api_router, db, get_current_user)

    from routes.routes_agent_playground import register_playground_routes
    register_playground_routes(api_router, db, get_current_user)

    from routes.routes_agent_catalog import register_agent_catalog_routes
    register_agent_catalog_routes(api_router, db, get_current_user)

    from routes.routes_agent_versioning import register_agent_versioning_routes
    register_agent_versioning_routes(api_router, db, get_current_user)

    from routes.routes_agent_analytics import register_agent_analytics_routes
    register_agent_analytics_routes(api_router, db, get_current_user)

    from routes.routes_agent_leaderboard import register_leaderboard_routes
    register_leaderboard_routes(api_router, db, get_current_user)

    from routes.routes_agent_marketplace import register_agent_marketplace_routes
    register_agent_marketplace_routes(api_router, db, get_current_user)

    from routes.routes_agent_memory import register_agent_memory_routes
    register_agent_memory_routes(api_router, db, get_current_user)

    from routes.routes_agent_protocol import register_agent_protocol_routes
    register_agent_protocol_routes(api_router, db, get_current_user)

    from routes.routes_agent_schedules import register_agent_schedule_routes
    register_agent_schedule_routes(api_router, db, get_current_user, AI_MODELS)

    from routes.routes_agent_teams import register_agent_team_routes
    register_agent_team_routes(api_router, db, get_current_user, ws_manager)

    from routes.routes_arena import register_arena_routes
    register_arena_routes(api_router, db, get_current_user)

    from routes.routes_dojo import register_dojo_routes
    register_dojo_routes(api_router, db, get_current_user)

    # --- Billing / Pricing ---
    from routes.routes_billing import register_billing_routes
    register_billing_routes(api_router, db, get_current_user)

    from routes.routes_billing_advanced import register_advanced_billing_routes
    register_advanced_billing_routes(api_router, db, get_current_user)

    from routes.routes_ai_billing import register_ai_billing_routes
    register_ai_billing_routes(api_router, db, get_current_user)

    from routes.routes_pricing import register_pricing_routes
    register_pricing_routes(api_router, db, get_current_user)

    from routes.routes_revenue_sharing import register_revenue_sharing_routes
    register_revenue_sharing_routes(api_router, db, get_current_user)

    from routes.routes_managed_keys import register_managed_keys_routes
    register_managed_keys_routes(api_router, db, get_current_user)

    # --- Content / Media ---
    from routes.routes_image_gen import register_image_gen_routes
    register_image_gen_routes(api_router, db, get_current_user)

    from routes.routes_image_understanding import register_image_understanding_routes
    register_image_understanding_routes(api_router, db, get_current_user)

    from routes.routes_media import register_media_routes
    register_media_routes(api_router, db, get_current_user)

    from routes.routes_content_gen import register_content_gen_routes
    register_content_gen_routes(api_router, db, get_current_user)

    # --- Collaboration / Workflow ---
    from routes.routes_sharing import register_sharing_routes
    register_sharing_routes(api_router, db, get_current_user)

    from routes.routes_threading import register_threading_routes
    register_threading_routes(api_router, db, get_current_user)

    from routes.routes_workflows import register_workflow_routes
    register_workflow_routes(api_router, db, get_current_user)

    from routes.routes_orchestration import register_orchestration_routes
    register_orchestration_routes(api_router, db, get_current_user)

    from routes.routes_orch_schedules import register_orch_schedule_routes
    register_orch_schedule_routes(api_router, db, get_current_user)

    from routes.routes_a2a_pipelines import register_a2a_routes
    register_a2a_routes(api_router, db, get_current_user)

    from routes.routes_operator import register_operator_routes
    register_operator_routes(api_router, db, get_current_user)

    from routes.routes_deployments import register_deployment_routes
    register_deployment_routes(api_router, db, get_current_user)

    from routes.routes_coordination import register_coordination_routes
    register_coordination_routes(api_router, db, get_current_user)

    # --- Research / Knowledge ---
    from routes.routes_research import register_research_routes
    register_research_routes(api_router, db, get_current_user)

    from routes.routes_research_library import register_research_library_routes
    register_research_library_routes(api_router, db, get_current_user, ws_manager)

    from routes.routes_knowledge_graph import register_knowledge_graph_routes
    register_knowledge_graph_routes(api_router, db, get_current_user)

    from routes.routes_knowledge_packs import register_knowledge_pack_routes
    register_knowledge_pack_routes(api_router, db, get_current_user)

    # --- Code ---
    from routes.routes_code_repo import register_code_repo_routes
    register_code_repo_routes(api_router, db, get_current_user)

    from routes.routes_code_dev import register_code_dev_routes
    register_code_dev_routes(api_router, db, get_current_user)

    from routes.routes_openclaw import register_openclaw_routes
    register_openclaw_routes(app, api_router, db, get_current_user)

    from routes.routes_cursor import register_cursor_routes
    register_cursor_routes(api_router, db, get_current_user)

    # --- Integrations ---
    from routes.routes_integrations import register_integration_routes
    register_integration_routes(api_router, db, get_current_user)

    from routes.routes_plugins import register_platform_plugin_routes
    register_platform_plugin_routes(api_router, db, get_current_user)

    from routes.routes_cloud_storage import register_cloud_storage_routes
    register_cloud_storage_routes(api_router, db, get_current_user)

    from routes.routes_social_publish import register_social_publish_routes
    register_social_publish_routes(api_router, db, get_current_user)

    from routes.routes_email import register_email_routes
    register_email_routes(api_router, db, get_current_user)

    from routes.routes_nexus_connect import register_nexus_connect_routes
    register_nexus_connect_routes(api_router, db, get_current_user)

    from routes.routes_webhooks import register_webhook_routes
    register_webhook_routes(api_router, db, get_current_user)

    # --- Mail / Smart Inbox ---
    from routes.routes_smart_inbox import register_smart_inbox_routes
    register_smart_inbox_routes(api_router, db, get_current_user)

    from routes.routes_mail_connections import register_mail_connection_routes
    register_mail_connection_routes(api_router, db, get_current_user)

    from routes.routes_mail_rules import register_mail_rule_routes
    register_mail_rule_routes(api_router, db, get_current_user)

    from routes.routes_mail_audit import register_mail_audit_routes
    register_mail_audit_routes(api_router, db, get_current_user)

    # --- Internal / Tier 2-3 ---
    from routes.routes_internal import register_internal_routes
    register_internal_routes(api_router, db, get_current_user)

    from routes.routes_tier23 import register_tier23_routes
    register_tier23_routes(api_router, db, get_current_user)

    # --- Admin / Analytics / Reporting ---
    from routes.routes_admin import register_admin_routes
    register_admin_routes(api_router, db, get_current_user)

    from routes.routes_analytics import register_analytics_routes
    register_analytics_routes(api_router, db, get_current_user)

    from routes.routes_reporting import register_reporting_routes
    register_reporting_routes(api_router, db, get_current_user)

    from routes.routes_error_tracking import register_error_tracking_routes
    register_error_tracking_routes(api_router, db, get_current_user)

    from routes.routes_notifications import register_notification_routes
    register_notification_routes(api_router, db, get_current_user)

    # --- Features / Modules ---
    from routes.routes_features import register_additional_features
    register_additional_features(api_router, db, get_current_user)

    from routes.routes_advanced_features import register_advanced_features_routes
    register_advanced_features_routes(api_router, db, get_current_user)

    from routes.routes_enhancements import register_enhancement_routes
    register_enhancement_routes(api_router, db, get_current_user)

    from routes.routes_nx_features import register_nx_features_routes
    register_nx_features_routes(api_router, db, get_current_user)

    from routes.routes_modules import register_module_routes
    register_module_routes(api_router, db, get_current_user)

    from routes.routes_strategic_v2 import register_strategic_features
    register_strategic_features(api_router, db, get_current_user)

    # --- Platform ---
    from routes.routes_status import register_status_routes
    register_status_routes(api_router, db, get_current_user)

    from routes.routes_legal import register_legal_routes
    register_legal_routes(api_router, db, get_current_user)

    from routes.routes_marketplace import register_marketplace_routes
    register_marketplace_routes(api_router, db, get_current_user)

    from routes.routes_support_desk import register_support_desk_routes
    register_support_desk_routes(api_router, db, get_current_user)

    from routes.routes_guide_me import register_guide_me_routes
    register_guide_me_routes(api_router, db, get_current_user)

    from routes.routes_walkthroughs_builder import register_walkthrough_routes
    register_walkthrough_routes(api_router, db, get_current_user)

    from routes.routes_helper import register_helper_routes
    register_helper_routes(api_router, db, get_current_user)

    from routes.routes_platform_profile import register_platform_profile_routes
    register_platform_profile_routes(api_router, db, get_current_user)

    # --- Misc ---
    from routes.routes_drive import register_drive_routes
    register_drive_routes(api_router, db, get_current_user)

    from routes.routes_export_audit import register_export_audit_routes
    register_export_audit_routes(api_router, db, get_current_user)

    from routes.routes_soc2 import register_soc2_routes
    register_soc2_routes(api_router, db, get_current_user)

    from routes.routes_cloudflare import register_cloudflare_routes
    register_cloudflare_routes(api_router, db, get_current_user)

    from routes.routes_keystone import register_keystone_routes
    register_keystone_routes(api_router, db, get_current_user)

    from routes.routes_workspace_templates import register_workspace_templates_routes
    register_workspace_templates_routes(api_router, db, get_current_user)

    from routes.routes_global_search import register_global_search_routes
    register_global_search_routes(api_router, db, get_current_user)

    from routes.routes_ideation import register_ideation_routes
    register_ideation_routes(api_router, db, get_current_user)

    from routes.routes_handoffs_memory import register_handoff_memory_routes
    register_handoff_memory_routes(api_router, db, get_current_user)

    from routes.routes_context_ledger import register_context_ledger_routes
    register_context_ledger_routes(api_router, db, get_current_user)

    from routes.routes_directive_engine import register_directive_engine_routes
    register_directive_engine_routes(api_router, db, get_current_user)

    from routes.routes_reviews import register_review_routes
    register_review_routes(api_router, db, get_current_user)

    from routes.routes_benchmarks import register_benchmark_routes
    register_benchmark_routes(api_router, db, get_current_user)

    from routes.routes_cost_alerts import register_cost_alert_routes
    register_cost_alert_routes(api_router, db, get_current_user)

    from routes.routes_cost_intelligence import register_cost_intelligence_routes
    register_cost_intelligence_routes(api_router, db, get_current_user)

    from routes.routes_model_perf import register_model_performance_routes
    register_model_performance_routes(api_router, db, get_current_user)

    from routes.routes_repository import register_repository_routes
    register_repository_routes(api_router, db, get_current_user)

    from routes.routes_reports import register_reports_routes
    register_reports_routes(api_router, db, get_current_user)

    from routes.routes_finetune import register_finetune_routes
    register_finetune_routes(api_router, db, get_current_user)

    from routes.routes_extended_tools import register_extended_tool_routes
    register_extended_tool_routes(api_router, db, get_current_user)

    from routes.routes_ai_skills import register_ai_skills_routes
    register_ai_skills_routes(api_router, db, get_current_user, check_workspace_permission)

    from routes.routes_ai_tools import register_ai_tools_routes
    register_ai_tools_routes(api_router, db, get_current_user)

    from routes.routes_plm_advanced import register_plm_advanced_routes
    register_plm_advanced_routes(api_router, db, get_current_user)

    from routes.routes_auto_refresh import register_auto_refresh_routes
    register_auto_refresh_routes(api_router, db, get_current_user)

    from routes.routes_training_analytics import register_training_analytics_routes
    register_training_analytics_routes(api_router, db, get_current_user)

    from routes.routes_nexus_browser import register_browser_routes
    register_browser_routes(api_router, db, get_current_user)

    from routes.routes_roi_calculator import register_roi_calculator_routes
    register_roi_calculator_routes(api_router, db, get_current_user)

    from routes.routes_roi_comparison import register_roi_comparison_routes
    register_roi_comparison_routes(api_router, db, get_current_user)

    from routes.routes_turboquant import register_turboquant_routes
    register_turboquant_routes(api_router, db, get_current_user)

    # --- WebSocket routes (need app, not api_router) ---
    from routes.routes_yjs import register_yjs_routes
    register_yjs_routes(app, db)

    from routes.routes_training_ws import register_training_ws_routes
    register_training_ws_routes(app, db, get_current_user)

    logger.info(f"Route registry: All route modules registered")
