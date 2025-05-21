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

// 로컬 스토리지 키 정의
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
        // 스토어 초기화 - 앱 시작 시 호출
        async initializeAuth() {
            this.loading = true;
            try {
                const savedTokens = localStorage.getItem(AUTH_TOKENS_KEY);
                const savedUser = localStorage.getItem(AUTH_USER_KEY);

                if (savedTokens && savedUser) {
                    this.tokens = JSON.parse(savedTokens);
                    this.user = JSON.parse(savedUser);

                    // 토큰 유효성 검증
                    if (this.tokens.accessToken) {
                        const isValid = await this.validateToken();
                        this.isAuthenticated = isValid;

                        // 토큰이 만료되었지만 리프레시 토큰이 있는 경우
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

        // 토큰 유효성 검증 함수
        async validateToken() {
            try {
                // 간단한 토큰 유효성 검사 (만료 시간 확인)
                if (!this.tokens.idToken) return false;

                const payload = this.parseJwt(this.tokens.idToken);
                if (!payload || !payload.exp) return false;

                // 토큰 만료 시간 확인 (현재 시간과 비교)
                const now = Math.floor(Date.now() / 1000);
                return payload.exp > now;
            } catch (error) {
                console.error('토큰 검증 오류:', error);
                return false;
            }
        },

        // 리프레시 토큰을 사용하여 새 토큰 획득
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

                // 새 토큰 저장
                this.tokens.idToken = response.data.id_token;
                this.tokens.accessToken = response.data.access_token;
                // 리프레시 토큰은 새로 받지 않을 수 있음
                if (response.data.refresh_token) {
                    this.tokens.refreshToken = response.data.refresh_token;
                }

                // 사용자 정보 업데이트
                this.user = this.parseJwt(response.data.id_token);
                this.isAuthenticated = true;

                // 로컬 스토리지 업데이트
                this.saveAuthToStorage();

                return true;
            } catch (error) {
                console.error('토큰 갱신 오류:', error);
                this.clearAuth();
                return false;
            }
        },

        // AWS Cognito로 직접 OAuth 로그인 시작
        initiateLogin() {
            this.loading = true;
            this.error = null;

            try {
                const clientId = import.meta.env.COGNITO_CLIENT_ID;
                const redirectUri = import.meta.env.COGNITO_REDIRECT_URI;
                const responseType = 'code';
                const scope = 'openid profile email';

                // Cognito OAuth 로그인 URL 구성
                // 중요: AWS 호스팅 UI 도메인을 사용
                const cognitoDomain = import.meta.env.COGNITO_DOMAIN;

                if (!cognitoDomain) {
                    throw new Error(
                        'Cognito 도메인이 설정되지 않았습니다. COGNITO_DOMAIN 환경 변수를 확인하세요.',
                    );
                }

                // AWS Cognito 호스팅 UI URL 형식 사용
                const authUrl = `https://${cognitoDomain}.auth.us-east-1.amazoncognito.com/login?response_type=${responseType}&client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&scope=${encodeURIComponent(scope)}`;

                // 리다이렉트 전 현재 경로 저장 (로그인 후 돌아오기 위함)
                localStorage.setItem('auth_redirect_path', window.location.pathname);

                // Cognito 로그인 페이지로 리다이렉트
                window.location.href = authUrl;
            } catch (error: any) {
                this.error = error.message || '로그인 시작 중 오류가 발생했습니다';
                console.error('Login initiation error:', error);
            } finally {
                this.loading = false;
            }
        },

        // Cognito에서 받은 인증 코드를 토큰으로 교환
        async exchangeCodeForTokens(authCode: string) {
            this.loading = true;
            this.error = null;

            try {
                const clientId = import.meta.env.COGNITO_CLIENT_ID;
                const redirectUri = import.meta.env.COGNITO_REDIRECT_URI;
                const clientSecret = import.meta.env.COGNITO_CLIENT_SECRET || '';

                // 토큰 엔드포인트 URL 구성
                const cognitoDomain = import.meta.env.COGNITO_DOMAIN;

                if (!cognitoDomain) {
                    throw new Error(
                        'Cognito 도메인이 설정되지 않았습니다. COGNITO_DOMAIN 환경 변수를 확인하세요.',
                    );
                }

                // AWS Cognito 호스팅 UI 토큰 엔드포인트
                const tokenEndpoint = `https://${cognitoDomain}.auth.us-east-1.amazoncognito.com/oauth2/token`;

                // 토큰 교환 요청
                const headers: Record<string, string> = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                };

                // 클라이언트 인증 정보
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

                // 토큰 정보 저장
                this.tokens = {
                    idToken: response.data.id_token,
                    accessToken: response.data.access_token,
                    refreshToken: response.data.refresh_token || null,
                };

                // JWT 파싱하여 사용자 정보 추출
                this.user = this.parseJwt(response.data.id_token);
                this.isAuthenticated = true;

                // 로컬 스토리지에 인증 정보 저장
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

        // 로컬 스토리지에 인증 정보 저장
        saveAuthToStorage() {
            try {
                localStorage.setItem(AUTH_TOKENS_KEY, JSON.stringify(this.tokens));
                localStorage.setItem(AUTH_USER_KEY, JSON.stringify(this.user));
            } catch (error) {
                console.error('인증 정보 저장 오류:', error);
            }
        },

        // JWT 토큰 디코딩 함수
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

        // 로그아웃
        async logout() {
            try {
                const clientId = import.meta.env.COGNITO_CLIENT_ID;
                const redirectUri = import.meta.env.COGNITO_REDIRECT_URI;

                // 로그아웃 전에 로컬 스토리지 비우기
                this.clearAuth();

                // Cognito 로그아웃 URL 구성
                const cognitoDomain = import.meta.env.COGNITO_DOMAIN;

                if (!cognitoDomain) {
                    console.error(
                        'Cognito 도메인이 설정되지 않았습니다. 로컬 로그아웃만 수행합니다.',
                    );
                    window.location.href = redirectUri;
                    return;
                }

                // AWS Cognito 호스팅 UI 로그아웃 URL
                const logoutUrl = `https://${cognitoDomain}.auth.us-east-1.amazoncognito.com/logout?client_id=${clientId}&response_type=code&redirect_uri=${encodeURIComponent(redirectUri)}`;
                // 로그아웃 리다이렉트
                window.location.href = logoutUrl;
            } catch (error) {
                console.error('로그아웃 중 오류 발생:', error);

                // 오류 발생해도 리다이렉트 시도
                window.location.href = import.meta.env.COGNITO_REDIRECT_URI;
            }
        },

        // 인증 정보 초기화
        clearAuth() {
            // 상태 초기화
            this.user = null;
            this.tokens = {
                idToken: null,
                accessToken: null,
                refreshToken: null,
            };
            this.isAuthenticated = false;

            // 로컬 스토리지 정리
            localStorage.removeItem(AUTH_TOKENS_KEY);
            localStorage.removeItem(AUTH_USER_KEY);
        },
    },
});
