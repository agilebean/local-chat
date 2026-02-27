"""Real-time audio I/O: microphone recording and speaker playback."""
import numpy as np
import sounddevice as sd
import queue
import webrtcvad
import struct

# Whisper expects 16kHz mono audio
WHISPER_SAMPLE_RATE = 16000


class AudioRecorder:
    """Record audio from the microphone using sounddevice with WebRTC VAD."""

    def __init__(self, sample_rate: int = WHISPER_SAMPLE_RATE):
        """Initialize the audio recorder.

        Args:
            sample_rate: Sample rate for recording (default: 16000 Hz for Whisper).
        """
        self.sample_rate = sample_rate
        # Initialize WebRTC VAD
        self.vad = webrtcvad.Vad(0)  # Mode 0 = least aggressive, best for conversational speech

    def record_until_silence(
        self,
        silence_duration: float = 1.5,
        max_duration: float = 30.0
    ) -> np.ndarray:
        """Record from mic until silence detected using WebRTC VAD.

        Uses proper Voice Activity Detection (VAD) for turn detection:
        1. Wait for speech to START (VAD detects voice)
        2. Record continuously while speech detected
        3. Stop after silence_duration seconds of no speech

        Args:
            silence_duration: Seconds of continuous silence before stopping (default: 0.8s).
            max_duration: Maximum recording duration (safety cap, default: 10s).

        Returns:
            Audio as float32 numpy array, mono, at self.sample_rate.
        """
        # WebRTC VAD requires 30ms frames at 16kHz = 480 samples
        frame_duration_ms = 30
        frame_size = int(self.sample_rate * frame_duration_ms / 1000)  # 480 samples

        q = queue.Queue()
        recording = []
        speech_started = False
        silence_frames = 0
        consecutive_non_speech = 0
        frames_needed_for_silence = int(silence_duration * 1000 / frame_duration_ms)
        SPEECH_SMOOTHING_FRAMES = 3  # ignore non-speech bursts < 90ms (VAD false negatives)

        def callback(indata, frames, time_info, status):
            """Called for each audio block from the microphone."""
            if status:
                print(f"Recording status: {status}")
            q.put(indata.copy())

        # Start recording
        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            blocksize=frame_size,
            callback=callback
        ):
            print("🎙️  Recording... (speak now, will stop after silence)")

            max_frames = int(max_duration * 1000 / frame_duration_ms)
            frame_count = 0

            while frame_count < max_frames:
                try:
                    data = q.get(timeout=0.1)
                    recording.append(data)
                    frame_count += 1

                    # Convert float32 to int16 PCM for VAD (required format)
                    audio_int16 = (data.flatten() * 32767).astype(np.int16)
                    audio_bytes = audio_int16.tobytes()

                    # RMS energy in int16 units — soft trailing speech still has energy
                    # even when VAD misclassifies it as non-speech
                    audio_rms = float(np.sqrt(np.mean(audio_int16.astype(np.float32) ** 2)))
                    SILENCE_ENERGY_THRESHOLD = 400  # ~1.2% of int16 max; below this = true silence

                    # Use WebRTC VAD to detect speech
                    is_speech = self.vad.is_speech(audio_bytes, self.sample_rate)

                    # A frame counts as silence only if VAD AND energy both confirm it
                    is_true_silence = not is_speech and audio_rms < SILENCE_ENERGY_THRESHOLD

                    if is_speech or audio_rms >= SILENCE_ENERGY_THRESHOLD:
                        if not speech_started and is_speech:
                            speech_started = True
                        consecutive_non_speech = 0
                        silence_frames = 0  # Reset silence counter
                    elif speech_started and is_true_silence:
                        consecutive_non_speech += 1
                        # Only count as silence after 3 consecutive true-silence frames (~90ms)
                        if consecutive_non_speech >= SPEECH_SMOOTHING_FRAMES:
                            silence_frames += 1
                            if silence_frames >= frames_needed_for_silence:
                                print("   (Silence detected, stopping)")
                                break

                except queue.Empty:
                    continue

        # Concatenate all chunks
        audio = np.concatenate(recording, axis=0).flatten()

        print(f"✓ Recorded {len(audio) / self.sample_rate:.1f}s")
        return audio

    def record_fixed(self, duration: float) -> np.ndarray:
        """Record a fixed duration from the mic (simpler, for testing).

        Args:
            duration: Duration in seconds to record.

        Returns:
            Audio as float32 numpy array, mono, at self.sample_rate.
        """
        print(f"🎙️  Recording {duration}s...")
        audio = sd.rec(
            int(duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32'
        )
        sd.wait()
        print(f"✓ Recorded {duration}s")
        return audio.flatten()


class AudioPlayer:
    """Play audio through speakers using sounddevice."""

    def play(self, audio: np.ndarray, sample_rate: int) -> None:
        """Play audio array through speakers (blocking until done).

        Args:
            audio: Audio as numpy array (mono or stereo).
            sample_rate: Sample rate of the audio.
        """
        sd.play(audio, samplerate=sample_rate)
        sd.wait()  # Block until playback is finished

    def play_async(self, audio: np.ndarray, sample_rate: int) -> None:
        """Play audio non-blocking (returns immediately).

        Args:
            audio: Audio as numpy array (mono or stereo).
            sample_rate: Sample rate of the audio.
        """
        sd.play(audio, samplerate=sample_rate)
