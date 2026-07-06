#!/usr/bin/env python3

# ── Data ──────────────────────────────────────────────
methods       = ["Traditional Polling", "Crawler Packet", "Meter+Digest (Ours)"]
control_bytes = [819200, 100, 400]
cp_crossings  = [4096, 2, 8]
latency_ms    = [3000, 114, 13]          # ← 114ms from real crawler measurement
colors        = ["#EF553B", "#FFA15A", "#00CC96"]

alert_seq  = [1, 2, 3, 4, 5, 6, 7, 8]
arrival_ms = [0.0, 3.7, 5.3, 7.1, 8.4, 8.8, 9.3, 12.8]
sw_labels  = ["s1→fwd","s2→fwd","s4→fwd","s3→fwd",
              "s4→rev","s2→rev","s1→rev","s3→rev"]

def make_bar_chart(title, methods, values, colors, value_labels,
                   ylabel, filename, log_scale=False):
    W, H     = 600, 400
    ml,mr    = 80, 30
    mt,mb    = 60, 80
    pw       = W - ml - mr
    ph       = H - mt - mb
    n        = len(methods)
    bw       = pw // (n * 3 + 1)  # ← fixed
    gap      = bw

    import math
    if log_scale:
        log_vals = [math.log10(max(v,1)) for v in values]
        max_log  = math.ceil(max(log_vals)) + 0.5
        def to_y(v):
            return ph - int((math.log10(max(v,1)) / max_log) * ph)
        tick_vals = [10**i for i in range(0, int(max_log)+1)]
        ticks = [(to_y(tv), f"{tv:,}") for tv in tick_vals if tv <= max(values)*2]
    else:
        max_v = max(values) * 1.15
        def to_y(v):
            return ph - int((v / max_v) * ph)
        step  = max_v / 5
        ticks = [(to_y(step*i), f"{int(step*i):,}") for i in range(0,6)]

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">')
    svg.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    svg.append(f'<text x="{W//2}" y="35" text-anchor="middle" '
               f'font-size="15" font-weight="bold" font-family="Arial">{title}</text>')

    # Y axis label
    svg.append(f'<text x="15" y="{mt + ph//2}" text-anchor="middle" '
               f'font-size="11" font-family="Arial" '
               f'transform="rotate(-90,15,{mt + ph//2})">{ylabel}</text>')

    # Grid + ticks
    for ty, tlabel in ticks:
        gy = mt + ty
        svg.append(f'<line x1="{ml}" y1="{gy}" x2="{ml+pw}" y2="{gy}" '
                   f'stroke="#ddd" stroke-width="1"/>')
        svg.append(f'<text x="{ml-5}" y="{gy+4}" text-anchor="end" '
                   f'font-size="10" font-family="Arial">{tlabel}</text>')

    # Axes
    svg.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+ph}" '
               f'stroke="#333" stroke-width="2"/>')
    svg.append(f'<line x1="{ml}" y1="{mt+ph}" x2="{ml+pw}" y2="{mt+ph}" '
               f'stroke="#333" stroke-width="2"/>')

    # Bars
    for i, (m, v, c, vl) in enumerate(zip(methods, values, colors, value_labels)):
        bx = ml + gap + i * (bw + gap*3)
        by = mt + to_y(v)
        bh = mt + ph - by
        svg.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" '
                   f'fill="{c}" rx="3"/>')
        # value label on top
        svg.append(f'<text x="{bx + bw//2}" y="{by - 5}" text-anchor="middle" '
                   f'font-size="11" font-weight="bold" font-family="Arial">{vl}</text>')
        # x label (word-wrapped)
        words = m.split()
        for wi, word in enumerate(words):
            svg.append(f'<text x="{bx + bw//2}" y="{mt+ph+18+wi*14}" '
                       f'text-anchor="middle" font-size="10" font-family="Arial">{word}</text>')

    svg.append('</svg>')

    with open(filename, 'w') as f:
        f.write('\n'.join(svg))
    print(f"[SAVED] {filename}")


