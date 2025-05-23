export interface ModelInfo {
    id: string;
    display_name: string;
}

export interface ModelsState {
    models: ModelInfo[];
    loading: boolean;
    error: string | null;
    selectedModel: ModelInfo;
}
