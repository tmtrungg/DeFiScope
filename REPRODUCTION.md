# DeFiScope — Reproduction Notes & Fixes

This file documents (a) every issue that stops a fresh clone of DeFiScope from
running, (b) the fixes applied to this working copy, and (c) exactly how to run
it — including a **no-API-key "checking mode"** that exercises the whole
deterministic pipeline for free. It is the companion to the paper *"Detecting
Various DeFi Price Manipulations with LLM Reasoning"* (ASE 2025).

Verified empirically on macOS (Apple Silicon, x86_64 Python 3.10.7) on 2026-07-05.

---

## TL;DR — what was broken and what we changed

| # | Blocker (fresh clone) | Severity | Status in this copy |
|---|---|---|---|
| 1 | `main.py` imported `torch` unconditionally, but `requirements.txt` omits torch/transformers/peft → `ModuleNotFoundError` even in OpenAI-only mode | fatal | **Fixed** — torch/transformers imported lazily, only for `--use_local_model` |
| 2 | OpenAI model hard-coded to the authors' **private** fine-tune `ft:gpt-3.5-turbo-1106:metatrust-labs::8zFctmxs`; nobody else's key can call it (returns `model_not_found`, silently swallowed → everything labelled benign) | fatal | **Fixed** — model id now from `DEFISCOPE_OPENAI_MODEL` env var (default public `gpt-3.5-turbo`) |
| 3 | Pipeline crashed with no `OPENAI_API_KEY` (`OpenAI()` constructed unconditionally; worker exception swallowed → `AttributeError` later) | fatal | **Fixed** — added no-key **checking mode** (see below); worker exceptions caught |
| 4 | Etherscan/BscScan **V1 API is retired (2025)**; every hard-coded `api.etherscan.io/api?...` / `api.bscscan.com/api?...` URL now returns *"deprecated V1 endpoint"*. `crytic-compile 0.3.7` (used by `slither-flat`) also only speaks V1 → **no contract source can be downloaded → no Type-I prompts** | fatal | **Partially fixed** — all direct explorer calls rewritten to **Etherscan V2 multichain**; source download bypasses crytic-compile via a direct V2 fetch. *Still needs a (free) key.* |
| 5 | Explorer API keys shipped empty (`"api_key": ""`) with no env override; empty key also made `slither-flat …--etherscan-apikey ` abort on argparse | fatal | **Fixed** — keys read from `ETHERSCAN_API_KEY`; empty-key `slither-flat` call skipped |
| 6 | Local-model device hard-coded `torch.device("cuda:0")` → crashes on macOS/CPU | major | **Fixed** — auto-detects CUDA → MPS → CPU |
| 7 | Trace cache poisoning: a failed RPC response was cached to `Data/<tx>.json` and reused forever | major | **Fixed** — cache only written/reused when it contains a valid `result` |
| 8 | `fast_filter` ran *before* the try/except → an RPC hiccup crashed with no result written | minor | **Fixed** — guarded; records `Error` instead |
| 9 | `sys.exit()`/`exit()` inside library code escaped `main.py`'s `except` | minor | **Fixed** — replaced with exceptions |
| 10 | `httpx>=0.28` breaks `openai==1.9.0` (`proxies` kwarg removed) | fatal (today) | **Fixed** — pinned `httpx==0.27.2` in requirements |
| 11 | `cbor2` newest release needs a Rust-2024 toolchain to build | build | **Fixed** — pinned `cbor2==5.6.5` (wheel) |
| 12 | Leaked personal QuickNode URL+token in a `transaction.py` comment | hygiene | **Fixed** — scrubbed |
| 13 | `.gitignore` didn't ignore `tmp/`, `Data/`, `detection_result.jsonl`, `checkpoints/` | minor | **Fixed** |
| 14 | On a **fresh machine** (empty `~/.solc-select`, no global version set) `solc_select.current_version()` raises before the auto-install could run → every Type-I extraction died with *"No solc version set"* (found on a clean EC2 box, 2026-07-07) | major | **Fixed** — `function.py` treats "no version set" as "install the required one" |
| 15 | `binaries.soliditylang.org` (Cloudflare) returns **403** to the default `Python-urllib` user agent from datacenter IPs (AWS EC2) → solc-select's on-demand solc download fails (`HTTP Error 403: Forbidden`), killing Type-I extraction. Works from residential IPs, so invisible on a home Mac | major | **Fixed** — `function.py` installs a global urllib opener with a browser-style UA before solc-select runs |
| 16 | **Free Etherscan V2 keys are limited to 3 calls/sec**; the pipeline queries the explorer once per contract in a trace (a burst of dozens) → `Max calls per sec rate limit reached` → source fetch fails mid-run → Type-I extraction dies / verdict `Error` | major | **Fixed** — all explorer GETs go through `config.explorer_get()`: thread-safe throttle (default 0.4 s between calls, tune with `DEFISCOPE_EXPLORER_MIN_INTERVAL`) + backoff-retry on rate-limit replies + a **persistent on-disk cache** (`explorer_cache/`, committable; override with `DEFISCOPE_EXPLORER_CACHE`) so each contract's source/ABI is fetched from Etherscan exactly once, ever |
| 17 | Multi-file verified sources are flattened by concatenation, so they contain one `pragma` per file; the code compiled with the **first** pragma found (e.g. a helper library's `>=0.6.0`) while the main contract needs newer syntax (PancakeRouter: `call{value:}` needs 0.6.2+) → `Invalid solc compilation`, and the **uncaught Slither exception killed the whole transaction** and left the process chdir'd into `tmp/` | major | **Fixed** — `function.py` compiles with the *highest* pragma version found; a Slither/solc failure on one contract now degrades that contract to "no source" (Type-II) instead of aborting the run, and the cwd is restored via `finally` |
| 18 | Local-model path: the released **adapter repo ships only the LoRA weights** (no tokenizer/config files), yet `load_model.py` loaded the tokenizer from the adapter path → crash. Also **transformers v5.x** (current in 2026) fails on this 2024-era Phi-3 checkpoint with a misleading *"You need to have sentencepiece…"* error even when sentencepiece IS installed (v5 removed the slow→fast conversion path) | fatal (local model) | **Fixed** — `load_model.py` falls back to the **base model's tokenizer** (resolved from `adapter_config.json`); install the local-model extras as `pip install torch "transformers==4.46.3" peft accelerate bitsandbytes sentencepiece tiktoken` |

**Things that turned out NOT to be blockers (verified live):** the QuickNode
`docs-demo` RPC endpoints in `utils/config.py` *do* serve `debug_traceTransaction`
(callTracer + logs) with archive depth for both Ethereum and BSC, and were not
rate-limited in our tests. You only need your own RPC for heavy batch runs.

---

## What the authors did NOT release (genuine reproducibility gaps)

These are not bugs — they are missing artifacts that make parts of the paper
**impossible to reproduce end-to-end from this repo alone**. Worth knowing for
RQ3-style benchmarking:

1. **The OpenAI fine-tuning recipe.** The paper's headline recall (80%) uses
   fine-tuned GPT-3.5-Turbo-1106 / GPT-4o. The repo ships only the resulting
   **private model id** (blocker #2) and the training CSVs — no CSV→JSONL
   converter, no fine-tuning-job script. And `gpt-3.5-turbo-1106` fine-tuning has
   since been retired by OpenAI, so the *exact* artifact can never be rebuilt.
   You can re-fine-tune a current base model from `dataset/training_set.csv`
   yourself (see below).
2. **The Foundry data-synthesis pipeline.** §IV describes fuzzing a Uniswap-V2
   BTC20 pool to synthesize 500 inflate + 500 deflate samples. Only the finished
   CSVs are shipped; the Foundry harness and the CoT-response generator are absent.
3. **`fine-tuning/lora_ds_config.json`** — referenced at `fine-tuning.py:225`,
   but **not in the repo**. Its intended contents are printed in
   `model_comparison_result.md` (under the different name `ds_config.json`).
   Fine-tuning `deepspeed.initialize` crashes without it.
4. **Ground-truth label files.** `D2.csv` (which of 968 are the 147 TP), `D3.csv`
   (benign), and `1000_tx.csv` (the 204 manually-labelled DeFi operations for the
   TG-vs-CFT experiment) ship **without labels**, so the paper's 96% precision and
   TPR 0.912 cannot be recomputed from the repo. Only the 6 D2 false positives are
   listed (in `supplementary_material.md`).
5. **No batch-evaluation harness.** `main.py` takes a single `-tx`; nothing loops
   over D1/D2/D3. (A minimal loop is trivial to write — see below.)
6. **Cross-chain (Polygon/Arbitrum) config** referenced in the supplementary is
   not in `utils/config.py` (only ethereum + bsc).

Data sanity (verified): D1=95, D2=968 (967 unique — one dup), D3=96,800 (96,776
unique — 24 dups), train/eval/test=800/100/100. 49 of the 95 D1 attacks also
appear in D2. ~2.5% of fine-tuning responses contradict their own CPMM ground
truth (synthetic-label noise). The BTC20 pool used to make the training data is
itself attack #21 in D1.

---

## Setup (macOS / Linux)

```bash
cd DeFiScope
python3.10 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt          # includes the httpx & cbor2 pins
# Only if you want the local Phi-3 model instead of OpenAI:
pip install torch transformers peft
```

Python **3.10.x** is the floor for detection (the code uses PEP-604 `A | B`
runtime type hints). Fine-tuning is a separate Linux+NVIDIA-only environment
(Python 3.12) — see the README.

---

## Running it

### Mode A — No-key "checking mode" (free, no OpenAI/Etherscan key)

Runs the entire **deterministic** pipeline: fetch trace → decode → slice into
user invocations → build the Transfer Graph → recover DeFi operations (Swap /
Deposit / …) → build the exact LLM prompts. The only thing skipped is the LLM's
price-direction scoring — every token's tendency defaults to `Uncertain`, so the
final verdict is always `False`, **but the prompts that *would* have been sent
are written to `prompts_dump/`** so you can read precisely what the model is asked.

```bash
unset OPENAI_API_KEY
python main.py -tx 0xca4d0d24aa448329b7d4eb81be653224a59e7b081fc7a1c9aad59c5a38d0ae19 -bp bsc
ls prompts_dump/        # the real Type-I / Type-II prompts for this transaction
```

This is the recommended way to *understand* DeFiScope, and it confirms the whole
program-analysis half of the paper works. (Example above is the AES attack, D1
row 1; it produces 6 Type-II CPMM prompts for the AES/USDT pool.)

### Mode B — Real detection with OpenAI

```bash
export OPENAI_API_KEY='sk-...'
# Optional: point at your own fine-tuned model to match the paper.
export DEFISCOPE_OPENAI_MODEL='gpt-4o'          # or 'ft:...your-own-finetune'
# Recommended for Type-I prompts (contract source): a free Etherscan V2 key.
export ETHERSCAN_API_KEY='YourEtherscanV2Key'   # one key works for ETH + BSC
python main.py -tx <hash> -bp <ethereum|bsc>
cat detection_result.jsonl
```

Without `ETHERSCAN_API_KEY`, detection still runs but can only produce **Type-II**
(CPMM-assumption) prompts for two-token pools it discovers from the transfer
graph — it cannot extract price-calculation source code, so custom-price-model
attacks will be under-detected relative to the paper.

### Mode C — Local Phi-3 model (no OpenAI)

```bash
python main.py -tx <hash> -bp bsc --use_local_model --model_path <hf-or-local-adapter>
```
Device is auto-detected (CUDA/MPS/CPU). Note: Phi-3-medium-128k is 14B params
(~28 GB in fp16) and the shipped `load_model.py` expects a LoRA/PEFT adapter
checkpoint, not a bare base model.

### Optional — environment variables summary

| Variable | Purpose | Default |
|---|---|---|
| `OPENAI_API_KEY` | Enables LLM scoring | *(unset → checking mode)* |
| `DEFISCOPE_OPENAI_MODEL` | OpenAI model id | `gpt-3.5-turbo` |
| `ETHERSCAN_API_KEY` | Etherscan **V2** multichain key (ETH+BSC) | `""` |
| `DEFISCOPE_ETH_RPC` | Ethereum RPC w/ `debug_traceTransaction` | QuickNode demo |
| `DEFISCOPE_BSC_RPC` | BSC RPC w/ `debug_traceTransaction` | QuickNode demo |

---

## Re-fine-tuning your own OpenAI model (to replace the private one)

The training data is `dataset/training_set.csv` (`ID,input,response`). Convert it
to OpenAI chat-JSONL and submit a job:

```python
import csv, json, openai
with open("dataset/training_set.csv") as f, open("train.jsonl","w") as out:
    for row in csv.DictReader(f):
        out.write(json.dumps({"messages":[
            {"role":"system","content":"You are a price oracle of DeFi protocols, your job is to evaluate the price change of assets based on the given information."},
            {"role":"user","content":row["input"]},
            {"role":"assistant","content":row["response"]}]})+"\n")
client = openai.OpenAI()
f = client.files.create(file=open("train.jsonl","rb"), purpose="fine-tune")
job = client.fine_tuning.jobs.create(training_file=f.id, model="gpt-4o-2024-08-06")
# when done: export DEFISCOPE_OPENAI_MODEL=<the ft:... id the job returns>
```

---

## Minimal batch runner over a dataset (not shipped)

```python
import csv, subprocess
CHAIN = {"ethereum":"ethereum","eth":"ethereum","bsc":"bsc"}
seen = set()
with open("dataset/D1.csv", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        h = row["Transaction Hash"].strip().lower()
        if h in seen: continue
        seen.add(h)
        subprocess.run(["python","main.py","-tx",h,"-bp",CHAIN[row["Chain"].lower()]])
# results accumulate in detection_result.jsonl
```
Note the chain-name conventions differ per file: D1 uses `ethereum`/`bsc`
(pipeline-ready), D2 uses `Ethereum`/`BSC`, D3 uses `ETH`/`BSC` — normalize before
calling.

---

## Known remaining caveats (not fixed here)

- **Type-I source download at scale.** The direct V2 fetch in
  `function.py:fetch_verified_source` handles single-file and standard-json
  multi-file verifications by concatenation. Very large multi-file contracts with
  cross-file symbol collisions may not fully parse under Slither; the brace-count
  function extractor still works on the concatenated text.
- **Train/serve prompt mismatch for local Phi-3.** Training uses
  `"Task: {x}\nResponse:\n"` (`fine-tuning.py:111`) while inference uses the Phi-3
  chat template (`gen_with_local_model.py:3`) — a known discrepancy that can
  degrade the paper's Phi-3 numbers.
- **Three `matched_pattern` label strings in `detector.py` are copy-paste wrong**
  (patterns V, VI, VIII print the wrong names). The boolean verdict is unaffected,
  but per-pattern statistics built from the log strings are unreliable.
- **Silent-benign failure mode.** Any OpenAI API error is caught and converted to
  zero scores → `Uncertain` → verdict `False`. When benchmarking, log the raw
  completions and confirm the model calls actually succeed before trusting recall.
