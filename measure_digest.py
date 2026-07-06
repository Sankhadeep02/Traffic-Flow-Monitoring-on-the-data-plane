#!/usr/bin/env python3
import time, os, json, struct, socket, threading, csv
from p4utils.utils.sswitch_p4runtime_API import SimpleSwitchP4RuntimeAPI
from p4utils.utils.sswitch_thrift_API import SimpleSwitchThriftAPI

# ── Load topology ─────────────────────────────────────
with open("topology.json") as f:
    t = json.load(f)

def get_node(sw_id):
    return next(n for n in t["nodes"] if n.get("id") == sw_id)

switches = {}
for sw_id in ["s1", "s2", "s3", "s4"]:
    node = get_node(sw_id)
    switches[sw_id] = {
        "p4rt":   SimpleSwitchP4RuntimeAPI(
                      device_id = node["device_id"],
                      grpc_port = node["grpc_port"],
                      p4rt_path = node["p4rt_path"],
                      json_path = node["json_path"]),
        "thrift": SimpleSwitchThriftAPI(node["thrift_port"])
    }
print("[OK] Connected to all switches")

# ── Forwarding rules ──────────────────────────────────
def install_rules():
    rules = {
        "s1": [("1","2"),("2","1")],
        "s2": [("1","2"),("2","1")],
        "s3": [("1","2"),("2","1")],
        "s4": [("1","2"),("2","1")],
    }
    for sw_name, sw in switches.items():
        for match, action in rules[sw_name]:
            try:
                sw["p4rt"].table_add("MyIngress.forward_table",
                                     "MyIngress.set_egress",
                                     [match], [action])
            except Exception as e:
                if "ALREADY_EXISTS" not in str(e) and "already" not in str(e).lower():
                    print("[WARN] " + sw_name + ": " + str(e))

def configure_meters():
    for sw_name, sw in switches.items():
        for i in range(1024):
            try:
                sw["thrift"].meter_set_rates(
                    "MyIngress.flow_meter", i, [(1,1),(2,1)])
            except:
                break

def enable_digests():
    for sw_name, sw in switches.items():
        try:
            sw["p4rt"].digest_enable("flow_alert_t", 0, 1, 0)
        except Exception as e:
            if "ALREADY_EXISTS" not in str(e):
                print("[WARN] " + sw_name + ": " + str(e))

install_rules()
configure_meters()
enable_digests()
print("[OK] Setup complete")

# ── Measurement storage ───────────────────────────────
# Each row: switch, flow, pkt_count, byte_count,
#           sw_timestamp_us, controller_rx_time_us, latency_ms
measurements = []
measurements_lock = threading.Lock()

# Track first packet time per flow (approximated by controller start)
experiment_start = time.time()

def int_to_ip(n):
    return socket.inet_ntoa(struct.pack("!I", n))

def digest_listener(sw_name, sw_p4rt):
    while True:
        try:
            msg = sw_p4rt.get_digest_list(timeout=2)
            if msg is None:
                continue

            controller_rx_time = time.time()

            for member in msg.data:
                field_names = ["src_ip","dst_ip","pkt_count",
                               "byte_count","timestamp",
                               "ingress_port","padding"]
                d = {}
                for i, field in enumerate(member.struct.members):
                    d[field_names[i]] = int.from_bytes(
                        field.bitstring, byteorder="big")

                src_ip   = int_to_ip(d["src_ip"])
                dst_ip   = int_to_ip(d["dst_ip"])
                sw_ts_us = d["timestamp"]

                # latency = time from experiment start to alert received
                latency_ms = (controller_rx_time - experiment_start) * 1000

                row = {
                    "switch":          sw_name,
                    "src_ip":          src_ip,
                    "dst_ip":          dst_ip,
                    "pkt_count":       d["pkt_count"],
                    "byte_count":      d["byte_count"],
                    "sw_timestamp_us": sw_ts_us,
                    "controller_rx_s": round(controller_rx_time - experiment_start, 4),
                    "latency_ms":      round(latency_ms, 2)
                }

                with measurements_lock:
                    measurements.append(row)

                print("  ALERT | " + sw_name +
                      " | " + src_ip + "->" + dst_ip +
                      " | pkts=" + str(d["pkt_count"]) +
                      " | latency=" + str(round(latency_ms,2)) + "ms")

        except Exception as e:
            err = str(e)
            if "timeout" not in err.lower():
                print("[ERR " + sw_name + "]: " + err)
            time.sleep(0.05)

# Start listeners
for sw_name, sw in switches.items():
    th = threading.Thread(target=digest_listener,
                          args=(sw_name, sw["p4rt"]),
                          daemon=True)
    th.start()

print("")
print("=" * 60)
print("  MEASUREMENT MODE — Digest Approach")
print("=" * 60)
print("  Run: h1 ping h2 -c 50")
print("  Waiting 120 seconds then saving results...")
print("")

experiment_start = time.time()
time.sleep(120)

# ── Save results to CSV ───────────────────────────────
csv_file = "digest_measurements.csv"
with open(csv_file, "w", newline="") as f:
    fieldnames = ["switch","src_ip","dst_ip","pkt_count",
                  "byte_count","sw_timestamp_us",
                  "controller_rx_s","latency_ms"]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    with measurements_lock:
        writer.writerows(measurements)

print("")
print("[DONE] Results saved to " + csv_file)
print("[DONE] Total alerts captured: " + str(len(measurements)))

