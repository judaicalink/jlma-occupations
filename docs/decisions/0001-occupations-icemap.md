# 0001 The occupations of the GND as an ICE-Map, with the persons of JudaicaLink

Status: accepted · Date: 2026-10-29

## Context

The ICE-Map Visualization (Eckert, 2012, chapter 2; implementation: [icemap](https://github.com/kaiec/icemap)) needs
a hierarchy and documents assigned to its concepts. Of 61,634 GND persons in JudaicaLink, 50,920 have occupations in
the GND, and the complete GND (4.06 million persons with occupations) is a reference that no other vocabulary
offers. The GND has no single tree of occupations, though: 9,815 subject headings are used as occupations, their
broader terms form a forest with 3,624 roots, and the subject categories (gnd-sc) are a separate list whose
hierarchy is only in the notations.

## Decision

- The hierarchy is assembled from the GND alone:
  - the subject headings used as occupations (`gndo:professionOrOccupation`, also when given as an `rdf:Seq`),
    with their broader terms (generic and general; partitive and instantial are left out);
  - above them the subject categories, nested by their notations (9 › 9.4 › 9.4a › 9.4ab); person categories
    (`…p`) and placeholders (`…m`) are left out;
  - a heading without a broader term hangs under its subject categories, under 9.4ab (individual occupations) only
    when it has no other.
- Primary parents (icemap 0002, 0003) as the GND lists them: the first broader term, or the first subject category.
  The others are shown as "also under".
- Two annotation sets: all persons of the GND with an occupation in the hierarchy, and those persons of JudaicaLink
  (the GND persons of the dataset gnd, stable version). Every person counts once per area (icemap 0004).
- Four views: the structure alone (IIC); JudaicaLink against the structure (IC − IIC); all GND persons against the
  structure; JudaicaLink against the GND (IC − IC).
- The statistics are those of Eckert (2012, Eqs. 2.4–2.8), as implemented by icemap, including the normalisation
  of IC by log(ŵ⁺ + 1) of each set; changes to the method come later, as options of icemap.
- Gendered forms (Wissenschaftler, Wissenschaftlerin) stay apart, as in the GND. Chains of single children stay.
- `build.py` reads the complete GND (`inputs:gnd/lds-2026-02-17`), the subject categories
  (`inputs:gnd/gnd-sc-2026-10-29`) and the dataset gnd from the store; it writes the generator's inputs to a work
  directory outside the repository (default `~/lokal/judaicalink/work/jlma-occupations`), runs `icemap.py` of an
  icemap checkout and copies `icemap.js` into the site (a copy: the site keeps working with the code it was built
  with). Python standard library only; the RDF reader is the one of judaicalink-data, copied.

## Consequences

Each build needs the GND dump (2.6 GB, read with GNU grep, then in Python). The page follows the platform contract
(`/kit/1/jl.css`, the platform bar by SSI, own CSS prefixed `occ-`, paths below `/occupations/`); `--standalone`
makes a version without the platform, for previews.
