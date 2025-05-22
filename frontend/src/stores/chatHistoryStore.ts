// src/stores/chatHistoryStore.ts

import { defineStore } from 'pinia';
import type { CancelTokenSource } from 'axios';
import axios from 'axios';
import type { BotResponse, ChatHistoryState, ChatMessageType, ChatSession } from '@/types/chat';

const generateId = () => {
    return Date.now().toString(36) + Math.random().toString(36).substring(2);
};

export const useChatHistoryStore = defineStore('chatHistory', {
    state: (): ChatHistoryState & { apiCancelToken: CancelTokenSource | null } => ({
        loading: false,
        error: null,
        sessions: [],
        currentSession: null,
        waitingForResponse: false,
        apiCancelToken: null,
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
            this.error = null;

            try {
                const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';
                const userId = localStorage.getItem('userId') || generateId();

                if (!localStorage.getItem('userId')) {
                    localStorage.setItem('userId', userId);
                }

                const response = await axios.get(`${apiUrl}/sessions`, {
                    params: { userId: userId },
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    withCredentials: true,
                });

                this.sessions = response.data.sessions || [];

                if (this.sessions.length > 0) {
                    await this.selectSession(this.sessions[0].sessionId);
                }

                return this.sessions;
            } catch (err: any) {
                console.error('채팅 세션 목록 가져오기 오류:', err);
                this.error = err.message || '채팅 세션 목록을 불러오는 중 오류가 발생했습니다.';
                throw err;
            } finally {
                this.loading = false;
            }
        },

        async createNewSession(title = '새 대화') {
            this.loading = true;
            this.error = null;

            try {
                const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';
                const userId = localStorage.getItem('userId') || generateId();

                if (!localStorage.getItem('userId')) {
                    localStorage.setItem('userId', userId);
                }

                const response = await axios.post(
                    `${apiUrl}/sessions`,
                    {
                        userId: userId,
                        title: title,
                    },
                    {
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        withCredentials: true,
                    },
                );

                const newSession: ChatSession = {
                    ...response.data,
                    messages: [],
                };

                this.sessions.unshift(newSession);
                this.currentSession = newSession;

                return newSession;
            } catch (err: any) {
                console.error('새 채팅 세션 생성 오류:', err);
                this.error = err.message || '새 채팅 세션을 생성하는 중 오류가 발생했습니다.';
                throw err;
            } finally {
                this.loading = false;
            }
        },

        async selectSession(sessionId: string) {
            this.loading = true;
            this.error = null;

            try {
                const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';

                const sessionResponse = await axios.get(`${apiUrl}/sessions/${sessionId}`, {
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    withCredentials: true,
                });

                const messagesResponse = await axios.get(
                    `${apiUrl}/sessions/${sessionId}/messages`,
                    {
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        withCredentials: true,
                    },
                );

                const session: ChatSession = {
                    ...sessionResponse.data,
                    messages: messagesResponse.data.messages || [],
                };

                this.currentSession = session;

                const index = this.sessions.findIndex((s) => s.sessionId === sessionId);
                if (index !== -1) {
                    this.sessions[index] = { ...this.sessions[index], ...session };
                }

                return session;
            } catch (err: any) {
                console.error('채팅 세션 선택 오류:', err);
                this.error = err.message || '채팅 세션을 선택하는 중 오류가 발생했습니다.';
                throw err;
            } finally {
                this.loading = false;
            }
        },

        async sendMessage(text: string) {
            if (!text.trim()) return;

            if (!this.currentSession) {
                await this.createNewSession();
            }

            this.waitingForResponse = true;
            let userMessageResponse = null;
            let loadingMessageId = '';

            try {
                const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';
                const sessionId = this.currentSession!.sessionId;

                userMessageResponse = await axios.post(
                    `${apiUrl}/sessions/${sessionId}/messages`,
                    {
                        sender: 'user',
                        text: text,
                    },
                    {
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        withCredentials: true,
                    },
                );

                const userMessage = userMessageResponse.data;
                userMessage.animationState = 'appear';

                if (!this.currentSession!.messages) {
                    this.currentSession!.messages = [];
                }
                this.currentSession!.messages.push(userMessage);

                if (this.currentSession!.messages.length === 1) {
                    const title = text.length > 30 ? text.substring(0, 30) + '...' : text;
                    await this.updateSessionTitle(sessionId, title);
                }

                const loadingMessage: ChatMessageType = {
                    id: generateId(),
                    sender: 'bot',
                    text: '...',
                    timestamp: new Date().toISOString(),
                    isTyping: true,
                };
                loadingMessageId = loadingMessage.id;

                this.currentSession!.messages.push(loadingMessage);

                console.log('API 취소 토큰 생성 중...');
                this.apiCancelToken = axios.CancelToken.source();
                console.log('API 취소 토큰 생성 완료:', !!this.apiCancelToken);

                const botResponseData = await this.generateBotResponse(text);

                if (this.currentSession && Array.isArray(this.currentSession.messages)) {
                    this.currentSession.messages = this.currentSession.messages.filter(
                        (msg) => msg.id !== loadingMessageId,
                    );
                }

                const botMessageResponse = await axios.post(
                    `${apiUrl}/sessions/${sessionId}/messages`,
                    {
                        sender: 'bot',
                        text: botResponseData.text,
                        ...(botResponseData.query_string && {
                            query_string: botResponseData.query_string,
                        }),
                        ...(botResponseData.query_result?.length && {
                            query_result: JSON.stringify(botResponseData.query_result),
                        }),
                        ...(botResponseData.elapsed_time && {
                            elapsed_time: botResponseData.elapsed_time,
                        }),
                        ...(botResponseData.inference && {
                            inference: JSON.stringify(botResponseData.inference),
                        }),
                    },
                    {
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        withCredentials: true,
                    },
                );

                const botMessage = botMessageResponse.data;

                if (botResponseData.query_string) {
                    botMessage.query_string = botResponseData.query_string;
                }
                if (botResponseData.query_result) {
                    botMessage.query_result = botResponseData.query_result;
                }
                if (botResponseData.elapsed_time) {
                    botMessage.elapsed_time = botResponseData.elapsed_time;
                }
                if (botResponseData.inference) {
                    botMessage.inference = botResponseData.inference;
                }

                botMessage.displayText = '';
                botMessage.animationState = 'typing';

                if (this.currentSession && Array.isArray(this.currentSession.messages)) {
                    this.currentSession.messages.push(botMessage);

                    const addedMessage =
                        this.currentSession.messages[this.currentSession.messages.length - 1];
                    addedMessage.displayText = '';
                    addedMessage.animationState = 'typing';

                    this.simulateTypingAnimation(addedMessage.id, botResponseData.text || '');
                }

                const sessionIndex = this.sessions.findIndex((s) => s.sessionId === sessionId);
                if (sessionIndex !== -1) {
                    this.sessions[sessionIndex].updatedAt = new Date().toISOString();

                    this.sessions.sort(
                        (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
                    );
                }

                this.apiCancelToken = null;

                console.log('메시지 전송 완료');
                return botMessage;
            } catch (err: any) {
                console.error('메시지 전송 오류:', err);

                if (axios.isCancel(err)) {
                    console.log('사용자가 요청을 취소했습니다.');

                    if (this.currentSession && Array.isArray(this.currentSession.messages)) {
                        this.currentSession.messages = this.currentSession.messages.filter(
                            (msg) => msg.id !== loadingMessageId,
                        );
                    }

                    const cancelMessage: ChatMessageType = {
                        id: generateId(),
                        sender: 'bot',
                        text: '요청이 취소되었습니다.',
                        timestamp: new Date().toISOString(),
                        animationState: 'appear',
                    };

                    if (this.currentSession && Array.isArray(this.currentSession.messages)) {
                        this.currentSession.messages.push(cancelMessage);
                    }

                    try {
                        const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';
                        const sessionId = this.currentSession!.sessionId;

                        await axios.post(
                            `${apiUrl}/sessions/${sessionId}/messages`,
                            {
                                sender: 'bot',
                                text: cancelMessage.text,
                            },
                            {
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                                withCredentials: true,
                            },
                        );
                        console.log('취소 메시지가 서버에 저장되었습니다.');
                    } catch (saveError) {
                        console.error('취소 메시지 저장 오류:', saveError);
                    }
                } else {
                    const errorMessage: ChatMessageType = {
                        id: generateId(),
                        sender: 'bot',
                        text: '죄송합니다. 응답을 처리하는 중에 오류가 발생했습니다. 다시 시도해 주세요.',
                        timestamp: new Date().toISOString(),
                        animationState: 'appear',
                    };

                    if (this.currentSession && Array.isArray(this.currentSession.messages)) {
                        this.currentSession.messages.push(errorMessage);
                    }

                    try {
                        const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';
                        const sessionId = this.currentSession!.sessionId;

                        await axios.post(
                            `${apiUrl}/sessions/${sessionId}/messages`,
                            {
                                sender: 'bot',
                                text: errorMessage.text,
                            },
                            {
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                                withCredentials: true,
                            },
                        );
                        console.log('오류 메시지가 서버에 저장되었습니다.');
                    } catch (saveError) {
                        console.error('오류 메시지 저장 실패:', saveError);
                    }

                    this.error = err.message || '메시지를 전송하는 중 오류가 발생했습니다.';
                }

                throw err;
            } finally {
                this.waitingForResponse = false;
                this.apiCancelToken = null;
            }
        },

        cancelRequest() {
            console.log('store.cancelRequest 호출됨, apiCancelToken 존재:', !!this.apiCancelToken);
            if (this.apiCancelToken) {
                console.log('API 요청 취소 중...');
                this.apiCancelToken.cancel('사용자가 요청을 취소했습니다.');
                this.apiCancelToken = null;
                this.waitingForResponse = false;
                console.log('API 요청 취소 완료');
            } else {
                console.log('취소할 API 토큰이 없습니다');
            }
        },

        async generateBotResponse(userMessage: string): Promise<BotResponse> {
            try {
                console.log('generateBotResponse 호출, 취소 토큰 존재:', !!this.apiCancelToken);

                const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';

                const response = await axios.post(
                    `${apiUrl}/llm1`,
                    {
                        text: userMessage,
                        sessionId: this.currentSession?.sessionId,
                    },
                    {
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        withCredentials: true,
                        cancelToken: this.apiCancelToken ? this.apiCancelToken.token : undefined,
                    },
                );

                console.log('API 응답 받음:', !!response.data);

                if (response.data) {
                    if (response.data.inference) {
                        return {
                            text: response.data.answer || '쿼리 결과 없음',
                            query_string: response.data.query_string,
                            query_result: response.data.query_result || [],
                            elapsed_time: response.data.elapsed_time,
                            inference: response.data.inference,
                        };
                    } else if (
                        response.data.query_string &&
                        response.data.elapsed_time !== undefined
                    ) {
                        return {
                            text: response.data.answer || '쿼리 결과 없음',
                            query_string: response.data.query_string,
                            query_result: response.data.query_result || [],
                            elapsed_time: response.data.elapsed_time,
                        };
                    } else if (response.data.answer && response.data.elapsed_time !== undefined) {
                        return {
                            text: response.data.answer,
                            elapsed_time: response.data.elapsed_time,
                        };
                    } else if (Array.isArray(response.data.answer)) {
                        const sortedItems = [...response.data.answer].sort(
                            (a, b) => a.rank_order - b.rank_order,
                        );
                        return {
                            text: sortedItems
                                .map((item) => `${item.context}\n${item.title}\n${item.url}`)
                                .join('\n\n'),
                            elapsed_time: response.data.elapsed_time,
                        };
                    } else if (typeof response.data.answer === 'string') {
                        return {
                            text: response.data.answer,
                            elapsed_time: response.data.elapsed_time,
                        };
                    } else {
                        return {
                            text: JSON.stringify(response.data.answer),
                            elapsed_time: response.data.elapsed_time,
                        };
                    }
                }

                return {
                    text: '죄송합니다. 유효한 응답 데이터를 받지 못했습니다.',
                };
            } catch (error) {
                console.log('generateBotResponse 오류:', error);

                if (axios.isCancel(error)) {
                    console.log('API 요청이 취소되었습니다');
                    throw error;
                }
                console.error('봇 응답 API 호출 오류:', error);
                return {
                    text: '죄송합니다. 응답을 처리하는 중에 오류가 발생했습니다. 다시 시도해 주세요.',
                };
            }
        },

        async simulateTypingAnimation(messageId: string, fullText: string) {
            if (!this.currentSession || !Array.isArray(this.currentSession.messages)) return;

            const message = this.currentSession.messages.find((m) => m.id === messageId);
            if (!message) return;

            const typingSpeed = 10;
            const maxTypingTime = 2000;

            const totalTypingTime = Math.min(fullText.length * typingSpeed, maxTypingTime);
            const charInterval = totalTypingTime / fullText.length;

            message.displayText = '';

            for (let i = 0; i < fullText.length; i++) {
                await new Promise((resolve) => setTimeout(resolve, charInterval));

                if (!this.currentSession || !Array.isArray(this.currentSession.messages)) {
                    return;
                }

                const updatedMessage = this.currentSession.messages.find((m) => m.id === messageId);
                if (!updatedMessage) return;

                updatedMessage.displayText = fullText.substring(0, i + 1);
            }

            if (!this.currentSession || !Array.isArray(this.currentSession.messages)) return;

            const completedMessage = this.currentSession.messages.find((m) => m.id === messageId);
            if (completedMessage) {
                completedMessage.animationState = 'complete';
            }
        },

        async updateSessionTitle(sessionId: string, title: string) {
            try {
                const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';

                const response = await axios.put(
                    `${apiUrl}/sessions/${sessionId}`,
                    { title: title },
                    {
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        withCredentials: true,
                    },
                );

                if (this.currentSession && this.currentSession.sessionId === sessionId) {
                    this.currentSession.title = title;
                }

                const sessionIndex = this.sessions.findIndex((s) => s.sessionId === sessionId);
                if (sessionIndex !== -1) {
                    this.sessions[sessionIndex].title = title;
                }

                return response.data;
            } catch (err: any) {
                console.error('세션 제목 업데이트 오류:', err);
                this.error = err.message || '세션 제목을 업데이트하는 중 오류가 발생했습니다.';
                throw err;
            }
        },

        async deleteSession(sessionId: string) {
            try {
                const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';

                await axios.delete(`${apiUrl}/sessions/${sessionId}`, {
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    withCredentials: true,
                });

                this.sessions = this.sessions.filter((s) => s.sessionId !== sessionId);

                if (this.currentSession && this.currentSession.sessionId === sessionId) {
                    if (this.sessions.length > 0) {
                        await this.selectSession(this.sessions[0].sessionId);
                    } else {
                        this.currentSession = null;
                    }
                }

                return true;
            } catch (err: any) {
                console.error('세션 삭제 오류:', err);
                this.error = err.message || '세션을 삭제하는 중 오류가 발생했습니다.';
                throw err;
            }
        },

        async clearMessages() {
            if (!this.currentSession) return;

            try {
                const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';
                const sessionId = this.currentSession.sessionId;

                try {
                    await axios.delete(`${apiUrl}/sessions/${sessionId}/messages`, {
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        withCredentials: true,
                    });
                } catch (error) {
                    console.log('메시지 삭제 API가 없거나 오류 발생, 프론트엔드에서만 처리합니다');
                }

                if (this.currentSession.messages) {
                    this.currentSession.messages = [];
                }

                return true;
            } catch (err: any) {
                console.error('메시지 삭제 오류:', err);
                this.error = err.message || '메시지를 삭제하는 중 오류가 발생했습니다.';
                throw err;
            }
        },

        async deleteAllSessions() {
            try {
                const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';
                const userId = localStorage.getItem('userId') || '';

                if (!userId) {
                    throw new Error('사용자 ID를 찾을 수 없습니다.');
                }

                await axios.delete(`${apiUrl}/sessions`, {
                    params: { userId: userId },
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    withCredentials: true,
                });

                this.sessions = [];
                this.currentSession = null;

                return true;
            } catch (err: any) {
                console.error('전체 세션 삭제 오류:', err);
                this.error = err.message || '전체 세션을 삭제하는 중 오류가 발생했습니다.';
                throw err;
            }
        },

        resetState() {
            this.loading = false;
            this.error = null;
            this.sessions = [];
            this.currentSession = null;
            this.waitingForResponse = false;

            if (this.apiCancelToken) {
                this.apiCancelToken.cancel('상태 초기화로 인한 취소');
                this.apiCancelToken = null;
            }
        },
    },
});
