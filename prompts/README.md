# Prompts

Single source of truth for every system prompt used by `improv` and the
sibling browser demo (`demos/browser-chat/`). Pure data — no code lives
here. The Python loader is `src/prompts.py`.

## Layout

```
improv/
├── prompts/                # pure data, this folder
│   ├── README.md           # this file
│   ├── friend.md           # warm conversational friend (small-talk + problem mode)
│   ├── improv.md           # theatrical improv partner
│   ├── therapy.md          # coaching/therapy w/ metacognitive pattern detection
│   ├── tutor.md            # language tutor                    (stub)
│   └── debate.md           # debate partner                    (stub)
└── src/
    └── prompts.py          # load_prompt(persona, section) + helpers
```

## File convention

One file per persona. Filename stem is the persona key.

```markdown
# <Persona> System Prompts

> Optional preamble. Free text. Ignored by the loader.

## system
...the default prompt body...

## <other_section>
...alternative or composable section (e.g. `ai-starts-extra`)...
```

Rules:

- The loader extracts everything between a `## section` header and the
  next `## ` (or end of file). Body is `.strip()`ed.
- A persona MUST define at least one `## ` section. The default section
  name is `system`; deviate only when the persona genuinely has multiple
  modes (improv has `prompt` + `ai-starts-extra`).
- Keep prose in markdown. No JSON, no YAML, no code fences around the
  prompt body itself — the body is loaded as-is and sent to the LLM.

## Usage

```python
from src.prompts import load_prompt, available_personas

system = load_prompt("improv", "prompt")
addon  = load_prompt("improv", "ai-starts-extra")

print(available_personas())  # ['debate', 'improv', 'therapy', 'tutor']
```

## Adding a new persona

1. Create `prompts/<name>.md` following the convention above.
2. Done. No code changes needed (Open/Closed).

If the new persona needs runtime wiring beyond the prompt (e.g. JSON
output parsing, tool calls, voice-only constraints), add that in the
caller, not here. Prompts stay pure data.
