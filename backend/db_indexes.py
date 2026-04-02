"""Database Index Definitions — extracted from server.py."""
import logging

logger = logging.getLogger(__name__)

async def create_all_indexes(db):
    """Create all MongoDB indexes."""
    try:
        await db.users.create_index("user_id", unique=True)
        await db.users.create_index("email", unique=True)
        await db.user_sessions.create_index("session_token", unique=True)
        await db.user_sessions.create_index("user_id")
        await db.user_sessions.create_index("expires_at")
        await db.workspaces.create_index("workspace_id", unique=True)
        await db.workspaces.create_index("owner_id")
        await db.channels.create_index("channel_id", unique=True)
        await db.channels.create_index("workspace_id")
        await db.messages.create_index("channel_id")
        await db.messages.create_index("message_id", unique=True)
        await db.organizations.create_index("slug", unique=True)
        await db.organizations.create_index("org_id", unique=True)
        await db.org_memberships.create_index([("org_id", 1), ("user_id", 1)], unique=True)
        await db.bug_reports.create_index("reporter_id")
        await db.projects.create_index("workspace_id")
        await db.projects.create_index("project_id", unique=True)
        await db.projects.create_index("linked_channels")
        await db.project_tasks.create_index("project_id")
        await db.project_tasks.create_index("task_id", unique=True)
        await db.workflows.create_index("workflow_id", unique=True)
        await db.workflows.create_index("workspace_id")
        await db.workflow_nodes.create_index("node_id", unique=True)
        await db.workflow_nodes.create_index("workflow_id")
        await db.workflow_edges.create_index("edge_id", unique=True)
        await db.workflow_edges.create_index("workflow_id")
        await db.workflow_runs.create_index("run_id", unique=True)
        await db.workflow_runs.create_index("workflow_id")
        await db.node_executions.create_index("exec_id", unique=True)
        await db.node_executions.create_index("run_id")
        await db.workflow_templates.create_index("template_id", unique=True)
        await db.artifacts.create_index("artifact_id", unique=True)
        await db.artifacts.create_index("workspace_id")
        await db.artifacts.create_index("workflow_id")
        await db.artifact_versions.create_index([("artifact_id", 1), ("version", -1)])
        await db.marketplace_templates.create_index("marketplace_id", unique=True)
        await db.marketplace_templates.create_index("scope")
        await db.marketplace_templates.create_index("category")
        await db.marketplace_templates.create_index("org_id")
        await db.marketplace_ratings.create_index([("marketplace_id", 1), ("user_id", 1)], unique=True)
        await db.agent_schedules.create_index("schedule_id", unique=True)
        await db.agent_schedules.create_index("workspace_id")
        await db.agent_schedules.create_index([("enabled", 1), ("next_run_at", 1)])
        await db.schedule_runs.create_index("run_id", unique=True)
        await db.schedule_runs.create_index("schedule_id")
        await db.handoffs.create_index("handoff_id", unique=True)
        await db.handoffs.create_index("channel_id")
        await db.workspace_memory.create_index("memory_id", unique=True)
        await db.workspace_memory.create_index("workspace_id")
        await db.workspace_memory.create_index([("workspace_id", 1), ("key", 1)], unique=True)
        await db.audit_log.create_index("audit_id", unique=True)
        await db.audit_log.create_index([("workspace_id", 1), ("timestamp", -1)])
        await db.webhooks.create_index("webhook_id", unique=True)
        await db.webhooks.create_index("workspace_id")
        await db.webhook_deliveries.create_index("delivery_id", unique=True)
        await db.webhook_deliveries.create_index("webhook_id")
        await db.disagreements.create_index("disagreement_id", unique=True)
        await db.disagreements.create_index("channel_id")
        await db.generated_images.create_index("image_id", unique=True)
        await db.generated_images.create_index("workspace_id")
        await db.image_data.create_index("image_id", unique=True)
        await db.artifact_comments.create_index("artifact_id")
        await db.artifact_comments.create_index("comment_id", unique=True)
        await db.personas.create_index("persona_id", unique=True)
        await db.walkthroughs.create_index("walkthrough_id", unique=True)
        await db.walkthroughs.create_index("status")
        await db.walkthrough_versions.create_index([("walkthrough_id", 1), ("version_number", -1)])
        await db.walkthrough_progress.create_index([("user_id", 1), ("walkthrough_id", 1)], unique=True)
        await db.walkthrough_events.create_index("walkthrough_id")
        await db.credit_balances.create_index([("user_id", 1), ("month", 1)], unique=True)
        await db.credit_transactions.create_index("user_id")
        await db.daily_usage.create_index("key", unique=True)
        await db.media_items.create_index("media_id", unique=True)
        await db.media_items.create_index([("workspace_id", 1), ("type", 1)])
        await db.media_data.create_index("media_id", unique=True)
        await db.task_comments.create_index("task_id")
        await db.task_comments.create_index("comment_id", unique=True)
        await db.task_attachments.create_index("task_id")
        await db.task_attachments.create_index("attachment_id", unique=True)
        await db.task_activity.create_index("task_id")
        await db.sprints.create_index("sprint_id", unique=True)
        await db.sprints.create_index("project_id")
        await db.task_dependencies.create_index("dependency_id", unique=True)
        await db.milestones.create_index("milestone_id", unique=True)
        await db.milestones.create_index("project_id")
        await db.programs.create_index("program_id", unique=True)
        await db.portfolios.create_index("portfolio_id", unique=True)
        await db.time_entries.create_index("entry_id", unique=True)
        await db.time_entries.create_index("task_id")
        await db.time_entries.create_index("user_id")
        await db.automation_rules.create_index("rule_id", unique=True)
        await db.custom_fields.create_index("field_id", unique=True)
        await db.custom_fields.create_index("project_id")
        await db.support_tickets.create_index("ticket_id", unique=True)
        await db.support_tickets.create_index("requester_id")
        await db.support_tickets.create_index("assigned_to")
        await db.support_tickets.create_index("status")
        await db.ticket_replies.create_index("ticket_id")
        await db.ticket_activity.create_index("ticket_id")
        await db.org_repository.create_index("file_id", unique=True)
        await db.org_repository.create_index([("org_id", 1), ("folder", 1)])
        await db.repo_file_data.create_index("file_id", unique=True)
        await db.org_integrations.create_index([("org_id", 1), ("key", 1)], unique=True)
        await db.ticket_attachments.create_index("ticket_id")
        await db.cloud_connections.create_index("connection_id", unique=True)
        await db.cloud_connections.create_index([("user_id", 1), ("provider", 1)])
        await db.cloud_connections.create_index([("org_id", 1), ("provider", 1)])
        await db.billing_accounts.create_index("user_id", unique=True)
        await db.invoices.create_index("invoice_id", unique=True)
        await db.invoices.create_index([("user_id", 1), ("period", 1)])
        await db.payments.create_index("user_id")
        await db.org_billing.create_index("org_id", unique=True)
        await db.plan_changes.create_index("user_id")
        await db.code_executions.create_index("exec_id", unique=True)
        await db.github_connections.create_index("connection_id", unique=True)
        await db.generated_content.create_index("content_id", unique=True)
        await db.generated_content.create_index("workspace_id")
        await db.content_versions.create_index([("content_id", 1), ("version", -1)])
        await db.drive_files.create_index("file_id", unique=True)
        await db.drive_files.create_index([("workspace_id", 1), ("path", 1)])
        await db.drive_file_data.create_index([("file_id", 1), ("chunk_index", 1)])
        await db.drive_shares.create_index("token", unique=True)
        await db.research_sessions.create_index("session_id", unique=True)
        await db.research_sources.create_index("session_id")
        await db.research_reports.create_index("session_id")
        await db.fact_checks.create_index("check_id", unique=True)
        await db.custom_agents.create_index("agent_id", unique=True)
        await db.user_presence.create_index([("workspace_id", 1), ("user_id", 1)])
        await db.voice_notes.create_index("note_id", unique=True)
        await db.plugin_connections.create_index("connection_id", unique=True)
        await db.plugin_connections.create_index([("user_id", 1), ("platform", 1)])
        await db.channel_mappings.create_index("mapping_id", unique=True)
        await db.channel_mappings.create_index([("platform", 1), ("external_channel_id", 1)])
        await db.plugin_messages.create_index([("platform", 1), ("timestamp", -1)])
        await db.code_repos.create_index([("workspace_id", 1), ("repo_id", 1)])
        # Drop old unique workspace_id index that blocks multi-repo
        try:
            await db.code_repos.drop_index("workspace_id_1")
        except Exception as _e:
            import logging; logging.getLogger("db_indexes").warning(f"Suppressed: {_e}")
        # Backfill legacy repo_files: assign to default repo if no repo_id
        try:
            legacy = await db.repo_files.count_documents({"$or": [{"repo_id": {"$exists": False}}, {"repo_id": ""}, {"repo_id": None}]})
            if legacy > 0:
                async for f in db.repo_files.find({"$or": [{"repo_id": {"$exists": False}}, {"repo_id": ""}, {"repo_id": None}]}, {"file_id": 1, "workspace_id": 1}):
                    repo = await db.code_repos.find_one({"workspace_id": f["workspace_id"]}, {"repo_id": 1})
                    if repo:
                        await db.repo_files.update_one({"file_id": f["file_id"]}, {"$set": {"repo_id": repo["repo_id"]}})
                logger.info(f"Backfilled {legacy} legacy repo_files with repo_id")
        except Exception as e:
            logger.warning(f"Repo backfill: {e}")
        await db.repo_files.create_index("file_id", unique=True)
        await db.repo_files.create_index([("workspace_id", 1), ("path", 1)])
        await db.repo_commits.create_index("commit_id", unique=True)
        await db.repo_commits.create_index([("workspace_id", 1), ("created_at", -1)])
        await db.repo_links.create_index("link_id", unique=True)
        await db.repo_links.create_index([("workspace_id", 1), ("target_type", 1)])
        await db.repo_branches.create_index([("workspace_id", 1), ("name", 1)], unique=True)
        await db.repo_reviews.create_index("review_id", unique=True)
        await db.milestones.create_index("milestone_id", unique=True)
        await db.milestones.create_index([("project_id", 1), ("due_date", 1)])
        await db.task_relationships.create_index("relationship_id", unique=True)
        await db.task_relationships.create_index("task_id")
        await db.task_relationships.create_index("target_task_id")
        await db.task_relationships.create_index("milestone_id")
        await db.wiki_pages.create_index("page_id", unique=True)
        await db.wiki_pages.create_index([("workspace_id", 1), ("title", 1)])
        await db.wiki_pages.create_index([("workspace_id", 1), ("parent_id", 1)])
        await db.wiki_versions.create_index([("page_id", 1), ("version", -1)])
        await db.email_log.create_index([("type", 1), ("timestamp", -1)])
        await db.password_resets.create_index("token", unique=True)
        await db.password_resets.create_index("email")
        await db.invitations.create_index("token")
        await db.invitations.create_index([("email", 1), ("org_id", 1)])
        await db.context_ledger.create_index("ledger_id", unique=True)
        await db.context_ledger.create_index([("channel_id", 1), ("agent_key", 1), ("created_at", -1)])
        await db.context_ledger.create_index([("workspace_id", 1), ("created_at", -1)])
        await db.context_ledger.create_index("event_type")
        await db.duplicate_overrides.create_index("override_id", unique=True)
        await db.duplicate_overrides.create_index([("workspace_id", 1), ("created_at", -1)])
        await db.duplicate_overrides.create_index("entity_type")
        await db.recycle_bin.create_index("bin_id", unique=True)
        await db.recycle_bin.create_index([("workspace_id", 1), ("deleted_at", -1)])
        await db.recycle_bin.create_index("collection")
        await db.recycle_bin.create_index("purged")
        await db.reporting_events.create_index("event_id", unique=True)
        await db.reporting_events.create_index([("timestamp", -1)])
        await db.reporting_events.create_index([("user_id", 1), ("timestamp", -1)])
        await db.reporting_events.create_index([("workspace_id", 1), ("timestamp", -1)])
        await db.reporting_events.create_index("date_key")
        await db.reporting_events.create_index("provider")
        # TTL cleanup handled by background task (dates stored as ISO strings, not BSON Date)
        await db.reporting_rollups.create_index("rollup_id", unique=True)
        await db.reporting_alerts.create_index("alert_id", unique=True)
        await db.reporting_alerts.create_index("resolved")
        await db.org_budgets.create_index("org_id", unique=True)
        # Deployment indexes
        await db.deployments.create_index("deployment_id", unique=True)
        await db.deployments.create_index("workspace_id")
        await db.deployments.create_index("status")
        await db.deployment_runs.create_index("run_id", unique=True)
        await db.deployment_runs.create_index("deployment_id")
        await db.deployment_runs.create_index([("deployment_id", 1), ("status", 1)])
        await db.deployment_action_log.create_index("action_id", unique=True)
        await db.deployment_action_log.create_index([("run_id", 1), ("sequence", 1)])

        # Agent Training & Knowledge indexes
        await db.agent_knowledge.create_index("chunk_id", unique=True)
        await db.agent_knowledge.create_index([("agent_id", 1), ("workspace_id", 1)])
        await db.agent_knowledge.create_index([("agent_id", 1), ("flagged", 1), ("quality_score", -1)])
        await db.agent_knowledge.create_index([("agent_id", 1), ("topic", 1)])
        await db.agent_knowledge.create_index([("agent_id", 1), ("session_id", 1)])
        await db.agent_training_sessions.create_index("session_id", unique=True)
        await db.agent_training_sessions.create_index([("agent_id", 1), ("workspace_id", 1)])
        await db.agent_training_sessions.create_index([("agent_id", 1), ("status", 1)])
        await db.payment_transactions.create_index("session_id")
        await db.payment_transactions.create_index("publisher_id")
        await db.agent_purchases.create_index([("agent_id", 1), ("buyer_id", 1)])

        # Agent Versioning indexes
        await db.agent_versions.create_index("version_id", unique=True)
        await db.agent_versions.create_index([("agent_id", 1), ("version_number", -1)])

        # A2A Pipeline indexes
        await db.a2a_pipelines.create_index("pipeline_id", unique=True)
        await db.a2a_pipelines.create_index("workspace_id")
        await db.a2a_runs.create_index("run_id", unique=True)
        await db.a2a_runs.create_index([("pipeline_id", 1), ("created_at", -1)])
        await db.a2a_runs.create_index([("workspace_id", 1), ("status", 1)])
        await db.a2a_step_executions.create_index("exec_id", unique=True)
        await db.a2a_step_executions.create_index([("run_id", 1), ("started_at", 1)])

        # Operator indexes
        await db.operator_sessions.create_index("session_id", unique=True)
        await db.operator_sessions.create_index("workspace_id")
        await db.operator_sessions.create_index("status")
        await db.operator_sessions.create_index([("workspace_id", 1), ("status", 1)])
        await db.operator_sessions.create_index([("workspace_id", 1), ("created_at", -1)])
        await db.operator_task_executions.create_index("exec_id", unique=True)
        await db.operator_task_executions.create_index("session_id")
        await db.operator_task_executions.create_index([("session_id", 1), ("task_id", 1)])
        await db.operator_task_executions.create_index([("session_id", 1), ("status", 1)])
        await db.operator_learnings.create_index("learning_id", unique=True)
        await db.operator_learnings.create_index("workspace_id")
        await db.operator_learnings.create_index("goal_type")

        # OpenClaw indexes
        await db.openclaw_tokens.create_index("token_hash", unique=True)
        await db.openclaw_tokens.create_index("workspace_id")
        await db.openclaw_sessions.create_index([("workspace_id", 1), ("sender_id", 1)])
        await db.openclaw_sessions.create_index("conversation_id")
        await db.openclaw_message_log.create_index([("session_id", 1), ("created_at", -1)])
        await db.openclaw_message_log.create_index([("workspace_id", 1), ("created_at", -1)])
        await db.openclaw_channel_mappings.create_index("workspace_id")

        # ============ Broad workspace_id + created_at compound indexes ============
        # Covers the majority of workspace-scoped queries across all collections
        workspace_collections = [
            "projects", "project_tasks", "milestones", "wiki_pages", "repo_files",
            "artifacts", "media_items", "workflows", "workflow_runs", "directives",
            "directive_tasks", "deployments", "ideation_sessions", "task_sessions",
            "content_generations", "reporting_events", "context_entries",
            "workspace_memory", "handoffs", "agent_model_costs", "scheduled_jobs",
            "budget_limits", "workspace_snapshots", "model_overrides", "routing_logs",
            "model_comparisons", "routing_rules", "finetune_datasets", "finetune_jobs",
            "cursor_sessions", "r2_uploads", "developer_api_keys",
        ]
        for coll in workspace_collections:
            try:
                await db[coll].create_index([("workspace_id", 1), ("created_at", -1)], background=True)
            except Exception as _e:
                import logging; logging.getLogger("db_indexes").warning(f"Suppressed: {_e}")  # Collection may not exist yet

        # AI call logs for analytics
        await db.ai_call_logs.create_index([("workspace_id", 1), ("created_at", -1)])
        await db.ai_call_logs.create_index([("provider", 1), ("model_used", 1)])

        # NAVC indexes
        await db.turboquant_profiles.create_index("profile_id", unique=True)
        await db.turboquant_profiles.create_index("workspace_id")
        await db.turboquant_runs.create_index("run_id", unique=True)
        await db.turboquant_runs.create_index("workspace_id")
        await db.turboquant_runs.create_index("profile_id")
        await db.turboquant_runs.create_index("status")
        await db.turboquant_promotions.create_index("promotion_id", unique=True)
        await db.turboquant_promotions.create_index("workspace_id")
        await db.turboquant_datasets.create_index("dataset_id", unique=True)
        await db.turboquant_datasets.create_index("workspace_id")
        await db.turboquant_events.create_index([("run_id", 1), ("ts", 1)])
        await db.helper_conversations.create_index("user_id", unique=True)
        await db.helper_conversations.create_index("updated_at", expireAfterSeconds=30*24*3600)
        await db.helper_actions.create_index("action_id", unique=True)
        await db.helper_actions.create_index([("user_id", 1), ("created_at", -1)])
        await db.helper_actions.create_index([("workspace_id", 1), ("status", 1)])

        # Smart Inbox indexes
        await db.mail_connections.create_index("connection_id", unique=True)
        await db.mail_connections.create_index("workspace_id")
        await db.mail_threads.create_index("thread_id", unique=True)
        await db.mail_threads.create_index([("workspace_id", 1), ("last_message_at", -1)])
        await db.mail_threads.create_index([("workspace_id", 1), ("connection_id", 1)])
        await db.mail_threads.create_index([("workspace_id", 1), ("priority", 1)])
        await db.mail_messages.create_index("message_id", unique=True)
        await db.mail_messages.create_index([("thread_id", 1), ("received_at", 1)])
        await db.mail_actions.create_index("action_id", unique=True)
        await db.mail_actions.create_index([("workspace_id", 1), ("status", 1)])
        await db.mail_rules.create_index("rule_id", unique=True)
        await db.mail_rules.create_index("workspace_id")
        await db.mail_audit_log.create_index([("workspace_id", 1), ("timestamp", -1)])

        # Knowledge Graph indexes
        await db.kg_entities.create_index([("workspace_id", 1), ("is_active", 1), ("access_count", -1)])
        await db.kg_entities.create_index([("workspace_id", 1), ("entity_type", 1)])
        await db.kg_entities.create_index("entity_id", unique=True)
        await db.kg_edges.create_index([("workspace_id", 1), ("source_entity_id", 1)])
        await db.kg_edges.create_index([("workspace_id", 1), ("target_entity_id", 1)])
        await db.kg_feedback.create_index("entity_id")

        # KG Consent + Purge indexes
        await db.kg_entities.create_index([("org_id", 1), ("org_shared", 1), ("is_active", 1)])
        await db.kg_consent_audit.create_index([("org_id", 1), ("timestamp", -1)])
        await db.kg_consent_audit.create_index([("workspace_id", 1), ("timestamp", -1)])
        await db.kg_purge_jobs.create_index([("status", 1), ("execute_by", 1)])
        await db.kg_platform_entities.create_index("source_org_hash")
        await db.kg_platform_entities.create_index([("entity_type", 1), ("category_tags", 1)])

        # Media operations (Veo/Lyria async polling)
        await db.media_operations.create_index("operation_id", unique=True)
        await db.media_operations.create_index([("workspace_id", 1), ("status", 1), ("created_at", -1)])

        # Research Intelligence indexes
        await db.research_libraries.create_index("library_id", unique=True)
        await db.research_libraries.create_index([("workspace_id", 1), ("created_at", -1)])
        await db.research_documents.create_index("doc_id", unique=True)
        await db.research_documents.create_index([("library_id", 1), ("ingestion_status", 1)])
        await db.research_documents.create_index([("workspace_id", 1), ("doi", 1)])
        await db.research_chunks.create_index("chunk_id", unique=True)
        await db.research_chunks.create_index([("doc_id", 1), ("para_index", 1)])
        await db.research_chunks.create_index([("doc_id", 1), ("workspace_id", 1)])
        await db.research_annotations.create_index([("doc_id", 1), ("created_at", -1)])
        await db.research_annotations.create_index([("workspace_id", 1), ("tags", 1)])

        # Agent Teams indexes
        await db.agent_team_sessions.create_index("session_id", unique=True)
        await db.agent_team_sessions.create_index([("workspace_id", 1), ("status", 1), ("created_at", -1)])
        await db.agent_team_templates.create_index([("workspace_id", 1), ("times_used", -1)])

        # Agent Dojo indexes
        await db.dojo_sessions.create_index(
            [("workspace_id", 1), ("status", 1), ("created_at", -1)],
            name="dojo_sessions_ws_status_date"
        )
        await db.dojo_sessions.create_index(
            [("session_id", 1)],
            unique=True,
            name="dojo_sessions_id_unique"
        )
        await db.dojo_sessions.create_index(
            [("workspace_id", 1), ("agents.agent_id", 1)],
            name="dojo_sessions_ws_agent"
        )
        await db.dojo_scenarios.create_index(
            [("scenario_id", 1)],
            unique=True,
            name="dojo_scenarios_id_unique"
        )
        await db.dojo_scenarios.create_index(
            [("workspace_id", 1), ("category", 1)],
            name="dojo_scenarios_ws_category"
        )
        await db.dojo_scenarios.create_index(
            [("is_builtin", 1), ("category", 1)],
            name="dojo_scenarios_builtin_category"
        )
        await db.dojo_extracted_data.create_index(
            [("extraction_id", 1)],
            unique=True,
            name="dojo_extracted_id_unique"
        )
        await db.dojo_extracted_data.create_index(
            [("session_id", 1), ("status", 1)],
            name="dojo_extracted_session_status"
        )
        await db.dojo_extracted_data.create_index(
            [("agent_id", 1), ("workspace_id", 1)],
            name="dojo_extracted_agent_ws"
        )

        # BM25 text search index for research
        try:
            await db.research_sources.create_index([("content", "text"), ("title", "text")], name="bm25_tokens", background=True)
        except Exception:
            pass

        # Replay rate limit cleanup
        try:
            await db.replay_rate_limits.create_index("key", unique=True)
        except Exception:
            pass

        # Support ticket org scoping index
        await db.support_tickets.create_index("org_id")

        logger.info("MongoDB indexes created successfully")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")
