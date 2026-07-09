# Running DeFiScope on AWS EC2 (GPU) — a step-by-step guide for beginners

This walks you from zero to running the **fine-tuned DeFiScope Phi-3** on a GPU
server, assuming you have an AWS account but have never launched a server. On a
real NVIDIA GPU you skip the Ollama/GGUF detour entirely and run DeFiScope's
**native local-model path** directly with the released adapter.

Everything you type is copy-paste. Read §0 first — it can save you money and a day of waiting.

---

## 0. Read this first

- **Cost.** A g5.2xlarge GPU instance is **~$1.20 per hour**. You are billed while it
  is *running*, even if idle. **The golden rule: STOP the instance the moment you're
  done** (§9). A forgotten GPU instance is how you get a surprise $100 bill. Stopped
  instances cost only pennies/day for their disk.
- **Quota (do this NOW — it can take hours to a day).** New AWS accounts often have a
  GPU quota of **0**, so your launch will fail with *"you have requested more vCPU
  capacity than your current limit."* Request the increase in §1 **before** anything
  else, because approval isn't instant.
- **What runs where.** The GPU server does the heavy lifting (loads the 14B model,
  runs detection). Your Mac is just the remote control (SSH) and where you copy the
  code up / results down.
- **Time budget.** First-time setup: ~30–60 min (most of it waiting on the quota
  approval and the model download). After that, runs are quick.

---

## 1. Request GPU quota (do this first)

1. Sign in to the AWS Console. Top-right, **pick a region** and remember it (e.g.
   **N. Virginia `us-east-1`** — cheapest and most GPU capacity). Use the same region everywhere.
2. Search for **"Service Quotas"** in the top search bar → open it.
3. Left menu **AWS services** → search **"EC2"** → click **Amazon Elastic Compute Cloud (Amazon EC2)**.
4. In the quota search box type **`Running On-Demand G and VT instances`** → click it.
5. Look at **Applied quota value**. You need at least **8** (a g5.2xlarge is 8 vCPUs).
   - If it's ≥ 8, you're done — skip to §2.
   - If it's 0 (or < 8): click **Request increase at account level**, enter **8** (or 16
     for headroom), submit. Approval can take minutes to ~24h; you'll get an email.
     School accounts sometimes have it pre-approved, sometimes need an admin — if it's
     denied, email your school's AWS administrator to raise the G-instance quota.

While you wait, you can still do §2 up to the launch step.

---

## 2. Launch the GPU server

