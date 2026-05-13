import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const ANALYTICS_TIMEOUT_MS = 30000;

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const sendMessage = async (conversationId, message, includeSteps = false) => {
  try {
    const response = await api.post('/api/chat', {
      conversation_id: conversationId,
      message: message,
      include_steps: includeSteps,
    });
    return response.data;
  } catch (error) {
    console.error('Error sending message:', error);
    throw error;
  }
};

export const sendBatchQuestions = async (questions, includeSteps = false, maxConcurrency = 10) => {
  try {
    const response = await api.post('/api/query/batch', {
      questions,
      include_steps: includeSteps,
      max_concurrency: maxConcurrency,
    });
    return response.data;
  } catch (error) {
    console.error('Error sending batch questions:', error);
    throw error;
  }
};

export const getConversation = async (conversationId) => {
  try {
    const response = await api.get(`/api/conversations/${conversationId}`);
    return response.data;
  } catch (error) {
    console.error('Error getting conversation:', error);
    throw error;
  }
};

export const deleteConversation = async (conversationId) => {
  try {
    const response = await api.delete(`/api/conversations/${conversationId}`);
    return response.data;
  } catch (error) {
    console.error('Error deleting conversation:', error);
    throw error;
  }
};

export const healthCheck = async () => {
  try {
    const response = await api.get('/health');
    return response.data;
  } catch (error) {
    console.error('Error checking health:', error);
    throw error;
  }
};

const localTodayBounds = () => {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  return {
    date_from: start.toISOString(),
    date_to: end.toISOString(),
  };
};

const analyticsParams = (days, source, period) => {
  const todayParams = period === 'today' ? localTodayBounds() : {};
  return {
    days,
    source: source || undefined,
    period: period === 'today' ? 'today' : undefined,
    ...todayParams,
  };
};

export const getAnalyticsSummary = async (days = 30, source = '', period = 'rolling') => {
  const response = await api.get('/admin/api/analytics/summary', {
    params: analyticsParams(days, source, period),
    timeout: ANALYTICS_TIMEOUT_MS,
  });
  return response.data;
};

export const getAnalyticsPerformance = async (days = 30, source = '', period = 'rolling') => {
  const response = await api.get('/admin/api/analytics/performance', {
    params: analyticsParams(days, source, period),
    timeout: ANALYTICS_TIMEOUT_MS,
  });
  return response.data;
};

export const getAnalyticsLatencyDistribution = async (days = 30, source = '', period = 'rolling') => {
  const response = await api.get('/admin/api/analytics/latency-distribution', {
    params: analyticsParams(days, source, period),
    timeout: ANALYTICS_TIMEOUT_MS,
  });
  return response.data;
};

export const getAnalyticsCostDistribution = async (days = 30, source = '', period = 'rolling') => {
  const response = await api.get('/admin/api/analytics/cost-distribution', {
    params: analyticsParams(days, source, period),
    timeout: ANALYTICS_TIMEOUT_MS,
  });
  return response.data;
};

export const getAnalyticsAccuracy = async (days = 30, source = '', period = 'rolling') => {
  const response = await api.get('/admin/api/analytics/accuracy', {
    params: analyticsParams(days, source, period),
    timeout: ANALYTICS_TIMEOUT_MS,
  });
  return response.data;
};

export const getAnalyticsQuestions = async (days = 30, source = '', period = 'rolling') => {
  const response = await api.get('/admin/api/analytics/questions', {
    params: analyticsParams(days, source, period),
    timeout: ANALYTICS_TIMEOUT_MS,
  });
  return response.data;
};

export const getAnalyticsEvent = async (eventId) => {
  const response = await api.get(`/admin/api/analytics/events/${eventId}`);
  return response.data;
};

export const invokeAutomaticReview = async (eventId) => {
  const response = await api.post(`/admin/api/analytics/events/${eventId}/automatic-review`);
  return response.data;
};

export const applyReview = async (eventId, outcome, llmReview = null, reviewer = 'user') => {
  const response = await api.post(`/admin/api/analytics/events/${eventId}/apply-review`, {
    outcome,
    reviewer,
    llm_review: llmReview,
  });
  return response.data;
};

export const applyAutomaticReview = applyReview;

export default api;

// Made with Bob
