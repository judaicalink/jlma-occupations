# jlma-occupations

Showcase of mannheim.judaicalink.org (`/occupations/`): the occupations of the GND as an ICE-Map, a zoomable treemap
of the hierarchy coloured by how often each occupation occurs among the persons of JudaicaLink, compared to the
structure alone or to the whole GND. The map uses the ICE-Map Visualization, as introduced by Eckert, Stuckenschmidt
and Pfeffer (2007) and described by Eckert (2012, chapter 2), in the implementation of
[icemap](https://github.com/kaiec/icemap), which also lists the references.

```sh
python3 build.py --inputs ~/lokal/judaicalink/inputs --store ~/lokal/judaicalink/store \
    --index ../judaicalink-data/catalog/dataindex.json --icemap ../icemap --out dist
python3 tools/serve.py          # http://localhost:8140/occupations/
```

`--icemap` is a checkout of <https://github.com/kaiec/icemap>. `--standalone` builds a version without the platform (relative paths, no platform bar). Decisions are in
[`docs/decisions/`](docs/decisions/).
