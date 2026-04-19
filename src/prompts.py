"""System-prompt registry.

Prompts live as pure data in `improv/prompts/<persona>.md` (sibling to
this `src/` directory). Each persona file may expose multiple named
sections via `## section_name` headers.

See `prompts/README.md` for the file convention.
"""
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(persona: str, section: str = "system") -> str:
    """Return the body of `## {section}` from `<persona>.md`.

    Args:
        persona: Filename stem under `prompts/` (e.g. "improv", "therapy").
        section: Markdown H2 header to extract. Defaults to "system".

    Raises:
        ValueError: if the persona file or the section header is missing.
    """
    path = _PROMPTS_DIR / f"{persona}.md"
    if not path.exists():
        raise ValueError(
            f"Unknown persona '{persona}'. Available: {available_personas()}"
        )

    text = path.read_text()
    marker = f"## {section}\n"
    start = text.find(marker)
    if start == -1:
        raise ValueError(
            f"Section '{section}' not found in {path.name}. "
            f"Available sections: {available_sections(persona)}"
        )

    body_start = text.index("\n", start) + 1
    next_section = text.find("\n## ", body_start)
    body = text[body_start:] if next_section == -1 else text[body_start:next_section]
    return body.strip()


def available_personas() -> list[str]:
    """Return persona names (filename stems) discovered in the prompts dir."""
    return sorted(p.stem for p in _PROMPTS_DIR.glob("*.md") if p.stem != "README")


def available_sections(persona: str) -> list[str]:
    """Return all `## section` names declared in a persona file."""
    path = _PROMPTS_DIR / f"{persona}.md"
    if not path.exists():
        return []
    return [
        line[3:].strip()
        for line in path.read_text().splitlines()
        if line.startswith("## ")
    ]


__all__ = ["load_prompt", "available_personas", "available_sections"]
