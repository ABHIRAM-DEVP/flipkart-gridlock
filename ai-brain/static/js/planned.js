(() => {
  const U = window.AstramUtils;
  const SAMPLE = {
    start_datetime: '2026-06-20T18:00',
    event_type: 'planned',
    event_cause: 'festival',
    corridor: 'Old Madras Road',
    zone: 'East Zone 1',
    junction: 'KR Puram',
    latitude: 13.0069,
    longitude: 77.6950,
    priority: 'high',
    address: 'KR Puram, Bangalore, Pin-560016',
    requires_road_closure: true,
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

  const form = document.getElementById('planned-form');

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
      event_type: 'planned',
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
    const panel = document.getElementById('impact-result');
    panel.classList.remove('hidden');
    document.getElementById('planned-key').textContent = result.planned_key || '—';
    document.getElementById('baseline').textContent = `${result.baseline_unplanned_rate ?? 0} events/day`;
    document.getElementById('spillover').textContent = result.spillover_events_per_planned_event ?? 0;
    document.getElementById('multiplier').textContent = `${result.impact_multiplier ?? 1}×`;
    document.getElementById('preposition').textContent = `${result.recommend_preposition_hours_before ?? 3} hours before`;
    const risk = Number(result.compounding_risk_score ?? 0);
    document.getElementById('risk-val').textContent = `${risk.toFixed(2)} / 100`;
    const bar = document.getElementById('risk-bar');
    bar.style.width = `${Math.min(100, risk)}%`;
    bar.className = `h-3 rounded transition-all duration-500 ${risk < 30 ? 'bg-green-500' : risk < 60 ? 'bg-amber-500' : 'bg-red-500'}`;
  }

  API.appData().then(data => {
    U.populateSelect('select-corridor', data.corridors, CORRIDORS);
    U.populateSelect('select-cause', data.causes, CAUSES);
    U.populateSelect('select-zone', data.zones, ['East Zone 1', 'North Zone 2']);
  }).catch(() => {
    U.populateSelect('select-corridor', CORRIDORS);
    U.populateSelect('select-cause', CAUSES);
    U.populateSelect('select-zone', ['East Zone 1']);
  });

  document.getElementById('btn-sample').addEventListener('click', () => fillForm(SAMPLE));

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      const payload = collectFormData();
      const result = await API.plannedImpact(payload);
      renderResult(result);
    } catch (err) {
      alert('Forecast failed: ' + (err.message || err));
    }
  });
})();
