"""
visualize_graph.py — MetaBP-RTS Phase 1
=======================================
Visualisation HTML du graphe de dépendances G = (N, E, W).

Améliorations par rapport à la version précédente :
  1. AUCUNE valeur codée en dur : τ_dormant est dérivé des scores réels
     (frontière AutoThreshold : (min Θ dormants + max Θ non-dormants)/2),
     et les poids ω sont lus depuis ewm_critic_weights_phase1.json
     s'il existe (sinon la ligne n'est pas affichée — jamais inventée).
  2. Layout hiérarchique parent→enfant (BFS) avec ordonnancement
     BARYCENTRIQUE de chaque niveau (réduit les croisements d'arcs).
  3. Étiquettes w_ij affichées AU SURVOL uniquement (plus de superposition) ;
     l'information permanente est portée par l'épaisseur et la couleur.
  4. Tooltips natifs <title> : détail complet des arcs (w, rate, lat, err,
     freq) et des services (C, P, F, Θ, niveau d'appel).
  5. Dimensions du SVG adaptatives (nb de niveaux / nb max de nœuds).

Interface conservée : generate(base_dir) et main() identiques.
"""

import json
import argparse
from pathlib import Path


# ────────────────────────────────────────────────────────────────────────────
# Chargement des données
# ────────────────────────────────────────────────────────────────────────────

def load_data(base_dir: Path):
    graph_path  = base_dir / "data/outputs/service_graph.json"
    scores_path = base_dir / "data/outputs/service_scores.json"

    with open(graph_path,  encoding="utf-8") as f:
        graph = json.load(f)
    with open(scores_path, encoding="utf-8") as f:
        scores = json.load(f)

    return graph, scores


def derive_tau(scores):
    """
    Derive tau_dormant des scores reels par la formule frontiere
    AutoThreshold : tau = (min Theta des dormants + max Theta des
    non-dormants) / 2. Retourne None si un des groupes est vide.
    """
    dorm = [s["theta_dormant"] for s in scores if s.get("is_dormant")]
    rest = [s["theta_dormant"] for s in scores if not s.get("is_dormant")]
    if dorm and rest:
        return round((min(dorm) + max(rest)) / 2, 4)
    return None


def load_omegas(base_dir: Path):
    """
    Tente de lire les poids EWM-CRITIC reels depuis
    ewm_critic_weights_phase1.json. Structure inconnue a priori :
    recherche defensive. Retourne None si introuvable.
    """
    p = base_dir / "data/outputs/ewm_critic_weights_phase1.json"
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    def find_weights(node):
        if isinstance(node, dict):
            keys = {str(k) for k in node.keys()}
            if keys & {"C", "P", "F"} and all(
                isinstance(v, (int, float)) for v in node.values()
            ):
                return {k: float(v) for k, v in node.items()}
            for k in ("weights_combined", "combined", "weights", "omega",
                      "final", "weighting"):
                if k in node:
                    r = find_weights(node[k])
                    if r:
                        return r
            for v in node.values():
                r = find_weights(v)
                if r:
                    return r
        return None

    return find_weights(data)


# ────────────────────────────────────────────────────────────────────────────
# Layout hiérarchique + ordonnancement barycentrique
# ────────────────────────────────────────────────────────────────────────────

