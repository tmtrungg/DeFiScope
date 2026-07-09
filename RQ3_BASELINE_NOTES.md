# RQ3 Baseline Notes — DeFiScope's fine-tuned Phi-3

Working notes for using DeFiScope as an RQ3 baseline. This file records the
research framing so any future session (or reader) has the full context.
Sources: `defiscope.pdf` (§II, §IV, §VII-B, §VIII), `supplementary_material.md`,
`model_comparison_result.md`, `fine-tuning/fine-tuning.py`, and the released
HF adapter's `adapter_config.json`.

---

## 0. The plan (what this baseline is for)

**We only care about the Phi-3 model and take it as the baseline.** The paper's
headline model (fine-tuned GPT-3.5-Turbo, recall 0.80) is private and
unreproducible; the released Phi-3 LoRA (recall **0.66**, Table VI) is the only
instance anyone outside the authors' OpenAI org can run. It is authentically
theirs: paper ref **[70]** cites the HF adapter
`RocketRaccoonnn/Phi-3-medium-128k-instruct_LoRA_CASUAL_LM_lora_v2`, and
`supplementary_material.md` §J says "We have released the fine-tuned Phi-3
model demonstrated in §VIII".

Steps:
1. **(done)** Understand, from the paper, how DeFi/blockchain domain knowledge
   was logically turned into the concrete numerical-parameter fine-tuning, how
   the authors proved that fine-tuning works, and how the result produces 0.66.
   That understanding is §§1–4 below.
2. **(next)** Run experiments around this Phi-3 on EC2 (deployment verified
   working — see `RUN_ON_EC2.md`; AES attack tx → `True` in 391 s on an L4).
   Repo for EC2 clones: private `github.com/tmtrungg/DeFiScope` (origin);
   authors' upstream: `github.com/AIS2Lab/DeFiScope`.

---

## 1. The domain knowledge the paper starts from

Three layers of knowledge, plus one empirical finding that motivates everything:

**(a) Blockchain mechanics.** EOAs vs contract accounts; external vs internal
transactions; a **user invocation** = an internal call from user-controlled
contracts into other contracts — the slicing unit of the whole pipeline.

**(b) DeFi pricing theory (§II-A).** A *price model* is an equation tying a
token's price to balances / total supply:
- **CPMM** (Uniswap-style): `x·y = k`, so the price of tokenX in tokenY units
  is `P = y/x`. Direction rule falls out of algebra: X's reserve ↑ and Y's ↓
  ⇒ P(X) ↓ and P(Y) ↑.
- **Stableswap invariant** (Curve): flat mid-curve, CPMM-like at extremes.
- **Custom models**: anything a protocol invents — e.g. UwULend prices sUSDe
  as the **median of 10 values** (5 instantaneous prices + 5 EMA prices of
  USDe across 5 pools).

**(c) Attack-shape knowledge (§V–VI).** High-level DeFi operations (swap,
deposit, withdraw, borrow, …) recovered from token transfers, and **8 mined
attack patterns**, each an ordered *triple* of operations across user
invocations (e.g. "Manipulate price → Deposit → Withdraw"). This part is
deterministic rules, not the LLM.

**(d) The motivating empirical finding.** 44.2% of the 95 real attacks
(2021–2024) target **non-standard** price models. SOTA tools (DeFiRanger,
DeFort) detect via *token exchange rates* and normal-fluctuation bounds, which
only make sense for standard models — in the UwULend attack ($19M, 2024) the
manipulated price moved just −4.2%/+4.43%, inside DeFort's bounds, undetected.

**The pivotal insight distilled from (b)+(d):** you don't need the *magnitude*
of a price change (exchange-rate computation) to detect manipulation — you only
need the **direction** (up/down) of each token's price per user invocation, and
direction is derivable from *(price model, token balance changes)* alone. For
CPMM that derivation is pure arithmetic; for custom models it requires reading
Solidity and reasoning — "certain intelligence" — hence an LLM, and hence
fine-tuning it to do exactly this one narrow task.

---

