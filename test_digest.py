#!/usr/bin/env python3
import json, time
from p4utils.utils.sswitch_p4runtime_API import SimpleSwitchP4RuntimeAPI

with open("/home/p4/Flowstalkermodified/topology.json") as f:
    t = json.load(f)

node = next(n for n in t["nodes"] if n.get("id") == "s1")
sw = SimpleSwitchP4RuntimeAPI(
    device_id = node["device_id"],
    grpc_port = node["grpc_port"],
    p4rt_path = node["p4rt_path"],
    json_path  = node["json_path"]
)
print("[OK] Connected to s1")

try:
    sw.digest_enable("flow_alert_t", 0, 1, 0)
    print("[OK] Digest enabled")
except Exception as e:
    print("[INFO] digest_enable said: " + str(e))

print("[WAITING] Send 'h1 ping h2 -c 20' in Mininet NOW...")
print("[WAITING] Listening for 30 seconds...")

deadline = time.time() + 30
got_something = False

while time.time() < deadline:
    try:
        msg = sw.get_digest_list(timeout=1)
        if msg is not None:
            print("[GOT DIGEST RAW]: " + str(msg))
            got_something = True
            break
    except Exception as e:
        err = str(e)
        if "timeout" not in err.lower() and "empty" not in err.lower():
            print("[ERROR]: " + err)

if not got_something:
    print("[RESULT] No digest received in 30 seconds")
    print("[CONCLUSION] P4 switch is NOT firing digest() call")

