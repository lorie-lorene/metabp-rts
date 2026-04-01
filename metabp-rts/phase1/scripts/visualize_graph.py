"""
visualize_graph.py
==================
BLOC      : Post-traitement Phase 1
ROLE      : Lit service_graph.json et service_scores.json et génère
            une page HTML avec :
              - Graphe G STATIQUE hiérarchique parent→enfant (style article)
              - Tableau de statistiques complet par service
              - Tableau récapitulatif des arcs avec poids w_ij
ENTREES   : data/outputs/service_graph.json
            data/outputs/service_scores.json
SORTIES   : data/outputs/graph_visualization.html
LIBRAIRIES: json, pathlib
USAGE     : python visualize_graph.py --base-dir ..
            (appelé automatiquement par run_phase1.py)
"""

import json
import argparse
from pathlib import Path


def load_data(base_dir: Path):
    graph_path  = base_dir / "data/outputs/service_graph.json"
    scores_path = base_dir / "data/outputs/service_scores.json"

    with open(graph_path,  encoding="utf-8") as f:
        graph = json.load(f)
    with open(scores_path, encoding="utf-8") as f:
        scores = json.load(f)

    return graph, scores


def compute_layout(nodes, links):
    """
    Calcule un layout hiérarchique parent→enfant.
    - Les noeuds sans parents entrants sont des racines (niveau 0)
    - Chaque niveau est espacé verticalement
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

    # Noeuds racines = pas de parent entrant
    roots = [n for n in node_ids if not parents[n]]
    if not roots:
        roots = [node_ids[0]]

    # BFS pour assigner les niveaux
    levels = {}
    queue  = list(roots)
    for r in roots:
        levels[r] = 0

    visited = set(roots)
    while queue:
        current = queue.pop(0)
        for child in children[current]:
            if child not in visited:
                levels[child] = levels[current] + 1
                visited.add(child)
                queue.append(child)

    # Noeuds non visités → niveau max+1
    max_level = max(levels.values()) if levels else 0
    for n in node_ids:
        if n not in levels:
            levels[n] = max_level + 1

    # Grouper par niveau
    level_groups = {}
    for n, lv in levels.items():
        level_groups.setdefault(lv, []).append(n)

    # Calculer les positions (SVG 900x500)
    W, H     = 900, 480
    margin_x = 80
    margin_y = 80
    positions = {}
    n_levels  = max(level_groups.keys()) + 1

    for lv, group in level_groups.items():
        y = margin_y + lv * ((H - 2 * margin_y) / max(n_levels - 1, 1))
        n_in_level = len(group)
        for i, nid in enumerate(sorted(group)):
            x = margin_x + i * ((W - 2 * margin_x) / max(n_in_level - 1, 1)) if n_in_level > 1 else W / 2
            positions[nid] = (round(x), round(y))

    return positions


def build_html(graph: dict, scores: list) -> str:
    score_map = {s["service_name"]: s for s in scores}

    nodes = graph.get("nodes", [])
    links = graph.get("links", [])

    nodes_js = []
    for n in nodes:
        name    = n["id"]
        sc      = score_map.get(name, {})
        dormant = sc.get("is_dormant", False)
        nodes_js.append({
            "id":      name,
            "theta":   round(sc.get("theta_dormant", 0), 4),
            "C":       round(sc.get("C", 0), 4),
            "P":       round(sc.get("P", 0), 4),
            "F":       round(sc.get("F", 0), 4),
            "dormant": dormant,
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
    avg_w = round(sum(l["w_ij"] for l in links_js) / max(len(links_js), 1), 4)
    density = round(len(links_js) / max(len(nodes_js) * (len(nodes_js) - 1), 1), 4)

    # Layout statique
    positions = compute_layout(nodes, links)

    # Générer le SVG du graphe statique
    SVG_W, SVG_H = 900, 480
    NODE_R = 36

    def short(name):
        return name.replace("-service", "").replace("ts-", "")

    def w_color(w):
        if w >= 0.6: return "#dc2626"
        if w >= 0.4: return "#f59e0b"
        return "#0d9488"

    # Construire les arcs SVG
    arcs_svg = []
    for l in links_js:
        sx, sy = positions.get(l["source"], (100, 100))
        tx, ty = positions.get(l["target"], (200, 200))
        # Direction
        dx, dy   = tx - sx, ty - sy
        dist     = max((dx**2 + dy**2)**0.5, 1)
        # Points de départ et arrivée sur le bord du noeud
        x1 = sx + dx / dist * NODE_R
        y1 = sy + dy / dist * NODE_R
        x2 = tx - dx / dist * (NODE_R + 8)
        y2 = ty - dy / dist * (NODE_R + 8)
        # Courbe de Bézier légère
        cx = (x1 + x2) / 2 - dy * 0.12
        cy = (y1 + y2) / 2 + dx * 0.12
        color = w_color(l["w_ij"])
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2 - 10

        arcs_svg.append(f'''
  <path d="M{x1:.1f},{y1:.1f} Q{cx:.1f},{cy:.1f} {x2:.1f},{y2:.1f}"
        fill="none" stroke="{color}" stroke-width="2"
        marker-end="url(#arr)" opacity="0.85"/>
  <text x="{mx:.1f}" y="{my:.1f}" text-anchor="middle"
        font-size="10" fill="{color}" font-weight="600"
        font-family="monospace">w={l["w_ij"]:.3f}</text>''')

    # Construire les noeuds SVG
    nodes_svg = []
    for nd in nodes_js:
        x, y    = positions.get(nd["id"], (SVG_W // 2, SVG_H // 2))
        fill    = "#3b1f8c" if nd["dormant"] else "#0f4c3a"
        stroke  = "#7c3aed" if nd["dormant"] else "#0d9488"
        label   = short(nd["id"])
        status  = "ED" if nd["dormant"] else ""
        theta_t = f"Θ={nd['theta']:.3f}"

        nodes_svg.append(f'''
  <g>
    <circle cx="{x}" cy="{y}" r="{NODE_R}"
            fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>
    <text x="{x}" y="{y - 6}" text-anchor="middle" dominant-baseline="central"
          font-size="11" font-weight="700" fill="#f1f5f9"
          font-family="'Segoe UI',sans-serif">{label}</text>
    <text x="{x}" y="{y + 9}" text-anchor="middle" dominant-baseline="central"
          font-size="9" fill="#94a3b8"
          font-family="monospace">{theta_t}</text>
    {"" if not nd["dormant"] else f'<text x="{x}" y="{y + 20}" text-anchor="middle" font-size="8" fill="#a78bfa" font-family="monospace">DORMANT</text>'}
  </g>''')

    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 {SVG_W} {SVG_H}" width="100%"
     style="background:#0f1117;border-radius:8px">
  <defs>
    <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5"
            markerWidth="5" markerHeight="5" orient="auto-start-reverse">
      <path d="M2 1L8 5L2 9" fill="none" stroke="#94a3b8"
            stroke-width="1.5" stroke-linecap="round"/>
    </marker>
  </defs>
  <!-- Arcs -->
  {"".join(arcs_svg)}
  <!-- Noeuds -->
  {"".join(nodes_svg)}
</svg>'''

    # Tableau des statistiques par service
    rows_stats = []
    for nd in sorted(nodes_js, key=lambda x: x["theta"], reverse=True):
        dormant_badge = (
            '<span style="background:#3b2f7f;color:#c4b5fd;padding:1px 6px;'
            'border-radius:4px;font-size:0.68rem">DORMANT</span>'
            if nd["dormant"] else
            '<span style="background:#134e4a;color:#5eead4;padding:1px 6px;'
            'border-radius:4px;font-size:0.68rem">actif</span>'
        )
        theta_bar = f'<div style="width:{nd["theta"]*100:.1f}%;height:4px;background:#f59e0b;border-radius:2px"></div>'
        C_bar     = f'<div style="width:{nd["C"]*100:.1f}%;height:4px;background:#0d9488;border-radius:2px"></div>'
        P_bar     = f'<div style="width:{nd["P"]*100:.1f}%;height:4px;background:#7c3aed;border-radius:2px"></div>'
        F_color   = "#f87171" if nd["F"] > 0 else "#94a3b8"

        rows_stats.append(f'''<tr>
  <td style="font-weight:600;color:#e2e8f0">{nd["id"]}</td>
  <td>{dormant_badge}</td>
  <td>
    <div style="display:flex;align-items:center;gap:6px">
      <div style="width:60px;height:4px;background:#1e2535;border-radius:2px">{theta_bar}</div>
      <span style="font-family:monospace;color:#f59e0b">{nd["theta"]:.4f}</span>
    </div>
  </td>
  <td>
    <div style="display:flex;align-items:center;gap:6px">
      <div style="width:60px;height:4px;background:#1e2535;border-radius:2px">{C_bar}</div>
      <span style="font-family:monospace">{nd["C"]:.4f}</span>
    </div>
  </td>
  <td>
    <div style="display:flex;align-items:center;gap:6px">
      <div style="width:60px;height:4px;background:#1e2535;border-radius:2px">{P_bar}</div>
      <span style="font-family:monospace">{nd["P"]:.4f}</span>
    </div>
  </td>
  <td style="font-family:monospace;color:{F_color}">{nd["F"]:.4f}</td>
</tr>''')

    # Tableau des arcs
    rows_arcs = []
    for l in sorted(links_js, key=lambda x: x["w_ij"], reverse=True):
        color = w_color(l["w_ij"])
        rows_arcs.append(f'''<tr>
  <td style="font-family:monospace;color:#e2e8f0">{l["source"]}</td>
  <td style="text-align:center;color:#64748b">→</td>
  <td style="font-family:monospace;color:#e2e8f0">{l["target"]}</td>
  <td><span style="background:{color}22;color:{color};padding:2px 8px;border-radius:4px;font-family:monospace;font-size:0.8rem">{l["w_ij"]:.4f}</span></td>
  <td style="font-family:monospace;color:#94a3b8">{l["rate_ij"]:.4f}</td>
  <td style="font-family:monospace;color:#94a3b8">{l["lat_norm"]:.4f}</td>
  <td style="font-family:monospace;color:{"#f87171" if l["err_ij"] > 0 else "#94a3b8"}">{l["err_ij"]:.4f}</td>
  <td style="font-family:monospace;color:#94a3b8">{l["freq"]}</td>
</tr>''')

    nodes_json = json.dumps(nodes_js, ensure_ascii=False)
    links_json = json.dumps(links_js, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>MetaBP-RTS — Graphe G Phase 1</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #0f1117;
  color: #e2e8f0;
  min-height: 100vh;
  padding: 0;
}}

/* Header */
header {{
  padding: 1rem 2rem;
  border-bottom: 1px solid #1e2535;
  background: #13161f;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
}}
header h1 {{
  font-size: 1rem;
  font-weight: 700;
  color: #f8fafc;
  letter-spacing: -0.02em;
}}
.badge {{
  padding: 0.2rem 0.7rem;
  border-radius: 9999px;
  font-size: 0.7rem;
  font-weight: 600;
}}
.badge-d {{ background: #3b2f7f; color: #c4b5fd; }}
.badge-n {{ background: #134e4a; color: #5eead4; }}
.badge-g {{ background: #1e3a5f; color: #93c5fd; }}

/* Layout principal */
.main {{
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}}

/* Section */
.section {{
  background: #13161f;
  border: 1px solid #1e2535;
  border-radius: 10px;
  overflow: hidden;
}}
.section-title {{
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid #1e2535;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #64748b;
  background: #0f1117;
}}

/* Métriques globales */
.metrics-grid {{
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 0;
}}
.metric-card {{
  padding: 1rem 1.25rem;
  border-right: 1px solid #1e2535;
  text-align: center;
}}
.metric-card:last-child {{ border-right: none; }}
.metric-label {{
  font-size: 0.65rem;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 6px;
}}
.metric-value {{
  font-size: 1.6rem;
  font-weight: 700;
  font-family: monospace;
  color: #f8fafc;
}}
.metric-sub {{
  font-size: 0.65rem;
  color: #475569;
  margin-top: 2px;
}}

/* Graphe statique */
.graph-container {{
  padding: 1.5rem;
}}

/* Légende */
.legend {{
  display: flex;
  gap: 1.5rem;
  padding: 0.75rem 1.25rem;
  border-top: 1px solid #1e2535;
  background: #0f1117;
  flex-wrap: wrap;
  align-items: center;
}}
.legend-item {{
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.72rem;
  color: #94a3b8;
}}
.legend-dot {{
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid;
}}
.legend-line {{
  width: 24px;
  height: 3px;
  border-radius: 2px;
}}

/* Tableaux */
table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}}
thead th {{
  padding: 0.6rem 1rem;
  text-align: left;
  font-size: 0.67rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748b;
  border-bottom: 1px solid #1e2535;
  background: #0f1117;
  position: sticky;
  top: 0;
}}
tbody td {{
  padding: 0.65rem 1rem;
  border-bottom: 1px solid #0f1117;
  vertical-align: middle;
}}
tbody tr:hover td {{ background: #1a1f2e; }}
tbody tr:last-child td {{ border-bottom: none; }}

/* Formules */
.formulas {{
  padding: 1.25rem;
  display: flex;
  gap: 2rem;
  flex-wrap: wrap;
}}
.formula {{
  font-family: monospace;
  font-size: 0.8rem;
  color: #94a3b8;
  background: #0f1117;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: 1px solid #1e2535;
}}
.formula strong {{ color: #e2e8f0; }}
</style>
</head>
<body>

<header>
  <h1>MetaBP-RTS — Graphe de services G · Phase 1</h1>
  <span class="badge badge-g">{len(nodes_js)} services · {len(links_js)} arcs</span>
  <span class="badge badge-d">{dormant_count} Écho-Dormant(s)</span>
  <span class="badge badge-n">{non_dormant_count} Non-Dormant(s)</span>
  <span style="margin-left:auto;font-size:0.7rem;color:#475569">
    τ_dormant = 0.40 · α=0.5 · β=0.3 · γ=0.2
  </span>
</header>

<div class="main">

  <!-- Métriques globales -->
  <div class="section">
    <div class="section-title">Métriques globales</div>
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-label">Services</div>
        <div class="metric-value" style="color:#93c5fd">{len(nodes_js)}</div>
        <div class="metric-sub">noeuds G</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Dépendances</div>
        <div class="metric-value" style="color:#93c5fd">{len(links_js)}</div>
        <div class="metric-sub">arcs G</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Densité</div>
        <div class="metric-value" style="color:#94a3b8;font-size:1.2rem">{density:.4f}</div>
        <div class="metric-sub">|E|/|V|(|V|−1)</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">w_ij moyen</div>
        <div class="metric-value" style="color:#f59e0b;font-size:1.2rem">{avg_w:.4f}</div>
        <div class="metric-sub">poids moyen</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Écho-Dormants</div>
        <div class="metric-value" style="color:#a78bfa">{dormant_count}</div>
        <div class="metric-sub">Θ ≥ τ_dormant</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Non-Dormants</div>
        <div class="metric-value" style="color:#5eead4">{non_dormant_count}</div>
        <div class="metric-sub">Θ &lt; τ_dormant</div>
      </div>
    </div>
  </div>

  <!-- Graphe statique -->
  <div class="section">
    <div class="section-title">Graphe G — Architecture des dépendances inter-services</div>
    <div class="graph-container">
      {svg_content}
    </div>
    <div class="legend">
      <div class="legend-item">
        <div class="legend-dot" style="background:#3b1f8c;border-color:#7c3aed"></div>
        Écho-Dormant (Θ ≥ 0.40)
      </div>
      <div class="legend-item">
        <div class="legend-dot" style="background:#0f4c3a;border-color:#0d9488"></div>
        Non-Dormant (Θ &lt; 0.40)
      </div>
      <div class="legend-item">
        <div class="legend-line" style="background:#0d9488"></div>
        w_ij &lt; 0.40 (faible)
      </div>
      <div class="legend-item">
        <div class="legend-line" style="background:#f59e0b"></div>
        0.40 ≤ w_ij &lt; 0.60 (moyen)
      </div>
      <div class="legend-item">
        <div class="legend-line" style="background:#dc2626"></div>
        w_ij ≥ 0.60 (élevé)
      </div>
    </div>
  </div>

  <!-- Formules -->
  <div class="section">
    <div class="section-title">Formules MetaBP-RTS</div>
    <div class="formulas">
      <div class="formula"><strong>w_ij</strong> = α·rate_ij + β·lat_norm + γ·err_ij</div>
      <div class="formula"><strong>Θ(si)</strong> = ω_C·C(si) + ω_P·P(si) + ω_F·F(si)</div>
      <div class="formula"><strong>S_dormant</strong> = &#123; si | Θ(si) ≥ τ_dormant &#125;</div>
      <div class="formula"><strong>α</strong>=0.5 · <strong>β</strong>=0.3 · <strong>γ</strong>=0.2 · <strong>τ</strong>=0.40</div>
      <div class="formula"><strong>ω_C</strong>=0.357 · <strong>ω_P</strong>=0.357 · <strong>ω_F</strong>=0.286</div>
    </div>
  </div>

  <!-- Tableau statistiques -->
  <div class="section">
    <div class="section-title">Scores par service — C(si), P(si), F(si), Θ_dormant</div>
    <div style="overflow-x:auto">
      <table>
        <thead>
          <tr>
            <th>Service</th>
            <th>Statut</th>
            <th>Θ_dormant</th>
            <th>C — Centralité</th>
            <th>P — Propagation</th>
            <th>F — Fragilité</th>
          </tr>
        </thead>
        <tbody>
          {"".join(rows_stats)}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Tableau arcs -->
  <div class="section">
    <div class="section-title">Arcs du graphe G — Poids w_ij et composantes</div>
    <div style="overflow-x:auto">
      <table>
        <thead>
          <tr>
            <th>Source</th>
            <th></th>
            <th>Cible</th>
            <th>w_ij</th>
            <th>rate_ij (α=0.5)</th>
            <th>lat_norm (β=0.3)</th>
            <th>err_ij (γ=0.2)</th>
            <th>fréquence</th>
          </tr>
        </thead>
        <tbody>
          {"".join(rows_arcs)}
        </tbody>
      </table>
    </div>
  </div>

</div>
</body>
</html>"""
    return html


def generate(base_dir: Path) -> Path:
    graph, scores = load_data(base_dir)
    html = build_html(graph, scores)
    output = base_dir / "data/outputs/graph_visualization.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(html)
    return output


def main():
    parser = argparse.ArgumentParser(
        description="MetaBP-RTS — Visualisation du graphe G"
    )
    parser.add_argument(
        "--base-dir",
        default="..",
        help="Répertoire phase1/ (défaut: ..)",
    )
    args = parser.parse_args()
    base_dir = Path(args.base_dir).resolve()
    output = generate(base_dir)
    print(f"Visualisation générée → {output}")
    print(f"Ouvrir dans le navigateur : file://{output}")


if __name__ == "__main__":
    main()