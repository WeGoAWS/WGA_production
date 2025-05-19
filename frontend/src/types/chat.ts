// src/types/chat.ts
import type { CancelTokenSource } from 'axios';

export interface ChatMessageType {
    id: string;
    sender: 'user' | 'bot';
    text: string;
    displayText?: string; // 타이핑 애니메이션을 위한 표시 텍스트
    timestamp: string;
    isTyping?: boolean; // 타이핑 중인지 여부
    animationState?: 'appear' | 'typing' | 'complete'; // 애니메이션 상태
}

export interface ChatSession {
    sessionId: string;
    userId: string;
    title: string;
    createdAt: string;
    updatedAt: string;
    messages: ChatMessageType[]; // 항상 배열로 존재하도록 수정
}

export interface ChatHistoryState {
    loading: boolean;
    error: string | null;
    sessions: ChatSession[];
    currentSession: ChatSession | null;
    waitingForResponse: boolean;
    apiCancelToken?: CancelTokenSource | null; // API 요청 취소를 위한 토큰
}
