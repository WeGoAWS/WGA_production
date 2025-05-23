// src/stores/settings.ts
import { defineStore } from 'pinia';

interface SettingsState {
    isCached: boolean;
}

export const useSettingsStore = defineStore('settings', {
    state: (): SettingsState => ({
        isCached: true,
    }),

    getters: {
        getIsCached: (state) => state.isCached,
    },

    actions: {
        setIsCached(value: boolean) {
            this.isCached = value;
            localStorage.setItem('isCached', JSON.stringify(value));
        },

        loadFromStorage() {
            const saved = localStorage.getItem('isCached');
            if (saved !== null) {
                this.isCached = JSON.parse(saved);
            }
        },

        resetSettings() {
            this.isCached = true;
            localStorage.removeItem('isCached');
        },
    },
});
