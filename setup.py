from setuptools import setup, find_packages

setup(
    name="improv",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "mlx>=0.20.0",
        "mlx-lm>=0.20.0",
        "mlx-audio>=0.3.0",
        "mlx-whisper>=0.4.0",
        "sounddevice>=0.4.6",
        "soundfile>=0.12.0",
        "webrtcvad>=2.0.10",
        "numpy>=1.24.0",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "improv=improv:main",
        ],
    },
    python_requires=">=3.10",
)
