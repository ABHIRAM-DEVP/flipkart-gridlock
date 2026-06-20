export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api';

export interface ApiError {
  error: string;
  details: string;
  upstreamStatus: number;
}

async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!res.ok) {
    let errorData: ApiError;
    try {
      errorData = await res.json();
    } catch {
      errorData = {
        error: 'Unknown Error',
        details: await res.text(),
        upstreamStatus: res.status,
      };
    }
    throw errorData;
  }

  const contentType = res.headers.get('content-type');
  const text = await res.text();

  if (contentType && contentType.includes('text/plain')) {
    const trimmed = text.trim();
    if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
      try {
        return JSON.parse(trimmed);
      } catch {
        return text as any;
      }
    }
    return text as any;
  }

  if (contentType && contentType.includes('application/json')) {
    try {
      return JSON.parse(text);
    } catch {
      return text as any;
    }
  }

  const trimmed = text.trim();
  if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
    try {
      return JSON.parse(trimmed);
    } catch {
      return text as any;
    }
  }

  return text as any;
}

// Typed Endpoints
export const checkHealth = () => fetchApi<{ backend: string; astramService: string }>('/health');

export const getMetrics = () => fetchApi<any>('/dashboard/metrics');
export const getGraphs = () => fetchApi<any>('/dashboard/graphs');
export const getHotspots = () => fetchApi<any[]>('/dashboard/hotspots');
export const getDbscanHotspots = () => fetchApi<any[]>('/dashboard/dbscan-hotspots');
export const getWeights = (kind?: 'duration' | 'severity', top?: number) => {
  const params = new URLSearchParams();
  if (kind) params.append('kind', kind);
  if (top) params.append('top', top.toString());
  const qs = params.toString();
  return fetchApi<any>(`/dashboard/weights${qs ? `?${qs}` : ''}`);
};

export const predict = (data: any) => fetchApi<any>('/predictions', { method: 'POST', body: JSON.stringify(data) });
export const getPredictionsHistory = () => fetchApi<any>('/predictions');

export const plan = (data: any) => fetchApi<any>('/plans', { method: 'POST', body: JSON.stringify(data) });
export const getPlanHistory = () => fetchApi<any>('/plans');

export const plannedImpact = (data: any) => fetchApi<any>('/planned-impact', { method: 'POST', body: JSON.stringify(data) });
export const getPlannedImpactHistory = () => fetchApi<any>('/planned-impact');

export const getReportText = () => fetchApi<string>('/reports/text');
export const getGraphFiles = () => fetchApi<string[]>('/reports/graph-files');

export const getGraphImageUrl = (name: string) => `${API_BASE}/reports/graph/${name}`;

// Agentic workflow
export const runAgent = (data: any) => fetchApi<any>('/agent/run', { method: 'POST', body: JSON.stringify(data) });

export const subscribeSSE = (onMessage: (msg: any) => void) => {
  const url = `${API_BASE.replace('/api', '')}/sse/live`;
  const es = new EventSource(url);
  es.onmessage = (e) => {
    try {
      const parsed = JSON.parse(e.data);
      onMessage(parsed);
    } catch (err) {
      onMessage({ type: 'raw', data: e.data });
    }
  };
  return () => es.close();
};
