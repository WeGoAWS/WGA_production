// src/types/chat.ts
export interface ChatMessageType {
    id: string;
    sender: 'user' | 'bot';
    text: string | any;
    displayText?: string;
    timestamp: string;
    isTyping?: boolean;
    animationState?: 'appear' | 'typing' | 'complete';
    query_string?: string;
    query_result?: any[];
    elapsed_time?: string | number;
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

// 봇 응답 타입 정의 추가
export interface BotResponse {
    text: string | any;
    query_string?: string;
    query_result?: any[];
    elapsed_time?: string | number;
}
