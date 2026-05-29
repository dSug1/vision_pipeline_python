"""Sound output.

`ISoundEngine` is the portable seam. The default debug engine just logs strikes;
the on-screen 'light signal' is rendered by the Visualizer (also a StrikeEvent
consumer). A real audio engine is added later with a license-free library (TBD).
Self-contained (no imports outside this app). See spec section 8.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict

from core.contracts import FingerId, StrikeEvent
from core.events import EventBus


class ISoundEngine(ABC):
    @abstractmethod
    def play(self, finger_id: FingerId) -> None:
        ...


class LoggingSoundEngine(ISoundEngine):
    """Debug engine: prints each strike. Subscribes to StrikeEvent on the bus."""

    def __init__(self, bus: EventBus, finger_sounds: Dict[FingerId, str]) -> None:
        self._sounds = finger_sounds
        bus.subscribe(StrikeEvent, self._on_strike)

    def _on_strike(self, event: StrikeEvent) -> None:
        self.play(event.finger_id)

    def play(self, finger_id: FingerId) -> None:
        print(f"[drum] {finger_id.value} -> {self._sounds.get(finger_id, '<unmapped>')}")


class AudioSoundEngine(ISoundEngine):
    """TODO: play a per-finger one-shot sample via a license-free audio library
    (candidates in spec section 8). Not yet implemented."""

    def __init__(self, bus: EventBus, finger_sounds: Dict[FingerId, str]) -> None:
        raise NotImplementedError(
            "AudioSoundEngine: choose a license-free audio library first (see spec section 8)."
        )

    def play(self, finger_id: FingerId) -> None:  # pragma: no cover
        raise NotImplementedError
