<template>
    <AppLayout>
        <div class="chatbot-container">
            <!-- 좌측 사이드바 (채팅 세션 목록) -->
            <div class="chatbot-sidebar" :class="{ 'disabled-sidebar': store.waitingForResponse }">
                <ChatHistory
                    :disabled="store.waitingForResponse"
                    @session-click="handleSessionClick"
                />
            </div>

            <!-- 메인 채팅 영역 -->
            <div class="chatbot-main">
                <div class="chat-header">
                    <h1 @click="handleGoMain">AWS Cloud Agent</h1>
                    <p class="chat-description">운영 정보/메뉴얼 질의</p>
                    <!-- 진행 중인 질의가 있을 때 상태 표시 -->
                    <div v-if="store.waitingForResponse" class="processing-indicator">
                        <div class="processing-spinner"></div>
                        <span>질의 처리 중...</span>
                    </div>
                </div>

                <!-- 오류 메시지 표시 영역 -->
                <div v-if="store.error" class="error-message">
                    {{ store.error }}
                    <button @click="dismissError" class="dismiss-error">×</button>
                </div>

                <!-- 세션 전환 시도 경고 모달 -->
                <div v-if="showSessionChangeWarning" class="session-warning-modal">
                    <div class="session-warning-content">
                        <h3>⚠️ 주의</h3>
                        <p>
                            현재 질의가 처리 중입니다. 다른 세션으로 전환하면 현재 진행 중인 질의가
                            중단됩니다.
                        </p>
                        <div class="warning-actions">
                            <button @click="cancelSessionChange" class="cancel-button">취소</button>
                            <button @click="confirmSessionChange" class="warning-confirm-button">
                                전환
                            </button>
                        </div>
                    </div>
                </div>

                <!-- 채팅 메시지 표시 영역 -->
                <div class="chat-messages" ref="messagesContainer">
                    <template v-if="store.currentSession && store.currentMessages.length > 0">
                        <ChatMessage
                            v-for="message in store.currentMessages"
                            :key="message.id"
                            :message="message"
                        />
                    </template>

                    <!-- 채팅이 없을 때 표시할 시작 화면 -->
                    <div v-else class="empty-chat">
                        <div class="empty-chat-content">
                            <img src="@/assets/agent-logo.png" alt="AWS Logo" class="aws-logo" />
                            <h2>AWS Cloud Agent</h2>
                            <p>
                                AWS 클라우드 운영에 관한 질문을 입력하거나 아래 예시를 클릭하세요.
                            </p>

                            <div class="example-questions">
                                <button
                                    @click="
                                        askExampleQuestion(
                                            '최근 24시간 동안 보안 이벤트가 있었나요?',
                                        )
                                    "
                                    class="example-question"
                                    :disabled="store.waitingForResponse"
                                >
                                    최근 24시간 동안 보안 이벤트가 있었나요?
                                </button>
                                <button
                                    @click="
                                        askExampleQuestion(
                                            '지난 주 CPU 사용률이 가장 높았던 EC2 인스턴스는?',
                                        )
                                    "
                                    class="example-question"
                                    :disabled="store.waitingForResponse"
                                >
                                    지난 주 CPU 사용률이 가장 높았던 EC2 인스턴스는?
                                </button>
                                <button
                                    @click="
                                        askExampleQuestion(
                                            '비용 최적화를 위한 추천사항을 알려주세요.',
                                        )
                                    "
                                    class="example-question"
                                    :disabled="store.waitingForResponse"
                                >
                                    비용 최적화를 위한 추천사항을 알려주세요.
                                </button>
                                <button
                                    @click="
                                        askExampleQuestion('IAM 정책 관리 모범 사례는 무엇인가요?')
                                    "
                                    class="example-question"
                                    :disabled="store.waitingForResponse"
                                >
                                    IAM 정책 관리 모범 사례는 무엇인가요?
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 채팅 입력 영역 -->
                <div class="input-container">
                    <ChatInput :disabled="store.waitingForResponse" @send="sendMessage" />
                </div>

                <!-- 채팅 관련 추가 액션 버튼들 -->
                <div
                    class="chat-actions"
                    v-if="store.currentSession && store.currentMessages.length > 0"
                >
                    <button
                        @click="clearChat"
                        class="clear-button"
                        :disabled="store.waitingForResponse"
                    >
                        <span class="action-icon">🧹</span>
                        대화 내용 지우기
                    </button>
                </div>
            </div>
        </div>
    </AppLayout>
