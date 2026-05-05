from __future__ import annotations

import logging

from backend.core.settings import get_settings

LOGGER = logging.getLogger(__name__)


def main() -> None:
    try:
        from redis import Redis
        from rq import Queue, Worker
    except ImportError as exc:
        raise RuntimeError("Install redis and rq before running workers") from exc

    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )
    connection = Redis.from_url(settings.redis_url)
    queue_names = ("high", "default", "scheduled", "analysis", "engagement")
    queues = [
        Queue(name, connection=connection)
        for name in queue_names
    ]
    LOGGER.info("Starting RQ worker for queues=%s redis_url=%s", ",".join(queue_names), settings.redis_url)
    Worker(queues, connection=connection).work(with_scheduler=True)


if __name__ == "__main__":
    main()