def compute_layout(nodes, links):
    """
    1. Niveaux par BFS depuis les racines (services sans appelant) :
       le niveau vertical materialise la hierarchie appelant -> appele.
    2. Dans chaque niveau, ordre BARYCENTRIQUE : chaque noeud est place
       pres de la moyenne des positions de ses parents (2 passes).
    """
    node_ids = [n["id"] for n in nodes]
    children = {n: [] for n in node_ids}
    parents  = {n: [] for n in node_ids}

    for l in links:
        s, t = l["source"], l["target"]
        if s in children:
            children[s].append(t)
        if t in parents:
            parents[t].append(s)

    roots = [n for n in node_ids if not parents[n]] or [node_ids[0]]

    levels  = {r: 0 for r in roots}
    queue   = list(roots)
    visited = set(roots)
    while queue:
        cur = queue.pop(0)
        for ch in children[cur]:
            if ch not in visited:
                levels[ch] = levels[cur] + 1
                visited.add(ch)
                queue.append(ch)

    max_level = max(levels.values()) if levels else 0
    for n in node_ids:
        levels.setdefault(n, max_level + 1)

    level_groups = {}
    for n, lv in levels.items():
        level_groups.setdefault(lv, []).append(n)

    n_levels      = max(level_groups.keys()) + 1
    max_per_level = max(len(g) for g in level_groups.values())

    W = max(900, 120 * max_per_level + 160)
    H = max(420, 190 * n_levels)
    margin_x, margin_y = 90, 90

    order = {0: sorted(level_groups.get(0, []))}
    for lv in range(1, n_levels):
        group = level_groups.get(lv, [])
        prev  = {nid: i for i, nid in enumerate(order.get(lv - 1, []))}

        def bary(nid):
            ps = [prev[p] for p in parents[nid] if p in prev]
            return sum(ps) / len(ps) if ps else len(prev) / 2

        order[lv] = sorted(group, key=lambda nid: (bary(nid), nid))

    for lv in range(1, n_levels):
        prev = {nid: i for i, nid in enumerate(order.get(lv - 1, []))}

        def bary2(nid):
            ps = [prev[p] for p in parents[nid] if p in prev]
            return sum(ps) / len(ps) if ps else len(prev) / 2

        order[lv] = sorted(order[lv], key=lambda nid: (bary2(nid), nid))

    positions = {}
    for lv in range(n_levels):
        group = order.get(lv, [])
        if not group:
            continue
        y = margin_y + lv * ((H - 2 * margin_y) / max(n_levels - 1, 1))
        n = len(group)
        for i, nid in enumerate(group):
            x = (margin_x + i * ((W - 2 * margin_x) / max(n - 1, 1))
                 if n > 1 else W / 2)
            positions[nid] = (round(x), round(y))

    return positions, levels, W, H


# ────────────────────────────────────────────────────────────────────────────
# Construction du HTML
# ────────────────────────────────────────────────────────────────────────────

