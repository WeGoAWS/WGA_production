<!-- src/layouts/AppLayout.vue -->
<template>
    <div class="app-container">
        <main class="main-content">
            <slot></slot>
        </main>
    </div>
</template>

<script lang="ts">
    import { defineComponent } from 'vue';

    export default defineComponent({
        name: 'AppLayout',
        components: {},
    });
</script>

<style scoped>
    .app-container {
        display: flex;
        min-height: 100vh;
    }

    .main-content {
        flex-grow: 1;
        padding: 20px;
        background-color: #f5f5f5;
        min-height: 100vh;
    }
</style>
