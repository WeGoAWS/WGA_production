<!-- src/views/LoginPage.vue -->
<template>
    <div class="login-container">
        <h1>AWS 로그인</h1>

        <div v-if="error" class="error-message">
            {{ error }}
        </div>

        <div class="login-form">
            <p class="login-description">
                AWS Cognito를 통해 로그인합니다. 인증 후 토큰이 백엔드로 전송됩니다.
            </p>

            <button @click="handleLogin" class="login-button" :disabled="loading">
                <span class="aws-icon">
                    <svg
                        width="24"
                        height="24"
                        viewBox="0 0 24 24"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                    >
                        <path
                            d="M15.0005 5H9.00049C6.79135 5 5.00049 6.79086 5.00049 9V15C5.00049 17.2091 6.79135 19 9.00049 19H15.0005C17.2096 19 19.0005 17.2091 19.0005 15V9C19.0005 6.79086 17.2096 5 15.0005 5Z"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        />
                        <path
                            d="M12 15C13.6569 15 15 13.6569 15 12C15 10.3431 13.6569 9 12 9C10.3431 9 9 10.3431 9 12C9 13.6569 10.3431 15 12 15Z"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        />
                    </svg>
                </span>
                {{ loading ? '로그인 중...' : 'AWS Cognito로 로그인' }}
            </button>
        </div>
    </div>
</template>

<script lang="ts">
    import { defineComponent, ref } from 'vue';
    import { useAuthStore } from '@/stores/auth';

    export default defineComponent({
        name: 'LoginPage',

        setup() {
            const authStore = useAuthStore();
            const loading = ref(false);
            const error = ref('');

            const handleLogin = () => {
                loading.value = true;
                error.value = '';

                try {
                    // AWS Cognito OAuth 로그인 시작
                    authStore.initiateLogin();
                    // 리다이렉트가 발생하므로 이 아래 코드는 실행되지 않음
                } catch (err: any) {
                    console.error('Login error:', err);
                    error.value = err.message || '로그인 과정에서 오류가 발생했습니다.';
                    loading.value = false;
                }
            };

            return {
                loading,
                error,
                handleLogin,
            };
        },
    });
</script>

<style scoped>
    .login-container {
        max-width: 500px;
        margin: 2rem auto;
        padding: 2rem;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        background-color: #fff;
    }

    h1 {
        text-align: center;
        margin-bottom: 1.5rem;
        color: #333;
    }

    .login-form {
        display: flex;
        flex-direction: column;
        gap: 1.5rem;
    }

    .login-description {
        text-align: center;
        line-height: 1.5;
        color: #555;
    }

    .login-button {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.75rem;
        padding: 0.75rem 1rem;
        background-color: #ff9900;
        color: #232f3e;
        border: none;
        border-radius: 4px;
        font-size: 1rem;
        font-weight: 600;
        cursor: pointer;
        transition: background-color 0.2s;
    }

    .login-button:hover {
        background-color: #ffac33;
    }

    .login-button:disabled {
        background-color: #ccc;
        cursor: not-allowed;
    }

    .aws-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        color: #232f3e;
    }

    .error-message {
        background-color: #fce4e4;
        border: 1px solid #f8b8b8;
        color: #d63301;
        padding: 0.75rem;
        border-radius: 4px;
        margin-bottom: 1rem;
    }
</style>
