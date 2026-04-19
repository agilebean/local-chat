# Git Commit Guidelines

## 1. Split by concern, not by file count

Group related changes into one commit; split unrelated changes into separate
commits. Reasons:

- **Revert isolation** — one broken concern can be reverted without losing
  unrelated work.
- **`git bisect`** is only meaningful when each commit corresponds to one
  runnable behavior change.
- **Readability** — `git blame` should land you on a focused commit, not a
  megacommit where the relevant change is buried.

Heuristic: if you have to write "and" in the subject line, it probably should
be two commits. Exception: feature + the docs that document that feature can
stay together.

## 2. Subject line: conventional prefix + one-line summary

Format: `type(scope): imperative summary` (≤ 72 chars).

Types in use: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
Scope is the affected module or app (`music`, `youtube`, `browser-chat`,
`tts`, etc.). No trailing period.

Examples from this repo:

```
feat(music): pluggable backend with vendored MLX MusicGen
feat(youtube): background-music and vocal-song modes
docs: rewrite README as single source of truth; rename to local-chat
```

## 3. Body explains *why*, not *what*

The diff already shows what changed. The body is the only place the *why*
survives — trade-offs considered, alternatives rejected, constraints that
forced the design.

Things that belong in the body:

- **Motivation**: what problem this solves
- **Trade-offs**: what was rejected and why
- **Constraints**: things that forced the design
- **Non-obvious gotchas** the diff hides

Things that do **not** belong: prose restatement of the diff, "Refactored X"
with no reason, "Updated files".

## 4. Wrap body at ~72 chars

So `git log` reads well in a terminal. Blank line between subject and body.

## 5. Don't commit unless explicitly asked

Even if changes look ready. When asked, propose the split first ("I'll do N
commits: A, B, C — ok?") unless the user has already specified the split.

## 6. Don't push without an explicit ask

After committing, report the commits and wait.

## 7. Pass commit messages via heredoc

```bash
git commit -m "$(cat <<'EOF'
feat(scope): subject line

Body paragraph explaining why, wrapped at ~72 chars.
EOF
)"
```
