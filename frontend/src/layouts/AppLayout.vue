<!-- src/layouts/AppLayout.vue -->
<template>
    <div class="app-container">
        <SidebarNav />
        <main class="main-content">
            <slot></slot>
        </main>
    </div>
</template>

<script lang="ts">
    import { defineComponent } from 'vue';
    import SidebarNav from '@/components/SidebarNav.vue';

    export default defineComponent({
        name: 'AppLayout',
        components: {
            SidebarNav,
        },
    });
</script>

<style scoped>
    .app-container {
        display: flex;
        min-height: 100vh;
    }

    .main-content {
        flex-grow: 1;
        margin-left: 20vw;
        padding: 20px;
        background-color: #f5f5f5;
        min-height: 100vh;
    }
</style>
