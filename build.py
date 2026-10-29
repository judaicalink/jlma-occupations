#!/usr/bin/env python3
"""Build the Occupations showcase: the occupations of the GND as an ICE-Map, with the persons of JudaicaLink.

    python3 build.py --inputs ~/lokal/judaicalink/inputs --store ~/lokal/judaicalink/store \
        --index ../judaicalink-data/catalog/dataindex.json --icemap ../icemap --out dist

Reads the complete GND (inputs:gnd/lds-2026-02-17), the GND subject categories (inputs:gnd/gnd-sc-2026-10-29) and the
stable version of the dataset gnd (the GND persons of JudaicaLink); writes the inputs of the ICE-Map generator to
work/, runs it (icemap.py of the icemap checkout) and writes a static site: dist/index.html, dist/assets/ (icemap.js
copied from the checkout), dist/data/ (the generator's files), dist/build.json. With --standalone, the page does not
use the platform (no /kit/1/, no platform bar) and all paths are relative.
"""

import argparse
import datetime
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from occ import hierarchy
from occ.rdf import read_triples

ROOT = Path(__file__).resolve().parent
DUMP = "gnd/lds-2026-02-17/authorities-gnd_lds_20260217.nt.gz"
GND_SC = "gnd/gnd-sc-2026-10-29/gnd-sc.ttl"
JL_GND = "http://data.judaicalink.org/data/gnd/"
FOAF_PERSON = "http://xmlns.com/foaf/0.1/Person"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
TITLE = "Occupations in the GND"

# for --standalone: the colour and type tokens of /kit/1/jl.css (judaicalink-mannheim), with the viewer's theme switch
TOKENS = """
:root { --jl-fg: #1d1d1f; --jl-muted: #5b5b66; --jl-line: #d8d8de; --jl-bg: #ffffff; --jl-accent: #1f4e8c;
  --jl-note: #f2f5fa; --jl-font: system-ui, -apple-system, "Segoe UI", sans-serif; --jl-width: 56rem; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --jl-fg: #e8e8ec; --jl-muted: #a2a2ad;
  --jl-line: #3a3a42; --jl-bg: #16161a; --jl-accent: #8db4ec; --jl-note: #20242c; color-scheme: dark; } }
:root[data-theme="dark"] { --jl-fg: #e8e8ec; --jl-muted: #a2a2ad; --jl-line: #3a3a42; --jl-bg: #16161a;
  --jl-accent: #8db4ec; --jl-note: #20242c; color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--jl-bg); color: var(--jl-fg); font: 16px/1.5 var(--jl-font); }
a { color: var(--jl-accent); }
"""

esc = html.escape


def stable_files(store, index, slug):
    e = json.loads(Path(index).read_text(encoding="utf-8"))["datasets"][slug]
    v = next(x for x in e["versions"] if x["version"] == e["stable"])
    files = [Path(store) / slug / e["stable"] / f["path"] for f in v["files"]
             if not f["path"].endswith("-meta.ttl.gz") and re.search(r"\.(ttl|nt)(\.gz)?$", f["path"])]
    return e["stable"], files


def jl_persons(files):
    out = set()
    for f in files:
        for s, p, o in read_triples(f):
            if p == RDF_TYPE and o == FOAF_PERSON and s.startswith(JL_GND):
                out.add(s[len(JL_GND):])
    return out


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:10]


def page(base, standalone, css_v, js_v, facts):
    head = (f"<style>{TOKENS}</style>" if standalone else '<link rel="stylesheet" href="/kit/1/jl.css">')
    bar = "" if standalone else '<!--# include virtual="/kit/1/header.html" -->\n'
    gnd, jl, nodes = (f"{facts[k]:,}" for k in ("gnd", "jl", "nodes"))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Occupations{'' if standalone else ' · JudaicaLink Mannheim'}</title>
