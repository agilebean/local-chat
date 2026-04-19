"""Music generation package."""
from .base import MusicGenerator
from .factory import get_music_generator

__all__ = ["MusicGenerator", "get_music_generator"]