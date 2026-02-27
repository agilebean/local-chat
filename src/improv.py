"""Real-time voice-to-voice improv partner conversation loop."""
import os
import warnings
import logging

# Suppress HuggingFace progress bars and warnings
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)

# Suppress huggingface_hub logging
logging.getLogger('huggingface_hub').setLevel(logging.ERROR)

from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from rich.console import Console

from src.llm import MlxLlm
from src.tts import MlxTts
from src.stt import MlxStt
from src.audio_io import AudioRecorder, AudioPlayer

console = Console()


IMPROV_SYSTEM_PROMPT = """You are a skilled theatrical improv partner.

GOLDEN RULE: YES-AND. Always ACCEPT what your partner says and ADD to it. Never deny, negate, or ignore.

How to respond:
1. ACCEPT what they just said as true
2. BUILD on it with something new and related
3. Keep it SHORT: 1-2 sentences maximum
4. React naturally - DON'T repeat their exact words

Format:
- FIRST turn ONLY: "I'm [character] at [place], and [situation]." (one sentence)
  - Use REALISTIC, EVERYDAY settings: office, coffee shop, apartment, store, park, bus, etc.
  - NO fantasy: no vampires, zombies, dragons, magic, space, apocalypse scenarios
- ALL OTHER turns: React naturally and add something new

Examples of GOOD yes-and:
Partner: "The coffee is really cold."
You: "I just made it five minutes ago!" (accepts + adds new info)

Partner: "Did you hear that noise upstairs?"
You: "It's been going on for an hour now." (accepts + adds new info)

Partner: "The whole event was like a wine tasting party."
You: "I saw the photos - everyone looked so fancy!" (accepts + builds naturally)

BAD reactions (NEVER do this):
❌ Repeating their exact words back: "Wine tasting party? ..."
❌ "No, that's not true"
❌ "I don't think so"
❌ Ignoring what they said
❌ Changing the subject
❌ Fantasy/supernatural elements (vampires, zombies, magic, dragons, etc.)

CRITICAL: REALISTIC scenarios only. ACCEPT + ADD naturally. NO verbatim repetition. 1-2 sentences. NO asterisks."""


