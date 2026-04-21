from __future__ import annotations

import pytest

from backend.services.community_engagement import EngagementValidationError, render_prompt_template


def test_prompt_rendering_allows_only_control_plane_variables() -> None:
    rendered = render_prompt_template(
        "Topic {{topic.name}}\nStyle {{style.community}}\nSource {{source_post.text}}\nReply {{reply_context}}",
        {
            "topic": {"name": "CRM"},
            "style": {"community": ["Keep it brief."]},
            "source_post": {"text": "Comparing CRM tools."},
            "reply_context": "A prior message asks about migration effort.",
        },
    )

    assert "CRM" in rendered
    assert "Keep it brief." in rendered
    assert "Comparing CRM tools." in rendered
    assert "migration effort" in rendered


def test_prompt_rendering_rejects_sender_identity_variables() -> None:
    with pytest.raises(EngagementValidationError) as exc_info:
        render_prompt_template("Sender {{sender.username}}", {"sender": {"username": "private"}})

    assert exc_info.value.code == "invalid_prompt_variable"