1. Console → search **EC2** → open it → big orange **Launch instance**.
2. **Name:** `defiscope-gpu`.
3. **Application and OS Images (AMI):** click **Browse more AMIs** → tab **AWS
   Marketplace AMIs** (or **Quickstart**) → search **`Deep Learning OSS Nvidia Driver AMI GPU PyTorch`**
   → pick the **Ubuntu 22.04** one (latest). *This is important:* it comes with the
   NVIDIA driver, CUDA, and PyTorch pre-installed, which saves you the hardest part of
   GPU setup. (It's free; you only pay for the instance.)
4. **Instance type:** click the selector → search **`g5.2xlarge`** → select it.
   (1× A10G 24 GB GPU, 8 vCPU, 32 GB RAM — the right size for a 14B model in 8-bit.)
5. **Key pair (login):** click **Create new key pair** → name it `defiscope-key`
   → type **RSA**, format **.pem** → **Create**. Your browser downloads
   `defiscope-key.pem`. **Keep it safe — it's your only way in.**
6. **Network settings:** click **Edit**. Under **Firewall (security groups)** make sure
   **Allow SSH traffic from** is checked, and set it to **My IP** (not "Anywhere" —
   safer). Leave the rest default.
7. **Configure storage:** the default 8 GB root disk is **far too small** (the model is
   ~28 GB). Change it to **`100` GiB**, type **gp3**.
8. Review the **Summary** panel on the right (instance type g5.2xlarge, 100 GiB) →
   **Launch instance**.
9. Click the instance ID → wait until **Instance state = Running** and **Status checks =
   2/2 passed** (~2 min). Copy its **Public IPv4 address** (e.g. `54.12.34.56`).

---

## 3. Connect to it from your Mac

Open the macOS **Terminal** and run (replace the path to your key and the IP):

```bash
# one-time: lock down the key file's permissions or SSH refuses it
chmod 400 ~/Downloads/defiscope-key.pem

# connect (the Deep Learning AMI's user is 'ubuntu')
ssh -i ~/Downloads/defiscope-key.pem ubuntu@54.12.34.56
```

Type **yes** at the "authenticity of host" prompt. You're now *inside the server* — your
prompt changes to something like `ubuntu@ip-172-31-...:~$`. Confirm the GPU is there:

```bash
nvidia-smi        # should print a table showing an "A10G" and 23028MiB memory
```

---

## 4. Put DeFiScope on the server

Your fixed copy lives on your Mac, so copy it up. **Open a SECOND Terminal tab on your
Mac** (Cmd-T) — this one runs on your laptop, not the server — and `rsync` the repo
(excluding the big local-only folders):

```bash
rsync -avz \
  --exclude '.venv' --exclude '.git' --exclude 'Data' \
  --exclude 'tmp' --exclude 'prompts_dump' \
  -e "ssh -i ~/Downloads/defiscope-key.pem" \
  /Users/tranminhtrung/Desktop/PhD/RQ3/benchmark/defiscope/DeFiScope/ \
  ubuntu@54.12.34.56:~/DeFiScope/
```

(Note the trailing slashes on both paths — they matter.) Now go back to your **first
tab (the server)** and confirm it arrived:

```bash
ls ~/DeFiScope        # you should see main.py, utils/, dataset/, requirements.txt ...
```

---

## 5. Install DeFiScope's dependencies (on the server)

The AMI already has PyTorch + CUDA, so you only add DeFiScope's own requirements:

```bash
cd ~/DeFiScope
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# local-model + 8-bit support. Pin transformers to 4.x: the v5 line breaks this
# 2024-era Phi-3 checkpoint (misleading "need sentencepiece" error).
pip install "transformers==4.46.3" peft accelerate bitsandbytes sentencepiece tiktoken
```

Quick check that the GPU is visible to PyTorch:

```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# -> CUDA: True NVIDIA A10G
```

---

## 6. Set your keys (on the server)

You do **not** need an OpenAI key — you're running the local model. You *do* want a free
Etherscan V2 key for the source-code (Type-I) prompts, and 8-bit loading so the model
fits the 24 GB GPU:

```bash
export DEFISCOPE_LOAD_8BIT=1                       # fit the 14B model in ~14 GB (needed on A10G)
export ETHERSCAN_API_KEY=YourFreeEtherscanV2Key    # optional but recommended; etherscan.io/apis
# (RPC defaults to the working QuickNode demo endpoints; set DEFISCOPE_ETH_RPC /
#  DEFISCOPE_BSC_RPC only if you hit rate limits on big batches.)
```

---

## 7. First run (one transaction)

```bash
cd ~/DeFiScope
source .venv/bin/activate
python main.py \
  --use_local_model \
  --model_path RocketRaccoonnn/Phi-3-medium-128k-instruct_LoRA_CASUAL_LM_lora_v2 \
  -tx 0xca4d0d24aa448329b7d4eb81be653224a59e7b081fc7a1c9aad59c5a38d0ae19 \
  -bp bsc
```

- The **first** run downloads the base Phi-3 model (~28 GB) — expect several minutes,
  once. Later runs reuse the cache.
- You'll see it load in 8-bit, run the pipeline, and print
  `The transaction is a price manipulation attack: True/False`.
- Result is appended to `detection_result.jsonl`.

Add `--debug` to see the recovered operations and which attack pattern fired.

---

## 8. Run the whole D1 benchmark (optional)

To evaluate over all 95 attacks, run this on the server (inside `~/DeFiScope`, venv
active). `tmux` keeps it going even if your SSH connection drops:

```bash
tmux new -s defiscope          # start a persistent session (detach later with Ctrl-b then d)

python - <<'PY'
import csv, subprocess
CHAIN = {"ethereum":"ethereum","eth":"ethereum","bsc":"bsc"}
ADAPTER = "RocketRaccoonnn/Phi-3-medium-128k-instruct_LoRA_CASUAL_LM_lora_v2"
seen = set()
with open("dataset/D1.csv", encoding="utf-8-sig") as f:
    for i, row in enumerate(csv.DictReader(f), 1):
        h = row["Transaction Hash"].strip().lower()
        if h in seen: continue
        seen.add(h)
        print(f"[{i}] {row['Protocol']} {h}")
        subprocess.run(["python","main.py","--use_local_model","--model_path",ADAPTER,
                        "-tx",h,"-bp",CHAIN[row["Chain"].lower()]])
print("DONE — results in detection_result.jsonl")
PY
```

Detach with **Ctrl-b** then **d**; re-attach later with `tmux attach -t defiscope`.
Each transaction takes a few minutes (model inference + trace/Slither), so the full
95 will run for a while — that's why we use a GPU server and tmux.

To compare against ground truth: every hash in `D1.csv` is a *real attack*, so any
`"False"` in `detection_result.jsonl` is a miss (false negative). Recall = fraction of
the 95 that came back `"True"`.

---

## 9. Get your results back, then STOP the server

**Download the results** to your Mac (run in your *laptop* Terminal tab):

```bash
scp -i ~/Downloads/defiscope-key.pem \
  ubuntu@54.12.34.56:~/DeFiScope/detection_result.jsonl \
  ~/Desktop/PhD/RQ3/benchmark/defiscope/DeFiScope/
```

**Then STOP the instance so you stop paying** (do this every time you finish):
- Console → EC2 → Instances → select `defiscope-gpu` → **Instance state ▾ → Stop instance**.
- **Stop** (not Terminate) keeps your disk + downloaded model, so next time you just
  Start it again and pick up where you left off (~$0.80/month for the stopped 100 GB disk).
- **Terminate** deletes everything permanently — only do that when you're completely
  finished with the project.

To resume later: Start the instance (its **Public IP will change** — copy the new one),
`ssh` back in, `cd ~/DeFiScope && source .venv/bin/activate`, and continue.

---

## 10. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Launch fails: *"requested more vCPU capacity than your current limit"* | GPU quota not approved yet (§1). Wait for the email or ping your school admin. |
| `ssh` → *"Permission denied (publickey)"* | Wrong user (must be `ubuntu` for this AMI) or key perms — run `chmod 400 …pem`. |
| `ssh` → *"Operation timed out"* | Security group doesn't allow your IP (§2.6), or you're using an old IP after a Stop/Start. |
| `torch.cuda.OutOfMemoryError` | You forgot `export DEFISCOPE_LOAD_8BIT=1`, or another process holds the GPU (`nvidia-smi`). |
| `ImportError: bitsandbytes` | `pip install bitsandbytes` (needs CUDA — it's fine on the GPU AMI). |
| Model download is slow / disk full | The base is ~28 GB; make sure you set the disk to 100 GiB (§2.7). Check with `df -h`. |
| Runs return all `"False"` | Confirm the model actually loaded (you should see "Model loaded successfully"); check a `--debug` run. Without `ETHERSCAN_API_KEY` you only get CPMM (Type-II) prompts, which under-detect. |
| SSH dropped and my batch died | Use `tmux` (§8) so the job survives disconnects. |

---

## What to tell your advisor about this setup

This runs the **public, reproducible** DeFiScope instance (the released Phi-3 LoRA,
paper recall ≈ 0.66) on a standard cloud GPU — anyone can reproduce your numbers. It is
*not* the authors' private GPT-3.5 model (recall 0.80), which is unavailable. See
`REPRODUCTION.md` for the full reproducibility story and `TEACHING_GUIDE.html` for how
the method works.
