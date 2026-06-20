"""Thread-safe Server-Sent Events broadcaster."""
from __future__ import annotations

import queue
import threading


class SSEBroadcaster:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queues: list[queue.Queue] = []

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=100)
        with self._lock:
            self._queues.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._queues = [x for x in self._queues if x is not q]

    def publish(self, event_type: str, payload: dict) -> None:
        msg = {"type": event_type, "payload": payload}
        from db import insert_live_feed_event

        insert_live_feed_event(event_type, payload)
        with self._lock:
            dead: list[queue.Queue] = []
            for client_q in self._queues:
                try:
                    client_q.put_nowait(msg)
                except queue.Full:
                    dead.append(client_q)
            for d in dead:
                if d in self._queues:
                    self._queues.remove(d)


broadcaster = SSEBroadcaster()
