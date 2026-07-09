# How to use DeFiScope

A practical, copy-paste run manual: what you need, how to install it, how to run
it, and how to read the results. For *why* things were broken and the deeper
audit, see `REPRODUCTION.md`. For *what the tool does*, see `TEACHING_GUIDE.html`.

Verified working on macOS (Apple Silicon) with Python 3.10, 2026-07-05.

---

## 1. What DeFiScope does

You give it **one transaction hash** and a **chain**; it prints whether that
transaction is a **DeFi price-manipulation attack** (`True` / `False`), and
appends the result to `detection_result.jsonl`.

```bash
python main.py -tx <transaction-hash> -bp <ethereum|bsc>
```

There are **three ways to run it**, from zero-setup to full reproduction:

| Mode | Needs | What you get |
|---|---|---|
| **A. Checking mode** | nothing (no keys) | Full deterministic pipeline runs; the LLM step is skipped; verdict always `False`; the prompts it *would* send are saved to `prompts_dump/`. Best for learning/testing. |
| **B. OpenAI mode** | `OPENAI_API_KEY` (+ ideally `ETHERSCAN_API_KEY`) | Real detection with a hosted model. |
| **C. Local model** | a GPU + a Phi-3 LoRA checkpoint | Real detection with a local model, no OpenAI. |

---

## 2. Prerequisites

- **Python 3.10.x** (this is a hard floor — the code uses `A | B` runtime type
  hints that fail on 3.9). Check with `python3.10 --version`.
- **macOS or Linux.** (Fine-tuning is Linux+GPU only; *detection* runs on macOS.)
- Internet access (it fetches transaction traces, contract source, and solc binaries).
- ~2–4 minutes of patience per transaction — trace fetch + Slither + on-demand
  solc install make each run take a few minutes. **It is not hung.**

---

## 3. Get the API keys / endpoints

All are read from **environment variables** — you never edit source code.

| Variable | Needed for | Where to get it | Default if unset |
|---|---|---|---|
| `OPENAI_API_KEY` | LLM scoring (Mode B) | platform.openai.com → API keys | *(unset → checking mode)* |
| `DEFISCOPE_OPENAI_MODEL` | which OpenAI model | your own `ft:…` fine-tune, or `gpt-4o` | `gpt-3.5-turbo` |
| `DEFISCOPE_OPENAI_BASE_URL` | point the OpenAI client at any OpenAI-compatible server (e.g. **local Ollama**) | `http://localhost:11434/v1` for Ollama | *(unset → api.openai.com)* |
| `ETHERSCAN_API_KEY` | downloading contract source (Type-I prompts) | etherscan.io/apis (free; **one V2 key works for both ETH and BSC**) | `""` (→ Type-II only) |
| `DEFISCOPE_ETH_RPC` | Ethereum trace fetch | any archive RPC with `debug_traceTransaction` (QuickNode Trace add-on, Alchemy, local Erigon) | QuickNode public demo* |
| `DEFISCOPE_BSC_RPC` | BSC trace fetch | same | QuickNode public demo* |

\* The built-in QuickNode `docs-demo` endpoints **do work** for
`debug_traceTransaction` (verified) — fine for trying a few transactions. Provide
your own only for heavy/batch runs, where the demo endpoints get rate-limited.

**Minimum to get a real verdict (Mode B):** just `OPENAI_API_KEY`. Add
`ETHERSCAN_API_KEY` to unlock source-code (Type-I) prompts — without it, detection
still runs but only with the CPMM-assumption (Type-II) prompts, which under-detects
custom-price-model attacks.

---

## 4. Install (one time)

Open a terminal (macOS default **zsh**, or bash — either is fine) and run from the
repo root:

