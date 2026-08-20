"""Full-history JSON API rendering from frozen public contracts."""

from __future__ import annotations

import json
from pathlib import PurePosixPath

from pydantic import BaseModel

from paperflow.render.view_models import PublicProjection


def render_json_files(projection: PublicProjection) -> dict[PurePosixPath, str]:
    files: dict[PurePosixPath, str] = {
        PurePosixPath("data/feed_index.json"): _json(projection.feed_index()),
        PurePosixPath("data/topics.json"): _json(projection.topics_index()),
    }
    for day, feed in projection.daily_feeds().items():
        files[PurePosixPath("data/daily_feeds", f"{day}.json")] = _json(feed)
    for topic in projection.topics:
        files[PurePosixPath("data/topic_feeds", topic.id, "all.json")] = _json(
            projection.topic_feed(topic.id)
        )
        for subtopic in topic.subtopics:
            files[
                PurePosixPath(
                    "data/topic_feeds", topic.id, f"{subtopic.id}.json"
                )
            ] = _json(projection.topic_feed(topic.id, subtopic.id))
    return files


def _json(model: BaseModel) -> str:
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
