# CLAUDE.md — DeFiScope baseline

Orientation for future Claude sessions. This is a **research baseline** in an
RQ3 benchmark (`RQ3/benchmark/defiscope/`). Read this first, then `how_to_use.md`
(run manual) and `REPRODUCTION.md` (full fix audit) as needed.

## What this repo is

DeFiScope — the first **LLM-based detector for DeFi price-manipulation attacks**.
Paper: Zhong, Wu, Liu et al., *"Detecting Various DeFi Price Manipulations with
LLM Reasoning"*, IEEE/ACM ASE 2025. Upstream: github.com/AIS2Lab/DeFiScope.

**Input:** one transaction hash + chain. **Output:** a True/False verdict
("is this a price-manipulation attack?") appended to `detection_result.jsonl`.

This clone has **local fixes applied** to make it runnable in 2026 (the upstream
does not run out of the box). All fixes are documented in `REPRODUCTION.md`.
`TEACHING_GUIDE.html` is a from-zero explainer of the paper + LLM concepts.

**Research framing:** the baseline is the **released fine-tuned Phi-3 only**
(paper Table VI, recall 0.66 on D1) — the 0.80 GPT-3.5 headline is private and
unreproducible. The domain-knowledge → fine-tuning → 0.66 chain and the
experiment plan live in **`RQ3_BASELINE_NOTES.md`**; read it before designing
any experiment. Git remotes: `origin` = private `tmtrungg/DeFiScope` (push
here), `upstream` = authors' `AIS2Lab/DeFiScope` (never push). Secrets
(`*.pem`, `.claude/`, `.env`) are gitignored — keep it that way.

## Core architecture — "LLM as sensor, plain code as judge"

The single most important thing to understand. The LLM is asked **one narrow
question** per user-invocation: *"given this pricing code and these balance
changes, did token T's price go up or down?"* (it scores 4 statements 1–10).
**Everything else is deterministic Python.** Never attribute an attack decision
to the model — it only labels price *direction*; hand-written rules decide "attack".

The 10-step pipeline (`main.py` orchestrates):

| Steps | What | Files |
|---|---|---|
| 1–2 | Fetch trace (`debug_traceTransaction`), decode, slice into "user invocations" | `transaction.py`, `tranxToUserCalls.py`, `transfer.py` |
| 3–4 | Build **Transfer Graph**, recover DeFi ops (Swap/Deposit/Withdraw/Borrow/Stake/Claim) | `transferGraph.py`, `defiAction.py`, `actionType.py` |
| 5 | Extract price-calc function source (keyword match → Slither) | `function.py` |
| 6–7 | Build prompt, call fine-tuned LLM — **the only learned step** | `priceChangeInference.py`, `gen_with_local_model.py`, `load_model.py` |
| 8 | Score → INCREASE / DECREASE / UNCERTAIN (argmax of up/down pair; no threshold) | `priceChangeInference.py` |
| 9 | Match **8 attack patterns** over ordered triples of user calls | `detector.py` |

Supporting: `userCall.py` (the `UserCall` object that ties a slice together),
`matchRelatedActions.py` (links a cross-call swap), `checkFlashloan.py`/`flashLoan.py`
(flash-loan flagging), `fast_filter.py` (cheap <=1-log screen), `config.py`
(networks, env vars, the `explorer_url` V2 helper), `multiThreadHelper.py`
(8-way parallel LLM calls), `account.py`, `log.py`, `debug_log.py`.

