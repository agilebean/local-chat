# MLX MusicGen

## About (`music/musicgen/`)

Source: [`ml-explore/mlx-examples`](https://github.com/ml-explore/mlx-examples) — the
`musicgen/`, `encodec/`, and `t5/` example folders.

Included directly in this repo (not pip-installed) because `audiocraft` (the upstream
PyPI package) pulls heavy unrelated dependencies. The MLX port is self-contained and
fits in ~150 KB.

### How to reinstall from scratch

```bash
# 1. Clone upstream to a temp location
git clone https://github.com/ml-explore/mlx-examples.git /tmp/mlx-examples

# 2. Copy the musicgen folder
cp -r /tmp/mlx-examples/musicgen music/musicgen

# 3. Replace symlinks with real files
#    (mlx-examples uses symlinks to sibling folders; we need standalone copies)
cp /tmp/mlx-examples/encodec/encodec.py music/musicgen/encodec.py
cp /tmp/mlx-examples/t5/t5.py          music/musicgen/t5.py

# 4. Add the package init (not in upstream — required to import as a Python package)
touch music/musicgen/__init__.py

# 5. Install runtime deps
mamba activate localai
pip install -r music/musicgen/requirements.txt

# 6. Delete the temp clone
rm -rf /tmp/mlx-examples
```

### What `requirements.txt` pulls

`mlx>=0.18`, `numpy`, `huggingface_hub`, `torch`, `transformers`, `scipy`.

`torch` is required at runtime even though inference is MLX — `MusicGen.from_pretrained`
calls `torch.load` to read the `state_dict.bin` weights file. Do not uninstall it.

### Model weights

`facebook/musicgen-small` (~600 MB) auto-downloads from HuggingFace into
`~/.cache/huggingface/hub/` on first run. `medium` and `large` variants are also
accepted by `-m` in `musicgen.py`.
