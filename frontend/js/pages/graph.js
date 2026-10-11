/* Schemes › Map: a knowledge graph of your schemes, the documents they need and
   their rules. Drawn with Cytoscape.js, served from /static/vendor/graph. */
import { esc, fmtINR } from '../util.js';
import { t } from '../i18n.js';
import { icon, toast } from '../ui.js';
import { emptyCard } from '../components.js';
import { state } from '../state.js';
import { knowledgeGraph } from '../features.js';
import { schemesTabs } from './schemes.js';

let cy = null;
let view = { missingOnly: false, rules: true };
let lib = null;

const loadCytoscape = async () => (lib ||= (await import('/static/vendor/graph/cytoscape.esm.min.js')).default);

function colors() {
  const cs = getComputedStyle(document.documentElement);
  const v = (n) => cs.getPropertyValue(n).trim();
  return { ink: v('--ink'), ink3: v('--ink-3'), line: v('--line-strong'), surface: v('--surface'), surface2: v('--surface-2'),
    green: v('--green'), red: v('--red'), indigo: v('--indigo'), saffron: v('--saffron') };
}

function style(c) {
  return [
    { selector: 'node', style: { label: 'data(label)', 'font-size': 10, 'font-family': 'system-ui, sans-serif', color: c.ink, 'text-wrap': 'wrap',
      'text-max-width': 110, 'text-valign': 'bottom', 'text-margin-y': 4, width: 'mapData(degree, 1, 12, 22, 46)', height: 'mapData(degree, 1, 12, 22, 46)',
      'border-width': 2, 'background-color': c.surface2, 'border-color': c.line } },
    { selector: 'node[kind = "scheme"]', style: { shape: 'round-rectangle', 'background-color': c.surface2, 'border-color': c.ink3, 'font-weight': 600 } },
    { selector: 'node[kind = "scheme"][status = "eligible"]', style: { 'background-color': c.indigo, 'border-color': c.indigo } },
    { selector: 'node[kind = "document"]', style: { shape: 'ellipse', 'background-color': c.surface, 'border-color': c.saffron, 'border-style': 'dashed', 'border-width': 3 } },
    { selector: 'node[kind = "document"][?have]', style: { 'background-color': c.green, 'border-color': c.green, 'border-style': 'solid' } },
    { selector: 'node[kind = "criterion"]', style: { shape: 'diamond', width: 18, height: 18, 'font-size': 9, color: c.ink3, 'border-color': c.red, 'background-color': c.surface } },
    { selector: 'node[kind = "criterion"][?met]', style: { 'border-color': c.green, 'background-color': c.green } },
    { selector: 'edge', style: { width: 1.2, 'line-color': c.line, 'curve-style': 'haystack', opacity: 0.8 } },
    { selector: 'edge[kind = "requires"]', style: { 'line-style': 'dotted' } },
    { selector: '.faded', style: { opacity: 0.12 } },
    { selector: 'node.focus', style: { 'border-width': 4, 'border-color': c.ink } },
    { selector: 'edge.focus', style: { width: 2.4, 'line-color': c.ink3, opacity: 1 } },
  ];
}

function keep(g) {
  const nodes = g.nodes.filter((n) => {
    if (!view.rules && n.kind === 'criterion') return false;
    if (!view.missingOnly) return true;
    if (n.kind === 'scheme') return n.status === 'eligible';
    if (n.kind === 'document') return !n.have;
    return false;
  });
  const ids = new Set(nodes.map((n) => n.id));
  let edges = g.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
  if (view.missingOnly) {   // only documents still linked to a scheme you qualify for
    const linked = new Set(edges.map((e) => e.target));
    return { nodes: nodes.filter((n) => n.kind === 'scheme' ? edges.some((e) => e.source === n.id) : linked.has(n.id)), edges };
  }
  return { nodes, edges };
}

