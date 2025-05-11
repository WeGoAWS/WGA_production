<!-- src/views/RedirectView.vue -->
<template>
    <div class="redirect-container">
        <div v-if="loading" class="loading-spinner">
            <div class="spinner"></div>
            <p>인증 처리 중입니다...</p>
        </div>

        <div v-if="error" class="error-message">
            <h2>인증 오류</h2>
            <p>{{ error.message }}</p>
            <div v-if="errorDetails" class="error-details">
                <pre>{{ errorDetails }}</pre>
            </div>
            <button @click="goToLogin" class="back-button">로그인 페이지로 돌아가기</button>
        </div>
    </div>
</template>

<script lang="ts">
    import { defineComponent, onMounted, ref } from 'vue';
    import { useRoute, useRouter } from 'vue-router';
    import { useAuthStore } from '@/stores/auth';

    export default defineComponent({
        name: 'RedirectView',

        setup() {
            const router = useRouter();
            const route = useRoute();
            const authStore = useAuthStore();

            const loading = ref(true);
            const error = ref<{ message: string } | null>(null);
            const errorDetails = ref('');

            onMounted(async () => {
                try {
                    // 백엔드에서 인증 처리된 후 일반적으로 쿼리 파라미터 없이 호출됨
                    // 쿼리 파라미터가 있다면 에러일 가능성이 높음 (예: error=access_denied)
                    if (route.query.error) {
                        throw new Error(
                            `인증 오류: ${route.query.error} - ${route.query.error_description || ''}`,
                        );
                    }

                    // 인증 상태 확인
                    const isAuthenticated = await authStore.validateToken();

                    if (isAuthenticated) {
                        // 세션 스토리지에 저장된 리다이렉트 경로가 있는지 확인
                        const redirectPath = localStorage.getItem('auth_redirect_path');
                        if (redirectPath) {
                            // 원래 요청한 페이지로 리다이렉트
                            router.push(redirectPath);
                            // 사용한 경로 정보 삭제
                            localStorage.removeItem('auth_redirect_path');
                        } else {
                            // 기본 리다이렉트
                            router.push('/start-chat');
                        }
                    } else {
                        // 인증되지 않은 경우 로그인 페이지로 리다이렉트
                        router.push('/login');
                    }
                } catch (err: any) {
                    console.error('Redirect handling error:', err);
                    error.value = { message: err.message || '인증 처리 중 오류가 발생했습니다.' };

                    // 에러 세부 정보 저장
                    if (err.response) {
                        errorDetails.value = JSON.stringify(
                            {
                                status: err.response.status,
                                data: err.response.data,
                                headers: err.response.headers,
                            },
                            null,
                            2,
                        );
                    } else if (err.request) {
                        errorDetails.value =
                            '서버로부터 응답이 없습니다. 네트워크 연결을 확인하세요.';
                    } else {
                        errorDetails.value = err.stack || '';
                    }
                } finally {
                    loading.value = false;
                }
            });

            const goToLogin = () => {
                router.push('/login');
            };

            return {
                loading,
                error,
                errorDetails,
                goToLogin,
            };
        },
    });
</script>

<style scoped>
    .redirect-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 60vh;
        padding: 2rem;
    }

    .loading-spinner {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 1rem;
    }

    .spinner {
        width: 50px;
        height: 50px;
        border: 5px solid #f3f3f3;
        border-top: 5px solid #ff9900;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        0% {
            transform: rotate(0deg);
        }
        100% {
            transform: rotate(360deg);
        }
    }

    .error-message {
        max-width: 90%;
        width: 600px;
        background-color: #fce4e4;
        border: 1px solid #f8b8b8;
        color: #d63301;
        padding: 1.5rem;
        border-radius: 8px;
        text-align: center;
    }

    .error-details {
        margin-top: 1rem;
        padding: 1rem;
        background-color: #f8f8f8;
        border-radius: 4px;
        text-align: left;
        overflow-x: auto;
    }

    .error-details pre {
        margin: 0;
        font-size: 0.85rem;
        white-space: pre-wrap;
        color: #333;
    }

    .back-button {
        margin-top: 1rem;
        padding: 0.75rem 1rem;
        background-color: #232f3e;
        color: white;
        border: none;
        border-radius: 4px;
        font-size: 1rem;
        cursor: pointer;
        transition: background-color 0.2s;
    }

    .back-button:hover {
        background-color: #364759;
    }
</style>
