// Occupations (jlma-occupations): the page around the ICE-Map component. The address holds the state:
// ?view=…&focus=…&select=… (GND ids of the shown top concept and of the selected one).
import { IceMap } from './icemap.js';

const VIEWS = {
  'iic': { a: 'iic' },
  'jl-iic': { a: 'jl', b: 'iic' },
  'gnd-iic': { a: 'gnd', b: 'iic' },
  'jl-gnd': { a: 'jl', b: 'gnd' },
};
const main = document.getElementById('main');
const el = document.getElementById('icemap');
const params = new URLSearchParams(location.search);
let view = VIEWS[params.get('view')] ? params.get('view') : 'iic';
const radios = [...document.querySelectorAll('input[name="view"]')];
radios.forEach(r => { r.checked = r.value === view; });

const link = id => id.startsWith('sc:')
  ? (id === 'sc:?' ? null : `https://d-nb.info/standards/vocab/gnd/gnd-sc#${id.slice(3)}`)
  : `https://d-nb.info/gnd/${id}`;

let map;
function save() {
  if (!map) return;
  const s = map.state(), p = new URLSearchParams();
  if (view !== 'iic') p.set('view', view);
  if (s.focus) p.set('focus', s.focus);
  if (s.select) p.set('select', s.select);
  const q = p.toString();
  try { history.replaceState(null, '', q ? `?${q}` : location.pathname); } catch { /* not allowed where the page is embedded */ }
}

try {
  map = await IceMap.open(el, {
    src: `${main.dataset.base}data/`, colour: VIEWS[view], link, onChange: save,
    focus: params.get('focus') || undefined, select: params.get('select') || undefined,
  });
  el.removeAttribute('aria-busy');
  radios.forEach(r => r.addEventListener('change', async () => {
    if (!r.checked) return;
    view = r.value;
    await map.setColour(VIEWS[view]);
    save();
  }));
} catch (e) {
  el.removeAttribute('aria-busy');
  el.innerHTML = `<p class="occ-wait">The map could not be loaded (${String(e.message || e)}). Reload the page to try again.</p>`;
  console.error(e);
}
