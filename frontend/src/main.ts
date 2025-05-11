import './assets/main.css';

import { createApp } from 'vue';
import { createPinia } from 'pinia';

import App from './App.vue';
import router from './router';
import axios from 'axios';
import markdownDirective from './directives/markdown-directive';

const app = createApp(App);

// Pinia 상태 관리 설정
const pinia = createPinia();
app.use(pinia);

app.use(router);

// 마크다운 디렉티브 설정
app.directive('markdown', markdownDirective);

// 전역 axios 설정
axios.defaults.withCredentials = true;

// API 기본 URL 설정 (환경 변수에서 가져옴)
const apiUrl = import.meta.env.VITE_API_DEST || '/api';
axios.defaults.baseURL = apiUrl;

// 인터셉터 설정
axios.interceptors.request.use(
    (config) => {
        // 요청이 전달되기 전에 작업 수행
        console.log(`API 요청: ${config.method?.toUpperCase()} ${config.url}`);

        // 인증 토큰 추가 (필요한 경우)
        const authStore = JSON.parse(localStorage.getItem('auth') || '{}');
        if (authStore && authStore.tokens && authStore.tokens.accessToken) {
            config.headers.Authorization = `Bearer ${authStore.tokens.accessToken}`;
        }

        return config;
    },
    (error) => {
        // 요청 오류 처리
        console.error('API 요청 오류:', error);
        return Promise.reject(error);
    },
);

// 응답 인터셉터
axios.interceptors.response.use(
    (response) => {
        // 응답 데이터가 있는 경우 처리
        return response;
    },
    (error) => {
        // 인증 오류 (401) 처리
        if (error.response && error.response.status === 401) {
            console.log('인증 실패. 로그인 페이지로 리다이렉트합니다.');
            router.push('/login');
        }

        // 다른 오류 처리
        console.error('API 응답 오류:', error);
        return Promise.reject(error);
    },
);

app.mount('#app');
