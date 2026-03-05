"""Local LLM text generation using MLX."""
import os
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'

from pathlib import Path
from typing import Optional


_MODELS = Path.home() / ".lmstudio" / "models"

MODEL_VARIANTS = {
    "qwen3": str(_MODELS / "lmstudio-community" / "Qwen3-4B-Instruct-2507-MLX-4bit"),
    "0.8b":  str(_MODELS / "mlx-community" / "Qwen3.5-0.8B-MLX-4bit"),
    "2b":    str(_MODELS / "mlx-community" / "Qwen3.5-2B-MLX-4bit"),
    "4b":    str(_MODELS / "mlx-community" / "Qwen3.5-4B-MLX-4bit"),
}

# Qwen3.5 variants are multimodal weight files; load with strict=False to use
# only the language model portion (vision tower weights are silently skipped).
_VLM_KEYS = {"0.8b", "2b", "4b"}

DEFAULT_MODEL_PATH = MODEL_VARIANTS["2b"]


class MlxLlm:
    """Wrapper around an MLX language model.

    Uses mlx_lm for all variants.  For Qwen3.5 (multimodal) models the
    weights are loaded with strict=False so vision-tower parameters are
    silently skipped; text generation works normally.
    """

    def __init__(self, model_path: Optional[str] = None, use_vlm: bool = False):
        """Initialize the LLM wrapper.

        Args:
            model_path: Path to the MLX model directory.
                       Defaults to Qwen3.5-2B (DEFAULT_MODEL_PATH).
            use_vlm: True for Qwen3.5 variants (loads with strict=False).
        """
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.use_vlm = use_vlm
        self.model = None
        self.tokenizer = None
        self.last_prompt_tokens: int = 0
        self.last_gen_tokens: int = 0

    def load(self):
        """Lazy-load model and tokenizer (call once, reuse across turns)."""
        if self.model is not None:
            return

        from mlx_lm.utils import load_model, load_tokenizer
        from pathlib import Path

        model_path = Path(self.model_path)
        if self.use_vlm:
            # Qwen3.5 weights include vision-tower params unknown to mlx_lm's
            # text-only architecture; strict=False silently skips them.
            self.model, _ = load_model(model_path, strict=False)
        else:
            self.model, _ = load_model(model_path)

        self.tokenizer = load_tokenizer(model_path)

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
            max_tokens: Maximum tokens to generate.
            temp: Sampling temperature (0.0-1.0).

        Returns:
            Generated text string.
        """
        if self.model is None:
            self.load()

        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        self.last_prompt_tokens = len(self.tokenizer.encode(prompt))
        sampler = make_sampler(temp=temp, min_p=0.05, top_k=50)
        response = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            sampler=sampler
        )
        response = response.strip()
        self.last_gen_tokens = len(self.tokenizer.encode(response))
        return response
