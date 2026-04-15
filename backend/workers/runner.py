from __future__ import annotations

from backend.core.settings import get_settings


def main() -> None:
    try:
        from redis import Redis
        from rq import Queue, Worker
    except ImportError as exc:
        raise RuntimeError("Install redis and rq before running workers") from exc

    settings = get_settings()
    connection = Redis.from_url(settings.redis_url)
    queues = [Queue(name, connection=connection) for name in ("high", "default", "scheduled", "analysis")]
    Worker(queues, connection=connection).work()


if __name__ == "__main__":
    main()

