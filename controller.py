#!/usr/bin/env python3
import time, os, json, struct, socket, threading
from p4utils.utils.helper import load_topo
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
    print("[OK] Connected to " + sw_id)

print("")

# ── Install forwarding rules ──────────────────────────
def install_rules():
    rules = {
        "s1": [("1", "2"), ("2", "1")],
        "s2": [("1", "2"), ("2", "1")],
        "s3": [("1", "2"), ("2", "1")],
        "s4": [("1", "2"), ("2", "1")],
    }
    print("Installing forwarding rules...")
    for sw_name, sw in switches.items():
        for match, action in rules[sw_name]:
            try:
                sw["p4rt"].table_add(
                    "MyIngress.forward_table",
                    "MyIngress.set_egress",
                    [match], [action])
                print("  [OK] " + sw_name + ": port " + match + " -> " + action)
            except Exception as e:
                if "ALREADY_EXISTS" in str(e):
                    print("  [OK] " + sw_name + ": port " + match +
                          " -> " + action + " (exists)")
                else:
                    print("  [ERROR] " + sw_name + ": " + str(e))
    print("")

# ── Configure meters ──────────────────────────────────
def configure_meters():
    print("Configuring meters on all switches...")
    for sw_name, sw in switches.items():
        for i in range(1024):
            try:
                # meter_set_rates(meter_name, index, [(cir, cburst), (pir, pburst)])
                sw["thrift"].meter_set_rates(
                    "MyIngress.flow_meter",
                    i,
                    [(1, 1), (2, 1)]   # (CIR, CBS), (PIR, PBS)
                )
            except Exception as e:
                print("  [ERROR] " + sw_name + " meter " + str(i) + ": " + str(e))
                break
        print("  [OK] " + sw_name + " meters configured")
    print("")

# ── Enable digests on switches ────────────────────────
def enable_digests():
    print("Enabling digest subscription on all switches...")
    for sw_name, sw in switches.items():
        try:
            # digest_enable(digest_name, max_timeout_ns, max_list_size, ack_timeout_ns)
            sw["p4rt"].digest_enable(
                "flow_alert_t",   # must match struct name in P4 exactly
                0,                # max_timeout_ns = 0 means send immediately
                1,                # max_list_size  = 1 means send one alert at a time
                0                 # ack_timeout_ns = 0
            )
            print("  [OK] " + sw_name + " digest enabled")
        except Exception as e:
            print("  [WARN] " + sw_name + ": " + str(e))
    print("")

# Call startup functions in correct order
install_rules()
configure_meters()
enable_digests()

# ── Digest listener ───────────────────────────────────
alerts_received = []
alerts_lock     = threading.Lock()

def int_to_ip(n):
    return socket.inet_ntoa(struct.pack("!I", n))

def parse_digest(sw_name, digest_data):
    src_ip       = int_to_ip(digest_data["src_ip"])
    dst_ip       = int_to_ip(digest_data["dst_ip"])
    pkt_count    = digest_data["pkt_count"]
    byte_count   = digest_data["byte_count"]
    timestamp    = digest_data["timestamp"]
    ingress_port = digest_data["ingress_port"]

    alert = {
        "switch":       sw_name,
        "src_ip":       src_ip,
        "dst_ip":       dst_ip,
        "pkt_count":    pkt_count,
        "byte_count":   byte_count,
        "timestamp":    timestamp,
        "ingress_port": ingress_port,
        "received_at":  time.strftime("%H:%M:%S")
    }

    with alerts_lock:
        alerts_received.append(alert)

    print("\n  *** ALERT from " + sw_name + " ***")
    print("  Flow : " + src_ip + " -> " + dst_ip)
    print("  Pkts : " + str(pkt_count))
    print("  Bytes: " + str(byte_count))
    print("  Port : " + str(ingress_port))
    print("  Time : " + alert["received_at"])

def digest_listener(sw_name, sw_p4rt):
    print("[Digest] Listening on " + sw_name + "...")
    while True:
        try:
            msg = sw_p4rt.get_digest_list(timeout=2)
            if msg is None:
                continue
            # msg is a single DigestList object, not a list of them
            for member in msg.data:
                digest_data = {}
                field_names = [
                    "src_ip", "dst_ip", "pkt_count",
                    "byte_count", "timestamp",
                    "ingress_port", "padding"
                ]
                for i, field in enumerate(member.struct.members):
                    digest_data[field_names[i]] = int.from_bytes(
                        field.bitstring, byteorder="big")
                parse_digest(sw_name, digest_data)
        except Exception as e:
            err = str(e)
            if "timeout" not in err.lower() and "empty" not in err.lower():
                print("[Digest ERROR on " + sw_name + "]: " + err)
            time.sleep(0.05)

# Start one digest listener thread per switch
for sw_name, sw in switches.items():
    t_digest = threading.Thread(
        target = digest_listener,
        args   = (sw_name, sw["p4rt"]),
        daemon = True
    )
    t_digest.start()

print("Digest listeners started on all 4 switches.")
print("Switches will push alerts autonomously when flows go RED.")
print("")

# ── Helper functions ──────────────────────────────────
def read_port_counters(sw_id):
    import io, sys
    sw_p4rt = switches[sw_id]["p4rt"]
    results = []
    for idx in range(4):
        old_out    = sys.stdout
        sys.stdout = io.StringIO()
        b, p       = sw_p4rt.counter_read("port_counter", idx)
        sys.stdout = old_out
        results.append((idx, p, b))
    return results

# ── Main display loop ─────────────────────────────────
print("FlowStalker Meter+Digest started.")
print("Run 'h1 ping h2 -c 200' in Mininet.")
print("Alerts will appear instantly when meter goes RED.")
print("")

try:
    while True:
        os.system("clear")
        now = time.strftime("%H:%M:%S")

        print("=" * 65)
        print("  FlowStalker — Meter + Digest Alert System  [" + now + "]")
        print("=" * 65)
        print("  Alert threshold:   Flow triggers alert after 50 packets")
        print("  Alert method:      Switch pushes digest — NO controller polling")
        print("")

        # Port counters
        for sw_id in ["s1", "s2", "s3", "s4"]:
            print("  [" + sw_id.upper() + " Port Counters]")
            print("  " + "-" * 48)
            for idx, pkts, byts in read_port_counters(sw_id):
                if pkts > 0:
                    print("  Port " + str(idx) + ":  " +
                          str(pkts).rjust(6) + " pkts   " +
                          str(byts).rjust(8) + " bytes")
            print("")

        # Show all alerts received so far
        print("  [Autonomous Alerts Received from Switches]")
        print("  " + "-" * 60)
        with alerts_lock:
            if not alerts_received:
                print("  No alerts yet — send traffic to trigger meters")
            else:
                print("  " +
                      "Switch".ljust(8) +
                      "Flow".ljust(32) +
                      "Pkts".rjust(8) +
                      "Bytes".rjust(10) +
                      "Time".rjust(10))
                print("  " + "-" * 68)
                for a in alerts_received[-20:]:
                    flow_str = a["src_ip"] + " -> " + a["dst_ip"]
                    print("  " +
                          a["switch"].ljust(8) +
                          flow_str.ljust(32) +
                          str(a["pkt_count"]).rjust(8) +
                          str(a["byte_count"]).rjust(10) +
                          a["received_at"].rjust(10))

        print("")
        print("  [Refreshing in 3s... Ctrl+C to stop]")
        time.sleep(3)

except KeyboardInterrupt:
    print("\n[FlowStalker stopped]")

