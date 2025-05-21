// src/router/index.ts
import type { RouteRecordRaw } from 'vue-router';
import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

import LoginPage from '@/views/LoginPage.vue';
import CallbackPage from '@/views/CallbackPage.vue';
import DashboardPage from '@/views/DashboardPage.vue';
import StartChatPage from '@/views/StartChatPage.vue';
import EnhancedChatbotPage from '@/views/EnhancedChatbotPage.vue';

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
        path: '/chat',
        name: 'EnhancedChat',
        component: EnhancedChatbotPage,
        meta: { requiresAuth: true },
    },
    {
        path: '/:pathMatch(.*)*',
        redirect: '/start-chat',
    },
];

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes,
});

router.beforeEach((to, from, next) => {
    const authStore = useAuthStore();
    const requiresAuth = to.matched.some((record) => record.meta.requiresAuth);

    if (requiresAuth && !authStore.isAuthenticated) {
        sessionStorage.setItem('auth_redirect_path', to.fullPath);
        next('/login');
    } else if (to.path === '/login' && authStore.isAuthenticated) {
        next('/start-chat');
    } else {
        next();
    }
});

export default router;
