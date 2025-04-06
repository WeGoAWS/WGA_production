<!-- src/components/SidebarNav.vue -->
<template>
    <nav class="sidebar">
        <div class="sidebar-header">
            <h1 class="logo">We Go AWS</h1>
        </div>

        <ul class="nav-menu">
            <li v-for="(item, index) in navItems" :key="index" class="nav-item">
                <router-link
                    :to="item.path"
                    class="nav-link"
                    :class="{ active: currentPath === item.path }"
                >
                    <span class="nav-icon" v-html="item.icon"></span>
                    <span class="nav-text">{{ item.title }}</span>
                </router-link>
            </li>
        </ul>

        <div class="sidebar-footer">
            <button @click="handleLogout" class="logout-button">
                <span class="logout-icon">
                    <svg
                        width="20"
                        height="20"
                        viewBox="0 0 24 24"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                    >
                        <path
                            d="M9 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H9"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        />
                        <path
                            d="M16 17L21 12L16 7"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        />
                        <path
                            d="M21 12H9"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        />
                    </svg>
                </span>
                <span>로그아웃</span>
            </button>
        </div>
    </nav>
</template>

<script lang="ts">
    import { computed, defineComponent, ref } from 'vue';
    import { useRoute, useRouter } from 'vue-router';
    import { useAuthStore } from '@/stores/auth';

    export default defineComponent({
        name: 'SidebarNav',

        setup() {
            const router = useRouter();
            const route = useRoute();
            const authStore = useAuthStore();

            // 현재 경로 계산
            const currentPath = computed(() => route.path);

            // 아이콘 SVG 문자열
            const icons = {
                logAnalysis: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M21 21H3V3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M21 6L12 15L9 12L3 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`,
                permission: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M19 11H5C3.89543 11 3 11.8954 3 13V20C3 21.1046 3.89543 22 5 22H19C20.1046 22 21 21.1046 21 20V13C21 11.8954 20.1046 11 19 11Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M7 11V7C7 5.67392 7.52678 4.40215 8.46447 3.46447C9.40215 2.52678 10.6739 2 12 2C13.3261 2 14.5979 2.52678 15.5355 3.46447C16.4732 4.40215 17 5.67392 17 7V11" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M12 16.5C12.8284 16.5 13.5 15.8284 13.5 15C13.5 14.1716 12.8284 13.5 12 13.5C11.1716 13.5 10.5 14.1716 10.5 15C10.5 15.8284 11.1716 16.5 12 16.5Z" fill="currentColor"/>
      </svg>`,
                serverAccess: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M5 12H19" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M5 5H19" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M5 19H19" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`,
                report: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M14 2V8H20" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M16 13H8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M16 17H8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M10 9H9H8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`,
                chatbot: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M21 15C21 15.5304 20.7893 16.0391 20.4142 16.4142C20.0391 16.7893 19.5304 17 19 17H7L3 21V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H19C19.5304 3 20.0391 3.21071 20.4142 3.58579C20.7893 3.96086 21 4.46957 21 5V15Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`,
            };

            // 네비게이션 아이템 정의
            const navItems = ref([
                {
                    title: '로그분석',
                    path: '/log-analysis',
                    icon: icons.logAnalysis,
                },
                {
                    title: '권한',
                    path: '/permissions',
                    icon: icons.permission,
                },
                {
                    title: '서버 접근 현황',
                    path: '/server-access',
                    icon: icons.serverAccess,
                },
                {
                    title: '주간 레포트',
                    path: '/weekly-report',
                    icon: icons.report,
                },
                {
                    title: '챗봇',
                    path: '/chatbot',
                    icon: icons.chatbot,
                },
            ]);

            // 로그아웃 핸들러
            const handleLogout = () => {
                authStore.logout();
                // 로그아웃 후 로그인 페이지로 리다이렉트는 auth 스토어에서 처리
            };

            return {
                navItems,
                currentPath,
                handleLogout,
            };
        },
    });
</script>

<style scoped>
    .sidebar {
        width: 20vw;
        height: 100vh;
        background-color: #232f3e;
        color: #fff;
        display: flex;
        flex-direction: column;
        position: fixed;
        left: 0;
        top: 0;
        box-shadow: 2px 0 5px rgba(0, 0, 0, 0.1);
    }

    .sidebar-header {
        padding: 20px;
        border-bottom: 1px solid #394b61;
    }

    .logo {
        font-size: 1.5rem;
        margin: 0;
        color: #ff9900;
    }

    .nav-menu {
        list-style: none;
        padding: 0;
        margin: 0;
        flex-grow: 1;
        overflow-y: auto;
    }

    .nav-item {
        margin: 0;
        padding: 0;
    }

    .nav-link {
        display: flex;
        align-items: center;
        padding: 15px 20px;
        color: #e1e1e1;
        text-decoration: none;
        transition:
            background-color 0.2s,
            color 0.2s;
    }

    .nav-link:hover {
        background-color: #394b61;
        color: #ffffff;
    }

    .nav-link.active {
        background-color: #394b61;
        color: #ff9900;
        border-left: 4px solid #ff9900;
    }

    .nav-icon {
        margin-right: 12px;
        display: flex;
        align-items: center;
    }

    .sidebar-footer {
        padding: 15px 20px;
        border-top: 1px solid #394b61;
    }

    .logout-button {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        padding: 10px;
        background-color: transparent;
        border: 1px solid #e1e1e1;
        border-radius: 4px;
        color: #e1e1e1;
        cursor: pointer;
        transition:
            background-color 0.2s,
            color 0.2s;
    }

    .logout-button:hover {
        background-color: #394b61;
        color: #ffffff;
    }

    .logout-icon {
        display: flex;
        align-items: center;
        margin-right: 8px;
    }
</style>
