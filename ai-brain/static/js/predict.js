(() => {
  const U = window.AstramUtils;
  const SAMPLE = {
    start_datetime: '2026-06-20T08:30',
    event_type: 'unplanned',
    event_cause: 'vehicle_breakdown',
    corridor: 'Tumkur Road',
    zone: 'North Zone 2',
    junction: 'Yeshwantpur',
    latitude: 13.014,
    longitude: 77.5608,
    priority: 'high',
    address: 'Near Yeshwantpur Metro, Pin-560022',
    requires_road_closure: false,
  };

  const CORRIDORS = [
    'Bellary Road 1', 'Bellary Road 2', 'Hosur Road', 'Magadi Road', 'Mysore Road',
    'Non-corridor', 'Old Madras Road', 'ORR East 1', 'ORR East 2', 'ORR North 1',
    'ORR North 2', 'ORR West 1', 'ORR West 2', 'Tumkur Road',
  ];

  const CAUSES = [
    'construction', 'encroachment', 'festival', 'flooding', 'footpath_encroachment',
    'others', 'pot_holes', 'procession', 'protest', 'public_event', 'road_conditions',
    'road_maintenance', 'road_widening', 'signal_failure', 'traffic_build_up',
    'vehicle_breakdown', 'vip_movement', 'water_logging',
  ];

  const form = document.getElementById('predict-form');

  function fillForm(data) {
    Object.entries(data).forEach(([k, v]) => {
      const el = form.elements.namedItem(k);
      if (!el) return;
      if (el.type === 'checkbox') el.checked = !!v;
      else if (k === 'start_datetime') el.value = String(v).replace(' ', 'T').slice(0, 16);
      else el.value = v;
    });
  }

  function collectFormData() {
    const fd = new FormData(form);
    return {
      start_datetime: fd.get('start_datetime'),
      event_type: fd.get('event_type'),
      event_cause: fd.get('event_cause'),
      corridor: fd.get('corridor'),
      zone: fd.get('zone'),
      junction: fd.get('junction'),
      latitude: parseFloat(fd.get('latitude')),
      longitude: parseFloat(fd.get('longitude')),
      priority: fd.get('priority'),
      address: fd.get('address'),
      requires_road_closure: form.elements.namedItem('requires_road_closure').checked,
    };
  }

  function renderResult(result) {
    const panel = document.getElementById('result-panel');
    panel.classList.remove('hidden');
    document.getElementById('res-duration').textContent = `${result.predicted_duration_min} min`;
    const badge = document.getElementById('res-severity-badge');
    const sev = (result.predicted_severity || 'medium').toLowerCase();
    badge.className = `px-3 py-1 rounded-full text-sm font-bold sev-${sev}`;
    badge.textContent = sev.toUpperCase();
    const interval = result.prediction_interval_min || {};
    document.getElementById('res-p10').textContent = interval.p10 ?? '—';
    document.getElementById('res-p90').textContent = interval.p90 ?? '—';
    const rp = result.resource_plan || {};
    document.getElementById('res-manpower').textContent = rp.manpower ?? '—';
    document.getElementById('res-barricades').textContent = rp.barricades ?? '—';
    document.getElementById('res-risk').textContent = rp.risk_score ?? '—';
    document.getElementById('res-diversion').textContent = rp.diversion ?? '—';
    document.getElementById('res-raw').textContent = JSON.stringify(result, null, 2);
  }

  function addHistoryRow(row) {
    const tbody = document.getElementById('history-rows');
    const payload = row.input_payload || {};
    const time = row.created_at ? new Date(row.created_at).toLocaleTimeString() : new Date().toLocaleTimeString();
    const tr = document.createElement('tr');
    tr.className = 'border-b border-slate-700/50';
    tr.innerHTML = `
      <td class="py-2 font-mono text-xs">${time}</td>
      <td class="py-2">${row.predicted_duration_min ?? '—'} min</td>
      <td class="py-2">${U.severityBadge(row.predicted_severity)}</td>
      <td class="py-2">${row.corridor || payload.corridor || '—'}</td>
      <td class="py-2"><button type="button" class="text-brand text-xs copy-btn">Copy</button></td>`;
    tr.querySelector('.copy-btn').addEventListener('click', () => {
      navigator.clipboard.writeText(JSON.stringify({ input: payload, result: row }, null, 2));
    });
    tbody.prepend(tr);
  }

  function loadHistory() {
    API.liveFeed().then(rows => {
      document.getElementById('history-rows').innerHTML = '';
      rows.forEach(addHistoryRow);
    });
  }

  API.appData().then(data => {
    U.populateSelect('select-corridor', data.corridors, CORRIDORS);
    U.populateSelect('select-cause', data.causes, CAUSES);
    U.populateSelect('select-zone', data.zones, ['North Zone 2', 'East Zone 1', 'South Zone 1']);
  }).catch(() => {
    U.populateSelect('select-corridor', CORRIDORS);
    U.populateSelect('select-cause', CAUSES);
    U.populateSelect('select-zone', ['North Zone 2', 'East Zone 1']);
  });

  document.getElementById('btn-sample').addEventListener('click', () => fillForm(SAMPLE));

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('btn-predict');
    btn.disabled = true;
    btn.textContent = 'Predicting…';
    try {
      const payload = collectFormData();
      const result = await API.predict(payload);
      renderResult(result);
      addHistoryRow({
        input_payload: payload,
        predicted_duration_min: result.predicted_duration_min,
        predicted_severity: result.predicted_severity,
        corridor: payload.corridor,
        created_at: new Date().toISOString(),
      });
    } catch (err) {
      alert('Prediction failed: ' + (err.message || err));
    } finally {
      btn.disabled = false;
      btn.textContent = 'Predict Incident Impact';
    }
  });

  document.addEventListener('astram:prediction', e => {
    const d = e.detail;
    addHistoryRow({
      input_payload: d.event,
      predicted_duration_min: d.predicted_duration_min,
      predicted_severity: d.predicted_severity,
      corridor: d.event?.corridor,
      created_at: new Date().toISOString(),
    });
  });

  loadHistory();
})();