Two prompt types (routing is plain code, not the model's choice):
- **Type-I** — verified source found: paste the pricing Solidity, ask the model to extract the price model then score.
- **Type-II** — closed-source but graph proved a 2-token pool: assert "this is a CPMM (x·y=k)" and score.

## Critical gotchas — read before changing anything

- **Silent-benign failure mode.** Any OpenAI API error is caught → zero scores →
  every direction becomes UNCERTAIN → verdict "False". A wrong/missing key or an
  inaccessible model makes the tool report **every transaction as benign with no
  crash**. Always confirm the model calls actually succeed before trusting any
  recall/precision number.
- **The paper's model is private.** Upstream hard-coded
  `ft:gpt-3.5-turbo-1106:metatrust-labs::8zFctmxs` (the authors' OpenAI org only).
  Now read from `DEFISCOPE_OPENAI_MODEL` (default public `gpt-3.5-turbo`). The
  paper's exact headline numbers **cannot** be reproduced.
- **Etherscan/BscScan V1 API is dead (retired 2025).** All explorer calls were
  rewritten to Etherscan **V2 multichain** (`config.explorer_url`). Needs a free
  `ETHERSCAN_API_KEY`; without it, only Type-II (CPMM) prompts are produced — no
  source-code Type-I prompts.
- **No-key "checking mode".** With no `OPENAI_API_KEY`, the whole deterministic
  pipeline still runs and dumps the prompts it *would* send to `prompts_dump/`.
  The verdict is always False (LLM skipped). This is the free way to exercise/test
  the pipeline end-to-end.
- **Runtime is ~2–4 minutes per transaction** (trace fetch + Slither + on-demand
  solc install). It is not hung.
- **Run from the repo root** — `tmp/`, `Data/`, `dataset/`, `detection_result.jsonl`
  are all relative paths. One run per working directory (`tmp/` is wiped each run).
- Detection needs **≥3 filtered user calls** (patterns are 3-step); single-invocation
  manipulations are structurally invisible. Detection is **single-transaction only**.

## Reproducibility status

**Works & verified:** the deterministic pipeline (ran end-to-end on the AES attack
`0xca4d0d24…d0ae19 -bp bsc`). Datasets are intact: D1=95 attacks, D2=968 suspicious,
D3=96,800 benign, train/eval/test=800/100/100.

**NOT reproducible from the repo** (missing artifacts, not bugs): the OpenAI
fine-tuning recipe (only the private model id ships; the base model's tuning is
retired), the Foundry data-synthesis code, `fine-tuning/lora_ds_config.json`
(absent), ground-truth labels for D2/D3/`1000_tx.csv`, and any batch harness.

## Environment

- Detection: **Python 3.10.x** (floor — PEP-604 runtime type hints). Local `.venv`.
  `pip install -r requirements.txt` (includes the `httpx==0.27.2` and `cbor2==5.6.5`
  pins that upstream lacks). Add `torch transformers peft` only for `--use_local_model`.
- Fine-tuning: separate Linux + NVIDIA-GPU env (Python 3.12); cannot run on macOS.
- Env vars: `OPENAI_API_KEY` (optional → checking mode), `DEFISCOPE_OPENAI_MODEL`,
  `DEFISCOPE_OPENAI_BASE_URL` (point the OpenAI client at a local Ollama, etc.),
  `ETHERSCAN_API_KEY` (V2 multichain, one key for ETH+BSC), `DEFISCOPE_ETH_RPC`,
  `DEFISCOPE_BSC_RPC` (both default to working QuickNode demo endpoints).
- **Local model on an NVIDIA GPU (e.g. AWS EC2):** use the native `--use_local_model
  --model_path RocketRaccoonnn/Phi-3-medium-128k-instruct_LoRA_CASUAL_LM_lora_v2` path.
  Fixed for this: `load_model.py` loads fp16/8-bit (was fp32 → OOM; set
  `DEFISCOPE_LOAD_8BIT=1` for 24 GB GPUs), `gen_with_local_model.py` caps
  `max_new_tokens` (was 128000-prompt_len → multi-minute hangs; override with
  `DEFISCOPE_MAX_NEW_TOKENS`), and `multi_thread_cuda` uses 1 worker (concurrent
  generate on one GPU crashes). Full walkthrough in `RUN_ON_EC2.md`.
- **Local model on non-NVIDIA (e.g. Intel Mac):** the PyTorch path can't use the GPU
  (no CUDA/MPS/ROCm on Intel macOS). Instead route the OpenAI path to **Ollama** via
  `DEFISCOPE_OPENAI_BASE_URL=http://localhost:11434/v1`; `local_phi3/` has a Colab
  notebook to build the GGUF and a Modelfile.

## Run (quick)

```bash
source .venv/bin/activate
python main.py -tx <hash> -bp <ethereum|bsc>   # add --debug for pattern details
```
Full setup, keys, modes, and troubleshooting: **`how_to_use.md`**.

## Docs in this repo

- `RQ3_BASELINE_NOTES.md` — the research plan + the paper's domain-knowledge → fine-tuning → 0.66 chain (read before experiments)
- `how_to_use.md` — setup + run manual (start here to run it)
- `REPRODUCTION.md` — every blocker, every fix, + a recipe to re-fine-tune your own model
- `TEACHING_GUIDE.html` — from-zero explainer of the paper and LLM concepts (open in a browser)
- `RUN_ON_EC2.md` — beginner walkthrough to run the fine-tuned Phi-3 on an AWS GPU (native PyTorch path)
- `local_phi3/` — run the released fine-tuned Phi-3 locally via Ollama (Colab GGUF builder + Modelfile)
- `supplementary_material.md`, `model_comparison_result.md` — original author docs
