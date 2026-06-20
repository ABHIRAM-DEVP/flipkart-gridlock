(() => {
  const U = window.AstramUtils;
  let featureChart, hourChart, causeChart;
  let mapInstance;
  let dbscanData = [];
  let sortKey = 'score';
  let sortAsc = false;

  const DEFAULT_CAUSES = [
    'construction', 'encroachment', 'festival', 'flooding', 'footpath_encroachment',
    'others', 'pot_holes', 'procession', 'protest', 'public_event', 'road_conditions',
    'road_maintenance', 'road_widening', 'signal_failure', 'traffic_build_up',
    'vehicle_breakdown', 'vip_movement', 'water_logging',
  ];

  const peakHourPlugin = {
    id: 'peakHours',
    beforeDraw(chart) {
      const { ctx, chartArea, scales } = chart;
      if (!chartArea || !scales.x) return;
      ctx.save();
      ctx.fillStyle = 'rgba(245, 158, 11, 0.08)';
      scales.x.ticks.forEach((tick, i) => {
        const h = parseInt(tick.label, 10);
        if (h >= 7 && h <= 10 || h >= 17 && h <= 20) {
          const x = scales.x.getPixelForTick(i);
          const next = scales.x.getPixelForTick(i + 1) || x + 20;
          ctx.fillRect(x - (next - x) / 2, chartArea.top, next - x, chartArea.bottom - chartArea.top);
        }
      });
      ctx.restore();
    },
  };

  function renderMetrics(metrics) {
    const m = metrics || {};
    U.countUp(document.getElementById('metric-r2'), m.duration_r2 ?? m.r2 ?? 0, 4);
    U.countUp(document.getElementById('metric-mae'), m.duration_mae_min ?? m.mae ?? 0, 2);
    U.countUp(document.getElementById('metric-acc'), m.severity_accuracy ?? m.severity_accuracy ?? 0, 4);
    U.countUp(document.getElementById('metric-f1'), m.severity_f1_macro ?? m.severity_f1_macro ?? 0, 4);
  }

  function renderFeatureChart(weights) {
    const top = (weights || []).slice(0, 10);
    const ctx = document.getElementById('chart-features');
    if (featureChart) featureChart.destroy();
    featureChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: top.map(w => w.feature),
        datasets: [{
          data: top.map(w => w.weight ?? w.gain ?? 0),
          backgroundColor: 'rgba(14, 165, 233, 0.8)',
          borderRadius: 4,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
          y: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 10 } } },
        },
      },
    });
  }

  function renderHourChart(hourCounts) {
    const hours = Object.keys(hourCounts || {}).sort((a, b) => +a - +b);
    const ctx = document.getElementById('chart-hours');
    if (hourChart) hourChart.destroy();
    hourChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: hours,
        datasets: [{
          data: hours.map(h => hourCounts[h]),
          borderColor: '#0ea5e9',
          backgroundColor: 'rgba(14, 165, 233, 0.15)',
          fill: true,
          tension: 0.4,
          pointRadius: 3,
        }],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
          y: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
        },
      },
      plugins: [peakHourPlugin],
    });
  }

  function renderCauseChart(causeCounts) {
    const entries = Object.entries(causeCounts || {}).sort((a, b) => b[1] - a[1]).slice(0, 10);
    const palette = ['#0ea5e9', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16'];
    const ctx = document.getElementById('chart-causes');
    if (causeChart) causeChart.destroy();
    causeChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: entries.map(e => e[0]),
        datasets: [{ data: entries.map(e => e[1]), backgroundColor: palette }],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: 'right', labels: { color: '#94a3b8', boxWidth: 12 } } },
      },
    });
  }

  function prependLiveFeedItem(item) {
    const container = document.getElementById('live-items');
    if (!container) return;
    const payload = item.payload || item;
    const event = payload.event || payload.input_payload || {};
    const corridor = event.corridor || payload.corridor || '—';
    const dur = payload.predicted_duration_min ?? '—';
    const sev = payload.predicted_severity || 'medium';
    const time = new Date().toLocaleTimeString();
    const div = document.createElement('div');
    div.className = 'flex items-center gap-3 py-2 border-b border-slate-700 text-sm animate-slide-in';
    div.innerHTML = `
      <span class="text-slate-400 text-xs font-mono whitespace-nowrap">${time}</span>
      ${U.severityBadge(sev)}
      <span class="text-slate-300">${dur} min · ${corridor}</span>`;
    container.prepend(div);
    while (container.children.length > 30) container.lastChild.remove();
  }

  function renderLiveFeed(feed) {
    const container = document.getElementById('live-items');
    if (!container) return;
    container.innerHTML = '';
    (feed || []).forEach(row => {
      prependLiveFeedItem({
        predicted_duration_min: row.predicted_duration_min,
        predicted_severity: row.predicted_severity,
        corridor: row.corridor,
        event: row.input_payload,
      });
    });
  }

  function renderMap(clusters) {
    const el = document.getElementById('heatmap');
    if (!el || typeof L === 'undefined') return;
    if (mapInstance) { mapInstance.remove(); mapInstance = null; }
    mapInstance = L.map('heatmap').setView([12.97, 77.59], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
    }).addTo(mapInstance);
    (clusters || []).forEach(c => {
      const lat = c.centroid_latitude ?? c.latitude;
      const lng = c.centroid_longitude ?? c.longitude;
      if (!lat || !lng) return;
      const score = c.hotspot_score ?? 0;
      const color = score > 80 ? '#ef4444' : score > 60 ? '#f97316' : '#eab308';
      L.circle([lat, lng], {
        radius: Math.sqrt(c.count || 1) * 150,
        color, fillColor: color, fillOpacity: 0.4,
      }).bindPopup(`
        <b>Cluster ${c.cluster_id ?? '—'}</b><br>
        Events: ${c.count ?? 0}<br>
        Avg duration: ${Number(c.avg_duration_min ?? 0).toFixed(1)} min<br>
        Heat score: ${Number(score).toFixed(1)}
      `).addTo(mapInstance);
    });
    setTimeout(() => mapInstance?.invalidateSize(), 200);
  }

  function sortDbscan() {
    const sorted = [...dbscanData].sort((a, b) => {
      let va, vb;
      switch (sortKey) {
        case 'count': va = a.count; vb = b.count; break;
        case 'duration': va = a.avg_duration_min; vb = b.avg_duration_min; break;
        case 'location': va = a.cluster_id; vb = b.cluster_id; break;
        default: va = a.hotspot_score; vb = b.hotspot_score;
      }
      return sortAsc ? va - vb : vb - va;
    });
    const tbody = document.getElementById('dbscan-rows');
    tbody.innerHTML = sorted.map(c => `
      <tr class="border-b border-slate-700/50">
        <td class="py-2">Cluster ${c.cluster_id ?? '—'}</td>
        <td class="py-2">${c.count ?? 0}</td>
        <td class="py-2">${Number(c.avg_duration_min ?? 0).toFixed(1)} min</td>
        <td class="py-2">${U.heatBadge(c.hotspot_score)}</td>
      </tr>`).join('');
  }

  function renderCorridorTable(riskRows) {
    const tbody = document.getElementById('corridor-rows');
    tbody.innerHTML = (riskRows || []).map(r => {
      const score = r.risk_score ?? 0;
      const barColor = score > 90 ? '#ef4444' : score > 75 ? '#f97316' : '#eab308';
      return `
      <tr class="border-b border-slate-700/50">
        <td class="py-2">${r.corridor}</td>
        <td class="py-2">${r.event_count}</td>
        <td class="py-2">${r.avg_duration_min} min</td>
        <td class="py-2">
          <div class="flex items-center gap-2">
            <div class="flex-1 h-2 bg-slate-700 rounded overflow-hidden">
              <div class="h-2 rounded" style="width:${Math.min(100, score)}%;background:${barColor}"></div>
            </div>
            <span class="text-xs w-10">${score.toFixed(0)}</span>
          </div>
        </td>
      </tr>`;
    }).join('');
  }

  async function loadAll() {
    const [graphs, stats, feed, snap] = await Promise.all([
      API.graphs(), API.eventStats(), API.liveFeed(), API.hotspots(),
    ]);
    renderMetrics(graphs.metrics);
    renderFeatureChart(graphs.feature_weights);
    renderHourChart(stats.hour_counts);
    renderCauseChart(stats.cause_counts);
    renderLiveFeed(feed);
    dbscanData = snap.dbscan || [];
    sortDbscan();
    renderMap(dbscanData);
    renderCorridorTable(stats.corridor_risk);
  }

  document.querySelectorAll('#dbscan-table th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      if (sortKey === key) sortAsc = !sortAsc;
      else { sortKey = key; sortAsc = false; }
      sortDbscan();
    });
  });

  document.addEventListener('astram:prediction', e => prependLiveFeedItem(e.detail));
  document.addEventListener('astram:dashboard', e => {
    const { graphs, stats, feed } = e.detail;
    renderMetrics(graphs.metrics);
    renderFeatureChart(graphs.feature_weights);
    renderHourChart(stats.hour_counts);
    renderCauseChart(stats.cause_counts);
    if (feed) renderLiveFeed(feed);
  });

  loadAll().catch(console.error);
})();
