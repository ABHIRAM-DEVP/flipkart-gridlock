const DEFAULT_API_BASE = 'http://localhost:8080/api';

declare global {
  interface Window {
    __ASTRAM_API_BASE__?: string;
  }
}

export const getApiBase = () => {
  if (typeof window !== 'undefined' && window.__ASTRAM_API_BASE__) {
    return window.__ASTRAM_API_BASE__;
  }

  return process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_BASE;
};

export interface ApiError {
  error: string;
  details: string;
  upstreamStatus: number;
}

async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const apiBase = getApiBase();
  let res: Response;
  try {
    res = await fetch(`${apiBase}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...options.headers,
      },
    });
  } catch (err) {
    throw { error: 'NetworkError', details: String(err), upstreamStatus: 0 };
  }

  if (!res.ok) {
    const text = await res.text();
    let errorData: ApiError;
    try {
      errorData = JSON.parse(text);
    } catch {
      errorData = { error: 'Unknown Error', details: text, upstreamStatus: res.status };
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

export const getMetrics = async () => {
  try {
    return await fetchApi<any>('/dashboard/metrics');
  } catch (e) {
    console.warn('getMetrics fallback', e);
    return { active_incidents: 0, avg_duration_min: 0 };
  }
};
export const getGraphs = async () => {
  try {
    return await fetchApi<any>('/dashboard/graphs');
  } catch (e) {
    console.warn('getGraphs fallback', e);
    return {};
  }
};
export const getHotspots = async () => {
  try {
    return await fetchApi<any>('/dashboard/hotspots');
  } catch (e) {
    console.warn('getHotspots fallback', e);
    return [];
  }
};
export const getDbscanHotspots = async () => {
  try {
    return await fetchApi<any[]>('/dashboard/dbscan-hotspots');
  } catch (e) {
    console.warn('getDbscanHotspots fallback', e);
    return [
      { centroid_latitude: 12.9716, centroid_longitude: 77.5946, hotspot_score: 0.8, count: 12, avg_duration_min: 15 },
    ];
  }
};
export const getWeights = async (kind?: 'duration' | 'severity', top?: number) => {
  const params = new URLSearchParams();
  if (kind) params.append('kind', kind);
  if (top) params.append('top', top.toString());
  const qs = params.toString();
  try {
    return await fetchApi<any>(`/dashboard/weights${qs ? `?${qs}` : ''}`);
  } catch (e) {
    console.warn('getWeights fallback', e);
    return [];
  }
};

export const predict = (data: any) => fetchApi<any>('/predictions', { method: 'POST', body: JSON.stringify(data) });
export const getPredictionsHistory = () => fetchApi<any>('/predictions');

export const plan = (data: any) => fetchApi<any>('/plans', { method: 'POST', body: JSON.stringify(data) });
export const getPlanHistory = () => fetchApi<any>('/plans');

export const plannedImpact = (data: any) => fetchApi<any>('/planned-impact', { method: 'POST', body: JSON.stringify(data) });
export const getPlannedImpactHistory = () => fetchApi<any>('/planned-impact');

export const getReportText = () => fetchApi<string>('/reports/text');
export const getGraphFiles = () => fetchApi<string[]>('/reports/graph-files');

export const getGraphImageUrl = (name: string) => `${getApiBase()}/reports/graph/${name}`;

// Agentic workflow
export const runAgent = (data: any) => fetchApi<any>('/agent/run', { method: 'POST', body: JSON.stringify(data) });

export const subscribeSSE = (onMessage: (msg: any) => void) => {
  const url = `${getApiBase().replace('/api', '')}/sse/live`;
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