@dataclass
class ConversationState:
    """Tracks the conversation history for LLM context."""
    messages: list = field(default_factory=list)
    max_history: int = 20  # Keep last N exchanges to prevent context overflow

    def __post_init__(self):
        """Initialize with system prompt."""
        self.messages = [{"role": "system", "content": IMPROV_SYSTEM_PROMPT}]

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

    def __init__(self, voice: str = "ryan", ref_audio: Optional[str] = None):
        """Initialize the improv session.

        Args:
            voice: TTS voice preset to use (default: ryan).
            ref_audio: Optional path to reference audio for voice cloning.
        """
        self.voice = voice
        self.ref_audio = ref_audio
        self.state = ConversationState()

        # Initialize components (lazy-loaded)
        self.llm = MlxLlm()
        self.tts = MlxTts()
        self.stt = MlxStt()
        self.recorder = AudioRecorder()
        self.player = AudioPlayer()

    def load_models(self):
        """Pre-load all three models. Call once at startup."""
        console.print("\n🎭 Loading models for improv session...", style="cyan bold")
        console.print("   Loading LLM (Qwen3-4B-Instruct)...", style="dim")
        self.llm.load()
        console.print("   Loading TTS (Qwen3-TTS)...", style="dim")
        self.tts.load()
        console.print("   Loading STT (Whisper)...", style="dim")
        # STT model is loaded on first call by mlx_whisper, but we can mention it
        console.print("✓ All models loaded. Ready to improv!", style="green bold")
        console.print("\n💡 Tip: Say 'end scene' or press Ctrl+C to exit\n", style="yellow dim")

    def run(self):
        """Main conversation loop."""
        self.load_models()

        # AI speaks first (greeting + scene suggestion)
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

                user_text = self.stt.transcribe(audio)
                # Clean up obvious repetition errors from STT
                user_text = self._clean_repetitions(user_text)

                # If transcription is empty or too short, skip this turn
                if not user_text or len(user_text.strip()) < 3:
                    console.print("   [Transcription unclear - try speaking louder]", style="yellow dim")
                    continue

                console.print(f"   You: {user_text}", style="yellow")

                # 3. Check for exit commands
                if self._is_exit_command(user_text):
                    console.print("\n🎬 Scene! Great improv session!", style="green bold")
                    break

                # 4. LLM generates response
                self.state.add_user(user_text)
                console.print("   (Thinking...)", style="dim")
                response = self.llm.generate(
                    self.state.messages,
                    max_tokens=30,  # Very strict - 1-2 SHORT sentences only
                    temp=0.8  # slightly more creative than summary mode's 0.7
                )

                # Debug: show raw response
                console.print(f"   [Raw: {len(response)} chars]", style="dim")

                # Aggressively enforce 2 sentence maximum
                response = self._truncate_to_sentences(response, max_sentences=2)

                # Fallback if empty
                if not response or len(response.strip()) < 5:
                    response = "What?"
                    console.print("   [Used fallback - LLM returned empty]", style="yellow dim")

                self.state.add_assistant(response)
                console.print(f"   AI: {response}", style="cyan")

                # 5. TTS speaks the response (strip out stage directions)
                console.print("   (Speaking...)", style="dim")
                speech_text = self._strip_stage_directions(response)
                audio_out, sr = self.tts.synthesize(
                    speech_text,
                    voice=self.voice,
                    ref_audio=self.ref_audio
                )
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
        response = self.llm.generate(
            self.state.messages,
            max_tokens=25,  # One SHORT sentence to set the scene
            temp=0.8
        )

        # Debug: show raw response
        console.print(f"   [Raw: {len(response)} chars]", style="dim")

        # Enforce 1 sentence for the opening
        response = self._truncate_to_sentences(response, max_sentences=1)

        # Fallback if empty
        if not response or len(response.strip()) < 5:
            response = "I'm a detective at the station, and this coffee is terrible."
            console.print("   [Used fallback - LLM returned empty]", style="yellow dim")

        self.state.add_assistant(response)
        console.print(f"   AI: {response}", style="cyan")

        console.print("   (Speaking...)", style="dim")
        speech_text = self._strip_stage_directions(response)
        audio_out, sr = self.tts.synthesize(
            speech_text,
            voice=self.voice,
            ref_audio=self.ref_audio
        )
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

        Args:
            text: Text to truncate.
            max_sentences: Maximum number of sentences to keep.

        Returns:
            Truncated text with at most max_sentences sentences.
        """
        import re

        # First, remove any incomplete trailing text after punctuation
        text = text.strip()

        # Split on sentence boundaries (., !, ?)
        # Use a more aggressive split that captures the punctuation
        sentences = re.split(r'([.!?])\s*', text)

        # Reconstruct complete sentences
        complete_sentences = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                sentence = sentences[i] + sentences[i + 1]
                complete_sentences.append(sentence.strip())

        # If there's leftover text without punctuation, drop it
        # (this is incomplete and should be cut)

        # Keep only first max_sentences
        if len(complete_sentences) > max_sentences:
            complete_sentences = complete_sentences[:max_sentences]

        result = ' '.join(complete_sentences)

        # Ensure it ends with punctuation
        if result and not result[-1] in '.!?':
            # If no proper ending, add period
            result += '.'

        return result.strip()

    @staticmethod
    def _is_exit_command(text: str) -> bool:
        """Check if user wants to end the session."""
        exit_phrases = ["end scene", "scene", "stop", "quit", "exit", "goodbye", "bye"]
        text_lower = text.lower().strip()
        return any(
            text_lower == phrase or text_lower.startswith(phrase + " ")
            for phrase in exit_phrases
        )
