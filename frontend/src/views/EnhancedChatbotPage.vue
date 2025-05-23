<template>
    <AppLayout>
        <div class="chatbot-container">
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

            <div class="chatbot-main" :class="{ 'sidebar-open': isSidebarOpen }">
                <div class="chat-header">
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

                    <button @click="handleLogout" class="logout-button" title="로그아웃">
                        <svg
                            width="24"
                            height="24"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        >
                            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                            <polyline points="16,17 21,12 16,7" />
                            <line x1="21" y1="12" x2="9" y2="12" />
                        </svg>
                    </button>

                    <div v-if="store.waitingForResponse" class="processing-indicator">
                        <div class="processing-spinner"></div>
                        <span>질의 처리 중...</span>
                    </div>
                </div>

                <div v-if="store.error" class="error-message">
                    {{ store.error }}
                    <button @click="dismissError" class="dismiss-error">×</button>
                </div>

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

                <div class="chat-messages" ref="messagesContainer">
                    <template v-if="store.currentSession && store.currentMessages.length > 0">
                        <ChatMessage
                            v-for="message in store.currentMessages"
                            :key="message.id"
                            :message="message"
                        />
                    </template>

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

                <div class="input-container">
                    <div class="chat-input-wrapper">
                        <textarea
                            v-model="messageText"
                            class="chat-input"
                            placeholder="질문을 입력하세요..."
                            @keydown="handleKeydown"
                            :disabled="store.waitingForResponse"
                            ref="inputRef"
                            rows="1"
                            @input="autoResize"
                        ></textarea>

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

                        <div class="model-selector-container">
                            <div
                                class="model-selector"
                                :class="{ disabled: store.waitingForResponse }"
                                @click="toggleModelDropdown"
                                ref="modelSelectorRef"
                            >
                                <span class="selected-model">
                                    {{ modelsStore.selectedModel?.display_name || '모델 선택' }}
                                </span>
                                <span class="dropdown-arrow" :class="{ open: isModelDropdownOpen }">
                                    ▼
                                </span>

                                <transition name="dropdown">
                                    <div
                                        v-if="isModelDropdownOpen"
                                        class="model-dropdown"
                                        @click.stop
                                    >
                                        <div
                                            v-for="model in modelsStore.models"
                                            :key="model.id"
                                            class="model-option"
                                            :class="{
                                                selected:
                                                    modelsStore.selectedModel?.id === model.id,
                                            }"
                                            @click="selectModel(model.id)"
                                        >
                                            {{ model.display_name }}
                                        </div>
                                    </div>
                                </transition>
                            </div>
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
    import { computed, defineComponent, nextTick, onMounted, ref, watch } from 'vue';
    import { useRouter } from 'vue-router';
    import axios from 'axios';
    import AppLayout from '@/layouts/AppLayout.vue';
    import ChatHistory from '@/components/ChatHistory.vue';
    import ChatMessage from '@/components/ChatMessage.vue';
    import { useChatHistoryStore } from '@/stores/chatHistoryStore';
    import type { BotResponse } from '@/types/chat';
    import { useModelsStore } from '@/stores/models';
    import { useSettingsStore } from '@/stores/settings.ts';

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
            const settingsStore = useSettingsStore();
            const messagesContainer = ref<HTMLElement | null>(null);
            const initialSetupDone = ref(false);
            const pendingQuestionProcessed = ref(false);
            const messageText = ref('');
            const inputRef = ref<HTMLTextAreaElement | null>(null);
            const showCancelIcon = ref(false);

            const showSessionChangeWarning = ref(false);
            const targetSessionId = ref<string | null>(null);

            const isSidebarOpen = ref(false);

            const isModelDropdownOpen = ref(false);
            const modelSelectorRef = ref<HTMLElement | null>(null);

            const modelsStore = useModelsStore();

            const isCached = computed({
                get: () => settingsStore.isCached,
                set: (value: boolean) => settingsStore.setIsCached(value),
            });

            const toggleSidebar = () => {
                isSidebarOpen.value = !isSidebarOpen.value;
            };

            const handleResize = () => {
                if (window.innerWidth < 768 && isSidebarOpen.value) {
                    isSidebarOpen.value = false;
                }
            };

            const toggleModelDropdown = () => {
                if (store.waitingForResponse) return;
                isModelDropdownOpen.value = !isModelDropdownOpen.value;
            };

            const selectModel = (modelId: string) => {
                modelsStore.selectModel(modelId);
                isModelDropdownOpen.value = false;
            };

            const handleClickOutside = (event: Event) => {
                if (
                    modelSelectorRef.value &&
                    !modelSelectorRef.value.contains(event.target as Node)
                ) {
                    isModelDropdownOpen.value = false;
                }
            };

            const handleEnterKey = (e: KeyboardEvent) => {
                if (e.shiftKey) return;

                if (store.waitingForResponse) {
                    cancelRequest();
                } else {
                    sendMessage();
                }
            };

            const handleKeydown = (e: KeyboardEvent) => {
                if (e.key === 'Enter') {
                    if (e.shiftKey) {
                        return;
                    } else {
                        e.preventDefault();
                        if (store.waitingForResponse) {
                            cancelRequest();
                        } else {
                            sendMessage();
                        }
                    }
                } else if (e.key === 'Escape') {
                    if (store.waitingForResponse) {
                        cancelRequest();
                    }
                }
            };

            const handleEscKey = () => {
                console.log('handleEscKey 호출됨, waitingForResponse:', store.waitingForResponse);
                if (store.waitingForResponse) {
                    console.log('ESC로 요청 취소 시도');
                    cancelRequest();
                } else {
                    console.log('취소할 요청이 없음');
                }
            };

            const autoResize = () => {
                if (!inputRef.value) return;

                inputRef.value.style.height = 'auto';

                const newHeight = Math.min(inputRef.value.scrollHeight, 150);
                inputRef.value.style.height = `${newHeight}px`;
            };

            const cancelRequest = () => {
                console.log('취소 요청 중...');
                if (store.waitingForResponse) {
                    store.cancelRequest();
                    showCancelIcon.value = false;
                    console.log('취소 요청 완료');
                } else {
                    console.log('취소할 요청이 없습니다');
                }
            };

            onMounted(async () => {
                try {
                    settingsStore.loadFromStorage();
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

                    window.addEventListener('resize', handleResize);

                    const handleGlobalKeydown = (e: KeyboardEvent) => {
                        if (e.key === 'Escape') {
                            console.log('ESC 키가 눌렸습니다');
                            handleEscKey();
                        }
                    };

                    document.addEventListener('keydown', handleGlobalKeydown);

                    return () => {
                        window.removeEventListener('resize', handleResize);
                        document.removeEventListener('keydown', handleGlobalKeydown);
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

                    if (!text) {
                        messageText.value = '';
                        if (inputRef.value) {
                            inputRef.value.style.height = 'auto';
                        }
                    }

                    if (window.innerWidth < 768) {
                        isSidebarOpen.value = false;
                    }

                    await store.sendMessage(messageToSend, settingsStore.isCached);

                    await nextTick();
                    scrollToBottom();
                } catch (error) {
                    console.error('메시지 전송 중 오류 발생:', error);
                    if (!axios.isCancel(error)) {
                        store.error = '메시지를 전송하는 중 오류가 발생했습니다.';
                    }
                }
            };

            const askExampleQuestion = async (question: string) => {
                if (store.waitingForResponse) return;

                try {
                    await sendMessage(question);
                } catch (error) {
                    console.error('예시 질문 전송 오류:', error);
                    store.error = '메시지를 전송하는 중 오류가 발생했습니다.';
                }
            };

            const handleSessionClick = (sessionId: string) => {
                if (store.waitingForResponse) {
                    targetSessionId.value = sessionId;
                    showSessionChangeWarning.value = true;
                } else {
                    store.selectSession(sessionId);

                    if (window.innerWidth < 768) {
                        isSidebarOpen.value = false;
                    }
                }
            };

            const cancelSessionChange = () => {
                targetSessionId.value = null;
                showSessionChangeWarning.value = false;
            };

            const confirmSessionChange = async () => {
                if (targetSessionId.value) {
                    store.cancelRequest();
                    store.waitingForResponse = false;

                    await store.selectSession(targetSessionId.value);

                    if (window.innerWidth < 768) {
                        isSidebarOpen.value = false;
                    }

                    targetSessionId.value = null;
                    showSessionChangeWarning.value = false;
                }
            };

            const generateBotResponse = async (userMessage: string): Promise<BotResponse> => {
                try {
                    const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';

                    const headers: Record<string, string> = {
                        'Content-Type': 'application/json',
                    };

                    if (modelsStore.selectedModel?.id) {
                        headers['modelId'] = modelsStore.selectedModel.id;
                    }

                    const response = await axios.post(
                        `${apiUrl}/llm1`,
                        {
                            text: userMessage,
                            sessionId: store.currentSession?.sessionId,
                            isCached: isCached.value,
                            modelId: modelsStore.selectedModel.id,
                        },
                        {
                            headers,
                            withCredentials: true,
                            cancelToken: store.apiCancelToken
                                ? store.apiCancelToken.token
                                : undefined,
                        },
                    );

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
                        } else if (response.data.elapsed_time) {
                            return {
                                text: response.data.answer || '쿼리 결과 없음',
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
                            };
                        } else if (typeof response.data.answer === 'string') {
                            return {
                                text: response.data.answer,
                            };
                        } else {
                            return {
                                text: JSON.stringify(response.data.answer),
                            };
                        }
                    }

                    return {
                        text: '죄송합니다. 유효한 응답 데이터를 받지 못했습니다.',
                    };
                } catch (error) {
                    if (axios.isCancel(error)) {
                        throw error;
                    }
                    console.error('봇 응답 API 호출 오류:', error);
                    return {
                        text: '죄송합니다. 응답을 처리하는 중에 오류가 발생했습니다. 다시 시도해 주세요.',
                    };
                }
            };

            const simulateTyping = async (messageId: string, fullText: string) => {
                if (!store.currentSession || !Array.isArray(store.currentSession.messages)) return;

                const message = store.currentSession.messages.find((m) => m.id === messageId);
                if (!message) return;

                const typingSpeed = 10;
                const maxTypingTime = 2000;

                const totalTypingTime = Math.min(fullText.length * typingSpeed, maxTypingTime);
                const charInterval = totalTypingTime / fullText.length;

                message.displayText = '';

                for (let i = 0; i < fullText.length; i++) {
                    await new Promise((resolve) => setTimeout(resolve, charInterval));

                    if (!store.currentSession || !Array.isArray(store.currentSession.messages)) {
                        return;
                    }

                    const updatedMessage = store.currentSession.messages.find(
                        (m) => m.id === messageId,
                    );
                    if (!updatedMessage) return;

                    updatedMessage.displayText = fullText.substring(0, i + 1);
                }

                if (!store.currentSession || !Array.isArray(store.currentSession.messages)) return;

                const completedMessage = store.currentSession.messages.find(
                    (m) => m.id === messageId,
                );
                if (completedMessage) {
                    completedMessage.animationState = 'complete';
                }
            };

            const clearChat = async () => {
                if (store.waitingForResponse) return;

                if (confirm('대화 내용을 모두 지우시겠습니까?')) {
                    try {
                        await store.clearMessages();
                    } catch (error) {
                        console.error('대화 내용 지우기 오류:', error);
                        store.error = '대화 내용을 지우는 중 오류가 발생했습니다.';
                    }
                }
            };

            const dismissError = () => {
                store.error = null;
            };

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

            const handleLogout = () => {
                localStorage.clear();
                window.location.reload();
            };

            return {
                store,
                messagesContainer,
                messageText,
                inputRef,
                showCancelIcon,
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
                isSidebarOpen,
                toggleSidebar,
                handleEnterKey,
                handleEscKey,
                handleKeydown,
                autoResize,
                cancelRequest,
                toggleModelDropdown,
                selectModel,
                handleClickOutside,
                modelsStore,
                isModelDropdownOpen,
                settingsStore,
                isCached,
                handleLogout,
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
        overflow-x: hidden;
    }

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

    @media (max-width: 767px) {
        .chatbot-sidebar {
            position: fixed;
            left: 0;
            top: 0;
        }
    }

    .sidebar-header h2 {
        margin: 0;
        font-size: 1.2rem;
        color: #333;
    }

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
        padding: 0 20px;
        position: relative;
        background-color: #f8f9fa;
        overflow: hidden;
        transition: all 0.3s ease-in-out;
        will-change: width, flex;
    }

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
        padding-left: 50px;
        border-bottom: 1px solid #e5e5e5;
        position: relative;
        text-align: center;
        display: flex;
        justify-content: center;
        align-items: center;
        flex-direction: column;
    }

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
        background-color: #dc3545;
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

    .sidebar-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px;
        border-bottom: 1px solid #e5e5e5;
        background-color: #f8f9fa;
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

    .sidebar-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 90;
    }

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

    .model-selector-container {
        display: flex;
        align-items: center;
        margin: 0 8px;
        min-width: fit-content;
    }

    .model-selector {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-width: 120px;
        padding: 4px 8px;
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        cursor: pointer;
        font-size: 0.85rem;
        color: #495057;
        transition: all 0.2s ease;
        user-select: none;
    }

    .model-selector:hover:not(.disabled) {
        background-color: #e9ecef;
        border-color: #adb5bd;
    }

    .model-selector.disabled {
        opacity: 0.6;
        cursor: not-allowed;
        background-color: #f8f9fa;
    }

    .selected-model {
        flex: 1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-right: 8px;
        font-weight: 500;
    }

    .dropdown-arrow {
        font-size: 0.7rem;
        transition: transform 0.3s ease;
        color: #6c757d;
        flex-shrink: 0;
    }

    .dropdown-arrow.open {
        transform: rotate(180deg);
    }

    .model-dropdown {
        position: absolute;
        left: 0;
        right: 0;
        bottom: 35px;
        width: fit-content;
        background-color: white;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 1000;
        margin-top: 4px;
        max-height: 200px;
        overflow-y: auto;
    }

    .model-option {
        width: initial;
        padding: 8px 12px;
        cursor: pointer;
        transition: background-color 0.2s ease;
        font-size: 0.85rem;
        border-bottom: 1px solid #f8f9fa;
    }

    .model-option:last-child {
        border-bottom: none;
    }

    .model-option:hover {
        background-color: #e9f5ff;
        color: #0056b3;
    }

    .model-option.selected {
        background-color: #e3f2fd;
        color: #0d47a1;
        font-weight: 600;
    }

    .model-option.selected:hover {
        background-color: #bbdefb;
    }

    .dropdown-enter-active,
    .dropdown-leave-active {
        transition: all 0.3s ease;
        transform-origin: top;
    }

    .dropdown-enter-from,
    .dropdown-leave-to {
        opacity: 0;
        transform: scaleY(0.8) translateY(-8px);
    }

    .dropdown-enter-to,
    .dropdown-leave-from {
        opacity: 1;
        transform: scaleY(1) translateY(0);
    }

    @media (max-width: 768px) {
        .model-selector-container {
            margin: 0 4px;
        }

        .model-selector {
            min-width: 100px;
            padding: 4px 6px;
        }

        .selected-model {
            font-size: 0.8rem;
            margin-right: 6px;
        }
    }

    .logout-button {
        position: absolute;
        right: 0;
        top: 50%;
        transform: translateY(-50%);
        background: none;
        border: none;
        color: #6c757d;
        cursor: pointer;
        padding: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        width: 36px;
        height: 36px;
        transition: all 0.2s ease;
    }

    .logout-button:hover {
        background-color: rgba(220, 53, 69, 0.1);
        color: #dc3545;
    }

    .logout-button:active {
        transform: translateY(-50%) scale(0.95);
    }
</style>
