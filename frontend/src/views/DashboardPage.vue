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

    @keyframes spin {
        0% {
            transform: rotate(0deg);
        }
        100% {
            transform: rotate(360deg);
        }
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

    .resource-card h3 {
        margin-bottom: 0.5rem;
        color: #333;
    }

    .resource-card p {
        margin-bottom: 1rem;
        color: #666;
        flex-grow: 1;
    }
</style>
