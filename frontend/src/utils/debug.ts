// src/utils/debug.ts

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

    Object.entries(vars).forEach(([key, value]) => {
        console.log(`${key}: ${value}`);
    });
};

export const validateOAuthUrl = (url: string): boolean => {
    try {
        const urlObj = new URL(url);

        const params = new URLSearchParams(urlObj.search);
        const requiredParams = ['client_id', 'redirect_uri', 'response_type', 'scope'];

        const missingParams = requiredParams.filter((param) => !params.has(param));

        if (missingParams.length > 0) {
            console.error('OAuth URL에 필수 파라미터가 누락되었습니다:', missingParams);
            return false;
        }

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

export const logRequestDetails = (
    method: string,
    url: string,
    headers: Record<string, any>,
    body?: any,
) => {
    const sanitizedHeaders = { ...headers };
    if (sanitizedHeaders['Authorization']) {
        sanitizedHeaders['Authorization'] = '*** 마스킹됨 ***';
    }

    if (body) {
        const sanitizedBody = { ...body };
        ['code', 'refresh_token', 'access_token', 'id_token'].forEach((field) => {
            if (sanitizedBody[field]) {
                sanitizedBody[field] = maskString(sanitizedBody[field]);
            }
        });
    }
};
