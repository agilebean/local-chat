"""Local LLM text generation using MLX."""
import os
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'

from pathlib import Path
from typing import Optional


# Default model path (same as used in youtube_to_speech.py)
DEFAULT_MODEL_PATH = str(
    Path.home() / ".lmstudio" / "models" / "lmstudio-community" / "Qwen3-4B-Instruct-2507-MLX-4bit"
)


class MlxLlm:
    """Wrapper around Qwen3-4B-Instruct loaded via mlx_lm.

    This class keeps the model resident in memory for efficient reuse
    across multiple generate() calls, unlike the original summarize_transcript()
    which reloads on every call.
    """

    def __init__(self, model_path: Optional[str] = None):
        """Initialize the LLM wrapper.

        Args:
            model_path: Path to the MLX model directory.
                       Defaults to Qwen3-4B-Instruct in LM Studio.
        """
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.model = None
        self.tokenizer = None

    def load(self):
        """Lazy-load model and tokenizer (call once, reuse across turns)."""
        if self.model is not None:
            return  # Already loaded

        from mlx_lm import load
        self.model, self.tokenizer = load(self.model_path)

    def generate(
        self,
        messages: list[dict],
        max_tokens: int = 80,
        temp: float = 0.7
    ) -> str:
        """Generate text from a list of chat messages.

        Args:
            messages: Chat messages in OpenAI format:
                     [{"role": "system", "content": "..."},
                      {"role": "user", "content": "..."},
                      {"role": "assistant", "content": "..."}]
                     Supports system, user, assistant roles.
            max_tokens: Maximum tokens to generate.
            temp: Sampling temperature (0.0-1.0).

        Returns:
            Generated text string.
        """
        if self.model is None:
            self.load()

        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        # Apply chat template (Qwen3-Instruct format)
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        # Create sampler with temperature
        sampler = make_sampler(temp=temp)

        # Generate text
        response = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            sampler=sampler
        )

        return response.strip()
