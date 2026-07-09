import os
import json as _json
import time as _time
import threading as _threading

import requests as _requests

# -----------------------------------------------------------------------------
# Configuration.
#
# Everything sensitive/environment-specific is read from environment variables
# with safe fallbacks, so you do NOT have to edit source code to run DeFiScope:
#
#   OPENAI_API_KEY        - OpenAI key (only needed for the LLM price-inference
#                           step; the pipeline runs without it in "checking mode").
#   DEFISCOPE_OPENAI_MODEL - OpenAI model id used for inference
#                           (default: "gpt-3.5-turbo"; set to your own "ft:..."
#                           fine-tune to reproduce the paper).
#   ETHERSCAN_API_KEY     - Etherscan V2 *multichain* API key. ONE key works for
#                           Ethereum, BSC, and every other chain via the chainid
#                           parameter. Get a free key at https://etherscan.io/apis
#   DEFISCOPE_ETH_RPC     - Ethereum JSON-RPC endpoint that supports
#                           debug_traceTransaction (archive + trace add-on).
#   DEFISCOPE_BSC_RPC     - BSC JSON-RPC endpoint (same requirement).
#
# IMPORTANT (2025+): Etherscan/BscScan retired their V1 API. The old
# "https://api.bscscan.com/api?..." style endpoints now reject every request
# with "deprecated V1 endpoint". DeFiScope therefore builds V2 multichain URLs
# ("https://api.etherscan.io/v2/api?chainid=...") via explorer_url() below. You
# still need a (free) key for V2 - keyless requests return "Missing/Invalid API
# Key". See REPRODUCTION.md for the full story.
# -----------------------------------------------------------------------------

# Etherscan V2 is multichain: one base URL, select the chain with ?chainid=N.
ETHERSCAN_V2_BASE = os.environ.get(
    "DEFISCOPE_EXPLORER_API_BASE", "https://api.etherscan.io/v2/api"
)

# One Etherscan V2 key covers all chains.
_EXPLORER_KEY = os.environ.get("ETHERSCAN_API_KEY", "")

SUPPORTED_NETWORK = {
    # platform name: {prefix in the crytic_compile, quick node api, explorer api prefix, command in flatting (check in cryticparser), explorer api key, address of wrapped stable coin}
    "ethereum": {
        "name": "mainet",
        "quick_node": os.environ.get("DEFISCOPE_ETH_RPC", "https://docs-demo.quiknode.pro/"),
        "api_prefix": ".etherscan.io",
        "key_command": "--etherscan-apikey",
        "api_key": _EXPLORER_KEY,
        "chainid": 1,
        "stable_coin": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
        "symbol": "WETH",
        },
    "bsc": {
        "name": "bsc",
        "quick_node": os.environ.get("DEFISCOPE_BSC_RPC", "https://docs-demo.bsc.quiknode.pro/"),
        "api_prefix": ".bscscan.com",
        "key_command": "--bscan-apikey",
        "api_key": _EXPLORER_KEY,
        "chainid": 56,
        "stable_coin": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # WBNB
        "symbol": "WBNB",
        },
}


def explorer_url(platform: str, action: str, **params) -> str:
    """Build an Etherscan V2 multichain explorer API URL.

    Example: explorer_url("bsc", "getsourcecode", address="0x...") ->
    https://api.etherscan.io/v2/api?chainid=56&module=contract&action=getsourcecode&address=0x...&apikey=KEY
    """
    net = SUPPORTED_NETWORK[platform]
    query = {
        "chainid": net["chainid"],
        "module": "contract",
        "action": action,
        "apikey": net["api_key"],
    }
    query.update(params)
    qs = "&".join(f"{k}={v}" for k, v in query.items())
    return f"{ETHERSCAN_V2_BASE}?{qs}"


# Free Etherscan V2 keys are limited to 3 calls/sec; the pipeline queries the
# explorer once per contract in a trace, easily bursting past that. All explorer
# GETs go through this throttled, retrying helper, backed by a persistent
# on-disk cache (explorer_cache/, repo-relative) so a contract's source/ABI is
# fetched from Etherscan exactly once and reused by every later run — including
# on another machine if you copy the directory along with the repo.
_EXPLORER_MIN_INTERVAL = float(os.environ.get("DEFISCOPE_EXPLORER_MIN_INTERVAL", "0.4"))
_EXPLORER_CACHE_DIR = os.environ.get("DEFISCOPE_EXPLORER_CACHE", "explorer_cache")
_explorer_lock = _threading.Lock()
_explorer_last_call = [0.0]


def _explorer_cache_path(platform: str, action: str, params: dict) -> str:
    chainid = SUPPORTED_NETWORK[platform]["chainid"]
    address = str(params.get("address", "noaddr")).lower()
    return os.path.join(_EXPLORER_CACHE_DIR, "{c}_{a}_{addr}.json".format(c=chainid, a=action, addr=address))


def _explorer_cacheable(ret: dict) -> bool:
    """Only stable outcomes are cached: successful replies and the permanent
    'source code not verified' answer — never transient errors (rate limit,
    bad key, network hiccups)."""
    if ret.get("status") == "1":
        return True
    result = ret.get("result")
    return isinstance(result, str) and "not verified" in result.lower()


def explorer_get(platform: str, action: str, retries: int = 5, **params) -> dict:
    """GET an explorer V2 API call as parsed JSON — cached, rate-limited, retried.

    Cache hit: returns the stored reply with no network call. Cache miss:
    serializes calls to at most one per _EXPLORER_MIN_INTERVAL seconds, backs
    off and retries when the API replies "Max calls per sec rate limit
    reached", and stores stable replies under explorer_cache/.
    """
    cache_path = _explorer_cache_path(platform, action, params)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf8") as f:
                return _json.load(f)
        except Exception:
            pass  # unreadable cache entry — refetch and overwrite

    url = explorer_url(platform, action, **params)
    ret = {}
    for attempt in range(retries):
        with _explorer_lock:
            wait = _EXPLORER_MIN_INTERVAL - (_time.monotonic() - _explorer_last_call[0])
            if wait > 0:
                _time.sleep(wait)
            _explorer_last_call[0] = _time.monotonic()
        ret = _json.loads(_requests.get(url, timeout=30).text)
        result = ret.get("result")
        if isinstance(result, str) and "rate limit" in result.lower():
            _time.sleep(1.0 + attempt)
            continue
        break

    if _explorer_cacheable(ret):
        try:
            os.makedirs(_EXPLORER_CACHE_DIR, exist_ok=True)
            tmp_path = cache_path + ".tmp{pid}".format(pid=os.getpid())
            with open(tmp_path, "w", encoding="utf8") as f:
                _json.dump(ret, f)
            os.replace(tmp_path, cache_path)
        except Exception as e:
            print("[!]Failed to write explorer cache {p}: {e}".format(p=cache_path, e=e))
    return ret
