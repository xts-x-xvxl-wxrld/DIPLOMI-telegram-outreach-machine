# ruff: noqa: F401,F403,F405
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.deps import require_bot_token
from backend.api.routes import engagement_targets as _engagement_targets
from backend.api.routes import engagement_settings_topics as _engagement_settings_topics
from backend.api.routes import engagement_prompts_style as _engagement_prompts_style
from backend.api.routes import engagement_candidates_actions as _engagement_candidates_actions
from backend.api.routes import engagement_cockpit as _engagement_cockpit
from backend.api.routes import engagement_task_first as _engagement_task_first
from backend.queue.client import (
    enqueue_community_join,
    enqueue_collection,
    enqueue_engagement_send,
    enqueue_engagement_target_resolve,
    enqueue_manual_engagement_detect,
)
from backend.services.community_engagement import (
    list_engagement_actions,
    list_engagement_candidates,
)

router = APIRouter(dependencies=[Depends(require_bot_token)])
router.include_router(_engagement_targets.router)
router.include_router(_engagement_settings_topics.router)
router.include_router(_engagement_prompts_style.router)
router.include_router(_engagement_candidates_actions.router)
router.include_router(_engagement_cockpit.router)
router.include_router(_engagement_task_first.router)

_SYNC_NAMES = (
    "enqueue_community_join",
    "enqueue_collection",
    "enqueue_engagement_send",
    "enqueue_engagement_target_resolve",
    "enqueue_manual_engagement_detect",
    "list_engagement_actions",
    "list_engagement_candidates",
)
_MODULES = (
    _engagement_targets,
    _engagement_settings_topics,
    _engagement_prompts_style,
    _engagement_candidates_actions,
    _engagement_cockpit,
    _engagement_task_first,
)


def _sync_route_dependencies() -> None:
    for module in _MODULES:
        for name in _SYNC_NAMES:
            if hasattr(module, name):
                setattr(module, name, globals()[name])

