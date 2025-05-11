// src/stores/chatbot.ts 수정
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

interface RankItem {
    context: string;
    rank_order: number;
    title: string;
    url: string;
}

// 유니크 ID 생성 함수
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
        // 채팅 세션 목록 불러오기
        async fetchSessions() {
            this.loading = true;
            this.error = '';

            try {
                // API 호출을 통해 채팅 세션 목록을 가져오는 로직
                // 여기서는 간단한 시뮬레이션
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

        // 새 채팅 세션 생성
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

        // 채팅 세션 선택
        selectSession(sessionId: string) {
            const session = this.sessions.find((s) => s.id === sessionId);
            if (session) {
                this.currentSession = session;
            }
        },

        // 메시지 전송
        async sendMessage(text: string) {
            if (!text.trim()) return;

            // 현재 세션이 없으면 새 세션 생성
            if (!this.currentSession) {
                this.createNewSession();
            }

            const now = new Date().toISOString();

            // 사용자 메시지 추가 (애니메이션 상태 포함)
            const userMessage: ChatMessage = {
                id: generateId(),
                sender: 'user',
                text: text,
                timestamp: now,
                animationState: 'appear',
            };

            this.currentSession!.messages.push(userMessage);
            this.currentSession!.updatedAt = now;

            // 첫 메시지인 경우 세션 제목 업데이트
            if (this.currentSession!.messages.length === 1) {
                this.currentSession!.title =
                    text.length > 30 ? text.substring(0, 30) + '...' : text;
            }

            // 봇 응답 처리
            this.waitingForResponse = true;

            try {
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

                // 실제 타이핑 효과를 위한 봇 메시지 추가
                const botMessage: ChatMessage = {
                    id: generateId(),
                    sender: 'bot',
                    text: botResponseText,
                    displayText: '', // 초기에는 빈 문자열로 시작
                    timestamp: new Date().toISOString(),
                    animationState: 'typing',
                };

                this.currentSession!.messages.push(botMessage);
                this.currentSession!.updatedAt = botMessage.timestamp;

                // 타이핑 애니메이션
                await this.simulateTyping(botMessage.id, botResponseText);
            } catch (err: any) {
                console.error('봇 응답 가져오기 오류:', err);

                // 오류 메시지 추가
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

        // 타이핑 애니메이션 시뮬레이션
        async simulateTyping(messageId: string, fullText: string) {
            if (!this.currentSession) return;

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

        // 간단한 봇 응답 생성 함수 (실제 구현에서는 API 호출로 대체)
        async generateBotResponse(userMessage: string): Promise<string> {
            try {
                // API URL 설정 - 환경변수나 설정에서 가져오는 것이 좋습니다
                const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';

                console.log('API 요청 전송:', userMessage);

                // API 호출
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
                        withCredentials: true, // 쿠키 및 인증 정보 포함
                    },
                );

                console.log('API 응답 수신:', response.data);

                // API 응답 처리 로직 개선
                if (response.data) {
                    // 응답이 배열 형태인지 확인 (첫 번째 형식: answer가 배열)
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
                        // 이미 문자열 형태인 경우 (두 번째 형식)
                        return response.data.answer;
                    } else {
                        console.log('예상 외 응답 형식:', typeof response.data.answer);
                        // 응답 형식이 예상과 다른 경우
                        return JSON.stringify(response.data.answer);
                    }
                }

                console.log('유효한 응답 데이터가 없음');
                return '죄송합니다. 유효한 응답 데이터를 받지 못했습니다.';
            } catch (error) {
                console.error('봇 응답 API 호출 오류:', error);

                // API 호출 실패 시 폴백 메시지 반환
                return '죄송합니다. 응답을 처리하는 중에 오류가 발생했습니다. 다시 시도해 주세요.';
            }
        },

        // 채팅 세션 삭제
        deleteSession(sessionId: string) {
            this.sessions = this.sessions.filter((s) => s.id !== sessionId);

            // 현재 선택된 세션이 삭제된 경우
            if (this.currentSession && this.currentSession.id === sessionId) {
                this.currentSession = this.sessions.length > 0 ? this.sessions[0] : null;
            }
        },

        // 채팅 기록 클리어
        clearMessages() {
            if (this.currentSession) {
                this.currentSession.messages = [];
                this.currentSession.updatedAt = new Date().toISOString();
            }
        },

        // 상태 초기화
        resetState() {
            this.loading = false;
            this.error = '';
            this.sessions = [];
            this.currentSession = null;
            this.waitingForResponse = false;
        },
    },
});
