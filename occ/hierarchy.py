"""The occupation hierarchy of the GND and who has which occupation, as inputs of the ICE-Map generator.

Concepts: the subject headings used as occupations of persons (gndo:professionOrOccupation), with their broader
terms (generic and general), and above them the GND subject categories (gnd-sc), nested by their notations.
A heading without a broader term hangs under its subject categories; 9.4ab (individual occupations) only when it
has no other. Parents are listed as the GND lists them, the first one primary (icemap decisions 0002, 0003).
"""

import collections
import os
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

from occ.rdf import Literal, read_triples, unescape_string

GND = "https://d-nb.info/gnd/"
GNDO = "https://d-nb.info/standards/elementset/gnd#"
SC = "https://d-nb.info/standards/vocab/gnd/gnd-sc#"
RDF_N = "http://www.w3.org/1999/02/22-rdf-syntax-ns#_"
BROADER = ("broaderTermGeneric", "broaderTermGeneral")
PATTERNS = ["gnd#professionOrOccupation>", "gnd#broaderTermGeneric>", "gnd#broaderTermGeneral>",
            "gnd#preferredNameForTheSubjectHeading>", "gnd#gndSubjectCategory>", "22-rdf-syntax-ns#_"]
LINE = re.compile(r'^(<[^>]*>|_:\S+) <([^>]*)> (<[^>]*>|_:\S+|"(?:[^"\\]|\\.)*")')


def extract(dump, cache):
    """The lines of the GND dump that matter here, cached (grep is much faster than Python on 2.6 GB)."""
    cache = Path(cache)
    if cache.exists() and cache.stat().st_mtime >= Path(dump).stat().st_mtime:
        return cache
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix(".tmp")
    # GNU grep: the BSD grep of macOS takes many minutes for several patterns on this file
    grep_cmd = shutil.which("ggrep") or "grep"
    with open(tmp, "wb") as out:
        gz = subprocess.Popen(["gzip", "-dc", str(dump)], stdout=subprocess.PIPE)
        grep = subprocess.run([grep_cmd, "-F", *sum((["-e", p] for p in PATTERNS), [])], stdin=gz.stdout,
                              stdout=out, env={**os.environ, "LC_ALL": "C"})
        gz.stdout.close()
        if gz.wait() != 0 or grep.returncode not in (0, 1):
            raise RuntimeError("reading the GND dump failed")
    tmp.rename(cache)
    return cache


def read_gnd(lines):
    """Labels, broader terms and subject categories of subject headings, and the occupations of persons."""
    label, broader, cats = {}, collections.defaultdict(list), collections.defaultdict(list)
    occupation, seq = collections.defaultdict(list), collections.defaultdict(list)
    with open(lines, encoding="utf-8") as f:
        for line in f:
            m = LINE.match(line)
            if not m:
                continue
            s, p, o = m.groups()
            if p.startswith(RDF_N):
                if s.startswith("_:") and o.startswith("<"):
                    seq[s].append((int(p[len(RDF_N):]), o[1:-1]))
                continue
            if not s.startswith("<" + GND):
                continue
            s, k = s[1 + len(GND):-1], p[len(GNDO):]
            if k == "preferredNameForTheSubjectHeading" and o.startswith('"'):
                label[s] = unicodedata.normalize("NFC", unescape_string(o[1:-1]))
            elif k in BROADER and o.startswith("<" + GND):
                broader[s].append(o[1 + len(GND):-1])
            elif k == "gndSubjectCategory" and o.startswith("<" + SC):
                cats[s].append(o[1 + len(SC):-1])
            elif k == "professionOrOccupation":
                occupation[s].append(o)
    for person, objs in occupation.items():
        out = []
        for o in objs:
            if o.startswith("_:"):
                out += [x[len(GND):] for _, x in sorted(seq.get(o, ())) if x.startswith(GND)]
            elif o.startswith("<" + GND):
                out.append(o[1 + len(GND):-1])
        occupation[person] = list(dict.fromkeys(out))
    return label, broader, cats, occupation


def read_categories(path):
    """Notation -> German label of the GND subject categories."""
    out = {}
    for s, p, o in read_triples(path):
        if p.endswith("#prefLabel") and isinstance(o, Literal) and o.lang == "de" and s.startswith(SC):
            out[s[len(SC):]] = unicodedata.normalize("NFC", o.value)
    return out


NOTATION = re.compile(r"^(\d+)(?:\.(\d+)([a-z]*))?$")


def category_parent(n, known):
    """The parent of a subject category by its notation: 9.4ab -> 9.4a -> 9.4 -> 9 (with or without '*')."""
    m = NOTATION.match(n.rstrip("*"))
    if not m or m.group(2) is None:
        return None
    a, b, letters = m.groups()
    cand = f"{a}.{b}{letters[:-1]}" if letters else a
    while cand:
        for c in (cand, cand + "*"):
            if c in known:
                return c
        m = NOTATION.match(cand)
        a, b, letters = m.groups()
        cand = (f"{a}.{b}{letters[:-1]}" if letters else a) if b is not None else None
    return None


def notation_key(n):
    parts = re.findall(r"\d+|[a-z]+", n)
    return [(0, int(x)) if x.isdigit() else (1, x) for x in parts]


def primary_categories(cs):
    cs = [c for c in dict.fromkeys(cs) if not c.endswith(("p", "m"))]
    if len(cs) > 1 and "9.4ab" in cs:
        cs.remove("9.4ab")
    return cs


def concepts(label, broader, cats, occupation, sc_labels):
    """(id, label, parents) for the generator: categories first, then headings."""
    used = {o for os in occupation.values() for o in os if o in label}
    nodes, stack = set(), list(used)
    while stack:
        s = stack.pop()
        if s in nodes:
            continue
        nodes.add(s)
        stack.extend(b for b in broader.get(s, ()) if b in label)
    parents = {s: [b for b in dict.fromkeys(broader.get(s, ())) if b in nodes and b != s] for s in nodes}
    need = set()
    for s in nodes:
        if not parents[s]:
            for c in primary_categories(cats.get(s, ())) or ["?"]:
                while c:
                    need.add(c)
                    c = category_parent(c, sc_labels) if c != "?" else None
    rows = []
    for c in sorted(need, key=notation_key):
        if c == "?":
            rows.append(("sc:?", "Without subject category", []))
            continue
        p = category_parent(c, sc_labels)
        rows.append((f"sc:{c}", f"{c.rstrip('*')} {sc_labels.get(c, '')}".strip(), [f"sc:{p}"] if p else []))
    for s in sorted(nodes, key=lambda x: label[x]):
        ps = parents[s] or [f"sc:{c}" for c in (primary_categories(cats.get(s, ())) or ["?"])]
        rows.append((s, label[s], ps))
    return rows


def clean(text):
    return " ".join(text.replace("\t", " ").split())


def write_concepts(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        for cid, lab, parents in rows:
            f.write(f"{cid}\t{clean(lab)}\t{' '.join(parents)}\n")


def write_set(occupation, persons, known, path):
    """document (person) and concept (occupation) per line; persons=None for all."""
    docs = 0
    with open(path, "w", encoding="utf-8") as f:
        for person, os in occupation.items():
            if persons is not None and person not in persons:
                continue
            os = [o for o in os if o in known]
            if os:
                docs += 1
                f.writelines(f"{person}\t{o}\n" for o in os)
    return docs