async def get_operator_capabilities(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_targets.get_operator_capabilities(*args, **kwargs)


async def get_engagement_targets(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_targets.get_engagement_targets(*args, **kwargs)


async def get_engagement_target_detail(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_targets.get_engagement_target_detail(*args, **kwargs)


async def post_engagement_target(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_targets.post_engagement_target(*args, **kwargs)


async def patch_engagement_target(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_targets.patch_engagement_target(*args, **kwargs)


async def post_engagement_target_resolve_job(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_targets.post_engagement_target_resolve_job(*args, **kwargs)


async def post_engagement_target_join_job(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_targets.post_engagement_target_join_job(*args, **kwargs)


async def post_engagement_target_collection_job(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_targets.post_engagement_target_collection_job(*args, **kwargs)


async def get_engagement_target_collection_runs(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_targets.get_engagement_target_collection_runs(*args, **kwargs)


async def post_engagement_target_detect_job(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_targets.post_engagement_target_detect_job(*args, **kwargs)


async def get_community_engagement_settings(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_settings_topics.get_community_engagement_settings(*args, **kwargs)


async def put_community_engagement_settings(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_settings_topics.put_community_engagement_settings(*args, **kwargs)


async def get_engagement_topics(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_settings_topics.get_engagement_topics(*args, **kwargs)


async def get_engagement_topic_detail(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_settings_topics.get_engagement_topic_detail(*args, **kwargs)


async def post_engagement_topic(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_settings_topics.post_engagement_topic(*args, **kwargs)


async def patch_engagement_topic(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_settings_topics.patch_engagement_topic(*args, **kwargs)


async def post_engagement_topic_example(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_settings_topics.post_engagement_topic_example(*args, **kwargs)


async def delete_engagement_topic_example(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_settings_topics.delete_engagement_topic_example(*args, **kwargs)


async def post_community_join_job(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_settings_topics.post_community_join_job(*args, **kwargs)


async def post_community_engagement_detect_job(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_settings_topics.post_community_engagement_detect_job(*args, **kwargs)


async def get_engagement_prompt_profiles(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_prompts_style.get_engagement_prompt_profiles(*args, **kwargs)


async def post_engagement_prompt_profile(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_prompts_style.post_engagement_prompt_profile(*args, **kwargs)


async def get_engagement_prompt_profile(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_prompts_style.get_engagement_prompt_profile(*args, **kwargs)


async def patch_engagement_prompt_profile(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_prompts_style.patch_engagement_prompt_profile(*args, **kwargs)


async def post_engagement_prompt_profile_activate(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_prompts_style.post_engagement_prompt_profile_activate(*args, **kwargs)


async def post_engagement_prompt_profile_duplicate(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_prompts_style.post_engagement_prompt_profile_duplicate(*args, **kwargs)


async def post_engagement_prompt_profile_rollback(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_prompts_style.post_engagement_prompt_profile_rollback(*args, **kwargs)


async def post_engagement_prompt_profile_preview(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_prompts_style.post_engagement_prompt_profile_preview(*args, **kwargs)


async def get_engagement_prompt_profile_versions(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_prompts_style.get_engagement_prompt_profile_versions(*args, **kwargs)


async def get_engagement_style_rules(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_prompts_style.get_engagement_style_rules(*args, **kwargs)


async def get_engagement_style_rule_detail(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_prompts_style.get_engagement_style_rule_detail(*args, **kwargs)


async def post_engagement_style_rule(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_prompts_style.post_engagement_style_rule(*args, **kwargs)


async def patch_engagement_style_rule(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_prompts_style.patch_engagement_style_rule(*args, **kwargs)


async def get_engagement_candidates(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_candidates_actions.get_engagement_candidates(*args, **kwargs)


async def get_engagement_candidate_detail(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_candidates_actions.get_engagement_candidate_detail(*args, **kwargs)


async def get_engagement_candidate_revisions(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_candidates_actions.get_engagement_candidate_revisions(*args, **kwargs)


async def get_engagement_actions(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_candidates_actions.get_engagement_actions(*args, **kwargs)


async def get_engagement_semantic_rollout(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_candidates_actions.get_engagement_semantic_rollout(*args, **kwargs)


async def get_engagement_cockpit_home(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_cockpit.get_engagement_cockpit_home(*args, **kwargs)


async def get_engagement_cockpit_approvals(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_cockpit.get_engagement_cockpit_approvals(*args, **kwargs)


async def get_engagement_cockpit_scoped_approvals(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_cockpit.get_engagement_cockpit_scoped_approvals(*args, **kwargs)


async def get_engagement_cockpit_issues(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_cockpit.get_engagement_cockpit_issues(*args, **kwargs)


async def get_engagement_cockpit_scoped_issues(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_cockpit.get_engagement_cockpit_scoped_issues(*args, **kwargs)


async def get_engagement_cockpit_engagements(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_cockpit.get_engagement_cockpit_engagements(*args, **kwargs)


async def get_engagement_cockpit_engagement_detail(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_cockpit.get_engagement_cockpit_engagement_detail(*args, **kwargs)


async def get_engagement_cockpit_sent(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_cockpit.get_engagement_cockpit_sent(*args, **kwargs)


async def post_engagement_cockpit_draft_approve(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_cockpit.post_engagement_cockpit_draft_approve(*args, **kwargs)


async def post_engagement_cockpit_draft_reject(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_cockpit.post_engagement_cockpit_draft_reject(*args, **kwargs)


async def post_engagement_cockpit_draft_edit(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_cockpit.post_engagement_cockpit_draft_edit(*args, **kwargs)


async def post_engagement_cockpit_issue_action(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_cockpit.post_engagement_cockpit_issue_action(*args, **kwargs)


async def get_engagement_cockpit_issue_rate_limit(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_cockpit.get_engagement_cockpit_issue_rate_limit(*args, **kwargs)


async def get_engagement_cockpit_quiet_hours(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_cockpit.get_engagement_cockpit_quiet_hours(*args, **kwargs)


async def put_engagement_cockpit_quiet_hours(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_cockpit.put_engagement_cockpit_quiet_hours(*args, **kwargs)


async def post_engagement_candidate_approve(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_candidates_actions.post_engagement_candidate_approve(*args, **kwargs)


async def post_engagement_candidate_edit(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_candidates_actions.post_engagement_candidate_edit(*args, **kwargs)


async def post_engagement_candidate_reject(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_candidates_actions.post_engagement_candidate_reject(*args, **kwargs)


async def post_engagement_candidate_expire(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_candidates_actions.post_engagement_candidate_expire(*args, **kwargs)


async def post_engagement_candidate_retry(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_candidates_actions.post_engagement_candidate_retry(*args, **kwargs)


async def post_engagement_candidate_send_job(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_candidates_actions.post_engagement_candidate_send_job(*args, **kwargs)


async def post_task_first_engagement(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_task_first.post_task_first_engagement(*args, **kwargs)


async def patch_engagement(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_task_first.patch_engagement(*args, **kwargs)


async def put_task_first_settings(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_task_first.put_task_first_settings(*args, **kwargs)


async def post_task_first_wizard_confirm(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_task_first.post_task_first_wizard_confirm(*args, **kwargs)


async def post_task_first_wizard_retry(*args, **kwargs):
    _sync_route_dependencies()
    return await _engagement_task_first.post_task_first_wizard_retry(*args, **kwargs)


__all__ = ["router", "enqueue_community_join", "enqueue_collection", "enqueue_engagement_send", "enqueue_engagement_target_resolve", "enqueue_manual_engagement_detect", "list_engagement_actions", "list_engagement_candidates",
    "get_operator_capabilities",
    "get_engagement_targets",
    "get_engagement_target_detail",
    "post_engagement_target",
    "patch_engagement_target",
    "post_engagement_target_resolve_job",
    "post_engagement_target_join_job",
    "post_engagement_target_collection_job",
    "get_engagement_target_collection_runs",
    "post_engagement_target_detect_job",
    "get_community_engagement_settings",
    "put_community_engagement_settings",
    "get_engagement_topics",
    "get_engagement_topic_detail",
    "post_engagement_topic",
    "patch_engagement_topic",
    "post_engagement_topic_example",
    "delete_engagement_topic_example",
    "post_community_join_job",
    "post_community_engagement_detect_job",
    "get_engagement_prompt_profiles",
    "post_engagement_prompt_profile",
    "get_engagement_prompt_profile",
    "patch_engagement_prompt_profile",
    "post_engagement_prompt_profile_activate",
    "post_engagement_prompt_profile_duplicate",
    "post_engagement_prompt_profile_rollback",
    "post_engagement_prompt_profile_preview",
    "get_engagement_prompt_profile_versions",
    "get_engagement_style_rules",
    "get_engagement_style_rule_detail",
    "post_engagement_style_rule",
    "patch_engagement_style_rule",
    "get_engagement_candidates",
    "get_engagement_candidate_detail",
    "get_engagement_candidate_revisions",
    "get_engagement_actions",
    "get_engagement_semantic_rollout",
    "get_engagement_cockpit_home",
    "get_engagement_cockpit_approvals",
    "get_engagement_cockpit_scoped_approvals",
    "get_engagement_cockpit_issues",
    "get_engagement_cockpit_scoped_issues",
    "get_engagement_cockpit_engagements",
    "get_engagement_cockpit_engagement_detail",
    "get_engagement_cockpit_sent",
    "post_engagement_cockpit_draft_approve",
    "post_engagement_cockpit_draft_reject",
    "post_engagement_cockpit_draft_edit",
    "post_engagement_cockpit_issue_action",
    "get_engagement_cockpit_issue_rate_limit",
    "get_engagement_cockpit_quiet_hours",
    "put_engagement_cockpit_quiet_hours",
    "post_engagement_candidate_approve",
    "post_engagement_candidate_edit",
    "post_engagement_candidate_reject",
    "post_engagement_candidate_expire",
    "post_engagement_candidate_retry",
    "post_engagement_candidate_send_job",
    "post_task_first_engagement",
    "patch_engagement",
    "put_task_first_settings",
    "post_task_first_wizard_confirm",
    "post_task_first_wizard_retry",
]
