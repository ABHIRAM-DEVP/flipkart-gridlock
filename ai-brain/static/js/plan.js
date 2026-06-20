(() => {
  const DEFAULT_JSON = `[
  {
    "start_datetime": "2026-06-20T18:00",
    "event_type": "planned",
    "event_cause": "festival",
    "corridor": "Old Madras Road",
    "zone": "East Zone 1",
    "junction": "KR Puram",
    "latitude": 13.0069,
    "longitude": 77.6950,
    "priority": "high",
    "requires_road_closure": true
  }
]`;

  const ta = document.getElementById('events-json');
  const modal = document.getElementById('event-modal');
  ta.value = DEFAULT_JSON;

  function renderResults(result, budget) {
    const alloc = result.allocation || {};
    const panel = document.getElementById('plan-results');
    panel.classList.remove('hidden');
    const status = (alloc.status || 'unknown').toUpperCase();
    document.getElementById('alloc-status').textContent = status;
    document.getElementById('alloc-status').className = `px-2 py-1 text-xs rounded ${status.includes('OPTIMAL') ? 'bg-green-600' : 'bg-amber-600'} text-white`;
    const remaining = alloc.remaining_personnel ?? 0;
    document.getElementById('alloc-remaining').textContent = remaining;
    document.getElementById('alloc-budget').textContent = budget;
    const used = Math.max(0, budget - remaining);
    document.getElementById('alloc-bar').style.width = `${Math.min(100, (used / budget) * 100)}%`;

    const scored = result.scored_events || [];
    const allocations = alloc.allocations || [];
    const tbody = document.getElementById('alloc-rows');
    tbody.innerHTML = scored.map((ev, i) => {
      const a = allocations.find(x => x.event_index === i) || {};
      const event = ev.event || {};
      return `
      <tr class="border-b border-slate-700/50">
        <td class="py-2">${i + 1}</td>
        <td class="py-2">${event.event_type || '—'}</td>
        <td class="py-2">${window.AstramUtils.severityBadge(ev.predicted_severity)}</td>
        <td class="py-2">${a.assigned_personnel ?? 0}</td>
        <td class="py-2">${a.covered ? '✓' : '—'}</td>
        <td class="py-2">${Number(a.risk_score ?? 0).toFixed(1)}</td>
        <td class="py-2">${ev.predicted_duration_min ?? '—'} min</td>
      </tr>`;
    }).join('');
  }

  function renderPlanHistory(plans) {
    const container = document.getElementById('plan-history');
    if (!plans.length) {
      container.innerHTML = '<p class="text-slate-500 text-sm">No plans yet.</p>';
      return;
    }
    container.innerHTML = plans.map(p => {
      const dt = new Date(p.created_at).toLocaleString();
      const events = p.input_events || [];
      return `
      <details class="bg-slate-900 rounded-lg border border-slate-700 mb-2">
        <summary class="p-4 cursor-pointer flex justify-between text-sm">
          <span>${dt} — Budget: ${p.personnel_budget} · Events: ${events.length}</span>
          <span>▼</span>
        </summary>
        <div class="p-4 border-t border-slate-700">
          <pre class="text-xs overflow-auto max-h-64">${JSON.stringify(p, null, 2)}</pre>
        </div>
      </details>`;
    }).join('');
  }

  document.getElementById('plan-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('btn-plan');
    btn.disabled = true;
    try {
      const events = JSON.parse(ta.value);
      const budget = parseInt(document.getElementById('budget').value, 10) || 50;
      if (!Array.isArray(events)) throw new Error('Events must be a JSON array');
      const result = await API.plan(events, budget);
      renderResults(result, budget);
      const plans = await API.plans();
      renderPlanHistory(plans);
    } catch (err) {
      alert(err.message || 'Plan failed');
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById('btn-add-event').addEventListener('click', () => {
    modal.classList.remove('hidden');
    modal.classList.add('flex');
  });

  document.getElementById('modal-cancel').addEventListener('click', () => {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  });

  document.getElementById('modal-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const event = {
      start_datetime: fd.get('start_datetime'),
      event_type: fd.get('event_type'),
      event_cause: fd.get('event_cause'),
      corridor: fd.get('corridor'),
      zone: fd.get('zone'),
      junction: fd.get('junction'),
      latitude: parseFloat(fd.get('latitude')),
      longitude: parseFloat(fd.get('longitude')),
      priority: fd.get('priority'),
      requires_road_closure: e.target.elements.namedItem('requires_road_closure').checked,
    };
    let arr = [];
    try { arr = JSON.parse(ta.value); } catch { arr = []; }
    arr.push(event);
    ta.value = JSON.stringify(arr, null, 2);
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    e.target.reset();
  });

  API.plans().then(renderPlanHistory).catch(() => renderPlanHistory([]));
})();
