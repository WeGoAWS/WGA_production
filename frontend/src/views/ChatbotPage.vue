<!-- src/views/ChatbotPage.vue -->
<template>
    <AppLayout>
        <div class="chatbot-container">
            <div class="chatbot-sidebar">
                <div class="sidebar-header">
                    <h2>대화 목록</h2>
                    <button @click="createNewChat" class="new-chat-button">
                        새 대화
                    </button>
                </div>

                <div v-if="store.loading" class="sidebar-loading">
                    <div class="mini-spinner"></div>
                    <span>로딩 중...</span>
                </div>

                <div v-else-if="store.hasSessions" class="chat-sessions">
                    <div 
                        v-for="session in store.sessions" 
                        :key="session.id" 
                        class="chat-session-item"
                        :class="{ active: store.currentSession?.id === session.id }"
                        @click="selectSession(session.id)"
                    >
                        <div class="session-title">{{ session.title }}</div>
                        <div class="session-date">{{ formatDate(session.updatedAt) }}</div>
                    </div>
                </div>

                <div v-else class="empty-sessions">
                    <p>대화 내역이 없습니다.</p>
                    <button @click="fetchSessions" class="refresh-button">새로고침</button>
                </div>
            </div>

            <div class="chatbot-main">
                <div class="chat-header">
                    <h1>AWS 보안 챗봇</h1>
                    <p class="chat-description">
                        AWS 클라우드 보안, 로그 분석, 권한 관리에 관한 질문을 할 수 있습니다.
                    </p>
                </div>

                <div class="error-message" v-if="store.error">
                    {{ store.error }}
                </div>

                <div class="chat-messages" ref="messagesContainer">
                    <div v-if="!store.currentSession || store.currentMessages.length === 0" class="empty-chat">
                        <div class="empty-chat-content">
                            <h2>새로운 대화 시작하기</h2>
                            <p>아래 예시 질문을 클릭하거나 직접 질문을 입력하세요.</p>
                            
                            <div class="example-questions">
                                <button @click="askExampleQuestion('AWS S3 버킷 접근 권한 설정은 어떻게 하나요?')" class="example-question">
                                    AWS S3 버킷 접근 권한 설정은 어떻게 하나요?
                                </button>
                                <button @click="askExampleQuestion('AWS CloudTrail 로그 분석 방법을 알려주세요.')" class="example-question">
                                    AWS CloudTrail 로그 분석 방법을 알려주세요.
                                </button>
                                <button @click="askExampleQuestion('IAM 권한 최소화 원칙을 적용하는 방법은?')" class="example-question">
                                    IAM 권한 최소화 원칙을 적용하는 방법은?
                                </button>
                            </div>
                        </div>
                    </div>

                    <template v-else>
                        <div 
                            v-for="message in store.currentMessages" 
                            :key="message.id" 
                            class="message"
                            :class="{ 'user-message': message.sender === 'user', 'bot-message': message.sender === 'bot' }"
                        >
                            <div class="message-content">{{ message.text }}</div>
                            <div class="message-time">{{ formatMessageTime(message.timestamp) }}</div>
                        </div>
                    </template>
                </div>

                <div class="chat-input-container">
                    <textarea 
                        v-model="messageText" 
                        class="chat-input" 
                        placeholder="질문을 입력하세요..." 
                        @keydown.enter.prevent="sendMessage"
                        :disabled="store.waitingForResponse"
                    ></textarea>
                    <button 
                        @click="sendMessage" 
                        class="send-button"
                        :disabled="!messageText.trim() || store.waitingForResponse"
                    >
                        <span v-if="store.waitingForResponse">응답 중...</span>
                        <span v-else>전송</span>
                    </button>
                </div>

                <div class="chat-actions" v-if="store.currentSession && store.currentMessages.length > 0">
                    <button @click="clearChat" class="clear-button">대화 내용 지우기</button>
                </div>
            </div>
        </div>
    </AppLayout>
</template>

