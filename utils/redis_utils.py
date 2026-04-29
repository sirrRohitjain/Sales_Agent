import requests
import json
from Data_base.connection import UPSTASH_URL, UPSTASH_HEADERS

def save_session(call_id: str, state_data: dict, history: list):
    """Saves session data via Upstash REST API using a pipeline for efficiency."""
    # Upstash supports pipelining via a single POST request
    pipeline_url = f"{UPSTASH_URL}/pipeline"
    
    # Expiration: 600 seconds (10 mins)
    payload = [
        ["SET", f"call:{call_id}:state", json.dumps(state_data), "EX", "600"],
        ["SET", f"call:{call_id}:history", json.dumps(history), "EX", "600"]
    ]
    
    res = requests.post(pipeline_url, headers=UPSTASH_HEADERS, json=payload)
    return res.status_code == 200

def get_session(call_id: str):
    """Retrieves state and history."""
    pipeline_url = f"{UPSTASH_URL}/pipeline"
    payload = [
        ["GET", f"call:{call_id}:state"],
        ["GET", f"call:{call_id}:history"]
    ]
    
    res = requests.post(pipeline_url, headers=UPSTASH_HEADERS, json=payload)
    if res.status_code == 200:
        data = res.json()
        state = json.loads(data[0]["result"]) if data[0].get("result") else None
        history = json.loads(data[1]["result"]) if data[1].get("result") else []
        return {"state": state, "history": history}
    return None

def delete_session(call_id: str):
    url = f"{UPSTASH_URL}/pipeline"
    payload = [["DEL", f"call:{call_id}:state"], ["DEL", f"call:{call_id}:history"]]
    requests.post(url, headers=UPSTASH_HEADERS, json=payload)