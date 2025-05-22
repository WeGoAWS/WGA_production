<template>
    <AppLayout>
        <div class="chatbot-container">
            <!-- 토글 가능한 좌측 사이드바 (채팅 세션 목록) -->
            <transition name="slide">
                <div
                    v-if="isSidebarOpen"
                    class="chatbot-sidebar"
                    :class="{ 'disabled-sidebar': store.waitingForResponse }"
                >
                    <ChatHistory
                        :disabled="store.waitingForResponse"
                        @session-click="handleSessionClick"
                    />
                </div>
            </transition>

            <!-- 메인 채팅 영역 -->
            <div class="chatbot-main" :class="{ 'sidebar-open': isSidebarOpen }">
                <div class="chat-header">
                    <!-- 사이드바 토글 버튼 추가 -->
                    <button @click="toggleSidebar" class="sidebar-toggle-button">
                        <svg
                            width="24"
                            height="24"
                            viewBox="0 0 24 24"
                            fill="none"
                            xmlns="http://www.w3.org/2000/svg"
                        >
                            <path
                                d="M3 12H21"
                                stroke="currentColor"
                                stroke-width="2"
                                stroke-linecap="round"
                                stroke-linejoin="round"
                            />
                            <path
                                d="M3 6H21"
                                stroke="currentColor"
                                stroke-width="2"
                                stroke-linecap="round"
                                stroke-linejoin="round"
                            />
                            <path
                                d="M3 18H21"
                                stroke="currentColor"
                                stroke-width="2"
                                stroke-linecap="round"
                                stroke-linejoin="round"
                            />
                        </svg>
                    </button>

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
                    <div class="chat-input-wrapper">
                        <textarea
                            v-model="messageText"
                            class="chat-input"
                            placeholder="질문을 입력하세요..."
                            @keydown.enter.prevent="handleEnterKey"
                            @keydown.esc="handleEscKey"
                            :disabled="store.waitingForResponse"
                            ref="inputRef"
                            rows="1"
                            @input="autoResize"
                        ></textarea>

                        <!-- 대화 컨텍스트 기억 토글 -->
                        <div class="context-toggle-container">
                            <label class="context-toggle-label">
                                <input
                                    type="checkbox"
                                    v-model="isCached"
                                    class="context-toggle-input"
                                    :disabled="store.waitingForResponse"
                                />
                                <span class="context-toggle-slider"></span>
                                <span class="context-toggle-text">대화 컨텍스트 기억</span>
                            </label>
                        </div>

                        <button
                            @click="store.waitingForResponse ? cancelRequest() : sendMessage()"
                            class="send-button"
                            :disabled="!messageText.trim() && !store.waitingForResponse"
                            :class="{
                                loading: store.waitingForResponse,
                                'cancel-mode': store.waitingForResponse,
                            }"
                            @mouseenter="showCancelIcon = true"
                            @mouseleave="showCancelIcon = false"
                        >
                            <span
                                v-if="store.waitingForResponse && !showCancelIcon"
                                class="loading-indicator"
                            >
                                <span class="loading-dot"></span>
                                <span class="loading-dot"></span>
                                <span class="loading-dot"></span>
                            </span>
                            <span
                                v-else-if="store.waitingForResponse && showCancelIcon"
                                class="cancel-icon"
                            >
                                <svg
                                    width="20"
                                    height="20"
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    stroke="white"
                                    stroke-width="2"
                                    stroke-linecap="round"
                                    stroke-linejoin="round"
                                >
                                    <line x1="18" y1="6" x2="6" y2="18"></line>
                                    <line x1="6" y1="6" x2="18" y2="18"></line>
                                </svg>
                            </span>
                            <svg
                                v-else
                                width="20"
                                height="20"
                                viewBox="0 0 24 24"
                                fill="none"
                                xmlns="http://www.w3.org/2000/svg"
                            >
                                <path
                                    d="M22 2L11 13"
                                    stroke="currentColor"
                                    stroke-width="2"
                                    stroke-linecap="round"
                                    stroke-linejoin="round"
                                />
                                <path
                                    d="M22 2L15 22L11 13L2 9L22 2Z"
                                    stroke="currentColor"
                                    stroke-width="2"
                                    stroke-linecap="round"
                                    stroke-linejoin="round"
                                />
                            </svg>
                        </button>
                    </div>
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
    import { useChatHistoryStore } from '@/stores/chatHistoryStore';
    import type { BotResponse, ChatMessageType } from '@/types/chat';

    export default defineComponent({
        name: 'EnhancedChatbotPage',

        components: {
            AppLayout,
            ChatHistory,
            ChatMessage,
        },

        setup() {
            const router = useRouter();
            const store = useChatHistoryStore();
            const messagesContainer = ref<HTMLElement | null>(null);
            const initialSetupDone = ref(false);
            const pendingQuestionProcessed = ref(false);
            const messageText = ref('');
            const inputRef = ref<HTMLTextAreaElement | null>(null);
            const showCancelIcon = ref(false);
            const isCached = ref(true); // 대화 컨텍스트 기억 토글 상태 (기본값: true)

            const showSessionChangeWarning = ref(false);
            const targetSessionId = ref<string | null>(null);

            // 사이드바 상태 관리 (토글 기능 추가)
            const isSidebarOpen = ref(false); // 기본적으로 사이드바가 닫힌 상태로 시작

            const toggleSidebar = () => {
                isSidebarOpen.value = !isSidebarOpen.value;
            };

            // 윈도우 크기 변화에 대응하는 함수
            const handleResize = () => {
                // 모바일 환경(<768px)에서 사이드바가 열려있을 경우 닫기
                if (window.innerWidth < 768 && isSidebarOpen.value) {
                    isSidebarOpen.value = false;
                }
            };

            // Enter 키 처리 (Shift+Enter는 줄바꿈)
            const handleEnterKey = (e: KeyboardEvent) => {
                if (e.shiftKey) return; // Shift+Enter는 줄바꿈

                if (store.waitingForResponse) {
                    // 요청 중이면 취소
                    cancelRequest();
                } else {
                    // 아니면 메시지 전송
                    sendMessage();
                }
            };

            // ESC 키 처리 (요청 취소)
            const handleEscKey = () => {
                if (store.waitingForResponse) {
                    cancelRequest();
                }
            };

            // 텍스트 에어리어 자동 크기 조절
            const autoResize = () => {
                if (!inputRef.value) return;

                // 높이 초기화
                inputRef.value.style.height = 'auto';

                // 새 높이 설정 (스크롤 높이 기준, 최대 5줄 정도로 제한)
                const newHeight = Math.min(inputRef.value.scrollHeight, 150);
                inputRef.value.style.height = `${newHeight}px`;
            };

            // 요청 취소
            const cancelRequest = () => {
                store.cancelRequest();
                showCancelIcon.value = false;
            };

            onMounted(async () => {
                try {
                    const pendingQuestion = sessionStorage.getItem('pendingQuestion');
                    const shouldCreateNewSession =
                        sessionStorage.getItem('createNewSession') === 'true';

                    sessionStorage.removeItem('createNewSession');

                    if (pendingQuestion && !pendingQuestionProcessed.value) {
                        pendingQuestionProcessed.value = true;
                        sessionStorage.removeItem('pendingQuestion');

                        if (store.sessions.length === 0 || shouldCreateNewSession) {
                            try {
                                await store.createNewSession(
                                    pendingQuestion.length > 30
                                        ? pendingQuestion.substring(0, 30) + '...'
                                        : pendingQuestion,
                                );
                            } catch (e) {
                                console.error('세션 생성 오류:', e);
                            }
                        } else if (!store.currentSession) {
                            try {
                                await store.selectSession(store.sessions[0].sessionId);
                            } catch (e) {
                                console.error('세션 선택 오류:', e);
                            }
                        }

                        await sendMessage(pendingQuestion, true);
                    } else {
                        if (shouldCreateNewSession) {
                            await store
                                .createNewSession()
                                .catch((e) => console.error('세션 생성 오류:', e));
                        } else {
                            if (store.sessions.length === 0) {
                                await store
                                    .fetchSessions()
                                    .catch((e) => console.error('세션 로드 오류:', e));
                            }

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
                                store.currentSession.messages = [];
                            }
                        }
                    }

                    initialSetupDone.value = true;

                    // 윈도우 리사이즈 이벤트 리스너 등록
                    window.addEventListener('resize', handleResize);

                    return () => {
                        window.removeEventListener('resize', handleResize);
                    };
                } catch (error) {
                    console.error('채팅 페이지 초기화 오류:', error);
                    store.error = '채팅 세션을 불러오는 중 오류가 발생했습니다.';
                }
            });

            watch(
                () => store.currentMessages,
                () => {
                    scrollToBottom();
                },
                { deep: true },
            );

            const scrollToBottom = async () => {
                await nextTick();
                if (messagesContainer.value) {
                    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
                }
            };

            const sendMessage = async (text?: string, isPending = false) => {
                const messageToSend = text || messageText.value;
                if (!messageToSend.trim() || store.waitingForResponse) return;

                try {
                    if (!store.currentSession) {
                        await store.createNewSession(
                            messageToSend.length > 30
                                ? messageToSend.substring(0, 30) + '...'
                                : messageToSend,
                        );
                    } else if (!store.currentSession.messages) {
                        store.currentSession.messages = [];
                    }

                    const messageId = 'msg-' + Date.now().toString(36);

                    const userMessage: ChatMessageType = {
                        id: messageId,
                        sender: 'user',
                        text: messageToSend,
                        timestamp: new Date().toISOString(),
                        animationState: 'appear',
                    };

                    // 안전하게 메시지를 UI에 추가 (null 체크)
                    if (store.currentSession && Array.isArray(store.currentSession.messages)) {
                        store.currentSession.messages.push(userMessage);
                    } else {
                        console.error('세션 또는 메시지 배열이 없습니다');
                        return;
                    }

                    // 로딩 메시지 즉시 추가
                    const loadingId = 'loading-' + Date.now().toString(36);
                    const loadingMessage: ChatMessageType = {
                        id: loadingId,
                        sender: 'bot',
                        text: '...',
                        timestamp: new Date().toISOString(),
                        isTyping: true,
                    };

                    // 안전하게 로딩 메시지를 UI에 추가 (null 체크)
                    if (store.currentSession && Array.isArray(store.currentSession.messages)) {
                        store.currentSession.messages.push(loadingMessage);
                    } else {
                        console.error('세션 또는 메시지 배열이 없습니다');
                        return;
                    }

                    store.waitingForResponse = true;

                    // 모바일에서 메시지 전송 시 사이드바 닫기
                    if (window.innerWidth < 768) {
                        isSidebarOpen.value = false;
                    }

                    // UI 텍스트 입력창 초기화
                    if (!text) {
                        messageText.value = '';
                        // 텍스트 에어리어 높이 초기화
                        if (inputRef.value) {
                            inputRef.value.style.height = 'auto';
                        }
                    }

                    // UI 업데이트 및 스크롤 조정
                    await nextTick();
                    scrollToBottom();

                    // 서버에 사용자 메시지 저장 (API 호출)
                    try {
                        const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';
                        const sessionId = store.currentSession.sessionId;

                        // 사용자 메시지를 서버에 저장
                        const userMessageResponse = await axios.post(
                            `${apiUrl}/sessions/${sessionId}/messages`,
                            {
                                sender: 'user',
                                text: messageToSend,
                            },
                            {
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                                withCredentials: true,
                            },
                        );
                    } catch (saveError) {
                        console.error('사용자 메시지 저장 오류:', saveError);
                        // 메시지 저장 실패해도 계속 진행
                    }

                    try {
                        // 직접 API 호출하여 봇 응답 생성
                        const botResponse = await generateBotResponse(messageToSend);

                        // 현재 세션과 메시지 배열이 존재하는지 확인
                        if (store.currentSession && Array.isArray(store.currentSession.messages)) {
                            // 로딩 메시지 제거
                            store.currentSession.messages = store.currentSession.messages.filter(
                                (msg) => msg.id !== loadingId,
                            );

                            // 실제 봇 메시지 추가 - 응답 형식에 따라 필드 추가
                            const botMessage: ChatMessageType = {
                                id: 'bot-' + Date.now().toString(36),
                                sender: 'bot',
                                text: botResponse.text || '',
                                displayText: '', // 초기에는 빈 문자열로 시작
                                timestamp: new Date().toISOString(),
                                animationState: 'typing',
                            };

                            // 쿼리 정보가 있으면 추가
                            if (botResponse.query_string) {
                                botMessage.query_string = botResponse.query_string;
                            }

                            if (botResponse.query_result) {
                                botMessage.query_result = botResponse.query_result;
                            }

                            if (botResponse.elapsed_time) {
                                botMessage.elapsed_time = botResponse.elapsed_time;
                            }
                            if (botResponse.inference) {
                                botMessage.inference = botResponse.inference;
                            }

                            store.currentSession.messages.push(botMessage);

                            // 타이핑 애니메이션
                            await simulateTyping(botMessage.id, botResponse.text || '');

                            // 봇 메시지를 서버에 저장 (API 호출)
                            try {
                                const apiUrl =
                                    import.meta.env.VITE_API_DEST || 'http://localhost:8000';
                                const sessionId = store.currentSession.sessionId;

                                // elapsed_time이 있으면 텍스트 메시지에 추가
                                const messageText = botResponse.text || '';

                                // 봇 메시지를 서버에 저장
                                await axios.post(
                                    `${apiUrl}/sessions/${sessionId}/messages`,
                                    {
                                        sender: 'bot',
                                        text: messageText,
                                        // 추가 정보가 있으면 함께 전송
                                        ...(botResponse.query_string && {
                                            query_string: botResponse.query_string,
                                        }),
                                        ...(botResponse.query_result?.length && {
                                            query_result: JSON.stringify(botResponse.query_result),
                                        }),
                                        ...(botResponse.elapsed_time && {
                                            elapsed_time: botResponse.elapsed_time,
                                        }),
                                        ...(botResponse.inference && {
                                            inference: JSON.stringify(botResponse.inference),
                                        }),
                                    },
                                    {
                                        headers: {
                                            'Content-Type': 'application/json',
                                        },
                                        withCredentials: true,
                                    },
                                );
                            } catch (saveError) {
                                console.error('봇 메시지 저장 오류:', saveError);
                                // 메시지 저장 실패해도 계속 진행
                            }
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

                            // 오류 메시지도 서버에 저장
                            try {
                                const apiUrl =
                                    import.meta.env.VITE_API_DEST || 'http://localhost:8000';
                                const sessionId = store.currentSession.sessionId;

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
                            } catch (saveError) {
                                console.error('오류 메시지 저장 실패:', saveError);
                            }
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

                    // 모바일에서는 세션 선택 후 사이드바 닫기
                    if (window.innerWidth < 768) {
                        isSidebarOpen.value = false;
                    }
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

                    // 모바일에서는 세션 선택 후 사이드바 닫기
                    if (window.innerWidth < 768) {
                        isSidebarOpen.value = false;
                    }

                    // 모달 닫기
                    targetSessionId.value = null;
                    showSessionChangeWarning.value = false;
                }
            };

            // 봇 응답 생성 함수
            const generateBotResponse = async (userMessage: string): Promise<BotResponse> => {
                try {
                    // API URL 설정
                    const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';

                    // API 호출 시 isCached 값을 포함
                    const response = await axios.post(
                        `${apiUrl}/llm1`,
                        {
                            text: userMessage,
                            sessionId: store.currentSession?.sessionId,
                            isCached: isCached.value, // 토글 상태 전송
                        },
                        {
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            withCredentials: true,
                            cancelToken: store.apiCancelToken
                                ? store.apiCancelToken.token
                                : undefined,
                        },
                    );

                    // API 응답 처리 로직
                    if (response.data) {
                        // inference 필드가 있는 경우 처리 (추가)
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
                            // 케이스 1: 쿼리 정보가 포함된 응답
                            return {
                                text: response.data.answer || '쿼리 결과 없음',
                                query_string: response.data.query_string,
                                query_result: response.data.query_result || [],
                                elapsed_time: response.data.elapsed_time,
                            };
                        } else if (response.data.elapsed_time) {
                            return {
                                text: response.data.answer || '쿼리 결과 없음',
                                elapsed_time: response.data.elapsed_time,
                            };
                        } else if (Array.isArray(response.data.answer)) {
                            // 기존 형식 - 배열 형태의 응답
                            const sortedItems = [...response.data.answer].sort(
                                (a, b) => a.rank_order - b.rank_order,
                            );
                            return {
                                text: sortedItems
                                    .map((item) => `${item.context}\n${item.title}\n${item.url}`)
                                    .join('\n\n'),
                            };
                        } else if (typeof response.data.answer === 'string') {
                            // 기존 형식 - 문자열 형태의 응답
                            return {
                                text: response.data.answer,
                            };
                        } else {
                            // 예상치 못한 형식
                            return {
                                text: JSON.stringify(response.data.answer),
                            };
                        }
                    }

                    return {
                        text: '죄송합니다. 유효한 응답 데이터를 받지 못했습니다.',
                    };
                } catch (error) {
                    // 오류 처리는 그대로 유지
                    if (axios.isCancel(error)) {
                        throw error;
                    }
                    console.error('봇 응답 API 호출 오류:', error);
                    return {
                        text: '죄송합니다. 응답을 처리하는 중에 오류가 발생했습니다. 다시 시도해 주세요.',
                    };
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
                messageText,
                inputRef,
                showCancelIcon,
                isCached, // 토글 상태 노출
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
                isSidebarOpen, // 사이드바 상태 노출
                toggleSidebar, // 사이드바 토글 함수 노출
                handleEnterKey,
                handleEscKey,
                autoResize,
                cancelRequest,
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
        position: relative;
        overflow-x: hidden; /* 너비 변경 시 스크롤바 방지 */
    }

    /* 채팅 목록 사이드바 스타일 */
    .chatbot-sidebar {
        min-width: 300px;
        width: 300px;
        height: 100%;
        background-color: #fff;
        border-right: 1px solid #e5e5e5;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
        z-index: 100;
        transition: transform 0.3s ease-in-out;
    }

    /* 모바일에서는 사이드바를 고정 위치에 표시 */
    @media (max-width: 767px) {
        .chatbot-sidebar {
            position: fixed;
            left: 0;
            top: 0;
        }
    }

    /* 사이드바 헤더 스타일 */
    .sidebar-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px;
        border-bottom: 1px solid #e5e5e5;
        background-color: #f8f9fa;
    }

    .sidebar-header h2 {
        margin: 0;
        font-size: 1.2rem;
        color: #333;
    }

    .close-sidebar-button {
        background: none;
        border: none;
        font-size: 1.5rem;
        cursor: pointer;
        color: #666;
        padding: 5px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        width: 30px;
        height: 30px;
        transition: background-color 0.2s;
    }

    .close-sidebar-button:hover {
        background-color: rgba(0, 0, 0, 0.05);
    }

    /* 사이드바 오버레이 스타일 */
    .sidebar-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 90;
    }

    /* 사이드바 애니메이션 트랜지션 */
    .slide-enter-active,
    .slide-leave-active {
        transition: transform 0.3s ease-in-out;
    }

    .slide-enter-from,
    .slide-leave-to {
        transform: translateX(-300px);
    }

    .slide-enter-to,
    .slide-leave-from {
        transform: translateX(0);
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
        transition: all 0.3s ease-in-out;
        will-change: width, flex; /* 브라우저에게 변경될 속성 힌트 제공 */
    }

    /* 사이드바 토글 버튼 스타일 */
    .sidebar-toggle-button {
        background: none;
        border: none;
        cursor: pointer;
        color: #333;
        padding: 5px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        transition: background-color 0.2s;
        position: absolute;
        left: 10px;
        top: 50%;
        transform: translateY(-50%);
    }

    .sidebar-toggle-button:hover {
        background-color: rgba(0, 0, 0, 0.05);
    }

    .chat-header {
        margin-bottom: 20px;
        padding-bottom: 15px;
        padding-left: 50px; /* 토글 버튼 공간 확보 */
        border-bottom: 1px solid #e5e5e5;
        position: relative;
        text-align: center;
        display: flex;
        justify-content: center;
        align-items: center;
        flex-direction: column;
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
        width: 250px;
        margin-bottom: 5px;
        cursor: pointer;
        color: #232f3e;
        font-size: 1.8rem;
    }

    .chat-header h1:hover {
        color: #007bff;
    }

    .chat-description {
        width: 200px;
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
    }

    /* 반응형 스타일 */
    @media (max-width: 768px) {
        .chatbot-container {
            flex-direction: column;
        }

        .chatbot-sidebar {
            width: 280px;
            position: fixed;
            left: 0;
            top: 0;
            height: 100%;
            z-index: 1000;
        }

        .chat-messages {
            max-height: calc(100vh - 220px);
        }

        .example-questions {
            grid-template-columns: 1fr;
        }

        .chat-header {
            padding-left: 45px;
        }
    }

    /* 채팅 입력 영역 새로운 스타일 */
    .input-container {
        margin-top: 20px;
    }

    .chat-input-wrapper {
        display: flex;
        align-items: center;
        background-color: #fff;
        border: 1px solid #e0e0e0;
        border-radius: 24px;
        padding: 8px 8px 8px 16px;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
        transition: all 0.3s;
        gap: 12px;
    }

    .chat-input-wrapper:focus-within {
        border-color: #90caf9;
        box-shadow: 0 4px 12px rgba(0, 123, 255, 0.1);
    }

    .chat-input {
        flex: 1;
        border: none;
        background: transparent;
        font-size: 1rem;
        line-height: 1.5;
        resize: none;
        outline: none;
        padding: 4px 0;
        max-height: 150px;
        min-height: 24px;
        font-family: inherit;
    }

    .chat-input::placeholder {
        color: #aaa;
    }

    .chat-input:disabled {
        background-color: transparent;
        color: #999;
    }

    /* 대화 컨텍스트 기억 토글 스타일 */
    .context-toggle-container {
        display: flex;
        align-items: center;
        margin: 0 8px;
        min-width: fit-content;
    }

    .context-toggle-label {
        display: flex;
        align-items: center;
        cursor: pointer;
        font-size: 0.85rem;
        color: #666;
        gap: 8px;
        padding: 4px 8px;
        border-radius: 12px;
        transition: background-color 0.2s;
        user-select: none;
        white-space: nowrap;
    }

    .context-toggle-label:hover {
        background-color: rgba(0, 123, 255, 0.05);
    }

    .context-toggle-input {
        display: none;
    }

    .context-toggle-slider {
        position: relative;
        width: 34px;
        height: 18px;
        background-color: #ccc;
        border-radius: 34px;
        transition: background-color 0.3s;
        flex-shrink: 0;
    }

    .context-toggle-slider::before {
        content: '';
        position: absolute;
        height: 14px;
        width: 14px;
        left: 2px;
        bottom: 2px;
        background-color: white;
        border-radius: 50%;
        transition: transform 0.3s;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
    }

    .context-toggle-input:checked + .context-toggle-slider {
        background-color: #007bff;
    }

    .context-toggle-input:checked + .context-toggle-slider::before {
        transform: translateX(16px);
    }

    .context-toggle-input:disabled + .context-toggle-slider {
        opacity: 0.6;
        cursor: not-allowed;
    }

    .context-toggle-text {
        font-weight: 500;
    }

    .send-button {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        background-color: #007bff;
        color: white;
        border: none;
        border-radius: 50%;
        cursor: pointer;
        transition: all 0.2s;
        flex-shrink: 0;
    }

    .send-button:hover:not(:disabled) {
        background-color: #0069d9;
        transform: scale(1.05);
    }

    .send-button:active:not(:disabled) {
        transform: scale(0.95);
    }

    .send-button:disabled {
        background-color: #b3d7ff;
        cursor: not-allowed;
    }

    .send-button.loading {
        background-color: #007bff;
    }

    .send-button.cancel-mode:hover {
        background-color: #dc3545; /* 빨간색 배경으로 변경 */
        transform: scale(1.05);
        cursor: pointer;
    }

    .loading-indicator {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 3px;
    }

    .loading-dot {
        width: 4px;
        height: 4px;
        background-color: white;
        border-radius: 50%;
        animation: loadingDotPulse 1.4s infinite ease-in-out;
    }

    .loading-dot:nth-child(1) {
        animation-delay: 0s;
    }

    .loading-dot:nth-child(2) {
        animation-delay: 0.2s;
    }

    .loading-dot:nth-child(3) {
        animation-delay: 0.4s;
    }

    .cancel-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
    }

    @keyframes loadingDotPulse {
        0%,
        60%,
        100% {
            transform: scale(1);
            opacity: 0.6;
        }
        30% {
            transform: scale(1.5);
            opacity: 1;
        }
    }

    /* 반응형 스타일 */
    @media (max-width: 768px) {
        .context-toggle-text {
            display: none;
        }

        .context-toggle-container {
            margin: 0 4px;
        }

        .chat-input-wrapper {
            gap: 8px;
            padding: 8px;
        }
    }
</style>
