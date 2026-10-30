import threading
import uuid

from .pricing import cost_usd


class UsageLedger:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, list[dict]] = {}

    def open(self) -> str:
        token = uuid.uuid4().hex
        with self._lock:
            self._entries[token] = []
        return token

    def record(self, token: str, model: str, input_tokens: int, output_tokens: int) -> None:
        with self._lock:
            bucket = self._entries.get(token.removesuffix("-local"))
            if bucket is None:
                return
            bucket.append(
                {
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                }
            )

    def close(self, token: str) -> dict:
        with self._lock:
            entries = self._entries.pop(token.removesuffix("-local"), [])
        if not entries:
            return {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
        return {
            "calls": len(entries),
            "model": entries[0]["model"],
            "input_tokens": sum(e["input_tokens"] for e in entries),
            "output_tokens": sum(e["output_tokens"] for e in entries),
            "cost_usd": round(
                sum(cost_usd(e["model"], e["input_tokens"], e["output_tokens"]) for e in entries),
                6,
            ),
        }


ledger = UsageLedger()
