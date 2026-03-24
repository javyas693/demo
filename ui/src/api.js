import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api/portfolio',
  timeout: 10000,
});

export const orchestratePortfolio = async (payload) => {
  try {
    const response = await api.post('/orchestrate', payload);
    return { data: response.data, error: null };
  } catch (err) {
    console.error('Orchestration Error:', err);
    return {
      data: null,
      error: err.response?.data?.detail || 'System unavailable. Failed to reach the AI Advisory Orchestrator.'
    };
  }
};

export const simulatePortfolio = async (payload) => {
  try {
    const mappedPayload = {
      ...payload,
      horizon_months: (payload.horizon_years || 1) * 12
    };
    const response = await api.post('/simulate', mappedPayload);
    console.log("API RESPONSE:", response.data);
    return {
      data: {
        timeline: response.data.timeline,
        timeline_series: response.data.timeline_series,
        monthly_intelligence: response.data.monthly_intelligence || [],
        monthly_intelligence_whatif: response.data.monthly_intelligence_whatif || null,
      },
      error: null
    };
  } catch (error) {
    console.error("Simulation Error", error);
    return { data: null, error: error.response?.data?.detail || "Failed to simulate specific time horizons." };
  }
};

export const fetchHistory = async () => {
  try {
    const response = await api.get('/history');
    return { data: response.data, error: null };
  } catch (err) {
    return { data: null, error: 'System unavailable. Failed to fetch historical logs.' };
  }
};

export const fetchProjection = async () => {
  try {
    const response = await api.get('/projection');
    return { data: response.data, error: null };
  } catch (err) {
    return { data: null, error: 'System unavailable. Failed to fetch projections.' };
  }
};
