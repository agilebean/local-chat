"""Factory for creating music generators."""
from .base import MusicGenerator
from .mlx_adapter import MlxMusicGenerator
from .suno_adapter import SunoMusicGenerator
from .sunoapi_org_adapter import SunoApiOrgGenerator

def get_music_generator(provider: str, **kwargs) -> MusicGenerator:
    """
    Factory function to get a music generator instance.

    Args:
        provider: 'mlx', 'suno' (AIMLAPI), or 'suno_org' (SunoAPI.org)
        **kwargs: Arguments to pass to the generator constructor

    Returns:
        Instance of MusicGenerator
    """
    provider = provider.lower()
    
    if provider == "mlx":
        return MlxMusicGenerator(
            model_name=kwargs.get("model", "facebook/musicgen-small")
        )
    elif provider == "suno":
        # Uses AIMLAPI
        return SunoMusicGenerator(
            api_key=kwargs.get("api_key")
        )
    elif provider == "suno_org":
        # Uses SunoAPI.org
        return SunoApiOrgGenerator(
            api_key=kwargs.get("api_key")
        )
    else:
        raise ValueError(f"Unknown music provider: {provider}. Choices: mlx, suno, suno_org")
