"""Real-time voice-to-voice improv partner conversation loop."""
import os
import warnings
import logging
from pathlib import Path

# Suppress HuggingFace progress bars and warnings
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', message='words count mismatch')

# Suppress huggingface_hub and phonemizer logging
logging.getLogger('huggingface_hub').setLevel(logging.ERROR)
logging.getLogger('phonemizer').setLevel(logging.ERROR)

import time
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from rich.console import Console

from src.llm import MlxLlm
from src.tts import MlxTts, NeuTtsTts
from src.stt import MlxStt
from src.audio_io import AudioRecorder, AudioPlayer

console = Console()

_PROMPT_FILE = Path(__file__).parent / "prompt.md"


def _load_prompt(section: str) -> str:
    """Load a named section from prompt.md."""
    text = _PROMPT_FILE.read_text()
    start = text.find(f"## {section}\n")
    if start == -1:
        raise ValueError(f"Section '{section}' not found in {_PROMPT_FILE}")
    start = text.index("\n", start) + 1
    end = text.find("\n## ", start)
    return text[start:] .strip() if end == -1 else text[start:end].strip()


IMPROV_SYSTEM_PROMPT = _load_prompt("prompt")
IMPROV_SYSTEM_PROMPT_AI_STARTS = _load_prompt("prompt") + "\n\n" + _load_prompt("ai-starts-extra")


@dataclass
class ConversationState:
    """Tracks the conversation history for LLM context."""
    messages: list = field(default_factory=list)
    max_history: int = 20  # Keep last N exchanges to prevent context overflow
    system_prompt: str = IMPROV_SYSTEM_PROMPT

    def __post_init__(self):
        """Initialize with system prompt."""
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def add_user(self, text: str):
        """Add a user message to the conversation history."""
        self.messages.append({"role": "user", "content": text})
        self._trim()

    def add_assistant(self, text: str):
        """Add an assistant message to the conversation history."""
        self.messages.append({"role": "assistant", "content": text})
        self._trim()

    def _trim(self):
        """Keep system prompt + last max_history messages."""
        if len(self.messages) > self.max_history + 1:
            # Keep first message (system prompt) + last max_history messages
            self.messages = [self.messages[0]] + self.messages[-(self.max_history):]


