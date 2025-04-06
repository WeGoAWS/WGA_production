// src/router/index.ts
import type { RouteRecordRaw } from 'vue-router';
import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

// 뷰 컴포넌트 가져오기
import LoginPage from '@/views/LoginPage.vue';
import CallbackPage from '@/views/CallbackPage.vue';
import DashboardPage from '@/views/DashboardPage.vue';
import LogAnalysisPage from '@/views/LogAnalysisPage.vue';
import PermissionsPage from '@/views/PermissionsPage.vue';
import ServerAccessPage from '@/views/ServerAccessPage.vue';
import WeeklyReportPage from '@/views/WeeklyReportPage.vue';
import ChatbotPage from '@/views/ChatbotPage.vue';

// 라우트 설정
const routes: Array<RouteRecordRaw> = [
    {
        path: '/',
        redirect: '/dashboard',
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
        path: '/log-analysis',
        name: 'LogAnalysis',
        component: LogAnalysisPage,
        meta: { requiresAuth: true },
    },
    {
        path: '/permissions',
        name: 'Permissions',
        component: PermissionsPage,
        meta: { requiresAuth: true },
    },
    {
        path: '/server-access',
        name: 'ServerAccess',
        component: ServerAccessPage,
        meta: { requiresAuth: true },
    },
    {
        path: '/weekly-report',
        name: 'WeeklyReport',
        component: WeeklyReportPage,
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
        redirect: '/dashboard',
    },
];

// 라우터 인스턴스 생성
const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes,
});

// 네비게이션 가드 설정
router.beforeEach((to, from, next) => {
    const authStore = useAuthStore();
    const requiresAuth = to.matched.some((record) => record.meta.requiresAuth);

    if (requiresAuth && !authStore.isAuthenticated) {
        // 인증이 필요한 페이지인데 인증이 안 되어 있을 때
        next('/login');
    } else if (to.path === '/login' && authStore.isAuthenticated) {
        // 이미 로그인되어 있으면 대시보드로 리다이렉트
        next('/dashboard');
    } else {
        // 그 외의 경우 정상 진행
        next();
    }
});

export default router;