function detail(g, id) {
  const n = g.nodes.find((x) => x.id === id);
  if (!n) return '';
  const linked = g.edges.filter((e) => e.source === id || e.target === id).map((e) => g.nodes.find((x) => x.id === (e.source === id ? e.target : e.source))).filter(Boolean);
  const names = (kind) => linked.filter((x) => x.kind === kind).map((x) => x.label);
  if (n.kind === 'scheme') {
    return `<p class="h3">${esc(n.label)}</p><p class="small">${n.status === 'eligible' ? `<span class="ok">${esc(t('st.eligible', 'Eligible'))}</span>` : esc(t('st.partial', 'Partial'))}${n.amount ? ` · ${esc(n.amount)}` : ''}</p>
      ${names('document').length ? `<p class="tiny quiet" style="margin-top:8px">${esc(t('map.needs', 'Needs'))}: ${esc(names('document').join(', '))}</p>` : ''}
      ${names('criterion').length ? `<p class="tiny quiet">${esc(t('map.rules', 'Rules'))}: ${esc(names('criterion').join(', '))}</p>` : ''}`;
  }
  if (n.kind === 'document') {
    return `<p class="h3">${esc(n.label)}</p><p class="small">${n.have ? `<span class="ok">${esc(t('st.have', 'Have'))}</span>` : `<span class="bad">${esc(t('map.missing', 'Missing'))}</span>`} · ${esc(t('map.usedBy', 'needed by {n} schemes', { n: names('scheme').length }))}</p>
      <p class="tiny quiet" style="margin-top:8px">${esc(names('scheme').join(', '))}</p>`;
  }
  return `<p class="h3">${esc(n.label)}</p><p class="small">${n.met ? `<span class="ok">${esc(t('map.met', 'You meet this'))}</span>` : `<span class="bad">${esc(t('map.notMet', 'You do not meet this'))}</span>`}</p>
    <p class="tiny quiet" style="margin-top:8px">${esc(names('scheme').join(', '))}</p>`;
}

async function draw(el, g) {
  const box = el.querySelector('#gCanvas');
  let cytoscape;
  try { cytoscape = await loadCytoscape(); } catch { box.innerHTML = `<p class="bad small" style="padding:20px">${esc(t('map.libFail', 'Could not load the graph library.'))}</p>`; return; }
  if (!box.isConnected) return;
  cy?.destroy();
  const { nodes, edges } = keep(g);
  cy = cytoscape({
    container: box,
    elements: [...nodes.map((n) => ({ data: { ...n } })), ...edges.map((e, i) => ({ data: { id: `e${i}`, ...e } }))],
    style: style(colors()),
    layout: { name: 'cose', animate: false, padding: 24, nodeRepulsion: () => 9000, idealEdgeLength: () => 80, randomize: false },
    wheelSensitivity: 0.3, minZoom: 0.3, maxZoom: 2.5,
  });
  // A small graph (only what is missing) should not be blown up to fill the box
  if (cy.zoom() > 1.3) { cy.zoom(1.3); cy.center(); }
  const info = el.querySelector('#gInfo');
  info.innerHTML = `<p class="small quiet">${esc(t('map.tap', 'Tap a scheme, document or rule to see how it connects.'))}</p>`;
  cy.on('tap', 'node', (e) => {
    const node = e.target;
    cy.elements().addClass('faded').removeClass('focus');
    node.closedNeighborhood().removeClass('faded').addClass('focus');
    info.innerHTML = detail(g, node.id());
  });
  cy.on('tap', (e) => {
    if (e.target !== cy) return;
    cy.elements().removeClass('faded focus');
    info.innerHTML = `<p class="small quiet">${esc(t('map.tap', 'Tap a scheme, document or rule to see how it connects.'))}</p>`;
  });
}

function insights(g) {
  const ins = g.insights || {};
  const top = ins.most_valuable_missing_document;
  const shared = ins.most_shared_document;
  return `<div class="figures" style="margin-bottom:14px">
    <div class="card figure"><p class="figure-value num">${ins.counts?.scheme ?? 0}</p><p class="figure-label">${esc(t('map.schemes', 'Open schemes'))}</p></div>
    <div class="card figure"><p class="figure-value num">${ins.counts?.document ?? 0}</p><p class="figure-label">${esc(t('map.docs', 'Documents they ask for'))}</p></div>
    <div class="card figure"><p class="figure-value num">${ins.counts?.criterion ?? 0}</p><p class="figure-label">${esc(t('map.rulesN', 'Rules'))}</p></div>
  </div>
  ${top ? `<section class="card panel-pad insight" style="margin-top:0;margin-bottom:14px"><span class="insight-icon">${icon('file-search')}</span><div>
    <p class="tiny quiet" style="text-transform:uppercase;letter-spacing:.06em;font-weight:700">${esc(t('map.topK', 'Most valuable missing document'))}</p>
    <h2 class="h3">${esc(top.label)}</h2>
    <p class="small">${esc(top.schemes.length === 1
      ? t('map.topP1', 'Unblocks a scheme you qualify for: {list}', { list: top.schemes[0] })
      : t('map.topP', 'Unblocks {n} schemes you qualify for: {list}', { n: top.schemes.length, list: top.schemes.slice(0, 3).join(', ') }))}${top.value ? ` ${esc(t('map.topWorth', 'Together worth about {amount} a year.', { amount: fmtINR(top.value) }))}` : ''}</p>
    <a class="link small" href="#/documents">${esc(t('map.toDocs', 'Go to Documents'))}</a></div></section>` : ''}
  ${shared && !top ? `<p class="small quiet" style="margin-bottom:14px">${esc(t('map.shared', '{doc} is asked for by the most schemes ({n}).', { doc: shared.label, n: shared.schemes }))}</p>` : ''}`;
}