## 2. How domain knowledge became the fine-tuning (the derivation chain)

**Step A — task narrowing.** The LLM is *not* asked "is this an attack?". It is
asked to score four statements, integers 1–10 (Fig. 2): price of input token
increases / decreases; price of output token increases / decreases — given
(i) pricing code and (ii) balance-change lines. Scoring (vs yes/no) exposes
confidence: if the two opposite statements tie, the answer is discarded as
UNCERTAIN. In this repo: prompt build + score parsing in
`utils/priceChangeInference.py` (argmax of the up/down pair per token).

**Step B — ground-truth labels for free, from the CPMM equation.** The single
cleverest move: because CPMM's direction rule is closed-form, **the domain
equation itself is the labeling function** — no human labeling of directions.
They used Foundry fuzzing on a forked chain (block height 17,949,214) against
the Uniswap V2 **BTC20/WETH** pool (a fresh token + simulated txs that never
existed on-chain ⇒ no pre-training data leakage), generating random swaps of
100–1000 ETH (1e20–1e21 wei), recording the pool's (Δbal_WETH, Δbal_BTC20)
per swap. 500 price-inflating + 500 price-deflating swaps ⇒ **1,000 labeled
balance-change pairs**.

**Step C — CoT-style prompt/response construction.** Each sample is wrapped in
a two-instruction chain-of-thought template: *first* extract the price model
from `{code}`, *then* score the four statements given the balance deltas.
Target responses were produced by having an LLM draft them, then **manually
verifying/correcting** (a wrong direction is fixed by swapping the two opposite
statements' scores). So the fine-tune teaches both the *procedure* (extract
model → infer from it) and the *direction mapping*.

**Step D — the numerical parameters (Phi-3 path = ours).** From
`model_comparison_result.md` (paper ref [69]), `fine-tuning/fine-tuning.py`,
and the released `adapter_config.json` (all three agree exactly):

| Parameter | Value |
|---|---|
| Base model | `microsoft/Phi-3-medium-128k-instruct` (14B) |
| Method | SFT with **LoRA**: `r=4, lora_alpha=8, target=[qkv_proj, o_proj], dropout=0.1`, task CAUSAL_LM |
| Data | all 1,000 samples, split **8:1:1** = `dataset/training_set.csv` (800) / `eval_set.csv` (100) / `test_set.csv` (100) |
| Optimizer | AdamW, `lr=1e-4`, linear schedule, **10 epochs** |
| Batch | micro-batch 2/GPU × grad-accum 4 × 4 GPUs = effective 32; `max_length=2000`; fp16; DeepSpeed ZeRO-2 |
| Hardware | 4× NVIDIA H800 |
| Artifact | HF `RocketRaccoonnn/..._lora_v2` — the adapter (~7.4 MB) *is* the frozen output of this training |

(The paper's *default* GPT path differs: OpenAI fine-tuning API, only 96
samples per the 50–100 guideline, 83/17 train/val, early-stop at 100% val
accuracy, ~1M training tokens, $8. Not our baseline — context only.)

---

## 3. How the authors proved the fine-tuning works (evidence ladder)

1. **Component accuracy, held-out:** on a 100-sample CPMM test set
   (`test_set.csv`), Type-I prompts score **99%** direction accuracy; Type-II
   (closed-source pools, CPMM asserted in the prompt) **97%**.
2. **System-level ablation (RQ2, Fig. 6):** of the 95 D1 attacks, only **78
   reach LLM inference** (8 lost to missing source/compile errors, 9 to
   cross-transaction / non-ERC20 issues). Reachable set = 45 CPMM + 30 custom
   + 3 Stableswap. Fine-tuning lifts GPT-3.5 by **+18 attacks (+31%)** and
   GPT-4o by +12 (+19%); CPMM-targeted detection hits 100% (GPT-3.5-FT).
