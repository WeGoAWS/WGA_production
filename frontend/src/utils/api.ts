// src/utils/api.ts
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.API_URL, // API Gateway base URL
  headers: {
    'Content-Type': 'application/json',
  },
});

export default api;