<meta name="description" content="The occupations of the GND as an ICE-Map: a treemap of the hierarchy, coloured by how often each occupation occurs among the persons of JudaicaLink compared to the structure or to the whole GND.">
{head}
<link rel="stylesheet" href="{base}assets/occ.css?v={css_v}">
</head>
<body>
{bar}<main class="occ" id="main" data-base="{base}">
<header class="occ-head">
<h1>Occupations</h1>
<p class="occ-lead">The occupations of the GND as one hierarchy, drawn as an ICE-Map: every area is an occupation or a
group of them, sized by how many concepts it holds, and coloured by how often it occurs among the persons of
JudaicaLink. Double-click to zoom in; the path above the map leads back out.</p>
</header>
<fieldset class="occ-views">
<legend>Colour by</legend>
<label><input type="radio" name="view" value="iic" checked> <span><b>Structure</b> intrinsic information content (IIC) alone</span></label>
<label><input type="radio" name="view" value="jl-iic"> <span><b>JudaicaLink against the structure</b> IC − IIC</span></label>
<label><input type="radio" name="view" value="gnd-iic"> <span><b>All GND persons against the structure</b> IC − IIC</span></label>
<label><input type="radio" name="view" value="jl-gnd"> <span><b>JudaicaLink against all GND persons</b> IC − IC</span></label>
</fieldset>
<div id="icemap" class="occ-map" aria-busy="true"><p class="occ-wait">Loading the hierarchy …</p></div>
<section class="occ-about">
<h2>How to read the map</h2>
<p>The map uses the ICE-Map Visualization, as introduced by Eckert, Stuckenschmidt and Pfeffer (2007) and described
in detail by Eckert (2012, chapter 2), in a web implementation (<a href="https://github.com/kaiec/icemap">icemap</a>).
The size of an area is determined by the structure alone: it is the number of concepts in its subtree. The colour
shows the information content (IC) of a concept or the difference between two ICs, computed as in Eckert (2012,
Eqs. 2.4–2.8).</p>
<ul>
<li><b>Structure (IIC)</b>: the intrinsic information content, from the hierarchy alone. The fewer concepts below an
occupation, the higher its IIC and the paler its area. This is the unpopulated hierarchy: what the map would show if
persons were spread evenly over it.</li>
<li><b>IC − IIC</b>: the information content from the persons (how many have this occupation or one below it) minus
the intrinsic one. <span class="occ-hot">Red</span>: more persons than the structure would let one expect;
<span class="occ-cold">blue</span>: fewer. Because the counts add up towards the top, the colours of deep concepts
show in the groups above them.</li>
<li><b>IC − IC</b>: the persons of JudaicaLink against all persons of the GND, the reference. Red: occupations that are
more frequent in JudaicaLink than in the GND as a whole.</li>
</ul>
<p>Contrast narrows the colour range, so smaller differences show; balance moves the neutral point (the button sets
it to the shown top concept).</p>
<h2>The hierarchy</h2>
<p>The GND has no single tree of occupations. This one is assembled from the GND itself: the subject headings that
are occupations of persons, with their broader terms; above them the GND subject categories, nested by their
notations (for example 9 › 9.4 › 9.4a › 9.4ab). A heading without a broader term hangs under its subject categories,
under 9.4ab (individual occupations) only when it has no other. Where the GND lists several broader terms or
categories, the first is used and the others are named under "Also under". {nodes} concepts in all.</p>
<h2>Data</h2>
<dl class="occ-facts">
<dt>Persons in the GND</dt><dd>{gnd} with at least one occupation in the hierarchy (GND, complete dump of
{facts['dump_date']}, Deutsche Nationalbibliothek, CC0)</dd>
<dt>Persons in JudaicaLink</dt><dd>{jl} of the {facts['jl_all']:,} GND persons of JudaicaLink (dataset gnd,
version {facts['gnd_version']})</dd>
<dt>Counting</dt><dd>every person once per area, however many of their occupations lie below it</dd>
</dl>
<h2>References</h2>
<ul class="occ-refs">
<li>Eckert, K. (2012). <i>Usage-driven Maintenance of Knowledge Organization Systems</i> (Doctoral dissertation).
Universität Mannheim. <a href="https://madoc.bib.uni-mannheim.de/31754/">madoc.bib.uni-mannheim.de/31754</a></li>
<li>Eckert, K., Stuckenschmidt, H., &amp; Pfeffer, M. (2007). Interactive thesaurus assessment for automatic document
annotation. In <i>Proceedings of the 4th International Conference on Knowledge Capture (K-CAP 2007)</i>
(pp. 103–110). ACM. <a href="https://doi.org/10.1145/1298406.1298426">doi:10.1145/1298406.1298426</a></li>
</ul>
</section>
</main>
<script type="module" src="{base}assets/occ.js?v={js_v}"></script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--inputs", required=True, type=Path, help="the inputs area (lokal/inputs)")
    ap.add_argument("--store", required=True, type=Path)
    ap.add_argument("--index", required=True, type=Path, help="the data index (judaicalink-data catalog/dataindex.json)")
    ap.add_argument("--icemap", type=Path, default=ROOT.parent / "icemap", help="a checkout of icemap")
    ap.add_argument("--work", type=Path, default=ROOT / "work")
    ap.add_argument("--out", type=Path, default=ROOT / "dist")
    ap.add_argument("--base", default="/occupations/")
    ap.add_argument("--standalone", action="store_true", help="no platform: relative paths, own tokens, no bar")
    args = ap.parse_args()
    say = lambda m: print(m, file=sys.stderr)
    args.work.mkdir(parents=True, exist_ok=True)

    say("reading the GND …")
    lines = hierarchy.extract(args.inputs / DUMP, args.work / "gnd-lines.nt")
    label, broader, cats, occupation = hierarchy.read_gnd(lines)
    sc_labels = hierarchy.read_categories(args.inputs / GND_SC)
    rows = hierarchy.concepts(label, broader, cats, occupation, sc_labels)
    hierarchy.write_concepts(rows, args.work / "concepts.tsv")
    known = {r[0] for r in rows}
    gnd_version, files = stable_files(args.store, args.index, "gnd")
    ours = jl_persons(files)
    n_gnd = hierarchy.write_set(occupation, None, known, args.work / "gnd.tsv")
    n_jl = hierarchy.write_set(occupation, ours, known, args.work / "jl.tsv")
    say(f"{len(rows)} concepts; persons with occupations: {n_gnd} in the GND, {n_jl} of {len(ours)} in JudaicaLink")

    out = args.out
    if out.exists():
        shutil.rmtree(out)
    (out / "assets").mkdir(parents=True)
    subprocess.run([sys.executable, str(args.icemap / "icemap.py"), "--concepts", str(args.work / "concepts.tsv"),
                    "--title", TITLE,
                    "--set", "jl", "Persons in JudaicaLink", str(args.work / "jl.tsv"),
                    "--set", "gnd", "Persons in the GND", str(args.work / "gnd.tsv"),
                    "--out", str(out / "data")], check=True)
    shutil.copy(args.icemap / "web" / "icemap.js", out / "assets" / "icemap.js")
    for f in ("occ.css", "occ.js"):
        shutil.copy(ROOT / "assets" / f, out / "assets" / f)
    manifest = json.loads((out / "data" / "manifest.json").read_text(encoding="utf-8"))
    base = "./" if args.standalone else args.base
    facts = {"gnd": n_gnd, "jl": n_jl, "jl_all": len(ours), "nodes": manifest["nodes"],
             "dump_date": "2026-02-17", "gnd_version": gnd_version}
    (out / "index.html").write_text(page(base, args.standalone, digest(out / "assets" / "occ.css"),
                                         digest(out / "assets" / "occ.js"), facts), encoding="utf-8")
    icemap_rev = subprocess.run(["git", "-C", str(args.icemap), "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True).stdout.strip() or "uncommitted"
    (out / "build.json").write_text(json.dumps({
        "built": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "inputs": [f"inputs:{DUMP}", f"inputs:{GND_SC}"], "datasets": {"gnd": gnd_version},
        "icemap": icemap_rev, "persons": {"gnd": n_gnd, "jl": n_jl}, "nodes": manifest["nodes"],
    }, indent=1), encoding="utf-8")
    say(f"written to {out}")


if __name__ == "__main__":
    main()
