<template>
    <AppLayout>
        <div class="chatbot-container">
            <!-- 좌측 사이드바 (채팅 세션 목록) -->
            <div class="chatbot-sidebar">
                <ChatHistory />
            </div>

            <!-- 메인 채팅 영역 -->
            <div class="chatbot-main">
                <div class="chat-header">
                    <h1 @click="handleGoMain">AWS Cloud Agent</h1>
                    <p class="chat-description">운영 정보/메뉴얼 질의</p>
                </div>

                <!-- 오류 메시지 표시 영역 -->
                <div v-if="store.error" class="error-message">
                    {{ store.error }}
                    <button @click="dismissError" class="dismiss-error">×</button>
                </div>

                <!-- 로딩 표시 -->
                <div v-if="initialLoading" class="loading-container">
                    <div class="loading-spinner"></div>
                    <p class="loading-text">메시지를 불러오는 중...</p>
                </div>

                <!-- 채팅 메시지 표시 영역 -->
                <div v-else class="chat-messages" ref="messagesContainer">
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
                            <img src="@/assets/aws-logo.svg" alt="AWS Logo" class="aws-logo" />
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
                                >
                                    비용 최적화를 위한 추천사항을 알려주세요.
                                </button>
                                <button
                                    @click="
                                        askExampleQuestion('IAM 정책 관리 모범 사례는 무엇인가요?')
                                    "
                                    class="example-question"
                                >
                                    IAM 정책 관리 모범 사례는 무엇인가요?
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 채팅 입력 영역 -->
                <div class="input-container">
                    <ChatInput
                        :disabled="store.waitingForResponse || initialLoading"
                        @send="sendMessage"
                    />
                </div>

                <!-- 채팅 관련 추가 액션 버튼들 -->
                <div
                    class="chat-actions"
                    v-if="store.currentSession && store.currentMessages.length > 0"
                >
                    <button @click="clearChat" class="clear-button">
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
    import AppLayout from '@/layouts/AppLayout.vue';
    import ChatHistory from '@/components/ChatHistory.vue';
    import ChatMessage from '@/components/ChatMessage.vue';
    import ChatInput from '@/components/ChatInput.vue';
    import { useChatHistoryStore } from '@/stores/chatHistoryStore';

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
            const initialLoading = ref(true);

            // 컴포넌트 마운트 시 초기화 로직
            onMounted(async () => {
                try {
                    // 채팅 세션 로드
                    if (store.sessions.length === 0) {
                        await store.fetchSessions();
                    }

                    // 세션이 없거나 첫 방문인 경우 새 세션 생성
                    if (!store.hasSessions || !store.currentSession) {
                        await store.createNewSession('새 대화');
                    }

                    // 세션 스토리지에 저장된 질문이 있는지 확인
                    const pendingQuestion = sessionStorage.getItem('pendingQuestion');
                    if (pendingQuestion) {
                        // 질문을 찾았으면 즉시 전송하고 세션스토리지에서 제거
                        await sendMessage(pendingQuestion);
                        sessionStorage.removeItem('pendingQuestion');
                    }
                } catch (error) {
                    console.error('초기화 오류:', error);
                    store.error = '대화 세션을 초기화하는 중 오류가 발생했습니다.';
                } finally {
                    // 로딩 완료
                    initialLoading.value = false;

                    // 메시지 목록 스크롤
                    nextTick(() => {
                        scrollToBottom();
                    });
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
            const sendMessage = async (text: string) => {
                if (!text.trim() || store.waitingForResponse || initialLoading.value) return;

                // 현재 세션이 없으면 새 세션 생성
                if (!store.currentSession) {
                    try {
                        await store.createNewSession('새 대화');
                    } catch (error) {
                        console.error('새 세션 생성 오류:', error);
                        return;
                    }
                }

                // 메시지 전송
                await store.sendMessage(text);
                scrollToBottom();
            };

            // 예시 질문 전송
            const askExampleQuestion = (question: string) => {
                sendMessage(question);
            };

            // 대화 내용 지우기
            const clearChat = async () => {
                if (confirm('대화 내용을 모두 지우시겠습니까?')) {
                    await store.clearMessages();
                }
            };

            // 오류 메시지 닫기
            const dismissError = () => {
                store.error = null;
            };

            // 메인 페이지로 이동
            const handleGoMain = () => {
                router.push('/start-chat');
            };

            return {
                store,
                messagesContainer,
                initialLoading,
                sendMessage,
                askExampleQuestion,
                clearChat,
                dismissError,
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

    /* 로딩 인디케이터 */
    .loading-container {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 40px;
    }

    .loading-spinner {
        width: 40px;
        height: 40px;
        border: 4px solid rgba(0, 123, 255, 0.1);
        border-left-color: #007bff;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-bottom: 16px;
    }

    .loading-text {
        color: #6c757d;
        font-size: 1rem;
    }

    @keyframes spin {
        to {
            transform: rotate(360deg);
        }
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

    .example-question:hover {
        background-color: #e1f0ff;
        border-color: #99caff;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
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

    .clear-button:hover {
        background-color: #f8f9fa;
        color: #495057;
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
