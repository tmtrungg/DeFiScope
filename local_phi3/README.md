# Running the fine-tuned DeFiScope Phi-3 locally (via Ollama)

This folder lets you run the **fine-tuned DeFiScope Phi-3** model (the public,
reproducible baseline, recall ≈ 0.66 in the paper) on your own machine — including
a 16 GB Intel Mac with an AMD GPU — by routing DeFiScope's OpenAI code path to a
local **Ollama** server instead of api.openai.com.

## Why this path exists

- The paper's headline model is a **private** OpenAI fine-tune you cannot access.
- DeFiScope's built-in local path uses **PyTorch**, which on an Intel Mac has no
  usable GPU backend (no CUDA / MPS / ROCm) and can't hold a 14B model in 16 GB.
- **Ollama uses llama.cpp + Metal**, which *can* drive your AMD/Intel GPU and runs
  a **4-bit-quantized** 14B model in ~8.5 GB — so it fits.
- The authors released the Phi-3 **LoRA adapter** publicly
  ([HuggingFace](https://huggingface.co/RocketRaccoonnn/Phi-3-medium-128k-instruct_LoRA_CASUAL_LM_lora_v2)),
  so no training is needed — only a one-time convert-to-GGUF step.

## Steps

### 1. Build the GGUF (one time, on a bigger machine)

The merge needs ~28 GB of RAM/VRAM, so do it once on Colab/Kaggle/cloud — **not**
on your laptop. Open **`build_defiscope_phi3_gguf.ipynb`** in Google Colab
(A100 runtime, or a High-RAM CPU runtime) and run all cells. It outputs
`defiscope-phi3-Q4_K_M.gguf` (~8 GB) to your Google Drive.

### 2. Register the model with Ollama (on your laptop)

Download the GGUF into **this folder**, then:

```bash
cd DeFiScope/local_phi3
ollama create defiscope-phi3 -f Modelfile
ollama list                       # you should see defiscope-phi3
```

### 3. Run DeFiScope against it

```bash
cd ..                             # repo root
source .venv/bin/activate
export OPENAI_API_KEY=ollama                          # any placeholder; Ollama ignores it
export DEFISCOPE_OPENAI_BASE_URL=http://localhost:11434/v1
export DEFISCOPE_OPENAI_MODEL=defiscope-phi3
export ETHERSCAN_API_KEY=YourFreeEtherscanV2Key       # optional: enables Type-I (source) prompts
python main.py -tx 0xca4d0d24aa448329b7d4eb81be653224a59e7b081fc7a1c9aad59c5a38d0ae19 -bp bsc
```

The three `DEFISCOPE_*`/`OPENAI_*` vars send every price-inference call to your local
Ollama; nothing goes to OpenAI and there is no API cost.

## What to expect

- **Speed:** a 14B Q4 model on a 16 GB Intel Mac is usable but not fast — expect a
  handful of seconds per price-inference call, and several calls per transaction, so
  a few minutes per transaction on top of the trace/Slither time.
- **Accuracy:** this is the Phi-3 model (paper recall ≈ 0.66), weaker than the
  private GPT model (0.80). That's expected — its value is that it's **fully public
  and reproducible**, which is what you want for a robustness/weakness study.
- **Fidelity note:** routing through the chat API applies Phi-3's chat template and
  includes DeFiScope's "price oracle" system message. The repo's own
  `gen_with_local_model.py` omits that system message and the training format differs
  slightly (`Task:/Response:` vs chat template) — a known train/serve discrepancy in
  the original code. For a baseline this is acceptable; note it in your write-up.

## Quick smoke test (optional, before wiring up DeFiScope)

Confirm Ollama answers in the scored format the pipeline expects:

```bash
ollama run defiscope-phi3 "0xPOOL is a CPMM pool. The balance of TOKENA increases by 1000. Score 1-10: 1) price of TOKENA increases 2) price of TOKENA decreases"
```
You should get low score for (1), high for (2) — more supply ⇒ cheaper.
