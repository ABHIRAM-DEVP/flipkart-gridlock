window.__astram = {
  predictions: [],
  plans: [],
  plannedImpacts: [],
  dashboard: null,
  liveFeed: [],

  onSSEMessage(msg) {
    if (msg.type === 'prediction') {
      this.predictions.unshift(msg.payload);
      this.liveFeed.unshift(msg.payload);
      document.dispatchEvent(new CustomEvent('astram:prediction', { detail: msg.payload }));
    }
    if (msg.type === 'plan') {
      this.plans.unshift(msg.payload);
      document.dispatchEvent(new CustomEvent('astram:plan', { detail: msg.payload }));
    }
    if (msg.type === 'planned_impact') {
      this.plannedImpacts.unshift(msg.payload);
      document.dispatchEvent(new CustomEvent('astram:planned_impact', { detail: msg.payload }));
    }
  },

  async pollDashboard() {
    try {
      const [graphs, stats, feed] = await Promise.all([
        fetch('/graphs').then(r => r.json()),
        fetch('/api/event-stats').then(r => r.json()),
        fetch('/api/live-feed').then(r => r.json()),
      ]);
      this.dashboard = { graphs, stats };
      document.dispatchEvent(new CustomEvent('astram:dashboard', { detail: { graphs, stats, feed } }));
    } catch (e) {
      console.warn('[astram] poll failed', e);
    }
  },
};