```bash
cd /Users/tranminhtrung/Desktop/PhD/RQ3/benchmark/defiscope/DeFiScope

# create + activate a Python 3.10 virtual environment
python3.10 -m venv .venv
source .venv/bin/activate            # (.venv) appears in your prompt

pip install --upgrade pip
pip install -r requirements.txt      # includes the httpx & cbor2 pins that upstream lacks

# ONLY if you plan to use --use_local_model (Mode C):
# (pin transformers to 4.x — the v5 line breaks the 2024-era Phi-3 checkpoint
#  with a misleading "need sentencepiece" error)
pip install torch "transformers==4.46.3" peft sentencepiece tiktoken
```

If a future `cbor2` build fails asking for a Rust toolchain, the pinned
`cbor2==5.6.5` in `requirements.txt` avoids it; re-run the pip install.

---

## 5. Run it

Always **activate the venv and run from the repo root** first:

```bash
source .venv/bin/activate
cd /Users/tranminhtrung/Desktop/PhD/RQ3/benchmark/defiscope/DeFiScope
```

### Mode A — Checking mode (no keys, free)

```bash
unset OPENAI_API_KEY
python main.py -tx 0xca4d0d24aa448329b7d4eb81be653224a59e7b081fc7a1c9aad59c5a38d0ae19 -bp bsc
```
This is the AES attack (row 1 of the benchmark). It runs the full pipeline, prints
`attack: False` (the LLM is skipped), and writes the prompts it would have sent to
`prompts_dump/`. Open those files — they are the real Type-II prompts for this
transaction. **This is the recommended first run.**

### Mode B — Real detection with OpenAI

```bash
export OPENAI_API_KEY='sk-...'
export ETHERSCAN_API_KEY='YourFreeEtherscanV2Key'   # optional but recommended
export DEFISCOPE_OPENAI_MODEL='gpt-4o'              # optional; default gpt-3.5-turbo
python main.py -tx 0xca4d0d24aa448329b7d4eb81be653224a59e7b081fc7a1c9aad59c5a38d0ae19 -bp bsc
```

> ⚠️ **Important:** a wrong key or an inaccessible model does **not** crash — the
> tool catches the error and reports `False` for everything. If you get all-`False`
> results, verify your key works first (e.g. a quick `curl` to the OpenAI API).

### Mode C — Local model via Ollama (recommended for no-OpenAI / Mac)

The cleanest way to run a **local** model — including the authors' released
fine-tuned Phi-3 — is to serve it with **Ollama** and route DeFiScope's OpenAI
code path to it. This works even on a 16 GB Intel Mac (Ollama uses the GPU via
Metal; the PyTorch path below does not). Full walkthrough: **`local_phi3/README.md`**.

```bash
# after building/registering the model in Ollama (see local_phi3/README.md):
export OPENAI_API_KEY=ollama                          # placeholder; Ollama ignores it
export DEFISCOPE_OPENAI_BASE_URL=http://localhost:11434/v1
export DEFISCOPE_OPENAI_MODEL=defiscope-phi3          # or any ollama model, e.g. phi3:medium
python main.py -tx <hash> -bp bsc
```

### Mode C′ — Local model via the built-in PyTorch path (NVIDIA GPU)

On a real NVIDIA GPU (e.g. an AWS EC2 g5 instance) this is the simplest path — no
Ollama, no GGUF. Point `--model_path` straight at the released adapter:

```bash
export DEFISCOPE_LOAD_8BIT=1      # fit the 14B model in ~14GB on a 24GB GPU
python main.py -tx <hash> -bp bsc --use_local_model \
  --model_path RocketRaccoonnn/Phi-3-medium-128k-instruct_LoRA_CASUAL_LM_lora_v2
```
Device is auto-detected (CUDA → Apple MPS → CPU). **Full AWS EC2 setup for total
beginners is in `RUN_ON_EC2.md`.** On an Intel Mac PyTorch has no usable GPU — use the
Ollama route (Mode C) there instead.

### Useful flags

- `--debug` — prints the recovered DeFi operations, the matched attack pattern, and
  the price-change reasoning for each user call. Use this to see *why* a verdict fired.

---

## 6. Read the output

- **Terminal:** `[*]The transaction is a price manipulation attack: True|False`
  and `[*]Execution Time: …s`.