class ImprovSession:
    """Orchestrates the real-time improv conversation loop."""

    def __init__(self, voice: Optional[str] = None, ai_starts: bool = False, llm_variant: str = "2b", tts_backend: str = "kokoro"):
        """Initialize the improv session.

        Args:
            voice: TTS voice preset. Defaults to backend's default voice when None.
            ai_starts: If True, the AI sets the scene on the first turn (default: False).
            llm_variant: LLM size — "0.8b", "2b" (default), "4b", or "qwen3".
            tts_backend: TTS engine — "kokoro" (default) or "neutts-nano".
        """
        self.voice = voice
        self.ai_starts = ai_starts
        self.llm_variant = llm_variant
        self.tts_backend = tts_backend
        prompt = IMPROV_SYSTEM_PROMPT_AI_STARTS if ai_starts else IMPROV_SYSTEM_PROMPT
        self.state = ConversationState(system_prompt=prompt)

        # Initialize components (lazy-loaded)
        from src.llm import MODEL_VARIANTS, _VLM_KEYS
        self.llm = MlxLlm(model_path=MODEL_VARIANTS[llm_variant], use_vlm=(llm_variant in _VLM_KEYS))
        self.tts = MlxTts() if tts_backend == "kokoro" else NeuTtsTts()
        self.stt = MlxStt()
        self.recorder = AudioRecorder()
        self.player = AudioPlayer()

    def load_models(self):
        """Pre-load all three models. Call once at startup."""
        llm_label = "Qwen3-4B-Instruct" if self.llm_variant == "qwen3" else f"Qwen3.5-{self.llm_variant.upper()}"
        tts_label = "NeuTTS-Nano" if self.tts_backend == "neutts-nano" else "Kokoro-82M"
        console.print("\n🎭 Loading models for improv session...", style="cyan bold")
        console.print(f"   Loading LLM ({llm_label})...", style="dim")
        self.llm.load()
        console.print(f"   Loading TTS ({tts_label})...", style="dim")
        self.tts.load()
        console.print("   Loading STT (Parakeet 110M)...", style="dim")
        self.stt.load()
        prompt_tokens = len(self.llm.tokenizer.encode(self.state.messages[0]["content"]))
        console.print(f"✓ All models loaded. Prompt: {prompt_tokens}tok. Ready to improv!", style="green bold")
        console.print("\n💡 Tip: Say 'end scene', 'and scene', or press Ctrl+C to exit\n", style="yellow dim")

    def run(self):
        """Main conversation loop."""
        self.load_models()

        if self.ai_starts:
            self._ai_turn_initial()

        # Main loop
        while True:
            try:
                # 1. Record user speech
                console.print("\n[Your turn - speak!]", style="bold yellow")
                audio = self.recorder.record_until_silence()

                # 2. Transcribe
                console.print("   (Transcribing...)", style="dim")

                # Check if audio was actually captured
                audio_level = np.max(np.abs(audio))

                # If audio is essentially silence, skip transcription
                if audio_level < 0.01:
                    console.print("   [No audio detected - skipping turn]", style="yellow dim")
                    continue

                _t0 = time.perf_counter()
                user_text = self.stt.transcribe(audio)
                _stt_s = time.perf_counter() - _t0
                # Clean up obvious repetition errors from STT
                user_text = self._clean_repetitions(user_text)

                # If transcription is empty or too short, skip this turn
                if not user_text or len(user_text.strip()) < 3:
                    console.print("   [Transcription unclear - try speaking louder]", style="yellow dim")
                    continue

                console.print(f"   You: {user_text} [STT: {_stt_s:.2f}s]", style="yellow")

                # 3. Check for exit commands
                if self._is_exit_command(user_text):
                    console.print("\n🎬 Scene! Great improv session!", style="green bold")
                    break

                # 4. LLM generates response
                self.state.add_user(user_text)
                console.print("   (Thinking...)", style="dim")
                _t0 = time.perf_counter()
                response = self.llm.generate(
                    self.state.messages,
                    max_tokens=35,  # 1-2 short sentences
                    temp=0.95
                )
                _llm_s = time.perf_counter() - _t0

                raw_len = len(response)
                response = self._truncate_to_sentences(response, max_sentences=2)
                cut = raw_len - len(response)
                gt = self.llm.last_gen_tokens
                tps = gt / _llm_s if _llm_s > 0 else 0
                console.print(f"   [{gt}tok {tps:.0f}tok/s | cut {cut}char | LLM: {_llm_s:.2f}s]", style="dim")

                # Fallback if empty
                if not response or len(response.strip()) < 5:
                    response = "That's exactly what I was thinking."
                    console.print("   [Used fallback - LLM returned empty]", style="yellow dim")

                self.state.add_assistant(response)
                console.print(f"   AI: {response}", style="cyan")

                # 5. TTS speaks the response (strip out stage directions)
                console.print("   (Speaking...)", style="dim")
                speech_text = self._strip_stage_directions(response)
                _tts_inline = getattr(self.tts, "streams_inline", False)
                _tts_cb = (lambda lat: console.print(f"   [TTS: {lat:.2f}s]", style="dim")) if _tts_inline else None
                audio_out, sr = self.tts.synthesize(speech_text, voice=self.voice, on_first_chunk=_tts_cb)
                if not _tts_inline:
                    console.print(f"   [TTS: {self.tts.last_latency_s:.2f}s]", style="dim")
                    self.player.play(audio_out, sr)

            except KeyboardInterrupt:
                console.print("\n\n🎬 Scene! (Ctrl+C) Great session!", style="green bold")
                break
            except Exception as e:
                console.print(f"\n❌ Error: {e}", style="red")
                console.print("Continuing...", style="yellow")
                continue

    def _ai_turn_initial(self):
        """AI's opening turn -- establish base reality with one sentence."""
        console.print("\n[AI's turn]", style="bold cyan")
        console.print("   (Thinking...)", style="dim")
        _t0 = time.perf_counter()
        response = self.llm.generate(
            self.state.messages,
            max_tokens=25,  # One short sentence to set the scene
            temp=0.95
        )
        _llm_s = time.perf_counter() - _t0

        raw_len = len(response)
        response = self._truncate_to_sentences(response, max_sentences=1)
        cut = raw_len - len(response)
        gt = self.llm.last_gen_tokens
        tps = gt / _llm_s if _llm_s > 0 else 0
        console.print(f"   [{gt}tok {tps:.0f}tok/s | cut {cut}char | LLM: {_llm_s:.2f}s]", style="dim")

        # Fallback if empty
        if not response or len(response.strip()) < 5:
            response = "I'm a detective at the station, and this coffee is terrible."
            console.print("   [Used fallback - LLM returned empty]", style="yellow dim")

        self.state.add_assistant(response)
        console.print(f"   AI: {response}", style="cyan")

        console.print("   (Speaking...)", style="dim")
        speech_text = self._strip_stage_directions(response)
        _tts_inline = getattr(self.tts, "streams_inline", False)
        _tts_cb = (lambda lat: console.print(f"   [TTS: {lat:.2f}s]", style="dim")) if _tts_inline else None
        audio_out, sr = self.tts.synthesize(speech_text, voice=self.voice, on_first_chunk=_tts_cb)
        if not _tts_inline:
            console.print(f"   [TTS: {self.tts.last_latency_s:.2f}s]", style="dim")
            self.player.play(audio_out, sr)

    def _strip_stage_directions(self, text: str) -> str:
        """Remove stage directions in asterisks from text before TTS.

        Args:
            text: Text with potential stage directions like *snaps fingers*.

        Returns:
            Text with stage directions removed.
        """
        import re
        # Remove anything in asterisks (stage directions)
        cleaned = re.sub(r'\*[^*]+\*', '', text)
        # Clean up extra spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def _clean_repetitions(self, text: str) -> str:
        """Clean up obvious word repetitions from STT errors.

        Args:
            text: Text with potential repetitions.

        Returns:
            Cleaned text with repetitions removed.
        """
        import re
        # Remove 3+ consecutive identical words (keep max 2)
        # Pattern: match word followed by same word 2+ more times
        def remove_excess_repeats(match):
            word = match.group(1)
            return f"{word} {word}"  # Keep max 2 repetitions

        # Match word boundary, word, then same word repeated 2+ times
        pattern = r'\b(\w+)(?:\s+\1){2,}'
        cleaned = re.sub(pattern, remove_excess_repeats, text, flags=re.IGNORECASE)

        return cleaned.strip()

    def _truncate_to_sentences(self, text: str, max_sentences: int) -> str:
        """Truncate text to maximum number of sentences.

        Uses word-based splitting to avoid cutting on abbreviation dots
        like 'vs.', 'Mr.', 'Dr.' (≤2 chars before the period).
        """
        text = text.strip()
        if not text:
            return text

        sentences = []
        current = []

        for word in text.split():
            current.append(word)
            last = word[-1]
            core = word.rstrip('.!?')
            # A real sentence end: ! or ?, or . after a word longer than 2 chars
            # Also require at least 3 words — prevents single-word affirmatives
            # like "Exactly." from being isolated as standalone sentences
            if (last in '!?' or (last == '.' and len(core) > 2)) and len(current) >= 3:
                sentences.append(' '.join(current))
                current = []

        # If no complete sentences (LLM cut off mid-sentence), use raw text
        if not sentences:
            tail = ' '.join(current)
            return (tail if tail[-1] in '.!?' else tail + '.') if tail else ''

        # If there's a trailing fragment and room for it, include it rather than drop it
        if current and len(sentences) < max_sentences:
            tail = ' '.join(current)
            sentences.append(tail if tail[-1] in '.!?' else tail + '.')

        result = ' '.join(sentences[:max_sentences])
        return result

    @staticmethod
    def _is_exit_command(text: str) -> bool:
        """Check if user wants to end the session."""
        exit_phrases = ["end scene", "and scene", "scene", "stop", "quit", "exit", "goodbye", "bye"]
        text_lower = text.lower().strip().rstrip(".,!?;:")
        return any(
            text_lower == phrase or text_lower.startswith(phrase + " ")
            for phrase in exit_phrases
        )
