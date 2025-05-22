// src/stores/auth.ts
import { defineStore } from 'pinia';
import axios from 'axios';

interface AuthState {
    isAuthenticated: boolean;
    user: any | null;
    tokens: {
        idToken: string | null;
        accessToken: string | null;
        refreshToken: string | null;
    };
    loading: boolean;
    error: string | null;
}

const AUTH_TOKENS_KEY = 'wga_auth_tokens';
const AUTH_USER_KEY = 'wga_auth_user';

export const useAuthStore = defineStore('auth', {
    state: (): AuthState => ({
        isAuthenticated: false,
        user: null,
        tokens: {
            idToken: null,
            accessToken: null,
            refreshToken: null,
        },
        loading: false,
        error: null,
    }),

    getters: {
        getUser: (state) => state.user,
        getIsAuthenticated: (state) => state.isAuthenticated,
        getLoading: (state) => state.loading,
        getError: (state) => state.error,
    },

    actions: {
        async initializeAuth() {
            this.loading = true;
            try {
                const savedTokens = localStorage.getItem(AUTH_TOKENS_KEY);
                const savedUser = localStorage.getItem(AUTH_USER_KEY);

                if (savedTokens && savedUser) {
                    this.tokens = JSON.parse(savedTokens);
                    this.user = JSON.parse(savedUser);

                    if (this.tokens.accessToken) {
                        const isValid = await this.validateToken();
                        this.isAuthenticated = isValid;

                        if (!isValid && this.tokens.refreshToken) {
                            await this.refreshTokens();
                        }
                    }
                }
            } catch (error) {
                console.error('인증 초기화 오류:', error);
                this.clearAuth();
            } finally {
                this.loading = false;
            }
        },

        async validateToken() {
            try {
                if (!this.tokens.idToken) return false;

                const payload = this.parseJwt(this.tokens.idToken);
                if (!payload || !payload.exp) return false;

                const now = Math.floor(Date.now() / 1000);
                return payload.exp > now;
            } catch (error) {
                console.error('토큰 검증 오류:', error);
                return false;
            }
        },

        async refreshTokens() {
            try {
                if (!this.tokens.refreshToken) {
                    throw new Error('리프레시 토큰이 없습니다');
                }

                const cognitoDomain = import.meta.env.COGNITO_DOMAIN;
                const clientId = import.meta.env.COGNITO_CLIENT_ID;
                const clientSecret = import.meta.env.COGNITO_CLIENT_SECRET || '';

                const tokenEndpoint = `https://${cognitoDomain}.auth.us-east-1.amazoncognito.com/oauth2/token`;

                const params = new URLSearchParams();
                params.append('grant_type', 'refresh_token');
                params.append('client_id', clientId);
                params.append('refresh_token', this.tokens.refreshToken);

                const headers: Record<string, string> = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                };

                if (clientSecret) {
                    const auth = btoa(`${clientId}:${clientSecret}`);
                    headers['Authorization'] = `Basic ${auth}`;
                }

                const response = await axios.post(tokenEndpoint, params, { headers });

                this.tokens.idToken = response.data.id_token;
                this.tokens.accessToken = response.data.access_token;
                if (response.data.refresh_token) {
                    this.tokens.refreshToken = response.data.refresh_token;
                }

                this.user = this.parseJwt(response.data.id_token);
                this.isAuthenticated = true;

                this.saveAuthToStorage();

                return true;
            } catch (error) {
                console.error('토큰 갱신 오류:', error);
                this.clearAuth();
                return false;
            }
        },

        initiateLogin() {
            this.loading = true;
            this.error = null;

            try {
                const clientId = import.meta.env.COGNITO_CLIENT_ID;
                const redirectUri = import.meta.env.COGNITO_REDIRECT_URI;
                const responseType = 'code';
                const scope = 'openid profile email';

                const cognitoDomain = import.meta.env.COGNITO_DOMAIN;

                if (!cognitoDomain) {
                    throw new Error(
                        'Cognito 도메인이 설정되지 않았습니다. COGNITO_DOMAIN 환경 변수를 확인하세요.',
                    );
                }

                const authUrl = `https://${cognitoDomain}.auth.us-east-1.amazoncognito.com/login?response_type=${responseType}&client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&scope=${encodeURIComponent(scope)}`;

                localStorage.setItem('auth_redirect_path', window.location.pathname);

                window.location.href = authUrl;
            } catch (error: any) {
                this.error = error.message || '로그인 시작 중 오류가 발생했습니다';
                console.error('Login initiation error:', error);
            } finally {
                this.loading = false;
            }
        },

        async exchangeCodeForTokens(authCode: string) {
            this.loading = true;
            this.error = null;

            try {
                const clientId = import.meta.env.COGNITO_CLIENT_ID;
                const redirectUri = import.meta.env.COGNITO_REDIRECT_URI;
                const clientSecret = import.meta.env.COGNITO_CLIENT_SECRET || '';

                const cognitoDomain = import.meta.env.COGNITO_DOMAIN;

                if (!cognitoDomain) {
                    throw new Error(
                        'Cognito 도메인이 설정되지 않았습니다. COGNITO_DOMAIN 환경 변수를 확인하세요.',
                    );
                }

                const tokenEndpoint = `https://${cognitoDomain}.auth.us-east-1.amazoncognito.com/oauth2/token`;

                const headers: Record<string, string> = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                };

                if (clientSecret) {
                    const auth = btoa(`${clientId}:${clientSecret}`);
                    headers['Authorization'] = `Basic ${auth}`;
                }

                const params = new URLSearchParams();
                params.append('grant_type', 'authorization_code');
                params.append('client_id', clientId);
                params.append('code', authCode);
                params.append('redirect_uri', redirectUri);

                const response = await axios.post(tokenEndpoint, params, { headers });

                this.tokens = {
                    idToken: response.data.id_token,
                    accessToken: response.data.access_token,
                    refreshToken: response.data.refresh_token || null,
                };

                this.user = this.parseJwt(response.data.id_token);
                this.isAuthenticated = true;

                this.saveAuthToStorage();

                return true;
            } catch (error: any) {
                this.error = error.message || '인증 코드 교환 중 오류가 발생했습니다';
                console.error('Token exchange error:', error);
                return false;
            } finally {
                this.loading = false;
            }
        },

        saveAuthToStorage() {
            try {
                localStorage.setItem(AUTH_TOKENS_KEY, JSON.stringify(this.tokens));
                localStorage.setItem(AUTH_USER_KEY, JSON.stringify(this.user));
            } catch (error) {
                console.error('인증 정보 저장 오류:', error);
            }
        },

        parseJwt(token: string) {
            try {
                const base64Url = token.split('.')[1];
                const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                const jsonPayload = decodeURIComponent(
                    atob(base64)
                        .split('')
                        .map(function (c) {
                            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
                        })
                        .join(''),
                );

                return JSON.parse(jsonPayload);
            } catch (error) {
                console.error('JWT parsing error:', error);
                return null;
            }
        },

        async logout() {
            try {
                const clientId = import.meta.env.COGNITO_CLIENT_ID;
                const redirectUri = import.meta.env.COGNITO_REDIRECT_URI;

                this.clearAuth();

                const cognitoDomain = import.meta.env.COGNITO_DOMAIN;

                if (!cognitoDomain) {
                    console.error(
                        'Cognito 도메인이 설정되지 않았습니다. 로컬 로그아웃만 수행합니다.',
                    );
                    window.location.href = redirectUri;
                    return;
                }

                const logoutUrl = `https://${cognitoDomain}.auth.us-east-1.amazoncognito.com/logout?client_id=${clientId}&response_type=code&redirect_uri=${encodeURIComponent(redirectUri)}`;
                window.location.href = logoutUrl;
            } catch (error) {
                console.error('로그아웃 중 오류 발생:', error);

                window.location.href = import.meta.env.COGNITO_REDIRECT_URI;
            }
        },

        clearAuth() {
            this.user = null;
            this.tokens = {
                idToken: null,
                accessToken: null,
                refreshToken: null,
            };
            this.isAuthenticated = false;

            localStorage.removeItem(AUTH_TOKENS_KEY);
            localStorage.removeItem(AUTH_USER_KEY);
        },
    },
});
