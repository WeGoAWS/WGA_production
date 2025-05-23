<!-- src/App.vue -->
<template>
    <div id="app">
        <router-view v-if="!initialLoading"></router-view>
        <div v-else class="initial-loading">
            <div class="spinner"></div>
            <p>불러오는 중...</p>
        </div>
    </div>
</template>

<script lang="ts">
    import { defineComponent, onMounted, ref } from 'vue';
    import { useAuthStore } from '@/stores/auth';
    import { useModelsStore } from '@/stores/models';
    import { useSettingsStore } from '@/stores/settings.ts';

    export default defineComponent({
        name: 'App',
        setup() {
            const authStore = useAuthStore();
            const modelsStore = useModelsStore();
            const settingsStore = useSettingsStore();
            const initialLoading = ref(true);

            onMounted(async () => {
                try {
                    await authStore.initializeAuth();
                    settingsStore.loadFromStorage();

                    try {
                        await modelsStore.fetchModels();
                        modelsStore.loadSelectedModelFromStorage();
                    } catch (modelError) {
                        console.error('모델 목록 로드 오류:', modelError);
                    }
                } catch (error) {
                    console.error('앱 초기화 오류:', error);
                } finally {
                    initialLoading.value = false;
                }
            });

            return {
                initialLoading,
            };
        },
    });
</script>

<style>
    body {
        margin: 0;
        padding: 0;
        font-family:
            -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell,
            'Open Sans', 'Helvetica Neue', sans-serif;
        background-color: #f5f5f5;
        color: #333;
    }

    * {
        box-sizing: border-box;
    }

    h1,
    h2,
    h3,
    h4,
    h5,
    h6 {
        margin-top: 0;
    }

    #app {
        min-height: 100vh;
    }

    .initial-loading {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100vh;
    }

    .spinner {
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
