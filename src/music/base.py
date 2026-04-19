from abc import ABC, abstractmethod
from pathlib import Path

class MusicGenerator(ABC):
    """Abstract base class for music generation strategies."""

    @abstractmethod
    def generate(self, prompt: str, output_path: Path, duration: float, instrumental: bool = False) -> float:
        """
        Generate music based on a prompt.

        Args:
            prompt: Text description of the music style.
            output_path: Path where the audio file should be saved.
            duration: Target duration in seconds.
            instrumental: Whether to generate instrumental music (no vocals).

        Returns:
            Actual duration of the generated audio in seconds.
        """
        pass
