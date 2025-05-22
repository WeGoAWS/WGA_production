import './assets/main.css';
import './assets/base.css';

import { createApp } from 'vue';
import { createPinia } from 'pinia';

import App from './App.vue';
import router from './router';
import axios from 'axios';
import markdownDirective from './directives/markdown-directive';

const app = createApp(App);

const pinia = createPinia();
app.use(pinia);

app.use(router);

app.directive('markdown', markdownDirective);

axios.defaults.withCredentials = true;

const apiUrl = import.meta.env.VITE_API_DEST || '/api';
axios.defaults.baseURL = apiUrl;

axios.interceptors.request.use(
    (config) => {
        const authStore = JSON.parse(localStorage.getItem('auth') || '{}');
        if (authStore && authStore.tokens && authStore.tokens.accessToken) {
            config.headers.Authorization = `Bearer ${authStore.tokens.accessToken}`;
        }

        return config;
    },
    (error) => {
        console.error('API 요청 오류:', error);
        return Promise.reject(error);
    },
);

axios.interceptors.response.use(
    (response) => {
        return response;
    },
    (error) => {
        if (error.response && error.response.status === 401) {
            router.push('/login');
        }

        console.error('API 응답 오류:', error);
        return Promise.reject(error);
    },
);

app.mount('#app');
