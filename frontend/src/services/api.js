import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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

export default api;

// Made with Bob
