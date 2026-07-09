from asyncio import futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from utils.userCall import UserCall

def execute(userCall: UserCall):
    try:
        userCall.priceChangeInference = userCall.generate_price_change_inference(defiActions=userCall.defiActions,functions=userCall.functions)
    except Exception as e:
        # executor.map would otherwise swallow this exception silently and leave
        # priceChangeInference as None, crashing main.py later with a cryptic error
        print("[!]Price change inference failed for a user call: {e}".format(e=e))
        userCall.priceChangeInference = {}

def execute_cuda(userCall: UserCall, model, tokenizer, device):
    userCall.priceChangeInference = userCall.generate_price_change_inference(defiActions=userCall.defiActions,
                                                                             functions=userCall.functions, 
                                                                             model=model, 
                                                                             tokenizer=tokenizer, 
                                                                             device=device)

def multi_thread(userCalls: List[UserCall]):
    with ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(execute, userCalls)

def multi_thread_cuda(userCalls: List[UserCall], model, tokenizer, device):
    # A single GPU model is not safe to call from 8 threads at once (concurrent
    # generate() -> CUDA errors / OOM). Serialize local-model inference with one
    # worker; the OpenAI path (multi_thread) keeps its 8-way network concurrency.
    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = [executor.submit(execute_cuda, userCall, model, tokenizer, device)
                   for userCall in userCalls]
        for future in as_completed(futures):
            future.result()