- **`detection_result.jsonl`** (appended each run): one JSON line per transaction,
  e.g. `{"0xca4d...": "False", "time": 176.7}`. Values are `"True"`, `"False"`, or
  `"Error"`.
- **`prompts_dump/`** (checking mode only): the exact prompt strings the LLM would
  have received — one file per price-inference call.
- **`Data/<hash>_raw_transaction.json`**: cached trace (delete to force re-download).
- **`tmp/`**: Slither working dir, wiped each run.

---

## 7. Test transactions (from the datasets)

The `dataset/` folder holds the paper's evaluation sets (hashes only, no labels):

- `D1.csv` — **95 confirmed attacks**, columns `Protocol,Chain,Date,Transaction Hash`.
  These are the ground-truth positives; the `Chain` values (`ethereum`/`bsc`) are
  exactly the `-bp` argument. Good source of test hashes.
- `D2.csv` — 968 suspicious transactions (`Transaction Hash,Chain`; chain is
  `Ethereum`/`BSC` — lowercase it before passing to `-bp`).
- `D3.csv` — 96,800 benign transactions (`Chain,DeFi Application,Transaction Hash`;
  chain is `ETH`/`BSC` — map `ETH`→`ethereum`).
- `1000_tx.csv` — Ethereum transactions for the Transfer-Graph-vs-CFT experiment.
- `training_set.csv` / `eval_set.csv` / `test_set.csv` — fine-tuning data (800/100/100).

**Batch runner** (there is no built-in one — `main.py` takes a single tx). Minimal loop:

```bash
source .venv/bin/activate
python - <<'PY'
import csv, subprocess
CHAIN = {"ethereum":"ethereum","eth":"ethereum","bsc":"bsc"}
seen = set()
with open("dataset/D1.csv", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        h = row["Transaction Hash"].strip().lower()
        if h in seen:                      # D2/D3 have a few duplicate hashes
            continue
        seen.add(h)
        subprocess.run(["python","main.py","-tx",h,"-bp",CHAIN[row["Chain"].lower()]])
# results accumulate in detection_result.jsonl
PY
```

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: torch` | using `--use_local_model` without the extra deps | `pip install torch transformers peft` |
| Every transaction returns `False` in Mode B | bad/inaccessible OpenAI key or model (errors are swallowed) | verify the key works; check `DEFISCOPE_OPENAI_MODEL` is one your key can call |
| Contracts show "code not verified" / no Type-I prompts | no `ETHERSCAN_API_KEY` (V2 needs a key), or the contract genuinely isn't verified | set a free `ETHERSCAN_API_KEY`; some contracts are legitimately closed-source (Type-II is expected) |
| `RuntimeError: debug_traceTransaction returned no result` | RPC endpoint doesn't support tracing or is rate-limited | set `DEFISCOPE_ETH_RPC` / `DEFISCOPE_BSC_RPC` to a trace-enabled archive node |
| Result is `"Error"` in the jsonl | an exception during processing (often RPC or unverified-contract edge case) | re-run with `--debug`; delete `Data/<hash>_raw_transaction.json` if a cached trace looks bad |
| Runs "forever" (~3 min) | normal — trace fetch + Slither + solc install | wait; it prints `Execution Time` when done |
| solc download fails on Apple Silicon | solc binaries for old versions are x86_64 | `softwareupdate --install-rosetta --agree-to-license` once |

---

## 9. Fine-tuning (optional, advanced)

Training a Phi-3 model is a **separate Linux + NVIDIA-GPU environment** (Python
3.12) and is **not runnable on macOS**. Note also that `fine-tuning/lora_ds_config.json`
is missing from the repo (recreate it from `model_comparison_result.md`) and the
OpenAI fine-tuning script was never shipped. To re-create your own OpenAI fine-tune
from `dataset/training_set.csv` and plug it in via `DEFISCOPE_OPENAI_MODEL`, follow
the recipe in **`REPRODUCTION.md`**.