3. **The transfer-learning surprise:** trained *only* on CPMM data, detection
   of **custom-price-model** attacks still jumps 60%→93.3% (GPT-3.5) and
   86.7%→96.7% (GPT-4o). Their response analysis explains why: fine-tuning's
   biggest effect is that the model **strictly follows the CoT procedure**
   (extract price model first, then infer from it + balance changes), whereas
   untuned models emit scores without following the procedure. I.e. the
   fine-tune instilled a *reasoning ritual*, not CPMM facts — that's why it
   generalizes.
4. **Cross-LLM generalizability (§VIII, Table VI) — our baseline row:** the
   same 1,000 samples, applied as LoRA SFT to open-source Phi-3, lift recall
   **0.52 → 0.66** on D1. Proves the method isn't tied to OpenAI's fine-tuning
   API. Full Table VI: GPT-3.5 0.61→0.80; GPT-4o 0.66→0.79; Phi-3 0.52→0.66.
5. **End-to-end (RQ1/RQ3, headline, private model):** recall 0.80 vs SOTA
   35.8–52.6%; precision 96% (147/153) on D2; zero false alarms on 96,800
   benign (D3); ~2.5 s/tx. Not reproducible (private model, unreleased D2/D3
   labels) — cite as context, never as our baseline.

---

## 4. How the released Phi-3 produces 0.66 at inference time

Per transaction (the 10-step pipeline, `main.py`):
trace → user invocations → transfer graph → DeFi ops (deterministic);
per invocation: extract price-calc source (`utils/function.py`, Slither) →
build Type-I prompt (verified source) or Type-II (proved 2-token pool, assert
CPMM) → **Phi-3 (base + LoRA) generates the CoT response ending in 4 scores**
→ parse → per-token `argmax(up, down)`, tie ⇒ UNCERTAIN → sequence of
(operation, price-direction) → match the **8 attack patterns** over ordered
triples (`detector.py`; needs ≥3 filtered user calls) → any match ⇒ `True`.

The arithmetic of 0.66: recall is measured over **all 95** D1 attacks, so
0.66 ≈ **63/95** detected. Since only 78/95 structurally reach the LLM, the
harness ceiling is ≈0.82 for *any* model — Phi-3 converts ~63 of the 78
reachable (~81%). The 0.80 GPT-3.5 number (76/95) is near that ceiling.

**Reproduction expectations on our EC2 box** (deltas vs the paper's setup):
we load in 8-bit (`DEFISCOPE_LOAD_8BIT=1`, vs their fp16), cap
`max_new_tokens` (`DEFISCOPE_MAX_NEW_TOKENS`, vs their 128000−prompt_len),
pin `transformers==4.46.3`, and run the 2026-patched pipeline against live
explorer/RPC state (their inference used temperature 1e-8, do_sample=True,
top_p=1.0 — see `model_comparison_result.md`). Any full-D1 recall in roughly
**0.60–0.70** counts as reproducing the 0.66 claim; expect a handful of
verdict flips from quantization + live-state drift.

Verified so far: AES attack
`0xca4d0d24aa448329b7d4eb81be653224a59e7b081fc7a1c9aad59c5a38d0ae19 -bp bsc`
→ `True` in 391 s (patterns "Manipulate→Deposit→Withdraw" and
"Deposit→Manipulate→Withdraw/Get reward"; Phi-3 scored AES=Decrease,
USDT=Increase). Full-D1 batch not yet run.

---

## 5. Pointers

- Paper: `defiscope.pdf` — §II background/motivation, §IV fine-tuning +
  inference, §VII-B ablation (Fig. 6, Table V), §VIII Table VI + refs [68]–[70].
- Authors' release statement: `supplementary_material.md` §J.
- Training recipe + inference config: `model_comparison_result.md`,
  `fine-tuning/fine-tuning.py` (note: `lora_ds_config.json` missing from repo,
  but its content is fully recoverable from `model_comparison_result.md`).
- Detection code: `utils/priceChangeInference.py` (prompts/scores),
  `utils/load_model.py` (base+LoRA load), `detector.py` (8 patterns).
- Run manuals: `how_to_use.md` (local), `RUN_ON_EC2.md` (GPU box);
  fix audit: `REPRODUCTION.md` (#1–18).
