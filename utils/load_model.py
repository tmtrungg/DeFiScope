import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel, PeftConfig


def load_model_for_device(model_path: str, device):
    """Load a base model + PEFT/LoRA adapter for inference.

    Memory-aware: the original code loaded the 14B base in fp32 (~56 GB) and would
    OOM on any normal GPU. Now:
      * on CUDA: load in fp16 (~28 GB) with device_map="auto";
      * set DEFISCOPE_LOAD_8BIT=1 to load in 8-bit (~14 GB) so it fits a 24 GB GPU
        (needs `pip install bitsandbytes`); use this on g5/A10G instances;
      * on CPU/MPS: load in fp32/fp16 and move to the given device.
    `model_path` can be a local path or a HuggingFace adapter id, e.g.
    RocketRaccoonnn/Phi-3-medium-128k-instruct_LoRA_CASUAL_LM_lora_v2
    """
    print(f"🕤 Loading model {model_path} on {device}...")
    peft_ckpt_config = PeftConfig.from_pretrained(model_path)
    base_model_name = peft_ckpt_config.base_model_name_or_path

    # The released adapter repo (RocketRaccoonnn/...) ships ONLY the LoRA weights
    # (adapter_config.json + adapter_model.safetensors) — no tokenizer or
    # config.json — so the tokenizer must come from the base model. Prefer the
    # adapter path when it does ship one (e.g. a local full checkpoint).
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    except Exception:
        tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    use_cuda = torch.cuda.is_available()
    load_8bit = os.environ.get("DEFISCOPE_LOAD_8BIT") == "1"
    kwargs = dict(trust_remote_code=True, low_cpu_mem_usage=True)
    used_device_map = False

    if use_cuda and load_8bit:
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        kwargs["device_map"] = "auto"
        used_device_map = True
        print("   loading in 8-bit (bitsandbytes) — fits a 24 GB GPU")
    elif use_cuda:
        kwargs["torch_dtype"] = torch.float16
        kwargs["device_map"] = "auto"
        used_device_map = True
        print("   loading in fp16 — needs ~28 GB GPU (or offloads the rest to CPU)")
    else:
        # CPU / MPS: no device_map; move explicitly below.
        kwargs["torch_dtype"] = torch.float32

    model = AutoModelForCausalLM.from_pretrained(base_model_name, **kwargs)
    model = PeftModel.from_pretrained(model, model_path)

    if not used_device_map:
        model.to(device)  # only when device_map/quantization did not place it
    model.eval()
    print("✅ Model loaded successfully.")
    return model, tokenizer
