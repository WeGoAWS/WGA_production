// src/utils/http.ts
// Axios 인스턴스 및 인터셉터 설정

import axios from 'axios';

// 기본 API URL 설정
const apiUrl = import.meta.env.API_URL || 'http://localhost:8000';

// Axios 인스턴스 생성
const http = axios.create({
    baseURL: apiUrl,
    withCredentials: true, // 세션 쿠키 포함을 위한 설정
    timeout: 10000, // 10초 타임아웃
    headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
    },
});

// 요청 인터셉터 설정
http.interceptors.request.use(
    (config) => {
        // 요청이 전달되기 전에 작업 수행
        console.log(`API 요청: ${config.method?.toUpperCase()} ${config.url}`);
        return config;
    },
    (error) => {
        // 요청 오류 처리
        console.error('API 요청 오류:', error);
        return Promise.reject(error);
    },
);

// 응답 인터셉터 설정
http.interceptors.response.use(
    (response) => {
        // 응답 데이터 처리
        return response;
    },
    (error) => {
        // 응답 오류 처리
        if (error.response) {
            // 서버가 응답을 반환한 경우
            console.error(`API 오류: ${error.response.status} - ${error.response.statusText}`);

            // 401 Unauthorized (인증 실패)
            if (error.response.status === 401) {
                console.log('인증 실패. 로그인 페이지로 리다이렉트해야 할 수 있습니다.');
                // 여기서 앱의 상태를 업데이트하거나 리다이렉트 처리
            }

            // 인증 오류나 다른 특정 오류에 대한 처리를 여기에 추가
        } else if (error.request) {
            // 요청이 전송되었지만 응답을 받지 못한 경우
            console.error('API 응답 없음:', error.request);
        } else {
            // 요청 설정 과정에서 오류가 발생한 경우
            console.error('API 요청 설정 오류:', error.message);
        }

        return Promise.reject(error);
    },
);

export default http;
