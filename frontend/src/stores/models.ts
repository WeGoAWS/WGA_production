// src/stores/models.ts
import { defineStore } from 'pinia';
import axios from 'axios';
import type { ModelInfo, ModelsState } from '@/types/models';

export const useModelsStore = defineStore('models', {
    state: (): ModelsState => ({
        models: [],
        loading: false,
        error: null,
        selectedModel: {
            display_name: 'Claude Sonnet 4',
            id: 'claude-sonnet-4-20250514',
        },
    }),

    getters: {
        getModelById:
            (state) =>
            (id: string): ModelInfo | undefined => {
                return state.models.find((model) => model.id === id);
            },
        hasModels: (state) => state.models.length > 0,
        getModelOptions: (state) =>
            state.models.map((model) => ({
                value: model.id,
                label: model.display_name,
            })),
    },

    actions: {
        async fetchModels() {
            this.loading = true;
            this.error = null;

            try {
                const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';

                const response = await axios.get(`${apiUrl}/health`, {
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    withCredentials: true,
                });

                if (response.data && response.data.models) {
                    this.models = response.data.models;

                    this.selectedModel = {
                        id: 'claude-sonnet-4-20250514',
                        display_name: 'Claude Sonnet 4',
                    };
                } else {
                    this.selectedModel = {
                        id: 'claude-sonnet-4-20250514',
                        display_name: 'Claude Sonnet 4',
                    };
                }

                return this.models;
            } catch (error: any) {
                console.error('모델 목록 가져오기 오류:', error);
                this.error = error.message || '모델 목록을 불러오는 중 오류가 발생했습니다.';
                throw error;
            } finally {
                this.loading = false;
            }
        },

        selectModel(modelId: string) {
            const model = this.getModelById(modelId);
            if (model) {
                this.selectedModel = model;
                localStorage.setItem('selectedModelId', modelId);
            }
        },

        loadSelectedModelFromStorage() {
            const savedModelId = localStorage.getItem('selectedModelId');
            if (savedModelId && this.models.length > 0) {
                const model = this.getModelById(savedModelId);
                if (model) {
                    this.selectedModel = model;
                }
            }
        },

        resetState() {
            this.models = [];
            this.loading = false;
            this.error = null;
            this.selectedModel = {
                display_name: 'Claude Sonnet 4',
                id: 'claude-sonnet-4-20250514',
            };
        },
    },
});
