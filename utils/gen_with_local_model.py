def generate_completion(prompt: str, model, tokenizer, device):
    # Prepare input
    inputs = tokenizer(f"<|user|>\n{prompt}<|end|>\n<|assistant|>\n", return_tensors="pt") # Phi-3 inference template, adjust this based on your model
    inputs = {k: v.to(device) for k, v in inputs.items()}

    # Compute the prompt length and determine the tokens available for new output.
    prompt_length = inputs['input_ids'].shape[1]
    context_window = 128000
    if prompt_length >= context_window:
        raise ValueError("The prompt length exceeds or equals 128k tokens!")
    # The answer (chain-of-thought + four scores) is short. The original code set
    # max_new_tokens = 128000 - prompt_length, which asked the model to generate up
    # to ~127k tokens PER call -> minutes-long generations / effective hangs.
    # Cap it to a sane budget (override with DEFISCOPE_MAX_NEW_TOKENS).
    import os
    max_new_tokens = int(os.environ.get("DEFISCOPE_MAX_NEW_TOKENS", "1024"))
    max_new_tokens = min(max_new_tokens, context_window - prompt_length)

    # Generate output
    outputs = model.generate(
        input_ids=inputs["input_ids"],
        attention_mask=inputs["attention_mask"],
        eos_token_id=tokenizer.eos_token_id,
        do_sample=True,
        temperature=1e-8, # Nearly deterministic, cannot set to 0: ValueError: `temperature` (=0) has to be a strictly positive float, otherwise your next token scores will be invalid.
        top_p=1.0,
        max_new_tokens=max_new_tokens
    )

    # Decode and only return the generated text
    decoded_output = tokenizer.decode(outputs[0][prompt_length:], skip_special_tokens=True)
    return decoded_output
