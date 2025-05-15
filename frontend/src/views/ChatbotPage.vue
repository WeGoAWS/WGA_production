<template>
    <AppLayout>
        <div class="chatbot-container">
            <div class="chatbot-sidebar">
                <div class="sidebar-header">
                    <h2>대화 목록</h2>
                    <button @click="createNewChat" class="new-chat-button">새 대화</button>
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
                    <h1 @click="handleGoMain">AWS Agent</h1>
                    <p class="chat-description">운영 정보/메뉴얼 질의</p>
                </div>

                <div class="error-message" v-if="store.error">
                    {{ store.error }}
                </div>

                <div class="chat-messages" ref="messagesContainer">
                    <template v-if="store.currentSession && store.currentMessages.length > 0">
                        <div
                            v-for="message in store.currentMessages"
                            :key="message.id"
                            class="message"
                            :class="{
                                'user-message': message.sender === 'user',
                                'bot-message': message.sender === 'bot',
                                typing: message.isTyping,
                                'appear-animation': message.animationState === 'appear',
                            }"
                        >
                            <div v-if="message.isTyping" class="typing-indicator">
                                <span class="dot"></span>
                                <span class="dot"></span>
                                <span class="dot"></span>
                            </div>
                            <div
                                v-else
                                class="message-content"
                                v-html="formatMessageContent(message.displayText || message.text)"
                            ></div>
                            <div class="message-time">
                                {{ formatMessageTime(message.timestamp) }}
                            </div>
                        </div>
                    </template>

                    <div v-else class="empty-chat">
                        <div class="empty-chat-content">
                            <h2>새로운 대화 시작하기</h2>
                            <p>아래 예시 질문을 클릭하거나 직접 질문을 입력하세요.</p>

                            <div class="example-questions">
                                <button
                                    @click="
                                        askExampleQuestion(
                                            'AWS S3 버킷 접근 권한 설정은 어떻게 하나요?',
                                        )
                                    "
                                    class="example-question"
                                >
                                    AWS S3 버킷 접근 권한 설정은 어떻게 하나요?
                                </button>
                                <button
                                    @click="
                                        askExampleQuestion(
                                            'AWS CloudTrail 로그 분석 방법을 알려주세요.',
                                        )
                                    "
                                    class="example-question"
                                >
                                    AWS CloudTrail 로그 분석 방법을 알려주세요.
                                </button>
                                <button
                                    @click="
                                        askExampleQuestion(
                                            'IAM 권한 최소화 원칙을 적용하는 방법은?',
                                        )
                                    "
                                    class="example-question"
                                >
                                    IAM 권한 최소화 원칙을 적용하는 방법은?
                                </button>
                            </div>
                        </div>
                    </div>
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
                        <span v-if="store.waitingForResponse" class="sending-text">전송 중...</span>
                        <svg
                            v-else
                            width="24"
                            height="24"
                            viewBox="0 0 24 24"
                            fill="none"
                            xmlns="http://www.w3.org/2000/svg"
                        >
                            <path
                                d="M22 2L11 13"
                                stroke="white"
                                stroke-width="2"
                                stroke-linecap="round"
                                stroke-linejoin="round"
                            />
                            <path
                                d="M22 2L15 22L11 13L2 9L22 2Z"
                                stroke="white"
                                stroke-width="2"
                                stroke-linecap="round"
                                stroke-linejoin="round"
                            />
                        </svg>
                    </button>
                </div>

                <div
                    class="chat-actions"
                    v-if="store.currentSession && store.currentMessages.length > 0"
                >
                    <button @click="clearChat" class="clear-button">대화 내용 지우기</button>
                </div>
            </div>
        </div>
    </AppLayout>
</template>

