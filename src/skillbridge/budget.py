"""Token budget meter.

Tracks tokens consumed across a run and reports when the budget is spent,
so the loop can stop and return a partial answer instead of running forever.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Budget:
    limit: int = 6000
    used: int = 0

    def spend(self, tokens: int) -> None:
        self.used += max(0, int(tokens))

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    def exceeded(self) -> bool:
        return self.used >= self.limit
