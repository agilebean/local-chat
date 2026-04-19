"""Vendored MLX MusicGen library.

Source: https://github.com/ml-explore/mlx-examples (musicgen, encodec, t5)
License: MIT (see LICENSE)

Vendored verbatim except for converting cross-file imports to relative
imports so the directory is a self-contained Python package rather than
a folder loaded via PYTHONPATH manipulation.
"""
from .musicgen import MusicGen
from .utils import save_audio

__all__ = ["MusicGen", "save_audio"]
