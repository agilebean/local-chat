"""MLX MusicGen adapter.

Wraps the vendored `src/music/musicgen` package (originally from
ml-explore/mlx-examples) behind the `MusicGenerator` interface.
"""
from pathlib import Path
from rich.console import Console

from .base import MusicGenerator
from .musicgen import MusicGen, save_audio

console = Console()


class MlxMusicGenerator(MusicGenerator):
    """Generate music using MLX MusicGen (local, Apple Silicon)."""

    # ~55 generation steps per second of audio (MusicGen default)
    STEPS_PER_SECOND = 55

    def __init__(self, model_name: str = "facebook/musicgen-small"):
        self.model_name = model_name
        self.model = None

    def load_model(self) -> None:
        """Lazy-load the MLX MusicGen model on first use."""
        if self.model is not None:
            return

        console.print(f"🎵 Loading MLX music model: {self.model_name}...", style="cyan")
        try:
            self.model = MusicGen.from_pretrained(self.model_name)
            console.print("✓ MLX model loaded successfully!", style="green")
        except Exception as e:
            console.print(f"❌ Error loading MLX music model: {e}", style="red")
            raise

    def generate(
        self,
        prompt: str,
        output_path: Path,
        duration: float,
        instrumental: bool = False,
    ) -> float:
        """Generate `duration` seconds of music from a text prompt.

        `instrumental` is ignored — MLX MusicGen always produces instrumental audio.
        Returns the actual audio duration in seconds.
        """
        self.load_model()

        max_steps = int(duration * self.STEPS_PER_SECOND)
        console.print(f"🎵 Generating {duration:.1f}s music with MLX...", style="cyan")
        console.print(f"   Prompt: {prompt}", style="dim")

        try:
            audio = self.model.generate(
                text=prompt,
                max_steps=max_steps,
                top_k=250,
                temp=1.0,
                guidance_coef=3.0,
            )
            sample_rate = self.model.sampling_rate

            if audio.ndim > 1:
                audio = audio.flatten()

            console.print(f"   Saving to {output_path}...", style="dim")
            save_audio(str(output_path), audio, sample_rate)

            actual_duration = float(audio.shape[0]) / sample_rate
            console.print(f"✓ Music generated: {actual_duration:.1f}s", style="green")
            return actual_duration

        except Exception as e:
            console.print(f"❌ Error during music generation: {e}", style="red")
            raise