<script lang="ts">
    import { defineComponent, ref, onMounted, nextTick, watch } from 'vue';
    import AppLayout from '@/layouts/AppLayout.vue';
    import { useChatbotStore } from '@/stores/chatbot';

    export default defineComponent({
        name: 'ChatbotPage',
        components: {
            AppLayout,
        },

        setup() {
            const store = useChatbotStore();
            const messageText = ref('');
            const messagesContainer = ref<HTMLElement | null>(null);

            onMounted(() => {
                // 챗봇 세션 로드
                if (store.sessions.length === 0) {
                    fetchSessions();
                }
            });

            // 메시지가 추가될 때마다 스크롤을 아래로 이동
            watch(() => store.currentMessages, () => {
                scrollToBottom();
            }, { deep: true });

            // 세션 목록 가져오기
            const fetchSessions = () => {
                store.fetchSessions();
            };

            // 새 채팅 세션 생성
            const createNewChat = () => {
                store.createNewSession();
                scrollToBottom();
            };

            // 채팅 세션 선택
            const selectSession = (sessionId: string) => {
                store.selectSession(sessionId);
                scrollToBottom();
            };

            // 메시지 전송
            const sendMessage = async () => {
                if (!messageText.value.trim() || store.waitingForResponse) return;
                
                await store.sendMessage(messageText.value);
                messageText.value = '';
                scrollToBottom();
            };

            // 예시 질문 전송
            const askExampleQuestion = (question: string) => {
                messageText.value = question;
                sendMessage();
            };

            // 대화 내용 지우기
            const clearChat = () => {
                if (confirm('대화 내용을 모두 지우시겠습니까?')) {
                    store.clearMessages();
                }
            };

            // 스크롤을 채팅 맨 아래로 이동
            const scrollToBottom = async () => {
                await nextTick();
                if (messagesContainer.value) {
                    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
                }
            };

            // 날짜 포맷팅 (YYYY년 MM월 DD일)
            const formatDate = (dateString: string): string => {
                try {
                    const date = new Date(dateString);
                    return date.toLocaleDateString('ko-KR', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric'
                    });
                } catch (e) {
                    return dateString;
                }
            };

            // 메시지 시간 포맷팅 (HH:MM)
            const formatMessageTime = (dateString: string): string => {
                try {
                    const date = new Date(dateString);
                    return date.toLocaleTimeString('ko-KR', {
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                } catch (e) {
                    return '';
                }
            };

            return {
                store,
                messageText,
                messagesContainer,
                fetchSessions,
                createNewChat,
                selectSession,
                sendMessage,
                askExampleQuestion,
                clearChat,
                formatDate,
                formatMessageTime
            };
        },
    });
</script>

<style scoped>
    .chatbot-container {
        display: flex;
        height: calc(100vh - 40px);
        max-height: calc(100vh - 40px);
    }

    .chatbot-sidebar {
        width: 300px;
        background-color: #f8f9fa;
        border-right: 1px solid #dee2e6;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .sidebar-header {
        padding: 15px;
        border-bottom: 1px solid #dee2e6;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .sidebar-header h2 {
        margin: 0;
        font-size: 1.2rem;
    }

    .new-chat-button {
        padding: 6px 12px;
        background-color: #28a745;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    }

    .sidebar-loading {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 20px;
        gap: 10px;
    }

    .mini-spinner {
        width: 16px;
        height: 16px;
        border: 2px solid #f3f3f3;
        border-top: 2px solid #007bff;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        0% {
            transform: rotate(0deg);
        }
        100% {
            transform: rotate(360deg);
        }
    }

    .chat-sessions {
        flex: 1;
        overflow-y: auto;
        padding: 10px;
    }

    .chat-session-item {
        padding: 12px;
        border-radius: 5px;
        margin-bottom: 8px;
        cursor: pointer;
        transition: background-color 0.2s;
    }

    .chat-session-item:hover {
        background-color: #e9ecef;
    }

    .chat-session-item.active {
        background-color: #dee2e6;
    }

    .session-title {
        font-weight: bold;
        margin-bottom: 5px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .session-date {
        font-size: 0.8rem;
        color: #6c757d;
    }

    .empty-sessions {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 20px;
        text-align: center;
        color: #6c757d;
    }

    .refresh-button {
        margin-top: 10px;
        padding: 6px 12px;
        background-color: #007bff;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    }

    .chatbot-main {
        flex: 1;
        display: flex;
        flex-direction: column;
        padding: 20px;
        overflow: hidden;
    }

    .chat-header {
        margin-bottom: 20px;
    }

    .chat-header h1 {
        margin-bottom: 5px;
    }

    .chat-description {
        color: #6c757d;
    }

    .error-message {
        background-color: #fce4e4;
        border: 1px solid #f8b8b8;
        color: #d63301;
        padding: 10px 15px;
        border-radius: 4px;
        margin-bottom: 15px;
    }

    .chat-messages {
        flex: 1;
        overflow-y: auto;
        padding: 10px;
        display: flex;
        flex-direction: column;
        gap: 15px;
    }

    .empty-chat {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .empty-chat-content {
        max-width: 500px;
        text-align: center;
    }

    .example-questions {
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin-top: 20px;
    }

    .example-question {
        padding: 10px;
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        text-align: left;
        cursor: pointer;
        transition: background-color 0.2s;
    }

    .example-question:hover {
        background-color: #e9ecef;
    }

    .message {
        max-width: 80%;
        padding: 12px;
        border-radius: 10px;
        position: relative;
    }

    .user-message {
        align-self: flex-end;
        background-color: #007bff;
        color: white;
    }

    .bot-message {
        align-self: flex-start;
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
    }

    .message-content {
        margin-bottom: 5px;
        white-space: pre-wrap;
    }

    .message-time {
        font-size: 0.75rem;
        opacity: 0.8;
        text-align: right;
    }

    .chat-input-container {
        margin-top: 20px;
        display: flex;
        gap: 10px;
    }

    .chat-input {
        flex: 1;
        padding: 12px;
        border: 1px solid #ced4da;
        border-radius: 4px;
        resize: none;
        height: 50px;
        font-family: inherit;
    }

    .send-button {
        padding: 0 20px;
        background-color: #007bff;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    }

    .send-button:disabled {
        background-color: #ccc;
        cursor: not-allowed;
    }

    .chat-actions {
        margin-top: 10px;
        display: flex;
        justify-content: center;
    }

    .clear-button {
        padding: 6px 12px;
        background-color: transparent;
        color: #6c757d;
        border: 1px solid #6c757d;
        border-radius: 4px;
        cursor: pointer;
    }
</style>