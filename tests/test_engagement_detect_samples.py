from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.db.enums import CollectionRunStatus
from backend.db.models import CollectionRun, Message
from backend.workers.engagement_detect import load_recent_detection_samples
from tests.test_engagement_detect_worker import DetectionSampleSession, _community


@pytest.mark.asyncio
async def test_detection_samples_prefer_exact_collection_run_batch() -> None:
    community_id = uuid4()
    collection_run_id = uuid4()
    now = datetime.now(timezone.utc)
    community = _community(community_id)
    community.store_messages = True
    run = CollectionRun(
        id=collection_run_id,
        community_id=community_id,
        status=CollectionRunStatus.COMPLETED.value,
        analysis_input={
            "engagement_messages": [
                {
                    "tg_message_id": 200,
                    "text": "Exact batch CRM question",
                    "message_date": now.isoformat(),
                    "is_replyable": True,
                }
            ],
        },
    )
    stored = Message(
        id=uuid4(),
        community_id=community_id,
        tg_message_id=100,
        text="Stored fallback CRM question",
        message_date=now,
    )

    messages = await load_recent_detection_samples(
        DetectionSampleSession(runs={collection_run_id: run}, stored_messages=[stored]),
        community=community,
        collection_run_id=collection_run_id,
        window_minutes=60,
    )

    assert [message.tg_message_id for message in messages] == [200]
    assert messages[0].text == "Exact batch CRM question"


@pytest.mark.asyncio
async def test_detection_samples_skip_wrong_community_collection_run() -> None:
    community_id = uuid4()
    other_community_id = uuid4()
    collection_run_id = uuid4()
    now = datetime.now(timezone.utc)
    community = _community(community_id)
    community.store_messages = True
    run = CollectionRun(
        id=collection_run_id,
        community_id=other_community_id,
        status=CollectionRunStatus.COMPLETED.value,
        analysis_input={
            "engagement_messages": [
                {
                    "tg_message_id": 200,
                    "text": "Wrong community batch",
                    "message_date": now.isoformat(),
                    "is_replyable": True,
                }
            ],
        },
    )
    stored = Message(
        id=uuid4(),
        community_id=community_id,
        tg_message_id=100,
        text="Stored fallback should not be used",
        message_date=now,
    )

    messages = await load_recent_detection_samples(
        DetectionSampleSession(runs={collection_run_id: run}, stored_messages=[stored]),
        community=community,
        collection_run_id=collection_run_id,
        window_minutes=60,
    )

    assert messages == []


@pytest.mark.asyncio
async def test_detection_samples_fall_back_to_latest_engagement_artifact_batch() -> None:
    community_id = uuid4()
    now = datetime.now(timezone.utc)
    community = _community(community_id)
    artifact_run = CollectionRun(
        id=uuid4(),
        community_id=community_id,
        status=CollectionRunStatus.COMPLETED.value,
        analysis_input={
            "engagement_messages": [
                {
                    "tg_message_id": 300,
                    "text": "Latest engagement artifact CRM question",
                    "message_date": now.isoformat(),
                    "is_replyable": True,
                }
            ],
        },
    )

    messages = await load_recent_detection_samples(
        DetectionSampleSession(artifact_runs=[artifact_run]),
        community=community,
        window_minutes=60,
    )

    assert [message.tg_message_id for message in messages] == [300]
    assert messages[0].text == "Latest engagement artifact CRM question"
