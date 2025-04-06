<template>
    <AppLayout>
        <div class="dashboard-container">
            <header class="dashboard-header">
                <h1>대시보드</h1>
            </header>

            <div class="user-info-card">
                <h2>사용자 정보</h2>
                <div v-if="user" class="user-details">
                    <div class="user-field">
                        <span class="field-label">이메일:</span>
                        <span class="field-value">{{ user.email }}</span>
                    </div>
                    <div class="user-field">
                        <span class="field-label">사용자명:</span>
                        <span class="field-value">{{
                            user.username || user['cognito:username'] || 'N/A'
                        }}</span>
                    </div>
                    <div class="user-field">
                        <span class="field-label">인증 시간:</span>
                        <span class="field-value">{{ formatDate(user.auth_time) }}</span>
                    </div>
                </div>
                <p v-else>사용자 정보를 불러오는 중...</p>
            </div>

            <div class="token-info">
                <h2>토큰 정보</h2>

                <div class="token-card">
                    <h3>ID 토큰</h3>
                    <div class="token-preview">
                        {{ truncateToken(tokens.idToken) }}
                    </div>
                </div>

                <div class="token-card">
                    <h3>액세스 토큰</h3>
                    <div class="token-preview">
                        {{ truncateToken(tokens.accessToken) }}
                    </div>
                </div>

                <div class="token-card">
                    <h3>리프레시 토큰</h3>
                    <div class="token-preview">
                        {{ truncateToken(tokens.refreshToken) }}
                    </div>
                </div>
            </div>
        </div>
    </AppLayout>
</template>

<script lang="ts">
    import { computed, defineComponent, onMounted } from 'vue';
    import { useRouter } from 'vue-router';
    import { useAuthStore } from '@/stores/auth';
    import AppLayout from '@/layouts/AppLayout.vue';

    export default defineComponent({
        name: 'DashboardPage',
        components: {
            AppLayout,
        },

        setup() {
            const router = useRouter();
            const authStore = useAuthStore();

            const user = computed(() => authStore.user);
            const tokens = computed(() => authStore.tokens);

            onMounted(() => {
                // 인증 상태 확인
                if (!authStore.isAuthenticated) {
                    router.push('/login');
                }
            });

            const handleLogout = () => {
                authStore.logout();
            };

            const truncateToken = (token: string | null): string => {
                if (!token) return 'No token available';

                const start = token.substring(0, 15);
                const end = token.substring(token.length - 15);
                return `${start}...${end}`;
            };

            const formatDate = (timestamp: number): string => {
                if (!timestamp) return 'N/A';

                return new Date(timestamp * 1000).toLocaleString();
            };

            return {
                user,
                tokens,
                handleLogout,
                truncateToken,
                formatDate,
            };
        },
    });
</script>

<style scoped>
    .dashboard-container {
        max-width: 1000px;
        margin: 0 auto;
        padding: 2rem;
    }

    .dashboard-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 2rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #eee;
    }

    .logout-button {
        padding: 0.5rem 1rem;
        background-color: #232f3e;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-weight: 500;
        transition: background-color 0.2s;
    }

    .logout-button:hover {
        background-color: #364759;
    }

    .dashboard-container {
        max-width: 1000px;
        margin: 0 auto;
        padding: 2rem;
    }

    .dashboard-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 2rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #eee;
    }

    .logout-button {
        padding: 0.5rem 1rem;
        background-color: #232f3e;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-weight: 500;
        transition: background-color 0.2s;
    }

    .logout-button:hover {
        background-color: #364759;
    }

    .loading-spinner {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 1rem;
        margin: 3rem 0;
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

    .auth-info-card {
        background-color: white;
        border-radius: 8px;
        padding: 1.5rem;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        margin-bottom: 2rem;
    }

    .auth-details {
        margin-top: 1rem;
    }

    .auth-field {
        display: flex;
        margin-bottom: 0.5rem;
    }

    .field-label {
        min-width: 120px;
        font-weight: 600;
        color: #555;
    }

    .field-value {
        color: #333;
    }

    .field-value.success {
        color: #28a745;
        font-weight: 600;
    }

    .resources-section {
        margin-top: 2rem;
    }

    .resources-info {
        margin-bottom: 1.5rem;
        color: #555;
    }

    .resource-cards {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 1.5rem;
    }

    .resource-card {
        background-color: white;
        border-radius: 8px;
        padding: 1.5rem;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        display: flex;
        flex-direction: column;
    }

    .resource-card h3 {
        margin-bottom: 0.5rem;
        color: #333;
    }

    .resource-card p {
        margin-bottom: 1rem;
        color: #666;
        flex-grow: 1;
    }

    .action-button {
        padding: 0.5rem 1rem;
        background-color: #ff9900;
        color: #232f3e;
        border: none;
        border-radius: 4px;
        font-weight: 500;
        cursor: pointer;
        transition: background-color 0.2s;
        align-self: flex-start;
    }

    .action-button:hover {
        background-color: #ffac33;
    }
</style>
