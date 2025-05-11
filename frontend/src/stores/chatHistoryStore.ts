// src/stores/chatHistoryStore.ts
import { defineStore } from 'pinia';
import axios from 'axios';

interface ChatMessage {
    id: string;
    sender: 'user' | 'bot';
    text: string;
    displayText?: string; // 타이핑 애니메이션을 위한 표시 텍스트
    timestamp: string;
    isTyping?: boolean; // 타이핑 중인지 여부
    animationState?: 'appear' | 'typing' | 'complete'; // 애니메이션 상태
}

interface ChatSession {
    sessionId: string;
    userId: string;
    title: string;
    createdAt: string;
    updatedAt: string;
    messages?: ChatMessage[];
}

interface ChatHistoryState {
    loading: boolean;
    error: string | null;
    sessions: ChatSession[];
    currentSession: ChatSession | null;
    waitingForResponse: boolean;
}

// 유니크 ID 생성 함수
const generateId = () => {
    return Date.now().toString(36) + Math.random().toString(36).substring(2);
};

export const useChatHistoryStore = defineStore('chatHistory', {
    state: (): ChatHistoryState => ({
        loading: false,
        error: null,
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
        // 채팅 세션 목록 불러오기
        async fetchSessions() {
            this.loading = true;
            this.error = null;

            try {
                const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
                const userId = localStorage.getItem('userId') || generateId();

                // 로컬 스토리지에 사용자 ID 저장 (영구적인 식별을 위해)
                if (!localStorage.getItem('userId')) {
                    localStorage.setItem('userId', userId);
                }

                // API 호출하여 세션 목록 가져오기
                const response = await axios.get(`${apiUrl}/sessions`, {
                    params: { userId: userId },
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    withCredentials: true, // 쿠키 및 인증 정보 포함
                });

                this.sessions = response.data.sessions || [];

                // 세션이 있을 경우 가장 최신 세션을 현재 세션으로 설정
                if (this.sessions.length > 0) {
                    await this.selectSession(this.sessions[0].sessionId);
                }
            } catch (err: any) {
                console.error('채팅 세션 목록 가져오기 오류:', err);
                this.error = err.message || '채팅 세션 목록을 불러오는 중 오류가 발생했습니다.';
            } finally {
                this.loading = false;
            }
        },

        // 새 채팅 세션 생성
        async createNewSession(title = '새 대화') {
            this.loading = true;
            this.error = null;

            try {
                const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
                const userId = localStorage.getItem('userId') || generateId();

                if (!localStorage.getItem('userId')) {
                    localStorage.setItem('userId', userId);
                }

                // API 호출하여 새 세션 생성
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

                const newSession = response.data;
                newSession.messages = []; // 메시지 배열 초기화

                // 새 세션을 목록 맨 앞에 추가
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

        // 채팅 세션 선택
        async selectSession(sessionId: string) {
            this.loading = true;
            this.error = null;

            try {
                const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

                // 세션 정보 가져오기
                const sessionResponse = await axios.get(`${apiUrl}/sessions/${sessionId}`, {
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    withCredentials: true,
                });

                // 세션의 메시지 가져오기
                const messagesResponse = await axios.get(
                    `${apiUrl}/sessions/${sessionId}/messages`,
                    {
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        withCredentials: true,
                    },
                );

                // 세션 정보와 메시지 합치기
                const session = sessionResponse.data;
                session.messages = messagesResponse.data.messages || [];

                // 현재 세션 설정
                this.currentSession = session;

                // 세션 목록에서 현재 세션 업데이트
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

        // 메시지 전송
        async sendMessage(text: string) {
            if (!text.trim()) return;

            // 현재 세션이 없으면 새 세션 생성
            if (!this.currentSession) {
                await this.createNewSession();
            }

            this.waitingForResponse = true;

            try {
                const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
                const sessionId = this.currentSession!.sessionId;

                // 사용자 메시지 추가
                const userMessageResponse = await axios.post(
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

                // 메시지 목록에 사용자 메시지 추가
                if (!this.currentSession!.messages) {
                    this.currentSession!.messages = [];
                }
                this.currentSession!.messages.push(userMessage);

                // 첫 메시지인 경우 세션 제목 업데이트
                if (this.currentSession!.messages.length === 1) {
                    const title = text.length > 30 ? text.substring(0, 30) + '...' : text;
                    await this.updateSessionTitle(sessionId, title);
                }

                // 로딩 중 표시 (타이핑 중 표시)
                const loadingMessage: ChatMessage = {
                    id: generateId(),
                    sender: 'bot',
                    text: '...',
                    timestamp: new Date().toISOString(),
                    isTyping: true,
                };

                this.currentSession!.messages.push(loadingMessage);

                // API 호출하여 봇 응답 가져오기
                const botResponseText = await this.generateBotResponse(text);

                // 로딩 메시지 제거
                this.currentSession!.messages = this.currentSession!.messages.filter(
                    (msg) => msg.id !== loadingMessage.id,
                );

                // 봇 메시지 추가
                const botMessageResponse = await axios.post(
                    `${apiUrl}/sessions/${sessionId}/messages`,
                    {
                        sender: 'bot',
                        text: botResponseText,
                    },
                    {
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        withCredentials: true,
                    },
                );

                const botMessage = botMessageResponse.data;
                botMessage.displayText = ''; // 초기에는 빈 문자열로 시작
                botMessage.animationState = 'typing';

                // 메시지 목록에 봇 메시지 추가
                this.currentSession!.messages.push(botMessage);

                // 타이핑 애니메이션
                await this.simulateTyping(botMessage.id, botResponseText);

                // 세션 목록 업데이트 (최신 내용 반영)
                const sessionIndex = this.sessions.findIndex((s) => s.sessionId === sessionId);
                if (sessionIndex !== -1) {
                    this.sessions[sessionIndex].updatedAt = new Date().toISOString();

                    // 세션 목록 재정렬 (최신순)
                    this.sessions.sort(
                        (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
                    );
                }

                return botMessage;
            } catch (err: any) {
                console.error('메시지 전송 오류:', err);

                // 오류 메시지 추가
                const errorMessage: ChatMessage = {
                    id: generateId(),
                    sender: 'bot',
                    text: '죄송합니다. 응답을 처리하는 중에 오류가 발생했습니다. 다시 시도해 주세요.',
                    timestamp: new Date().toISOString(),
                    animationState: 'appear',
                };

                if (this.currentSession && this.currentSession.messages) {
                    this.currentSession.messages.push(errorMessage);
                }

                this.error = err.message || '메시지를 전송하는 중 오류가 발생했습니다.';
                throw err;
            } finally {
                this.waitingForResponse = false;
            }
        },

        // 타이핑 애니메이션 시뮬레이션
        async simulateTyping(messageId: string, fullText: string) {
            if (!this.currentSession || !this.currentSession.messages) return;

            const message = this.currentSession.messages.find((m) => m.id === messageId);
            if (!message) return;

            const typingSpeed = 10; // 문자당 타이핑 시간 (밀리초)
            const maxTypingTime = 2000; // 최대 타이핑 시간 (밀리초)

            // 최대 타이핑 시간에 맞춰 속도 조절
            const totalTypingTime = Math.min(fullText.length * typingSpeed, maxTypingTime);
            const charInterval = totalTypingTime / fullText.length;

            message.displayText = '';

            for (let i = 0; i < fullText.length; i++) {
                await new Promise((resolve) => setTimeout(resolve, charInterval));

                // 메시지가 여전히 존재하는지 확인 (삭제되었을 수 있음)
                const updatedMessage = this.currentSession?.messages.find(
                    (m) => m.id === messageId,
                );
                if (!updatedMessage) return;

                // 다음 글자 추가
                updatedMessage.displayText = fullText.substring(0, i + 1);
            }

            // 애니메이션 완료 상태로 변경
            const completedMessage = this.currentSession.messages.find((m) => m.id === messageId);
            if (completedMessage) {
                completedMessage.animationState = 'complete';
            }
        },

        // 봇 응답 생성 함수
        async generateBotResponse(userMessage: string): Promise<string> {
            try {
                // API URL 설정
                const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

                console.log('API 요청 전송:', userMessage);

                // API 호출
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
                    },
                );

                console.log('API 응답 수신:', response.data);

                // API 응답 처리 로직
                if (response.data) {
                    // 응답이 배열 형태인지 확인
                    if (Array.isArray(response.data.answer)) {
                        console.log('배열 형태의 응답 변환 처리');
                        // rank_order로 정렬
                        const sortedItems = [...response.data.answer].sort(
                            (a, b) => a.rank_order - b.rank_order,
                        );

                        // 배열을 문자열로 변환
                        return sortedItems
                            .map((item) => `${item.context}\n${item.title}\n${item.url}`)
                            .join('\n\n');
                    } else if (typeof response.data.answer === 'string') {
                        console.log('문자열 형태의 응답 처리');
                        return response.data.answer;
                    } else {
                        console.log('예상 외 응답 형식:', typeof response.data.answer);
                        return JSON.stringify(response.data.answer);
                    }
                }

                console.log('유효한 응답 데이터가 없음');
                return '죄송합니다. 유효한 응답 데이터를 받지 못했습니다.';
            } catch (error) {
                console.error('봇 응답 API 호출 오류:', error);
                return '죄송합니다. 응답을 처리하는 중에 오류가 발생했습니다. 다시 시도해 주세요.';
            }
        },

        // 세션 제목 업데이트
        async updateSessionTitle(sessionId: string, title: string) {
            try {
                const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

                // API 호출하여 세션 제목 업데이트
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

                // 현재 세션이면 제목 업데이트
                if (this.currentSession && this.currentSession.sessionId === sessionId) {
                    this.currentSession.title = title;
                }

                // 세션 목록에서도 제목 업데이트
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

        // 채팅 세션 삭제
        async deleteSession(sessionId: string) {
            try {
                const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

                // API 호출하여 세션 삭제
                await axios.delete(`${apiUrl}/sessions/${sessionId}`, {
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    withCredentials: true,
                });

                // 세션 목록에서 삭제
                this.sessions = this.sessions.filter((s) => s.sessionId !== sessionId);

                // 현재 선택된 세션이 삭제된 경우
                if (this.currentSession && this.currentSession.sessionId === sessionId) {
                    this.currentSession = this.sessions.length > 0 ? this.sessions[0] : null;

                    // 새로운 현재 세션이 설정된 경우 해당 세션의 메시지 로드
                    if (this.currentSession) {
                        await this.selectSession(this.currentSession.sessionId);
                    }
                }

                return true;
            } catch (err: any) {
                console.error('세션 삭제 오류:', err);
                this.error = err.message || '세션을 삭제하는 중 오류가 발생했습니다.';
                throw err;
            }
        },

        // 채팅 기록 클리어 (현재 세션의 메시지만 삭제)
        async clearMessages() {
            if (!this.currentSession) return;

            try {
                // 백엔드에서는 메시지 삭제 API가 없으므로, 프론트엔드에서만 처리
                // 실제 구현 시에는 백엔드에 메시지 삭제 API 추가 필요

                // 현재 세션의 메시지만 초기화
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

        // 상태 초기화
        resetState() {
            this.loading = false;
            this.error = null;
            this.sessions = [];
            this.currentSession = null;
            this.waitingForResponse = false;
        },
    },
});
