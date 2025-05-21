// src/types/chat.ts
export interface ChatMessageType {
    id: string;
    sender: 'user' | 'bot';
    text: string;
    displayText?: string;
    timestamp: string;
    isTyping?: boolean;
    animationState?: 'appear' | 'typing' | 'complete';
    query_string?: string;
    query_result?: any[];
    elapsed_time?: string | number;
    inference?: any; // 추가된 inference 필드
}

export interface ChatSession {
    sessionId: string;
    title: string;
    messages: ChatMessageType[];
    createdAt: string;
    updatedAt: string;
}

export interface ChatHistoryState {
    loading: boolean;
    error: string | null;
    sessions: ChatSession[];
    currentSession: ChatSession | null;
    waitingForResponse: boolean;
}

export interface BotResponse {
    text: string;
    query_string?: string;
    query_result?: any[];
    elapsed_time?: string | number;
    inference?: any; // 추가된 inference 필드
}
