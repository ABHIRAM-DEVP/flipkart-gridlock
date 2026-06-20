const API = {
  predict: (event) => fetch('/predict', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(event),
  }).then(r => r.json()),

  plan: (events, budget) => fetch('/plan', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ events, budget }),
  }).then(r => r.json()),

  plannedImpact: (event) => fetch('/planned-impact', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(event),
  }).then(r => r.json()),

  liveFeed: (limit = 20) => fetch(`/api/live-feed?limit=${limit}`).then(r => r.json()),
  graphs: () => fetch('/graphs').then(r => r.json()),
  appData: () => fetch('/app-data').then(r => r.json()),
  hotspots: () => fetch('/api/hotspot-snapshot').then(r => r.json()),
  eventStats: () => fetch('/api/event-stats').then(r => r.json()),
  modelRuns: () => fetch('/api/model-runs').then(r => r.json()),
  graphFiles: () => fetch('/graph-files').then(r => r.json()),
  plans: () => fetch('/api/plans').then(r => r.json()),
  plannedImpacts: () => fetch('/api/planned-impacts').then(r => r.json()),
};

window.AstramAPI = API;

window.AstramUtils = {
  severityBadge(sev) {
    const s = (sev || 'medium').toLowerCase();
    const cls = { low: 'sev-low', medium: 'sev-medium', high: 'sev-high', critical: 'sev-critical' }[s] || 'sev-medium';
    return `<span class="px-2 py-0.5 rounded text-xs font-bold ${cls}">${s.toUpperCase()}</span>`;
  },

  heatBadge(score) {
    const s = Number(score) || 0;
    const cls = s > 80 ? 'badge-heat-high' : s > 60 ? 'badge-heat-mid' : 'badge-heat-low';
    return `<span class="px-2 py-0.5 rounded text-xs font-bold ${cls}">${s.toFixed(1)}</span>`;
  },

  countUp(el, target, decimals = 2) {
    const num = Number(target);
    if (!el || Number.isNaN(num)) { if (el) el.textContent = '—'; return; }
    const start = performance.now();
    const from = 0;
    const dur = 800;
    const step = (t) => {
      const p = Math.min(1, (t - start) / dur);
      const val = from + (num - from) * (1 - Math.pow(1 - p, 3));
      el.textContent = decimals === 0 ? Math.round(val) : val.toFixed(decimals);
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  },

  populateSelect(id, items, fallback = []) {
    const el = document.getElementById(id);
    if (!el) return;
    const opts = (items && items.length ? items : fallback);
    el.innerHTML = opts.map(v => `<option value="${v}">${v}</option>`).join('');
  },
};