export const schemeMap = {
  title: () => t('map.title', 'Scheme map'),
  sub: () => t('map.sub', 'How your schemes, the documents they need and their rules connect.'),
  deps: ['run', 'vault', 'ownedDocs'],
  leave() { cy?.destroy(); cy = null; },
  async render(el) {
    if (!state.run) {
      el.innerHTML = schemesTabs('map') + emptyCard({ iconName: 'network', title: t('sch.noRun', 'Fill in your profile first to see schemes.'), action: `<a class="btn btn-primary" href="#/start">${esc(t('land.start', 'Get started free'))}</a>` });
      return;
    }
    el.innerHTML = `${schemesTabs('map')}<div id="gTop"><p class="working quiet"><span class="spinner"></span>${esc(t('map.loading', 'Building the map…'))}</p></div>
      <div class="toolbar">
        <div class="segmented" role="group" aria-label="${esc(t('map.show', 'Show'))}">
          <button type="button" data-v="all" aria-pressed="${!view.missingOnly}">${esc(t('map.all', 'Everything'))}</button>
          <button type="button" data-v="missing" aria-pressed="${view.missingOnly}">${esc(t('map.onlyMissing', 'Only what I am missing'))}</button>
        </div>
        <label class="check"><input type="checkbox" id="gRules" ${view.rules ? 'checked' : ''} /> <span class="small">${esc(t('map.showRules', 'Show rules'))}</span></label>
      </div>
      <div class="graph-wrap">
        <div class="card graph-canvas" id="gCanvas" role="img" aria-label="${esc(t('map.aria', 'Graph of schemes, documents and rules'))}"></div>
        <aside class="card panel-pad graph-side">
          <div id="gInfo"><p class="small quiet">${esc(t('map.tap', 'Tap a scheme, document or rule to see how it connects.'))}</p></div>
          <ul class="graph-legend">
            <li><i class="lg-scheme on"></i>${esc(t('map.lgElig', 'Scheme you qualify for'))}</li>
            <li><i class="lg-scheme"></i>${esc(t('map.lgPartial', 'Scheme you are close to'))}</li>
            <li><i class="lg-doc on"></i>${esc(t('map.lgHave', 'Document you have'))}</li>
            <li><i class="lg-doc"></i>${esc(t('map.lgMissing', 'Document you are missing'))}</li>
            <li><i class="lg-rule on"></i>${esc(t('map.lgMet', 'Rule you meet'))}</li>
            <li><i class="lg-rule"></i>${esc(t('map.lgUnmet', 'Rule you do not meet'))}</li>
          </ul>
        </aside>
      </div>`;
    el.querySelectorAll('[data-go]').forEach((b) => b.addEventListener('click', () => { location.hash = b.dataset.go; }));
    let g;
    try { g = await knowledgeGraph(); } catch (err) { toast(err.message, 'bad'); el.querySelector('#gTop').innerHTML = ''; return; }
    if (!el.isConnected) return;
    el.querySelector('#gTop').innerHTML = insights(g);
    draw(el, g);
    el.querySelectorAll('[data-v]').forEach((b) => b.addEventListener('click', () => {
      view.missingOnly = b.dataset.v === 'missing';
      el.querySelectorAll('[data-v]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      draw(el, g);
    }));
    el.querySelector('#gRules').addEventListener('change', (e) => { view.rules = e.target.checked; draw(el, g); });
  },
};
