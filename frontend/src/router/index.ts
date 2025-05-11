// src/router/index.ts
import type { RouteRecordRaw } from 'vue-router';
import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

// 뷰 컴포넌트 가져오기
import LoginPage from '@/views/LoginPage.vue';
import CallbackPage from '@/views/CallbackPage.vue';
import DashboardPage from '@/views/DashboardPage.vue';
import ChatbotPage from '@/views/ChatbotPage.vue';
import StartChatPage from '@/views/StartChatPage.vue';

// 라우트 설정
const routes: Array<RouteRecordRaw> = [
    {
        path: '/',
        redirect: '/start-chat',
    },
    {
        path: '/login',
        name: 'Login',
        component: LoginPage,
        meta: { requiresAuth: false },
    },
    {
        path: '/redirect',
        name: 'Redirect',
        component: CallbackPage,
        meta: { requiresAuth: false },
    },
    {
        path: '/dashboard',
        name: 'Dashboard',
        component: DashboardPage,
        meta: { requiresAuth: true },
    },
    {
        path: '/start-chat',
        name: 'StartChat',
        component: StartChatPage,
        meta: { requiresAuth: true },
    },
    {
        path: '/chatbot',
        name: 'Chatbot',
        component: ChatbotPage,
        meta: { requiresAuth: true },
    },
    // 페이지를 찾을 수 없을 때
    {
        path: '/:pathMatch(.*)*',
        redirect: '/start-chat',
    },
];

// 라우터 인스턴스 생성
const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes,
});

// 인증 초기화 상태를 추적하는 변수
let isAuthInitialized = false;

// 네비게이션 가드 설정
router.beforeEach(async (to, from, next) => {
    const authStore = useAuthStore();

    // 앱 실행 시 딱 한 번만 인증 초기화 실행
    if (!isAuthInitialized) {
        await authStore.initializeAuth();
        isAuthInitialized = true;
    }

    const requiresAuth = to.matched.some((record) => record.meta.requiresAuth);

    // 로딩 중에는 잠시 대기 (초기화 중 깜빡임 방지)
    if (authStore.loading) {
        // 인증 상태 로딩이 완료될 때까지 잠시 대기
        // 실제 구현에서는 로딩 컴포넌트나 스플래시 스크린 표시 등을 고려할 수 있음
        await new Promise((resolve) => {
            const checkLoading = () => {
                if (!authStore.loading) {
                    resolve(true);
                } else {
                    setTimeout(checkLoading, 100);
                }
            };
            checkLoading();
        });
    }

    // 인증이 필요한 페이지 접근 시 로그인 체크
    if (requiresAuth && !authStore.isAuthenticated) {
        // 인증이 필요한 페이지에 접근하려고 했다는 정보 저장
        localStorage.setItem('auth_redirect_path', to.fullPath);

        // 로그인 페이지로 리다이렉트
        next('/login');
    } else if (to.path === '/login' && authStore.isAuthenticated) {
        // 이미 로그인되어 있는데 로그인 페이지로 가려고 하면 대시보드로 리다이렉트
        next('/start-chat');
    } else {
        // 그 외의 경우 정상 진행
        next();
    }
});

export default router;
