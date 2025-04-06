// src/utils/debug.ts
// 디버깅을 위한 유틸리티 함수들

/**
 * 현재 환경 변수를 콘솔에 출력합니다.
 * 민감한 정보는 마스킹 처리합니다.
 */
export const logEnvironmentVars = () => {
    const vars = {
        AWS_REGION: import.meta.env.AWS_REGION || '설정되지 않음',
        AWS_ACCESS_KEY_ID: import.meta.env.AWS_ACCESS_KEY_ID ? '***설정됨***' : '설정되지 않음',
        AWS_SECRET_ACCESS_KEY: import.meta.env.AWS_SECRET_ACCESS_KEY
            ? '***설정됨***'
            : '설정되지 않음',
        COGNITO_DOMAIN: import.meta.env.COGNITO_DOMAIN || '설정되지 않음',
        USER_POOL_ID: import.meta.env.USER_POOL_ID || '설정되지 않음',
        COGNITO_CLIENT_ID: maskString(import.meta.env.COGNITO_CLIENT_ID) || '설정되지 않음',
        COGNITO_CLIENT_SECRET: import.meta.env.COGNITO_CLIENT_SECRET
            ? '***설정됨***'
            : '설정되지 않음',
        COGNITO_IDENTITY_POOL_ID: import.meta.env.COGNITO_IDENTITY_POOL_ID || '설정되지 않음',
        COGNITO_REDIRECT_URI: import.meta.env.COGNITO_REDIRECT_URI || '설정되지 않음',
        API_URL: import.meta.env.API_URL || '설정되지 않음',
    };

    console.log('====== 환경 변수 ======');
    Object.entries(vars).forEach(([key, value]) => {
        console.log(`${key}: ${value}`);
    });
    console.log('======================');
};

/**
 * OAuth 요청 URL이 올바르게 구성되었는지 확인합니다.
 */
export const validateOAuthUrl = (url: string): boolean => {
    try {
        const urlObj = new URL(url);

        // 필수 파라미터 확인
        const params = new URLSearchParams(urlObj.search);
        const requiredParams = ['client_id', 'redirect_uri', 'response_type', 'scope'];

        const missingParams = requiredParams.filter((param) => !params.has(param));

        if (missingParams.length > 0) {
            console.error('OAuth URL에 필수 파라미터가 누락되었습니다:', missingParams);
            return false;
        }

        // 프로토콜 검사
        if (urlObj.protocol !== 'https:') {
            console.error('OAuth URL은 HTTPS 프로토콜을 사용해야 합니다');
            return false;
        }

        return true;
    } catch (error) {
        console.error('OAuth URL 유효성 검사 오류:', error);
        return false;
    }
};

/**
 * 문자열의 일부를 마스킹 처리합니다.
 */
export const maskString = (str?: string): string => {
    if (!str) return '';

    if (str.length <= 8) {
        return '*'.repeat(str.length);
    }

    const visibleChars = 4;
    const firstVisible = str.substring(0, visibleChars);
    const lastVisible = str.substring(str.length - visibleChars);
    const maskedMiddle = '*'.repeat(Math.min(8, str.length - visibleChars * 2));

    return `${firstVisible}${maskedMiddle}${lastVisible}`;
};

/**
 * HTTP 요청의 세부 정보를 로깅합니다.
 */
export const logRequestDetails = (
    method: string,
    url: string,
    headers: Record<string, any>,
    body?: any,
) => {
    console.log('====== HTTP 요청 상세 정보 ======');
    console.log(`${method} ${url}`);

    console.log('헤더:');
    const sanitizedHeaders = { ...headers };
    if (sanitizedHeaders['Authorization']) {
        sanitizedHeaders['Authorization'] = '*** 마스킹됨 ***';
    }
    console.log(sanitizedHeaders);

    if (body) {
        console.log('본문:');
        // 민감한 정보를 포함할 수 있는 필드 마스킹
        const sanitizedBody = { ...body };
        ['code', 'refresh_token', 'access_token', 'id_token'].forEach((field) => {
            if (sanitizedBody[field]) {
                sanitizedBody[field] = maskString(sanitizedBody[field]);
            }
        });
        console.log(sanitizedBody);
    }

    console.log('================================');
};
