<!-- src/views/CallbackPage.vue -->
<template>
    <div class="callback-container">
        <div v-if="loading" class="loading-spinner">
            <div class="spinner"></div>
            <p>인증 처리 중입니다...</p>
        </div>

        <div v-if="error" class="error-message">
            <h2>인증 오류</h2>
            <p>{{ error }}</p>
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
        name: 'CallbackPage',

        setup() {
            const router = useRouter();
            const route = useRoute();
            const authStore = useAuthStore();

            const loading = ref(true);
            const error = ref('');
            const errorDetails = ref('');

            onMounted(async () => {
                try {
                    const code = route.query.code as string;

                    if (!code) {
                        throw new Error('인증 코드가 없습니다. URL 쿼리 파라미터를 확인하세요.');
                    }

                    const success = await authStore.exchangeCodeForTokens(code);

                    if (success) {
                        const redirectPath =
                            localStorage.getItem('auth_redirect_path') || '/start-chat';

                        localStorage.removeItem('auth_redirect_path');

                        router.push(redirectPath);
                    } else {
                        throw new Error('토큰 교환 과정에서 오류가 발생했습니다.');
                    }
                } catch (err: any) {
                    console.error('Callback handling error:', err);
                    error.value = err.message || '인증 과정에서 오류가 발생했습니다.';

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
    .callback-container {
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
