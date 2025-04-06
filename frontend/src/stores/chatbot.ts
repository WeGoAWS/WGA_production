// src/stores/chatbot.ts
import { defineStore } from 'pinia';

interface ChatMessage {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  timestamp: string;
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
        await new Promise(resolve => setTimeout(resolve, 500));
        
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
                  timestamp: yesterday
                },
                {
                  id: 'msg-2',
                  sender: 'bot',
                  text: 'AWS S3 버킷의 접근 권한은 버킷 정책과 IAM 정책을 통해 설정할 수 있습니다. 버킷 정책은 특정 버킷에 대한 접근을 제어하는 JSON 문서입니다. IAM 정책은 사용자, 그룹 또는 역할에 연결되어 AWS 리소스에 대한 접근을 제어합니다.',
                  timestamp: yesterday
                }
              ],
              createdAt: yesterday,
              updatedAt: yesterday
            },
            {
              id: 'session-2',
              title: '로그 분석 도구 추천',
              messages: [
                {
                  id: 'msg-3',
                  sender: 'user',
                  text: 'AWS 로그 분석에 좋은 도구가 무엇인가요?',
                  timestamp: now
                },
                {
                  id: 'msg-4',
                  sender: 'bot',
                  text: 'AWS 로그 분석을 위해 여러 도구를 사용할 수 있습니다. AWS 자체 서비스로는 CloudWatch Logs Insights, Amazon Athena, Amazon OpenSearch Service 등이 있습니다. 서드파티 도구로는 Splunk, ELK Stack(Elasticsearch, Logstash, Kibana), Datadog 등이 인기가 있습니다.',
                  timestamp: now
                }
              ],
              createdAt: now,
              updatedAt: now
            }
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
        updatedAt: now
      };
      
      this.sessions.unshift(newSession);
      this.currentSession = newSession;
      
      return newSession;
    },

    // 채팅 세션 선택
    selectSession(sessionId: string) {
      const session = this.sessions.find(s => s.id === sessionId);
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
      
      // 사용자 메시지 추가
      const userMessage: ChatMessage = {
        id: generateId(),
        sender: 'user',
        text: text,
        timestamp: now
      };
      
      this.currentSession!.messages.push(userMessage);
      this.currentSession!.updatedAt = now;
      
      // 첫 메시지인 경우 세션 제목 업데이트
      if (this.currentSession!.messages.length === 1) {
        this.currentSession!.title = text.length > 30 ? text.substring(0, 30) + '...' : text;
      }
      
      // 봇 응답 처리
      this.waitingForResponse = true;
      
      try {
        // 실제 API 호출을 통해 봇 응답을 가져오는 로직
        // 여기서는 간단한 시뮬레이션
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        const botMessage: ChatMessage = {
          id: generateId(),
          sender: 'bot',
          text: this.generateBotResponse(text),
          timestamp: new Date().toISOString()
        };
        
        this.currentSession!.messages.push(botMessage);
        this.currentSession!.updatedAt = botMessage.timestamp;
      } catch (err: any) {
        console.error('봇 응답 가져오기 오류:', err);
        
        // 오류 메시지 추가
        const errorMessage: ChatMessage = {
          id: generateId(),
          sender: 'bot',
          text: '죄송합니다. 응답을 처리하는 중에 오류가 발생했습니다. 다시 시도해 주세요.',
          timestamp: new Date().toISOString()
        };
        
        this.currentSession!.messages.push(errorMessage);
        this.currentSession!.updatedAt = errorMessage.timestamp;
      } finally {
        this.waitingForResponse = false;
      }
    },

    // 간단한 봇 응답 생성 함수 (실제 구현에서는 API 호출로 대체)
    generateBotResponse(userMessage: string): string {
      if (userMessage.toLowerCase().includes('안녕')) {
        return '안녕하세요! 무엇을 도와드릴까요?';
      } else if (userMessage.toLowerCase().includes('aws') || userMessage.toLowerCase().includes('클라우드')) {
        return 'AWS 클라우드 서비스에 관한 질문이군요. 보안, 로그 분석, 권한 관리 등 특정 주제에 대해 질문해 주시면 더 자세히 답변드릴 수 있습니다.';
      } else if (userMessage.toLowerCase().includes('로그') || userMessage.toLowerCase().includes('분석')) {
        return '로그 분석은 보안 모니터링의 중요한 부분입니다. CloudTrail, CloudWatch Logs 등의 서비스를 활용하여 로그를 수집하고 분석할 수 있습니다.';
      } else if (userMessage.toLowerCase().includes('권한') || userMessage.toLowerCase().includes('iam')) {
        return 'AWS IAM(Identity and Access Management)은 AWS 리소스에 대한 접근을 안전하게 제어하는 서비스입니다. 최소 권한 원칙을 따라 필요한 권한만 부여하는 것이 좋습니다.';
      } else {
        return '질문해 주셔서 감사합니다. 더 자세한 정보가 필요하시면 질문을 구체적으로 해주시거나, 로그 분석, IAM 권한, 보안 설정 등의 특정 주제에 대해 질문해 주세요.';
      }
    },

    // 채팅 세션 삭제
    deleteSession(sessionId: string) {
      this.sessions = this.sessions.filter(s => s.id !== sessionId);
      
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
    }
  }
});