def make_line_chart(title, x_vals, y_vals, labels, ylabel, xlabel, filename):
    W, H  = 700, 380
    ml,mr = 80, 30
    mt,mb = 60, 80
    pw    = W - ml - mr
    ph    = H - mt - mb

    max_x = max(x_vals)
    max_y = 16
    def px(x): return ml + int((x-1) / (max_x-1) * pw)
    def py(y): return mt + ph - int((y / max_y) * ph)

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">')
    svg.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    svg.append(f'<text x="{W//2}" y="35" text-anchor="middle" '
               f'font-size="15" font-weight="bold" font-family="Arial">{title}</text>')

    # Y axis label
    svg.append(f'<text x="15" y="{mt+ph//2}" text-anchor="middle" '
               f'font-size="11" font-family="Arial" '
               f'transform="rotate(-90,15,{mt+ph//2})">{ylabel}</text>')

    # X axis label
    svg.append(f'<text x="{ml+pw//2}" y="{H-10}" text-anchor="middle" '
               f'font-size="11" font-family="Arial">{xlabel}</text>')

    # Grid lines Y
    for yv in range(0, 17, 2):
        gy = py(yv)
        svg.append(f'<line x1="{ml}" y1="{gy}" x2="{ml+pw}" y2="{gy}" '
                   f'stroke="#ddd" stroke-width="1"/>')
        svg.append(f'<text x="{ml-5}" y="{gy+4}" text-anchor="end" '
                   f'font-size="10" font-family="Arial">{yv}</text>')

    # Axes
    svg.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+ph}" '
               f'stroke="#333" stroke-width="2"/>')
    svg.append(f'<line x1="{ml}" y1="{mt+ph}" x2="{ml+pw}" y2="{mt+ph}" '
               f'stroke="#333" stroke-width="2"/>')

    # Max line
    svg.append(f'<line x1="{ml}" y1="{py(12.8)}" x2="{ml+pw}" y2="{py(12.8)}" '
               f'stroke="red" stroke-width="1" stroke-dasharray="6,3" opacity="0.5"/>')
    svg.append(f'<text x="{ml+pw-5}" y="{py(12.8)-4}" text-anchor="end" '
               f'font-size="10" fill="red" font-family="Arial">Max=12.8ms</text>')

    # Fill area
    fill_pts = [f"{px(x)},{py(y)}" for x,y in zip(x_vals, y_vals)]
    fill_pts = [f"{px(x_vals[0])},{py(0)}"] + fill_pts + [f"{px(x_vals[-1])},{py(0)}"]
    svg.append(f'<polygon points="{" ".join(fill_pts)}" fill="#00CC96" opacity="0.15"/>')

    # Line
    pts = " ".join([f"{px(x)},{py(y)}" for x,y in zip(x_vals, y_vals)])
    svg.append(f'<polyline points="{pts}" fill="none" stroke="#00CC96" stroke-width="2.5"/>')

    # Dots + labels
    for x, y, label in zip(x_vals, y_vals, labels):
        svg.append(f'<circle cx="{px(x)}" cy="{py(y)}" r="6" '
                   f'fill="white" stroke="#00CC96" stroke-width="2.5"/>')
        svg.append(f'<text x="{px(x)}" y="{py(y)-10}" text-anchor="middle" '
                   f'font-size="10" font-family="Arial" fill="#333">{label}</text>')

    # X ticks
    for x in x_vals:
        svg.append(f'<text x="{px(x)}" y="{mt+ph+16}" text-anchor="middle" '
                   f'font-size="10" font-family="Arial">{x}</text>')

    svg.append('</svg>')
    with open(filename, 'w') as f:
        f.write('\n'.join(svg))
    print(f"[SAVED] {filename}")


# ── Generate all 4 graphs ─────────────────────────────
make_bar_chart(
    "Control Plane Bytes",
    methods, control_bytes, colors,
    ["819 KB", "100 B", "400 B"],
    "Bytes (log scale)",
    "graph_bytes.svg",
    log_scale=True
)

make_bar_chart(
    "Control Path Crossings",
    methods, cp_crossings, colors,
    ["4096", "2", "8"],
    "Crossings (log scale)",
    "graph_crossings.svg",
    log_scale=True
)

make_bar_chart(
    "Detection Latency",
    methods, latency_ms, colors,
    ["3000 ms", "114 ms", "13 ms"],   # ← real measured values
    "Latency ms (log scale)",
    "graph_latency.svg",
    log_scale=True                     # ← log scale so 13ms bar is visible
)

make_line_chart(
    "Alert Arrival at Controller (Real Data)",
    alert_seq, arrival_ms, sw_labels,
    "Time since first alert (ms)",
    "Alert Sequence Number",
    "graph_alert_spread.svg"
)

print("")
print("Open these files in any browser (Firefox/Chrome):")
print("  graph_bytes.svg")
print("  graph_crossings.svg")
print("  graph_latency.svg")
print("  graph_alert_spread.svg")

