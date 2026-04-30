"""Monitor protocol/interface for Experiment 005: Reasoning Monitor Agent."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


@dataclass
class MonitorVerdict:
    """Result of a monitor evaluation."""

    verdict: Literal["clean", "suspicious"]
    confidence: float  # 0.0-1.0
    reason: str
    technique: str  # "llm", "canary", "tool_allowlist"

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")


class Monitor(ABC):
    """Base class for all reasoning monitors."""

    @abstractmethod
    def evaluate(self, transcript: list[dict]) -> MonitorVerdict:
        """Evaluate a stripped agent transcript for signs of compromise.

        Args:
            transcript: List of transcript entries (dicts with role, content, etc.).
                        Must NOT include the initial user message content — the monitor
                        is deliberately blind to the original inputs.

        Returns:
            MonitorVerdict with verdict, confidence, reason, and technique.
        """
