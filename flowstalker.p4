#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4  = 0x0800;
const bit<32> FLOW_TABLE_SIZE = 1024;

typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

// ── Headers ───────────────────────────────────────────
header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<8>    diffserv;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
}

struct headers {
    ethernet_t ethernet;
    ipv4_t     ipv4;
}

// ── Digest struct ─────────────────────────────────────
// This is what the switch sends to the controller
// when a flow crosses the RED threshold
struct flow_alert_t {
    ip4Addr_t src_ip;       // flow source IP
    ip4Addr_t dst_ip;       // flow destination IP
    bit<32>   pkt_count;    // how many packets seen
    bit<32>   byte_count;   // how many bytes seen
    bit<48>   timestamp;    // when threshold was crossed
    bit<9>    ingress_port; // which port this flow came in on
    bit<7>    padding;      // keep byte alignment
}

struct metadata {
    bit<32>      flow_index;
    bit<2>       meter_color;   // 0=GREEN, 1=YELLOW, 2=RED
    flow_alert_t alert;
}

// ── Parser ────────────────────────────────────────────
parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {
    state start {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            default:   accept;
        }
    }
    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition accept;
    }
}

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply { }
}

// ── Ingress ───────────────────────────────────────────
control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    // Per-flow packet and byte counters
    register<bit<32>>(FLOW_TABLE_SIZE) pkt_count;
    register<bit<32>>(FLOW_TABLE_SIZE) byte_count;
    register<bit<48>>(FLOW_TABLE_SIZE) base_timestamp;

    // Per-flow alert flag — so we only alert ONCE per flow
    register<bit<1>>(FLOW_TABLE_SIZE)  alert_sent;

    // Meter — one per flow slot
    // CIR = committed info rate, CBS = committed burst size
    // PIR = peak info rate,      PBS = peak burst size
    // GREEN  = below CIR  → normal
    // YELLOW = between CIR and PIR → warning
    // RED    = above PIR  → alert!
    meter(FLOW_TABLE_SIZE, MeterType.packets) flow_meter;

    counter(256, CounterType.packets_and_bytes) port_counter;

    action set_egress(bit<9> port) {
        standard_metadata.egress_spec = port;
    }

    action drop_packet() {
        mark_to_drop(standard_metadata);
    }

    table forward_table {
        key = { standard_metadata.ingress_port : exact; }
        actions = { set_egress; drop_packet; NoAction; }
        default_action = NoAction;
        size = 8;
    }

    apply {
        port_counter.count((bit<32>) standard_metadata.ingress_port);

        if (hdr.ipv4.isValid()) {

            // Step 1 — Hash to get flow index
            hash(meta.flow_index,
                 HashAlgorithm.crc32,
                 (bit<32>) 0,
                 { hdr.ipv4.srcAddr, hdr.ipv4.dstAddr },
                 (bit<32>) FLOW_TABLE_SIZE);

            // Step 2 — Execute meter for this flow
            // Meter colors this packet GREEN / YELLOW / RED
            flow_meter.execute_meter(meta.flow_index, meta.meter_color);

            // Step 3 — Update counters regardless of color
            bit<32> pkts;
            bit<32> byts;
            pkt_count.read(pkts,   meta.flow_index);
            byte_count.read(byts,  meta.flow_index);
            pkts = pkts + 1;
            byts = byts + (bit<32>) hdr.ipv4.totalLen;
            pkt_count.write(meta.flow_index,  pkts);
            byte_count.write(meta.flow_index, byts);

            // Record base timestamp on first packet of flow
            bit<48> base_ts;
            base_timestamp.read(base_ts, meta.flow_index);
            if (base_ts == 0) {
                base_timestamp.write(meta.flow_index,
                    standard_metadata.ingress_global_timestamp);
            }

            // Step 4 — If RED and alert not sent yet → send digest to controller
            // Step 4 — Alert when packet count crosses threshold (50 packets)
            // Meter color kept for future use but threshold based on count
            if (pkts >= 50) {
                bit<1> already_alerted;
                alert_sent.read(already_alerted, meta.flow_index);

                if (already_alerted == 0) {
                    alert_sent.write(meta.flow_index, 1);
                    meta.alert.src_ip       = hdr.ipv4.srcAddr;
                    meta.alert.dst_ip       = hdr.ipv4.dstAddr;
                    meta.alert.pkt_count    = pkts;
                    meta.alert.byte_count   = byts;
                    meta.alert.timestamp    = standard_metadata.ingress_global_timestamp;
                    meta.alert.ingress_port = standard_metadata.ingress_port;
                    meta.alert.padding      = 0;
                    digest<flow_alert_t>(1, meta.alert);
                }
            }

            // Step 5 — Forward packet normally
            forward_table.apply();

        } else {
            mark_to_drop(standard_metadata);
        }
    }
}

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply { }
}

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version, hdr.ipv4.ihl, hdr.ipv4.diffserv,
              hdr.ipv4.totalLen, hdr.ipv4.identification,
              hdr.ipv4.flags, hdr.ipv4.fragOffset,
              hdr.ipv4.ttl, hdr.ipv4.protocol,
              hdr.ipv4.srcAddr, hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16
        );
    }
}

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
    }
}

V1Switch(
    MyParser(),
    MyVerifyChecksum(),
    MyIngress(),
    MyEgress(),
    MyComputeChecksum(),
    MyDeparser()
) main;