</template>

<script lang="ts">
    import { defineComponent, nextTick, onMounted, ref, watch } from 'vue';
    import { useRouter } from 'vue-router';
    import axios from 'axios';
    import AppLayout from '@/layouts/AppLayout.vue';
    import ChatHistory from '@/components/ChatHistory.vue';
    import ChatMessage from '@/components/ChatMessage.vue';
    import ChatInput from '@/components/ChatInput.vue';
    import { useChatHistoryStore } from '@/stores/chatHistoryStore';
    import type { ChatMessageType } from '@/types/chat';

    export default defineComponent({
        name: 'EnhancedChatbotPage',

        components: {
            AppLayout,
            ChatHistory,
            ChatMessage,
            ChatInput,
        },

        setup() {
            const router = useRouter();
            const store = useChatHistoryStore();
            const messagesContainer = ref<HTMLElement | null>(null);
            const initialSetupDone = ref(false);
            const pendingQuestionProcessed = ref(false);

            // 세션 전환 관련 상태
            const showSessionChangeWarning = ref(false);
            const targetSessionId = ref<string | null>(null);

            // 컴포넌트 마운트 시 세션 로드 및 초기화
            onMounted(async () => {
                try {
                    // 세션스토리지에서 질문과 새 세션 생성 플래그 가져오기
                    const pendingQuestion = sessionStorage.getItem('pendingQuestion');
                    const shouldCreateNewSession =
                        sessionStorage.getItem('createNewSession') === 'true';

                    // 플래그 사용 후 제거
                    sessionStorage.removeItem('createNewSession');

                    // 보류 중인 질문이 있는 경우
                    if (pendingQuestion && !pendingQuestionProcessed.value) {
                        pendingQuestionProcessed.value = true;
                        sessionStorage.removeItem('pendingQuestion');

                        // 세션 관련 작업 진행
                        if (store.sessions.length === 0 || shouldCreateNewSession) {
                            try {
                                // 세션이 없거나 새 세션 요청인 경우 새 세션 생성
                                await store.createNewSession(
                                    pendingQuestion.length > 30
                                        ? pendingQuestion.substring(0, 30) + '...'
                                        : pendingQuestion,
                                );
                            } catch (e) {
                                console.error('세션 생성 오류:', e);
                            }
                        } else if (!store.currentSession) {
                            // 세션 선택 필요
                            try {
                                await store.selectSession(store.sessions[0].sessionId);
                            } catch (e) {
                                console.error('세션 선택 오류:', e);
                            }
                        }

                        // 여기서 메시지 처리는 한 번만 수행
                        // sendMessage 함수 호출로 통합 (자체 구현하지 않고)
                        await sendMessage(pendingQuestion, true);
                    } else {
                        // 보류 중인 질문이 없는 경우 일반적인 세션 초기화
                        if (shouldCreateNewSession) {
                            // 플래그가 있으면 항상 새 세션 생성
                            await store
                                .createNewSession()
                                .catch((e) => console.error('세션 생성 오류:', e));
                        } else {
                            // 플래그가 없으면 기존 로직 수행
                            // 세션 로드
                            if (store.sessions.length === 0) {
                                await store
                                    .fetchSessions()
                                    .catch((e) => console.error('세션 로드 오류:', e));
                            }

                            // 세션 선택 또는 생성
                            if (!store.currentSession) {
                                if (store.sessions.length > 0) {
                                    await store
                                        .selectSession(store.sessions[0].sessionId)
                                        .catch((e) => console.error('세션 선택 오류:', e));
                                } else {
                                    await store
                                        .createNewSession()
                                        .catch((e) => console.error('세션 생성 오류:', e));
                                }
                            } else if (!store.currentSession.messages) {
                                // messages가 없는 경우에 대비해 빈 배열로 초기화
                                store.currentSession.messages = [];
                            }
                        }
                    }

                    // 이미 초기화가 완료되었는지 확인 (중복 실행 방지)
                    initialSetupDone.value = true;
                } catch (error) {
                    console.error('채팅 페이지 초기화 오류:', error);
                    store.error = '채팅 세션을 불러오는 중 오류가 발생했습니다.';
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

            // 스크롤을 채팅 맨 아래로 이동
            const scrollToBottom = async () => {
                await nextTick();
                if (messagesContainer.value) {
                    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
                }
            };

            // 메시지 전송 처리
            const sendMessage = async (text: string, isPending = false) => {
                if (!text.trim() || store.waitingForResponse) return;

                try {
                    // 현재 세션 확인
                    if (!store.currentSession) {
                        // 세션이 없으면 새 세션 생성
                        await store.createNewSession(
                            text.length > 30 ? text.substring(0, 30) + '...' : text,
                        );
                    } else if (!store.currentSession.messages) {
                        // messages가 없는 경우 빈 배열로 초기화
                        store.currentSession.messages = [];
                    }

                    // 메시지 ID 생성
                    const messageId = 'msg-' + Date.now().toString(36);

                    // 사용자 메시지 UI에 즉시 표시
                    const userMessage: ChatMessageType = {
                        id: messageId,
                        sender: 'user',
                        text: text,
                        timestamp: new Date().toISOString(),
                        animationState: 'appear',
                    };

                    // 메시지를 UI에 추가
                    store.currentSession.messages.push(userMessage);

                    // 로딩 메시지 즉시 추가
                    const loadingId = 'loading-' + Date.now().toString(36);
                    const loadingMessage: ChatMessageType = {
                        id: loadingId,
                        sender: 'bot',
                        text: '...',
                        timestamp: new Date().toISOString(),
                        isTyping: true,
                    };

                    store.currentSession.messages.push(loadingMessage);
                    store.waitingForResponse = true;

                    // UI 업데이트 및 스크롤 조정
                    await nextTick();
                    scrollToBottom();

                    try {
                        // 직접 API 호출하여 봇 응답 생성
                        const botResponseText = await generateBotResponse(text);

                        // 현재 세션과 메시지 배열이 존재하는지 확인
                        if (store.currentSession && Array.isArray(store.currentSession.messages)) {
                            // 로딩 메시지 제거
                            store.currentSession.messages = store.currentSession.messages.filter(
                                (msg) => msg.id !== loadingId,
                            );

                            // 실제 봇 메시지 추가
                            const botMessage: ChatMessageType = {
                                id: 'bot-' + Date.now().toString(36),
                                sender: 'bot',
                                text: botResponseText,
                                displayText: '', // 초기에는 빈 문자열로 시작
                                timestamp: new Date().toISOString(),
                                animationState: 'typing',
                            };

                            store.currentSession.messages.push(botMessage);

                            // 타이핑 애니메이션
                            await simulateTyping(botMessage.id, botResponseText);
                        }
                    } catch (responseError) {
                        console.error('봇 응답 가져오기 오류:', responseError);

                        // 현재 세션과 메시지 배열이 존재하는지 확인
                        if (store.currentSession && Array.isArray(store.currentSession.messages)) {
                            // 로딩 메시지 제거
                            store.currentSession.messages = store.currentSession.messages.filter(
                                (msg) => msg.id !== loadingId,
                            );

                            // 오류 메시지 추가
                            const errorMessage: ChatMessageType = {
                                id: 'error-' + Date.now().toString(36),
                                sender: 'bot',
                                text: '죄송합니다. 응답을 처리하는 중에 오류가 발생했습니다. 다시 시도해 주세요.',
                                timestamp: new Date().toISOString(),
                                animationState: 'appear',
                            };

                            store.currentSession.messages.push(errorMessage);
                        }
                    }

                    // 대화 상태 업데이트
                    store.waitingForResponse = false;

                    // 스크롤 조정
                    await nextTick();
                    scrollToBottom();
                } catch (error) {
                    console.error('메시지 전송 중 오류 발생:', error);
                    store.error = '메시지를 전송하는 중 오류가 발생했습니다.';
                    store.waitingForResponse = false;
                }
            };

            // 예시 질문 전송
            const askExampleQuestion = async (question: string) => {
                if (store.waitingForResponse) return; // 이미 응답 대기 중이면 중단

                try {
                    // 즉시 예시 질문 전송 (세션 생성 대기 없이)
                    await sendMessage(question);
                } catch (error) {
                    console.error('예시 질문 전송 오류:', error);
                    store.error = '메시지를 전송하는 중 오류가 발생했습니다.';
                }
            };

            // 세션 클릭 처리 (대기 중일 때 모달 표시)
            const handleSessionClick = (sessionId: string) => {
                if (store.waitingForResponse) {
                    // 대기 중이면 경고 모달 표시
                    targetSessionId.value = sessionId;
                    showSessionChangeWarning.value = true;
                } else {
                    // 대기 중이 아니면 바로 세션 전환
                    store.selectSession(sessionId);
                }
            };

            // 세션 전환 취소
            const cancelSessionChange = () => {
                targetSessionId.value = null;
                showSessionChangeWarning.value = false;
            };

            // 세션 전환 확인
            const confirmSessionChange = async () => {
                if (targetSessionId.value) {
                    // 현재 응답 대기 상태 해제
                    store.waitingForResponse = false;

                    // 세션 전환
                    await store.selectSession(targetSessionId.value);

                    // 모달 닫기
                    targetSessionId.value = null;
                    showSessionChangeWarning.value = false;
                }
            };

            // 봇 응답 생성 함수
            const generateBotResponse = async (userMessage: string): Promise<string> => {
                try {
                    // API URL 설정
                    const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';

                    // API 호출
                    const response = await axios.post(
                        `${apiUrl}/llm1`,
                        {
                            text: userMessage,
                            sessionId: store.currentSession?.sessionId,
                        },
                        {
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            withCredentials: true,
                        },
                    );

                    // API 응답 처리 로직
                    if (response.data) {
                        // 응답이 배열 형태인지 확인
                        if (Array.isArray(response.data.answer)) {
                            // rank_order로 정렬
                            const sortedItems = [...response.data.answer].sort(
                                (a, b) => a.rank_order - b.rank_order,
                            );

                            // 배열을 문자열로 변환
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
                    throw error; // 오류를 상위로 전파하여 UI에서 처리
                }
            };

            // 타이핑 애니메이션 시뮬레이션
            const simulateTyping = async (messageId: string, fullText: string) => {
                if (!store.currentSession || !Array.isArray(store.currentSession.messages)) return;

                const message = store.currentSession.messages.find((m) => m.id === messageId);
                if (!message) return;

                const typingSpeed = 10; // 문자당 타이핑 시간 (밀리초)
                const maxTypingTime = 2000; // 최대 타이핑 시간 (밀리초)

                // 최대 타이핑 시간에 맞춰 속도 조절
                const totalTypingTime = Math.min(fullText.length * typingSpeed, maxTypingTime);
                const charInterval = totalTypingTime / fullText.length;

                message.displayText = '';

                for (let i = 0; i < fullText.length; i++) {
                    await new Promise((resolve) => setTimeout(resolve, charInterval));

                    // 메시지가 여전히 존재하는지 확인
                    if (!store.currentSession || !Array.isArray(store.currentSession.messages)) {
                        return;
                    }

                    const updatedMessage = store.currentSession.messages.find(
                        (m) => m.id === messageId,
                    );
                    if (!updatedMessage) return;

                    // 다음 글자 추가
                    updatedMessage.displayText = fullText.substring(0, i + 1);
                }

                // 애니메이션 완료 상태로 변경
                if (!store.currentSession || !Array.isArray(store.currentSession.messages)) return;

                const completedMessage = store.currentSession.messages.find(
                    (m) => m.id === messageId,
                );
                if (completedMessage) {
                    completedMessage.animationState = 'complete';
                }
            };

            // 대화 내용 지우기
            const clearChat = async () => {
                if (store.waitingForResponse) return; // 대기 중이면 중단

                if (confirm('대화 내용을 모두 지우시겠습니까?')) {
                    try {
                        await store.clearMessages();
                    } catch (error) {
                        console.error('대화 내용 지우기 오류:', error);
                        store.error = '대화 내용을 지우는 중 오류가 발생했습니다.';
                    }
                }
            };

            // 오류 메시지 닫기
            const dismissError = () => {
                store.error = null;
            };

            // 메인 페이지로 이동
            const handleGoMain = () => {
                if (store.waitingForResponse) {
                    if (
                        confirm('질의 처리가 진행 중입니다. 정말 메인 페이지로 이동하시겠습니까?')
                    ) {
                        router.push('/start-chat');
                    }
                } else {
                    router.push('/start-chat');
                }
            };

            return {
                store,
                messagesContainer,
                sendMessage,
                askExampleQuestion,
                clearChat,
                dismissError,
                handleGoMain,
                generateBotResponse,
                simulateTyping,
                showSessionChangeWarning,
                targetSessionId,
                handleSessionClick,
                cancelSessionChange,
                confirmSessionChange,
            };
        },
    });
</script>

<style scoped>
    .chatbot-container {
        display: flex;
        height: calc(100vh - 40px);
        max-height: calc(100vh - 40px);
        background-color: #f8f9fa;
    }

    .chatbot-sidebar {
        width: 300px;
        background-color: #fff;
        border-right: 1px solid #e5e5e5;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        box-shadow: 2px 0 5px rgba(0, 0, 0, 0.03);
        transition: opacity 0.3s;
    }

    /* 사이드바 비활성화 스타일 */
    .disabled-sidebar {
        position: relative;
        opacity: 0.7;
        pointer-events: none;
    }

    .disabled-sidebar::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(255, 255, 255, 0.3);
        z-index: 10;
    }

    .chatbot-main {
        flex: 1;
        display: flex;
        flex-direction: column;
        padding: 20px;
        position: relative;
        background-color: #f8f9fa;
        overflow: hidden;
    }

    .chat-header {
        margin-bottom: 20px;
        padding-bottom: 15px;
        border-bottom: 1px solid #e5e5e5;
        position: relative;
    }

    /* 처리 중 인디케이터 스타일 */
    .processing-indicator {
        position: absolute;
        top: 0;
        right: 0;
        display: flex;
        align-items: center;
        background-color: #fff8e1;
        border: 1px solid #ffd54f;
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 0.85rem;
        color: #f57c00;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0% {
            box-shadow: 0 0 0 0 rgba(255, 193, 7, 0.4);
        }
        70% {
            box-shadow: 0 0 0 6px rgba(255, 193, 7, 0);
        }
        100% {
            box-shadow: 0 0 0 0 rgba(255, 193, 7, 0);
        }
    }

    .processing-spinner {
        width: 16px;
        height: 16px;
        border: 2px solid rgba(245, 124, 0, 0.2);
        border-top: 2px solid #f57c00;
        border-radius: 50%;
        margin-right: 8px;
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

    .chat-header h1 {
        margin-bottom: 5px;
        cursor: pointer;
        color: #232f3e;
        font-size: 1.8rem;
    }

    .chat-header h1:hover {
        color: #007bff;
    }

    .chat-description {
        color: #6c757d;
        font-size: 0.95rem;
    }

    .error-message {
        background-color: #f8d7da;
        color: #721c24;
        padding: 12px 15px;
        border-radius: 6px;
        margin-bottom: 15px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 0.95rem;
        border-left: 4px solid #dc3545;
    }

    .dismiss-error {
        background: none;
        border: none;
        font-size: 1.2rem;
        cursor: pointer;
        color: #721c24;
        padding: 0 5px;
    }

    /* 세션 전환 경고 모달 스타일 */
    .session-warning-modal {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
    }

    .session-warning-content {
        background-color: white;
        padding: 24px;
        border-radius: 12px;
        width: 90%;
        max-width: 400px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    }

    .session-warning-content h3 {
        margin-top: 0;
        margin-bottom: 16px;
        color: #f57c00;
    }

    .warning-actions {
        display: flex;
        justify-content: flex-end;
        gap: 12px;
        margin-top: 20px;
    }

    .cancel-button {
        padding: 8px 16px;
        background-color: #f0f0f0;
        border: none;
        border-radius: 6px;
        cursor: pointer;
    }

    .warning-confirm-button {
        padding: 8px 16px;
        background-color: #f57c00;
        color: white;
        border: none;
        border-radius: 6px;
        cursor: pointer;
    }

    .cancel-button:hover {
        background-color: #e0e0e0;
    }

    .warning-confirm-button:hover {
        background-color: #ef6c00;
    }

    .chat-messages {
        flex: 1;
        overflow-y: auto;
        padding: 10px;
        padding-right: 15px;
        display: flex;
        flex-direction: column;
        background-color: white;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
    }

    .empty-chat {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 20px;
    }

    .empty-chat-content {
        max-width: 600px;
        text-align: center;
        padding: 40px;
    }

    .aws-logo {
        width: 100px;
        margin-bottom: 20px;
    }

    .empty-chat-content h2 {
        font-size: 2rem;
        margin-bottom: 16px;
        color: #232f3e;
    }

    .empty-chat-content p {
        color: #6c757d;
        margin-bottom: 30px;
        font-size: 1.1rem;
    }

    .example-questions {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 15px;
        margin-top: 20px;
    }

    .example-question {
        padding: 16px;
        background-color: #f1f8ff;
        border: 1px solid #cce5ff;
        border-radius: 8px;
        text-align: left;
        cursor: pointer;
        transition: all 0.2s;
        color: #0d6efd;
        font-size: 0.95rem;
    }

    .example-question:hover:not(:disabled) {
        background-color: #e1f0ff;
        border-color: #99caff;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
    }

    .example-question:disabled {
        opacity: 0.6;
        cursor: not-allowed;
        transform: none;
        box-shadow: none;
    }

    .input-container {
        margin-top: 20px;
        padding: 10px 0;
    }

    .chat-actions {
        display: flex;
        justify-content: center;
        margin-top: 15px;
    }

    .clear-button {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 16px;
        background-color: transparent;
        color: #6c757d;
        border: 1px solid #ced4da;
        border-radius: 20px;
        cursor: pointer;
        font-size: 0.9rem;
        transition: all 0.2s;
    }

    .clear-button:hover:not(:disabled) {
        background-color: #f8f9fa;
        color: #495057;
    }

    .clear-button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .action-icon {
        font-size: 1rem;
    }

    /* 반응형 스타일 */
    @media (max-width: 768px) {
        .chatbot-container {
            flex-direction: column;
        }

        .chatbot-sidebar {
            width: 100%;
            height: 60px;
            flex-direction: row;
            overflow: auto;
        }

        .chat-messages {
            max-height: calc(100vh - 220px);
        }

        .example-questions {
            grid-template-columns: 1fr;
        }
    }
</style>
