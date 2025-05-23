<!-- src/components/AuthCheck.vue -->
<template>
    <div v-if="loading" class="auth-loading">
        <div class="loading-spinner"></div>
        <p>인증 확인 중...</p>
    </div>
</template>

<script lang="ts">
    import { defineComponent, onMounted, ref } from 'vue';
    import { useRouter } from 'vue-router';

    export default defineComponent({
        name: 'AuthCheck',

        setup() {
            const router = useRouter();
            const loading = ref(true);

            onMounted(async () => {
                try {
                    const redirectPath = sessionStorage.getItem('auth_redirect_path');
                    if (redirectPath) {
                        router.push(redirectPath);
                        sessionStorage.removeItem('auth_redirect_path');
                    } else {
                        router.push('/login');
                    }
                } catch (error) {
                    console.error('Authentication check error:', error);
                    router.push('/login');
                } finally {
                    loading.value = false;
                }
            });

            return {
                loading,
            };
        },
    });
</script>

<style scoped>
    .auth-loading {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100vh;
    }

    .loading-spinner {
        width: 50px;
        height: 50px;
        border: 5px solid #f3f3f3;
        border-top: 5px solid #ff9900;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-bottom: 1rem;
    }

    @keyframes spin {
        0% {
            transform: rotate(0deg);
        }
        100% {
            transform: rotate(360deg);
        }
    }
</style>
