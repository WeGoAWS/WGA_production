// src/stores/chatbot.ts
import { defineStore } from 'pinia';
import axios from 'axios';
import type { BotResponse, ChatMessageType } from '@/types/chat.ts';

interface ChatMessage {
    id: string;
    sender: 'user' | 'bot';
    text: string;
    displayText?: string;
    timestamp: string;
    isTyping?: boolean;
    animationState?: 'appear' | 'typing' | 'complete';
}

interface ChatSession {
    id: string;
    title: string;
    messages: ChatMessage[];
    createdAt: string;
    updatedAt: string;
}

interface ChatbotState {
    loading: boolean;
    error: string;
    sessions: ChatSession[];
    currentSession: ChatSession | null;
    waitingForResponse: boolean;
}

const generateId = () => {
    return Date.now().toString(36) + Math.random().toString(36).substring(2);
};

export const useChatbotStore = defineStore('chatbot', {
    state: (): ChatbotState => ({
        loading: false,
        error: '',
        sessions: [],
        currentSession: null,
        waitingForResponse: false,
    }),

    getters: {
        hasSessions: (state) => state.sessions.length > 0,

        currentMessages: (state) => {
            return state.currentSession?.messages || [];
        },
    },

    actions: {
        async fetchSessions() {
            this.loading = true;
            this.error = '';

            try {
                await new Promise((resolve) => setTimeout(resolve, 500));

                const now = new Date().toISOString();
                const yesterday = new Date(Date.now() - 86400000).toISOString();

                if (this.sessions.length === 0) {
                    this.sessions = [
                        {
                            id: 'session-1',
                            title: '보안 정책 질문',
                            messages: [
                                {
                                    id: 'msg-1',
                                    sender: 'user',
                                    text: 'AWS S3 버킷 접근 권한 설정은 어떻게 하나요?',
                                    timestamp: yesterday,
                                },
                                {
                                    id: 'msg-2',
                                    sender: 'bot',
                                    text: 'AWS S3 버킷의 접근 권한은 버킷 정책과 IAM 정책을 통해 설정할 수 있습니다. 버킷 정책은 특정 버킷에 대한 접근을 제어하는 JSON 문서입니다. IAM 정책은 사용자, 그룹 또는 역할에 연결되어 AWS 리소스에 대한 접근을 제어합니다.',
                                    timestamp: yesterday,
                                },
                            ],
                            createdAt: yesterday,
                            updatedAt: yesterday,
                        },
                        {
                            id: 'session-2',
                            title: '로그 분석 도구 추천',
                            messages: [
                                {
                                    id: 'msg-3',
                                    sender: 'user',
                                    text: 'AWS 로그 분석에 좋은 도구가 무엇인가요?',
                                    timestamp: now,
                                },
                                {
                                    id: 'msg-4',
                                    sender: 'bot',
                                    text: 'AWS 로그 분석을 위해 여러 도구를 사용할 수 있습니다. AWS 자체 서비스로는 CloudWatch Logs Insights, Amazon Athena, Amazon OpenSearch Service 등이 있습니다. 서드파티 도구로는 Splunk, ELK Stack(Elasticsearch, Logstash, Kibana), Datadog 등이 인기가 있습니다.',
                                    timestamp: now,
                                },
                            ],
                            createdAt: now,
                            updatedAt: now,
                        },
                    ];
                }
            } catch (err: any) {
                console.error('채팅 세션 목록 가져오기 오류:', err);
                this.error = err.message || '채팅 세션 목록을 불러오는 중 오류가 발생했습니다.';
            } finally {
                this.loading = false;
            }
        },

        createNewSession() {
            const now = new Date().toISOString();
            const newSession: ChatSession = {
                id: generateId(),
                title: '새 대화',
                messages: [],
                createdAt: now,
                updatedAt: now,
            };

            this.sessions.unshift(newSession);
            this.currentSession = newSession;

            return newSession;
        },

        selectSession(sessionId: string) {
            const session = this.sessions.find((s) => s.id === sessionId);
            if (session) {
                this.currentSession = session;
            }
        },

        async sendMessage(text: string) {
            if (!text.trim()) return;

            if (!this.currentSession) {
                this.createNewSession();
            }

            const now = new Date().toISOString();

            const userMessage: ChatMessage = {
                id: generateId(),
                sender: 'user',
                text: text,
                timestamp: now,
                animationState: 'appear',
            };

            this.currentSession!.messages.push(userMessage);
            this.currentSession!.updatedAt = now;

            if (this.currentSession!.messages.length === 1) {
                this.currentSession!.title =
                    text.length > 30 ? text.substring(0, 30) + '...' : text;
            }

            this.waitingForResponse = true;

            try {
                const loadingMessage: ChatMessage = {
                    id: generateId(),
                    sender: 'bot',
                    text: '...',
                    timestamp: new Date().toISOString(),
                    isTyping: true,
                };

                this.currentSession!.messages.push(loadingMessage);

                const botResponseText = await this.generateBotResponse(text);

                this.currentSession!.messages = this.currentSession!.messages.filter(
                    (msg) => msg.id !== loadingMessage.id,
                );

                const botMessage: ChatMessageType = {
                    id: generateId(),
                    sender: 'bot',
                    text: botResponseText,
                    displayText: '',
                    timestamp: new Date().toISOString(),
                    animationState: 'typing',
                };

                this.currentSession!.messages.push(botMessage);
                this.currentSession!.updatedAt = botMessage.timestamp;

                await this.simulateTyping(botMessage.id, botResponseText);
            } catch (err: any) {
                console.error('봇 응답 가져오기 오류:', err);

                const errorMessage: ChatMessage = {
                    id: generateId(),
                    sender: 'bot',
                    text: '죄송합니다. 응답을 처리하는 중에 오류가 발생했습니다. 다시 시도해 주세요.',
                    timestamp: new Date().toISOString(),
                    animationState: 'appear',
                };

                this.currentSession!.messages.push(errorMessage);
                this.currentSession!.updatedAt = errorMessage.timestamp;
            } finally {
                this.waitingForResponse = false;
            }
        },

        async simulateTyping(messageId: string, fullText: string) {
            if (!this.currentSession) return;

            const message = this.currentSession.messages.find((m) => m.id === messageId);
            if (!message) return;

            const typingSpeed = 10;
            const maxTypingTime = 2000;

            const totalTypingTime = Math.min(fullText.length * typingSpeed, maxTypingTime);
            const charInterval = totalTypingTime / fullText.length;

            message.displayText = '';

            for (let i = 0; i < fullText.length; i++) {
                await new Promise((resolve) => setTimeout(resolve, charInterval));

                const updatedMessage = this.currentSession?.messages.find(
                    (m) => m.id === messageId,
                );
                if (!updatedMessage) return;

                updatedMessage.displayText = fullText.substring(0, i + 1);
            }

            const completedMessage = this.currentSession.messages.find((m) => m.id === messageId);
            if (completedMessage) {
                completedMessage.animationState = 'complete';
            }
        },

        async generateBotResponse(userMessage: string): Promise<BotResponse | any> {
            try {
                const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';

                const response = await axios.post(
                    `${apiUrl}/llm1`,
                    {
                        text: userMessage,
                        sessionId: this.currentSession?.id,
                    },
                    {
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        withCredentials: true,
                    },
                );

                if (response.data) {
                    if (Array.isArray(response.data.answer)) {
                        const sortedItems = [...response.data.answer].sort(
                            (a, b) => a.rank_order - b.rank_order,
                        );

                        return sortedItems
                            .map((item) => `${item.context}\n${item.title}\n${item.url}`)
                            .join('\n\n');
                    } else if (typeof response.data.answer === 'string') {
                        return response.data.answer;
                    } else {
                        return JSON.stringify(response.data.answer);
                    }
                }

                return '죄송합니다. 유효한 응답 데이터를 받지 못했습니다.';
            } catch (error) {
                console.error('봇 응답 API 호출 오류:', error);

                return '죄송합니다. 응답을 처리하는 중에 오류가 발생했습니다. 다시 시도해 주세요.';
            }
        },

        deleteSession(sessionId: string) {
            this.sessions = this.sessions.filter((s) => s.id !== sessionId);

            if (this.currentSession && this.currentSession.id === sessionId) {
                this.currentSession = this.sessions.length > 0 ? this.sessions[0] : null;
            }
        },

        clearMessages() {
            if (this.currentSession) {
                this.currentSession.messages = [];
                this.currentSession.updatedAt = new Date().toISOString();
            }
        },

        resetState() {
            this.loading = false;
            this.error = '';
            this.sessions = [];
            this.currentSession = null;
            this.waitingForResponse = false;
        },
    },
});
