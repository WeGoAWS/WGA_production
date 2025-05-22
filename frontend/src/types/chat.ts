// src/types/chat.ts
export interface ChatMessageType {
    id: string;
    sender: 'user' | 'assistant';
    text: string;
    displayText?: string;
    timestamp: string;
    isTyping?: boolean;
    animationState?: 'appear' | 'typing' | 'complete';
    query_string?: string;
    query_result?: any[];
    elapsed_time?: string | number;
    inference?: any;
}

export interface ChatSession {
    sessionId: string;
    userId: string;
    title: string;
    createdAt: string;
    updatedAt: string;
    messages: ChatMessageType[];
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
    inference?: any;
}
