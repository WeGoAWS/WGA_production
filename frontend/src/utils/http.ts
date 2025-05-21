// src/utils/http.ts

import axios from 'axios';

const apiUrl = import.meta.env.API_URL || 'http://localhost:8000';

const http = axios.create({
    baseURL: apiUrl,
    withCredentials: true,
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
    },
});

http.interceptors.request.use(
    (config) => {
        return config;
    },
    (error) => {
        console.error('API 요청 오류:', error);
        return Promise.reject(error);
    },
);

http.interceptors.response.use(
    (response) => {
        return response;
    },
    (error) => {
        if (error.response) {
            console.error(`API 오류: ${error.response.status} - ${error.response.statusText}`);

            if (error.response.status === 401) {
                console.log('인증 실패. 로그인 페이지로 리다이렉트해야 할 수 있습니다.');
            }
        } else if (error.request) {
            console.error('API 응답 없음:', error.request);
        } else {
            console.error('API 요청 설정 오류:', error.message);
        }

        return Promise.reject(error);
    },
);

export default http;