def build_html(graph: dict, scores: list, base_dir: Path) -> str:
    score_map = {s["service_name"]: s for s in scores}
    nodes = graph.get("nodes", [])
    links = graph.get("links", [])

    nodes_js = []
    for n in nodes:
        name = n["id"]
        sc   = score_map.get(name, {})
        nodes_js.append({
            "id":      name,
            "theta":   round(sc.get("theta_dormant", 0), 4),
            "C":       round(sc.get("C", 0), 4),
            "P":       round(sc.get("P", 0), 4),
            "F":       round(sc.get("F", 0), 4),
            "dormant": sc.get("is_dormant", False),
        })

    links_js = []
    for l in links:
        links_js.append({
            "source":   l["source"],
            "target":   l["target"],
            "w_ij":     round(l.get("w_ij",    0), 4),
            "rate_ij":  round(l.get("rate_ij", 0), 4),
            "lat_norm": round(l.get("lat_norm", 0), 4),
            "err_ij":   round(l.get("err_ij",  0), 4),
            "freq":     l.get("freq", 0),
        })

    dormant_count     = sum(1 for s in scores if s.get("is_dormant"))
    non_dormant_count = len(scores) - dormant_count
    avg_w   = round(sum(l["w_ij"] for l in links_js) / max(len(links_js), 1), 4)
    density = round(len(links_js) / max(len(nodes_js) * (len(nodes_js) - 1), 1), 4)

    tau    = derive_tau(scores)
    omegas = load_omegas(base_dir)
    tau_txt = f"{tau:.4f}" if tau is not None else "n/a"

    positions, levels, SVG_W, SVG_H = compute_layout(nodes, links)
    NODE_R = 34

    def short(name):
        return name.replace("-service", "").replace("ts-", "")

    def w_color(w):
        if w >= 0.6:
            return "#ef4444"
        if w >= 0.4:
            return "#f59e0b"
        return "#14b8a6"

    def w_marker(w):
        if w >= 0.6:
            return "arrR"
        if w >= 0.4:
            return "arrO"
        return "arrT"

    # ── Arcs SVG ──
    arcs_svg = []
    for idx, l in enumerate(links_js):
        sx, sy = positions.get(l["source"], (100, 100))
        tx, ty = positions.get(l["target"], (200, 200))
        dx, dy = tx - sx, ty - sy
        dist   = max((dx**2 + dy**2) ** 0.5, 1)
        x1 = sx + dx / dist * NODE_R
        y1 = sy + dy / dist * NODE_R
        x2 = tx - dx / dist * (NODE_R + 9)
        y2 = ty - dy / dist * (NODE_R + 9)

        same_level = levels.get(l["source"]) == levels.get(l["target"])
        bend = 0.28 if same_level else 0.10
        cx = (x1 + x2) / 2 - dy * bend
        cy = (y1 + y2) / 2 + dx * bend

        color  = w_color(l["w_ij"])
        marker = w_marker(l["w_ij"])
        width  = 1.4 + l["w_ij"] * 4.2
        lx = (x1 + 2 * cx + x2) / 4
        ly = (y1 + 2 * cy + y2) / 4 - 6

        tooltip = (f"{l['source']} -> {l['target']}"
                   f"&#10;w_ij = {l['w_ij']:.4f}"
                   f"&#10;rate = {l['rate_ij']:.4f} | lat = {l['lat_norm']:.4f}"
                   f" | err = {l['err_ij']:.4f}"
                   f"&#10;frequence = {l['freq']} appels")

        arcs_svg.append(f'''
  <g class="edge" data-i="{idx}">
    <path d="M{x1:.1f},{y1:.1f} Q{cx:.1f},{cy:.1f} {x2:.1f},{y2:.1f}"
          fill="none" stroke="{color}" stroke-width="{width:.1f}"
          marker-end="url(#{marker})" opacity="0.75">
      <title>{tooltip}</title>
    </path>
    <text id="wl{idx}" x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle"
          font-size="11" fill="{color}" font-weight="700"
          font-family="monospace" visibility="hidden"
          paint-order="stroke" stroke="#0f1117" stroke-width="3">w={l["w_ij"]:.3f}</text>
  </g>''')

    # ── Nœuds SVG ──
    nodes_svg = []
    for nd in nodes_js:
        x, y   = positions.get(nd["id"], (SVG_W // 2, SVG_H // 2))
        fill   = "#3b1f8c" if nd["dormant"] else "#0f4c3a"
        stroke = "#8b5cf6" if nd["dormant"] else "#14b8a6"
        label  = short(nd["id"])
        tooltip = (f"{nd['id']}"
                   f"&#10;Theta_dormant = {nd['theta']:.4f}"
                   f"&#10;C = {nd['C']:.4f} | P = {nd['P']:.4f} | F = {nd['F']:.4f}"
                   f"&#10;niveau d'appel = {levels.get(nd['id'], '?')}")
        badge = (f'<text x="{x}" y="{y + 21}" text-anchor="middle" font-size="8"'
                 f' fill="#c4b5fd" font-family="monospace"'
                 f' font-weight="700">DORMANT</text>'
                 if nd["dormant"] else "")

        nodes_svg.append(f'''
  <g class="node">
    <circle cx="{x}" cy="{y}" r="{NODE_R}" fill="{fill}"
            stroke="{stroke}" stroke-width="2.5">
      <title>{tooltip}</title>
    </circle>
    <text x="{x}" y="{y - 7}" text-anchor="middle" dominant-baseline="central"
          font-size="11" font-weight="700" fill="#f1f5f9"
          font-family="'Segoe UI',sans-serif" pointer-events="none">{label}</text>
    <text x="{x}" y="{y + 8}" text-anchor="middle" dominant-baseline="central"
          font-size="9" fill="#94a3b8" font-family="monospace"
          pointer-events="none">&#920;={nd["theta"]:.3f}</text>
    {badge}
  </g>''')

    # ── Étiquettes de niveau ──
    level_labels = []
    level_names = {0: "niveau 0 &#8212; points d'entree (jamais appeles)"}
    for lv in sorted(set(levels.values())):
        name = level_names.get(lv, f"niveau {lv} &#8212; appeles (profondeur {lv})")
        ys = [positions[n][1] for n in levels
              if levels[n] == lv and n in positions]
        if not ys:
            continue
        level_labels.append(
            f'<text x="12" y="{min(ys) - 52}" font-size="10" fill="#475569" '
            f'font-family="monospace">{name}</text>'
            f'<line x1="8" y1="{min(ys) - 46}" x2="{SVG_W - 8}" '
            f'y2="{min(ys) - 46}" stroke="#1e2535" stroke-dasharray="4 6"/>'
        )

    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 {SVG_W} {SVG_H}" width="100%"
     style="background:#0f1117;border-radius:8px">
  <defs>
    <marker id="arrT" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5"
            markerHeight="5" orient="auto-start-reverse">
      <path d="M2 1L8 5L2 9" fill="none" stroke="#14b8a6" stroke-width="1.6"/>
    </marker>
    <marker id="arrO" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5"
            markerHeight="5" orient="auto-start-reverse">
      <path d="M2 1L8 5L2 9" fill="none" stroke="#f59e0b" stroke-width="1.6"/>
    </marker>
    <marker id="arrR" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5"
            markerHeight="5" orient="auto-start-reverse">
      <path d="M2 1L8 5L2 9" fill="none" stroke="#ef4444" stroke-width="1.6"/>
    </marker>
  </defs>
  {"".join(level_labels)}
  {"".join(arcs_svg)}
  {"".join(nodes_svg)}
</svg>
<script>
document.querySelectorAll('.edge').forEach(function(g) {{
  var lbl = document.getElementById('wl' + g.dataset.i);
  var path = g.querySelector('path');
  g.addEventListener('mouseenter', function() {{
    lbl.setAttribute('visibility', 'visible');
    path.setAttribute('opacity', '1');
    path.setAttribute('stroke-width',
        (parseFloat(path.getAttribute('stroke-width')) + 1.5));
  }});
  g.addEventListener('mouseleave', function() {{
    lbl.setAttribute('visibility', 'hidden');
    path.setAttribute('opacity', '0.75');
    path.setAttribute('stroke-width',
        (parseFloat(path.getAttribute('stroke-width')) - 1.5));
  }});
}});
</script>'''

    # ── Tableau des scores ──
    rows_stats = []
    for nd in sorted(nodes_js, key=lambda x: x["theta"], reverse=True):
        badge = ('<span style="background:#3b2f7f;color:#c4b5fd;padding:1px 6px;'
                 'border-radius:4px;font-size:0.68rem">DORMANT</span>'
                 if nd["dormant"] else
                 '<span style="background:#134e4a;color:#5eead4;padding:1px 6px;'
                 'border-radius:4px;font-size:0.68rem">actif</span>')
        bars = ""
        for key, colr in (("theta", "#f59e0b"), ("C", "#14b8a6"),
                          ("P", "#8b5cf6")):
            v = nd[key]
            bars += (f'<td><div style="display:flex;align-items:center;gap:6px">'
                     f'<div style="width:60px;height:4px;background:#1e2535;'
                     f'border-radius:2px"><div style="width:{v*100:.1f}%;'
                     f'height:4px;background:{colr};border-radius:2px">'
                     f'</div></div>'
                     f'<span style="font-family:monospace;color:{colr}">'
                     f'{v:.4f}</span></div></td>')
        f_color = "#f87171" if nd["F"] > 0 else "#94a3b8"
        rows_stats.append(
            f'<tr><td style="font-weight:600;color:#e2e8f0">{nd["id"]}</td>'
            f'<td>{badge}</td>{bars}'
            f'<td style="font-family:monospace;color:{f_color}">'
            f'{nd["F"]:.4f}</td></tr>'
        )

    # ── Tableau des arcs ──
    rows_arcs = []
    for l in sorted(links_js, key=lambda x: x["w_ij"], reverse=True):
        c = w_color(l["w_ij"])
        rows_arcs.append(
            f'<tr><td style="font-family:monospace;color:#e2e8f0">'
            f'{l["source"]}</td>'
            f'<td style="text-align:center;color:#64748b">&#8594;</td>'
            f'<td style="font-family:monospace;color:#e2e8f0">'
            f'{l["target"]}</td>'
            f'<td style="font-family:monospace;color:{c};font-weight:700">'
            f'{l["w_ij"]:.4f}</td>'
            f'<td style="font-family:monospace">{l["rate_ij"]:.4f}</td>'
            f'<td style="font-family:monospace">{l["lat_norm"]:.4f}</td>'
            f'<td style="font-family:monospace">{l["err_ij"]:.4f}</td>'
            f'<td style="font-family:monospace;color:#94a3b8">'
            f'{l["freq"]}</td></tr>'
        )

    omega_formula = ""
    if omegas:
        parts = " &#183; ".join(
            f"<strong>&#969;_{k}</strong>={v:.4f}" for k, v in omegas.items()
        )
        omega_formula = (f'<div class="formula">{parts} '
                         f'<span style="color:#475569">'
                         f'(EWM-CRITIC, run courant)</span></div>')

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>MetaBP-RTS &#8212; Graphe G (Phase 1)</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0a0c10; color:#cbd5e1;
       font-family:'Segoe UI',system-ui,sans-serif; }}
header {{ display:flex; align-items:center; gap:1rem; flex-wrap:wrap;
         padding:1rem 1.5rem; border-bottom:1px solid #1e2535;
         background:#0f1117; }}
h1 {{ font-size:1rem; letter-spacing:0.04em; color:#e2e8f0;
     text-transform:uppercase; }}
.badge {{ font-size:0.7rem; padding:2px 10px; border-radius:12px;
         font-family:monospace; }}
.badge-g {{ background:#132036; color:#93c5fd; }}
.badge-d {{ background:#2a1f5e; color:#c4b5fd; }}
.badge-n {{ background:#134e4a; color:#5eead4; }}
.main {{ padding:1.25rem; display:flex; flex-direction:column;
        gap:1.25rem; max-width:1500px; margin:0 auto; }}
.section {{ background:#141821; border:1px solid #1e2535;
           border-radius:10px; overflow:hidden; }}
.section-title {{ padding:0.7rem 1.25rem; font-size:0.72rem;
                 font-weight:700; text-transform:uppercase;
                 letter-spacing:0.1em; color:#64748b;
                 border-bottom:1px solid #1e2535; background:#0f1117; }}
.graph-container {{ padding:1rem; }}
.metrics-grid {{ display:grid;
                grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
                gap:1px; background:#1e2535; }}
.metric-card {{ background:#141821; padding:0.9rem 1.1rem; }}
.metric-label {{ font-size:0.65rem; text-transform:uppercase;
                letter-spacing:0.08em; color:#64748b; }}
.metric-value {{ font-size:1.5rem; font-weight:700; font-family:monospace;
                margin-top:2px; }}
.metric-sub {{ font-size:0.65rem; color:#475569; font-family:monospace; }}
.legend {{ display:flex; gap:1.5rem; padding:0.75rem 1.25rem;
          border-top:1px solid #1e2535; background:#0f1117;
          flex-wrap:wrap; align-items:center; }}
.legend-item {{ display:flex; align-items:center; gap:6px;
               font-size:0.72rem; color:#94a3b8; }}
.legend-dot {{ width:12px; height:12px; border-radius:50%;
              border:2px solid; }}
.legend-line {{ width:24px; border-radius:2px; }}
table {{ width:100%; border-collapse:collapse; font-size:0.8rem; }}
thead th {{ padding:0.6rem 1rem; text-align:left; font-size:0.67rem;
           font-weight:700; text-transform:uppercase;
           letter-spacing:0.08em; color:#64748b;
           border-bottom:1px solid #1e2535; background:#0f1117;
           position:sticky; top:0; }}
tbody td {{ padding:0.65rem 1rem; border-bottom:1px solid #0f1117;
           vertical-align:middle; }}
tbody tr:hover td {{ background:#1a1f2e; }}
.formulas {{ padding:1.25rem; display:flex; gap:1rem 2rem;
            flex-wrap:wrap; }}
.formula {{ font-family:monospace; font-size:0.8rem; color:#94a3b8;
           background:#0f1117; padding:0.5rem 1rem; border-radius:6px;
           border:1px solid #1e2535; }}
.formula strong {{ color:#e2e8f0; }}
.hint {{ padding:0.5rem 1.25rem; font-size:0.7rem; color:#475569;
        border-top:1px solid #1e2535; background:#0f1117; }}
</style>
</head>
<body>

<header>
  <h1>MetaBP-RTS &#8212; Graphe de services G &#183; Phase 1</h1>
  <span class="badge badge-g">{len(nodes_js)} services &#183; {len(links_js)} arcs</span>
  <span class="badge badge-d">{dormant_count} &#201;cho-Dormant(s)</span>
  <span class="badge badge-n">{non_dormant_count} Non-Dormant(s)</span>
  <span style="margin-left:auto;font-size:0.7rem;color:#475569">
    &#964;_dormant = {tau_txt} (AutoThreshold, d&#233;riv&#233; du run courant)
  </span>
</header>

<div class="main">

  <div class="section">
    <div class="section-title">M&#233;triques globales</div>
    <div class="metrics-grid">
      <div class="metric-card"><div class="metric-label">Services</div>
        <div class="metric-value" style="color:#93c5fd">{len(nodes_js)}</div>
        <div class="metric-sub">n&#339;uds de G</div></div>
      <div class="metric-card"><div class="metric-label">D&#233;pendances</div>
        <div class="metric-value" style="color:#93c5fd">{len(links_js)}</div>
        <div class="metric-sub">arcs de G</div></div>
      <div class="metric-card"><div class="metric-label">Densit&#233;</div>
        <div class="metric-value" style="color:#94a3b8;font-size:1.2rem">{density:.4f}</div>
        <div class="metric-sub">|E| / |V|(|V|&#8722;1)</div></div>
      <div class="metric-card"><div class="metric-label">w_ij moyen</div>
        <div class="metric-value" style="color:#f59e0b;font-size:1.2rem">{avg_w:.4f}</div>
        <div class="metric-sub">poids moyen des arcs</div></div>
      <div class="metric-card"><div class="metric-label">&#201;cho-Dormants</div>
        <div class="metric-value" style="color:#a78bfa">{dormant_count}</div>
        <div class="metric-sub">&#920; &#8805; &#964; = {tau_txt}</div></div>
      <div class="metric-card"><div class="metric-label">Non-Dormants</div>
        <div class="metric-value" style="color:#5eead4">{non_dormant_count}</div>
        <div class="metric-sub">&#920; &lt; &#964; = {tau_txt}</div></div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">Graphe G &#8212; hi&#233;rarchie appelant &#8594; appel&#233;
      (agr&#233;gation des relations parent-enfant des spans)</div>
    <div class="graph-container">
      {svg_content}
    </div>
    <div class="legend">
      <div class="legend-item">
        <div class="legend-dot" style="background:#3b1f8c;border-color:#8b5cf6"></div>
        &#201;cho-Dormant (&#920; &#8805; {tau_txt})</div>
      <div class="legend-item">
        <div class="legend-dot" style="background:#0f4c3a;border-color:#14b8a6"></div>
        Non-Dormant (&#920; &lt; {tau_txt})</div>
      <div class="legend-item">
        <div class="legend-line" style="background:#14b8a6;height:2px"></div>
        w_ij &lt; 0.40</div>
      <div class="legend-item">
        <div class="legend-line" style="background:#f59e0b;height:3px"></div>
        0.40 &#8804; w_ij &lt; 0.60</div>
      <div class="legend-item">
        <div class="legend-line" style="background:#ef4444;height:4px"></div>
        w_ij &#8805; 0.60</div>
      <div class="legend-item" style="color:#475569">
        &#233;paisseur &#8733; w_ij &#183; survoler un arc pour w exact &#183;
        survoler un n&#339;ud pour C/P/F/&#920;</div>
    </div>
    <div class="hint">
      Lecture : un arc s_i &#8594; s_j signifie &#171; des spans du service s_i
      ont &#233;t&#233; parents de spans du service s_j dans les traces &#187;
      (relation appelant &#8594; appel&#233; agr&#233;g&#233;e sur l'ensemble
      des traces). Les niveaux verticaux mat&#233;rialisent la profondeur
      d'appel : niveau 0 = services jamais appel&#233;s (points d'entr&#233;e
      du trafic observ&#233;).
    </div>
  </div>

  <div class="section">
    <div class="section-title">Formules MetaBP-RTS (param&#232;tres du run courant)</div>
    <div class="formulas">
      <div class="formula"><strong>w_ij</strong> = &#945;&#183;rate_ij + &#946;&#183;lat_norm + &#947;&#183;err_ij</div>
      <div class="formula"><strong>&#920;(s_i)</strong> = &#969;_C&#183;C + &#969;_P&#183;P + &#969;_F&#183;F</div>
      <div class="formula"><strong>S_dormant</strong> = &#123; s_i | &#920;(s_i) &#8805; &#964; &#125;
        &#183; <strong>&#964;</strong> = {tau_txt}</div>
      {omega_formula}
    </div>
  </div>

  <div class="section">
    <div class="section-title">Scores par service &#8212; &#920;, C, P, F</div>
    <div style="overflow-x:auto"><table>
      <thead><tr><th>Service</th><th>Statut</th><th>&#920;_dormant</th>
        <th>C &#8212; Centralit&#233;</th><th>P &#8212; Propagation</th>
        <th>F &#8212; Fragilit&#233;</th>
      </tr></thead>
      <tbody>{"".join(rows_stats)}</tbody>
    </table></div>
  </div>

  <div class="section">
    <div class="section-title">Arcs de G &#8212; poids w_ij et composantes</div>
    <div style="overflow-x:auto"><table>
      <thead><tr><th>Source</th><th></th><th>Cible</th><th>w_ij</th>
        <th>rate_ij</th><th>lat_norm</th><th>err_ij</th><th>fr&#233;q.</th>
      </tr></thead>
      <tbody>{"".join(rows_arcs)}</tbody>
    </table></div>
  </div>

</div>
</body>
</html>"""
    return html


def generate(base_dir: Path) -> Path:
    graph, scores = load_data(base_dir)
    html = build_html(graph, scores, base_dir)
    output = base_dir / "data/outputs/graph_visualization.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(html)
    return output


def main():
    parser = argparse.ArgumentParser(
        description="MetaBP-RTS - Visualisation du graphe G"
    )
    parser.add_argument("--base-dir", default="..",
                        help="Repertoire phase1/ (defaut: ..)")
    args = parser.parse_args()
    base_dir = Path(args.base_dir).resolve()
    output = generate(base_dir)
    print(f"Visualisation generee -> {output}")
    print(f"Ouvrir dans le navigateur : file://{output}")


if __name__ == "__main__":
    main()