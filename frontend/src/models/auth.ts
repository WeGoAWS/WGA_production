// src/models/auth.ts
// 인증 관련 타입 정의

export interface TokenData {
    id_token: string;
    access_token?: string;
    refresh_token?: string;
    provider: 'cognito' | 'google' | 'azure';
}

export interface AuthUser {
    username?: string;
    email?: string;
    provider?: string;
    attributes?: Record<string, any>;
}

export interface AuthError {
    status?: number;
    message: string;
    details?: any;
}
