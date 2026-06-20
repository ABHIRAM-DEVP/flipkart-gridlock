(() => {
  let historyChart;

  function renderPerfCards(run) {
    if (!run) {
      document.getElementById('perf-cards').innerHTML = '<p class="text-slate-500 col-span-3">No model runs recorded. Train the model first.</p>';
      return;
    }
    const cards = [
      ['MAE (min)', run.duration_mae_min, 2],
      ['RMSE (min)', run.duration_rmse_min, 2],
      ['R²', run.duration_r2, 4],
      ['Accuracy', run.severity_accuracy, 4],
      ['F1 Macro', run.severity_f1_macro, 4],
      ['F1 Weighted', run.severity_f1_weighted, 4],
    ];
    document.getElementById('perf-cards').innerHTML = cards.map(([label, val, dec]) => `
      <div class="bg-slate-900 rounded-lg p-4 border border-slate-700">
        <p class="text-xs text-slate-400 uppercase">${label}</p>
        <p class="text-2xl font-bold mt-1">${val != null ? Number(val).toFixed(dec) : '—'}</p>
      </div>`).join('');
  }

  function parseClassificationReport(text) {
    const tbody = document.getElementById('clf-report-rows');
    if (!text || typeof text !== 'string') {
      tbody.innerHTML = '<tr><td colspan="5" class="py-4 text-slate-500">No classification report available.</td></tr>';
      return;
    }
    const lines = text.split('\n').filter(l => l.trim() && !l.includes('precision') && !l.includes('---') && !l.includes('accuracy'));
    tbody.innerHTML = lines.map(line => {
      const parts = line.trim().split(/\s+/);
      if (parts.length < 5) return '';
      const [cls, prec, rec, f1, sup] = parts;
      if (cls === 'macro' || cls === 'weighted') return '';
      return `<tr class="border-b border-slate-700/50">
        <td class="py-2">${cls}</td>
        <td class="py-2">${prec}</td>
        <td class="py-2">${rec}</td>
        <td class="py-2">${f1}</td>
        <td class="py-2">${sup}</td>
      </tr>`;
    }).join('');
  }

  function renderHistoryChart(runs) {
    const ctx = document.getElementById('chart-history');
    if (historyChart) historyChart.destroy();
    if (!runs.length) return;
    historyChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: runs.map(r => (r.trained_at || '').slice(0, 16)),
        datasets: [
          { label: 'R²', data: runs.map(r => r.duration_r2), borderColor: '#0ea5e9', tension: 0.3 },
          { label: 'F1 Macro', data: runs.map(r => r.severity_f1_macro), borderColor: '#22c55e', tension: 0.3 },
          { label: 'Accuracy', data: runs.map(r => r.severity_accuracy), borderColor: '#f59e0b', tension: 0.3 },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { labels: { color: '#94a3b8' } } },
        scales: {
          x: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } },
          y: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } },
        },
      },
    });
  }

  function renderGraphs(graphs) {
    const grid = document.getElementById('graphs-grid');
    const list = graphs?.graphs || graphs || [];
    if (!list.length) {
      grid.innerHTML = '<p class="text-slate-500">No graphs generated yet. Run training.</p>';
      return;
    }
    grid.innerHTML = list.map(g => {
      const name = g.name || g;
      return `
      <div class="border border-slate-700 rounded-xl overflow-hidden">
        <div class="p-2 bg-slate-900 text-xs font-mono text-slate-400 truncate">${name}</div>
        <img src="/graph/${name}" alt="${name}" class="w-full cursor-pointer graph-thumb" data-name="${name}" />
        <a href="/graph/${name}" download="${name}" class="block p-2 text-xs text-brand hover:underline">Download</a>
      </div>`;
    }).join('');

    grid.querySelectorAll('.graph-thumb').forEach(img => {
      img.addEventListener('click', () => {
        document.getElementById('modal-img').src = `/graph/${img.dataset.name}`;
        document.getElementById('graph-modal').classList.remove('hidden');
        document.getElementById('graph-modal').classList.add('flex');
      });
    });
  }

  document.getElementById('modal-close').addEventListener('click', () => {
    document.getElementById('graph-modal').classList.add('hidden');
    document.getElementById('graph-modal').classList.remove('flex');
  });

  Promise.all([API.modelRuns(), API.graphFiles(), fetch('/report.txt').then(r => r.text()).catch(() => '')])
    .then(([runs, graphs, reportText]) => {
      const latest = runs.length ? runs[runs.length - 1] : null;
      renderPerfCards(latest);
      parseClassificationReport(latest?.classification_report);
      renderHistoryChart(runs);
      renderGraphs(graphs);
    })
    .catch(console.error);
})();