<script lang="ts">
    import { defineComponent, nextTick, onMounted, ref, watch } from 'vue';
    import AppLayout from '@/layouts/AppLayout.vue';
    import { useChatbotStore } from '@/stores/chatbot';
    import router from '@/router';

    export default defineComponent({
        name: 'ChatbotPage',
        components: {
            AppLayout,
        },

        setup() {
            const store = useChatbotStore();
            const messageText = ref('');
            const messagesContainer = ref<HTMLElement | null>(null);

            onMounted(async () => {
                // 챗봇 세션 로드
                if (store.sessions.length === 0) {
                    await fetchSessions();
                }

                // 대화 페이지로 오면서 저장된 질문이 있는지 확인
                const pendingQuestion = sessionStorage.getItem('pendingQuestion');
                if (pendingQuestion) {
                    // 질문을 찾았으면 전송하고 세션스토리지에서 제거
                    await store.sendMessage(pendingQuestion);
                    sessionStorage.removeItem('pendingQuestion');
                    scrollToBottom();
                }
            });

            // 메시지가 추가될 때마다 스크롤을 아래로 이동
            watch(
                () => store.currentMessages,
                () => {
                    scrollToBottom();
                },
                { deep: true },
            );

            // 세션 목록 가져오기
            const fetchSessions = async () => {
                await store.fetchSessions();
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

                const text = messageText.value;
                messageText.value = '';

                await store.sendMessage(text);
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

            // 메시지 내용 서식 지정 (URL을 클릭 가능한 링크로 변환)
            const formatMessageContent = (content: string): string => {
                if (!content) return '';

                // 1. 안전하게 HTML 엔티티 이스케이프 처리 (XSS 방지)
                const escapeHtml = (text: string) => {
                    return text
                        .replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;')
                        .replace(/"/g, '&quot;')
                        .replace(/'/g, '&#039;');
                };

                // 내용을 이스케이프 처리
                const escapedContent = escapeHtml(content);

                // 2. URL 패턴 정규식 개선 - 더 정확한 URL 인식
                const urlPattern = /(https?:\/\/[^\s<]+[^.\s<,.;:!?）)}\]]*)/g;

                // 3. 처리 순서 변경: URL을 먼저 링크로 변환한 후 줄바꿈 처리
                let processed = escapedContent;

                // URL을 링크로 변환
                processed = processed.replace(
                    urlPattern,
                    (url) =>
                        `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`,
                );

                // 줄바꿈 변환
                processed = processed.replace(/\n/g, '<br>');

                return processed;
            };

            // 날짜 포맷팅 (YYYY년 MM월 DD일)
            const formatDate = (dateString: string): string => {
                try {
                    const date = new Date(dateString);
                    return date.toLocaleDateString('ko-KR', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
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
                        minute: '2-digit',
                    });
                } catch (e) {
                    return '';
                }
            };

            const handleGoMain = () => {
                router.push('/start-chat');
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
                formatMessageContent,
                formatDate,
                formatMessageTime,
                handleGoMain,
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
        cursor: pointer;
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
        border-radius: 20px;
        position: relative;
        animation-duration: 0.3s;
        animation-fill-mode: both;
        transform-origin: bottom;
    }

    .user-message {
        align-self: flex-end;
        background-color: #0b93f6;
        color: white;
        border-top-left-radius: 5px;
        animation-name: sendMessage;
    }

    .bot-message {
        align-self: flex-start;
        background-color: #e5e5ea;
        color: black;
        border-top-left-radius: 5px;
        animation-name: receiveMessage;
    }

    @keyframes sendMessage {
        0% {
            transform: translateY(20px) scale(0.8);
            opacity: 0;
        }
        100% {
            transform: translateY(0) scale(1);
            opacity: 1;
        }
    }

    @keyframes receiveMessage {
        0% {
            transform: translateY(10px) scale(0.9);
            opacity: 0;
        }
        100% {
            transform: translateY(0) scale(1);
            opacity: 1;
        }
    }

    .appear-animation {
        animation-name: appearMessage;
        animation-duration: 0.3s;
    }

    @keyframes appearMessage {
        0% {
            opacity: 0;
            transform: translateY(10px);
        }
        100% {
            opacity: 1;
            transform: translateY(0);
        }
    }

    .typing-indicator {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 4px;
        min-height: 20px;
        min-width: 40px;
    }

    .dot {
        width: 8px;
        height: 8px;
        background-color: rgba(0, 0, 0, 0.5);
        border-radius: 50%;
        animation: dotPulse 1.4s infinite ease-in-out;
    }

    .dot:nth-child(1) {
        animation-delay: 0s;
    }

    .dot:nth-child(2) {
        animation-delay: 0.2s;
    }

    .dot:nth-child(3) {
        animation-delay: 0.4s;
    }

    @keyframes dotPulse {
        0%,
        60%,
        100% {
            transform: scale(0.8);
            opacity: 0.6;
        }
        30% {
            transform: scale(1.2);
            opacity: 1;
        }
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
        gap: 12px;
        position: relative;
        background-color: #fff;
        border-radius: 16px;
        padding: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        transition: all 0.3s ease;
    }

    .chat-input-container:focus-within {
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
    }

    .chat-input {
        flex: 1;
        padding: 14px 18px;
        border: 1px solid #e8e8e8;
        border-radius: 12px;
        resize: none;
        height: 56px;
        min-height: 56px;
        max-height: 120px;
        font-family: inherit;
        font-size: 1rem;
        line-height: 1.5;
        color: #333;
        background-color: #f9f9f9;
        transition: all 0.3s ease;
        overflow-y: auto;
    }

    .chat-input:focus {
        outline: none;
        border-color: #007bff;
        background-color: #fff;
    }

    .chat-input:disabled {
        background-color: #f5f5f5;
        cursor: not-allowed;
        color: #999;
    }

    .send-button {
        min-width: 56px;
        height: 56px;
        background-color: #007bff;
        color: white;
        border: none;
        border-radius: 12px;
        cursor: pointer;
        font-weight: 600;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s ease;
        box-shadow: 0 2px 4px rgba(0, 123, 255, 0.2);
    }

    .send-button:hover:not(:disabled) {
        background-color: #0056b3;
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0, 123, 255, 0.3);
    }

    .send-button:active:not(:disabled) {
        transform: translateY(1px);
        box-shadow: 0 1px 2px rgba(0, 123, 255, 0.3);
    }

    .send-button:disabled {
        background-color: #b3d9ff;
        cursor: not-allowed;
        box-shadow: none;
    }

    .chat-actions {
        margin-top: 16px;
        display: flex;
        justify-content: center;
    }

    .clear-button {
        padding: 8px 18px;
        background-color: transparent;
        color: #6c757d;
        border: 1px solid #6c757d;
        border-radius: 8px;
        cursor: pointer;
        font-weight: 500;
        font-size: 0.9rem;
        transition: all 0.3s ease;
    }

    .clear-button:hover {
        background-color: #f8f9fa;
        color: #495057;
        border-color: #495057;
    }

    /* 텍스트 타이핑 애니메이션 클래스 */
    .typing .message-content {
        white-space: pre-wrap;
        overflow: hidden;
    }

    .sending-text {
        font-size: 0.85rem;
        white-space: nowrap;
    }

    /* 링크 스타일 */
    :deep(.message-content a) {
        color: #007bff;
        text-decoration: underline;
    }

    :deep(.bot-message .message-content a) {
        color: #0056b3;
    }

    :deep(.user-message .message-content a) {
        color: #ffffff;
    }
</style>
