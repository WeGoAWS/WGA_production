<!-- src/views/StartChatPage.vue -->
<template>
    <AppLayout>
        <transition name="slide">
            <div v-if="isNavOpen" class="nav-sidebar">
                <div class="nav-header">
                    <h2>대화 내역</h2>
                    <button @click="toggleNav" class="close-nav-button">
                        <span>&times;</span>
                    </button>
                </div>

                <div v-if="chatHistoryStore.loading" class="nav-loading">
                    <div class="nav-spinner"></div>
                    <span>로딩 중...</span>
                </div>

                <div v-else-if="chatHistoryStore.hasSessions" class="nav-sessions">
                    <div class="nav-sessions-list">
                        <div
                            v-for="session in chatHistoryStore.sessions"
                            :key="session.sessionId"
                            class="nav-session-item"
                            @click="selectAndGoToChat(session.sessionId)"
                        >
                            <div class="session-title">{{ session.title }}</div>
                            <div class="session-date">{{ formatDate(session.updatedAt) }}</div>
                        </div>
                    </div>

                    <button @click="confirmDeleteAllSessions" class="delete-all-button">
                        <svg
                            width="20"
                            height="20"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        >
                            <polyline points="3,6 5,6 21,6"></polyline>
                            <path
                                d="m19,6v14a2,2 0 0,1 -2,2H7a2,2 0 0,1 -2,-2V6m3,0V4a2,2 0 0,1 2,-2h4a2,2 0 0,1 2,2v2"
                            ></path>
                            <line x1="10" y1="11" x2="10" y2="17"></line>
                            <line x1="14" y1="11" x2="14" y2="17"></line>
                        </svg>
                        <span>대화 전체 삭제</span>
                    </button>
                </div>

                <div v-else class="nav-empty">
                    <p>대화 내역이 없습니다</p>
                    <button @click="loadSessions" class="nav-refresh-button">새로고침</button>
                </div>

                <div v-if="showDeleteAllConfirm" class="delete-modal">
                    <div class="delete-modal-content">
                        <h3>⚠️ 전체 대화 삭제 확인</h3>
                        <p>모든 대화를 삭제하시겠습니까?</p>
                        <p class="warning">
                            이 작업은 되돌릴 수 없으며, 모든 대화 내역이 영구적으로 삭제됩니다.
                        </p>
                        <div class="delete-actions">
                            <button @click="cancelDeleteAll" class="cancel-button">취소</button>
                            <button @click="confirmDeleteAll" class="delete-confirm-button">
                                전체 삭제
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </transition>

        <div v-if="isNavOpen" class="nav-overlay" @click="toggleNav"></div>

        <div class="start-chat-container">
            <div class="start-chat-header">
                <div class="header-content">
                    <button @click="toggleNav" class="nav-toggle-button">
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

                    <h1 @click="getHealth">AWS Cloud Agent</h1>
                </div>
                <p class="start-chat-description">클라우드 운영 정보 질의응답 서비스</p>
            </div>

            <div class="start-chat-input-container">
                <textarea
                    v-model="messageText"
                    class="start-chat-input"
                    placeholder="AWS 클라우드 운영에 관한 질문을 물어보세요!"
                    @keydown="handleKeydown"
                    ref="inputRef"
                    rows="1"
                    @input="autoResize"
                ></textarea>
                <button @click="startNewChat" class="send-button" :disabled="!messageText.trim()">
                    <span>질문하기</span>
                    <svg
                        width="20"
                        height="20"
                        viewBox="0 0 24 24"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                        style="margin-left: 8px"
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

            <div class="example-questions-container">
                <h2>자주 묻는 질문 예시</h2>
                <div class="example-questions">
                    <div class="question-category">
                        <h3>리소스 모니터링</h3>
                        <button
                            @click="
                                askExampleQuestion(
                                    '지난 24시간 동안 CPU 사용률이 가장 높았던 EC2 인스턴스는 무엇인가요?',
                                )
                            "
                            class="example-question"
                        >
                            지난 24시간 동안 CPU 사용률이 가장 높았던 EC2 인스턴스는 무엇인가요?
                        </button>
                        <button
                            @click="
                                askExampleQuestion(
                                    '이번 달 메모리 사용량이 가장 많은 Lambda 함수 Top 5를 알려주세요.',
                                )
                            "
                            class="example-question"
                        >
                            이번 달 메모리 사용량이 가장 많은 Lambda 함수 Top 5를 알려주세요.
                        </button>
                    </div>

                    <div class="question-category">
                        <h3>보안 감사</h3>
                        <button
                            @click="
                                askExampleQuestion(
                                    '최근 7일간 발생한 보안 이벤트를 심각도 순으로 정리해주세요.',
                                )
                            "
                            class="example-question"
                        >
                            최근 7일간 발생한 보안 이벤트를 심각도 순으로 정리해주세요.
                        </button>
                        <button
                            @click="
                                askExampleQuestion('어제 루트 계정으로 로그인한 기록이 있나요?')
                            "
                            class="example-question"
                        >
                            어제 루트 계정으로 로그인한 기록이 있나요?
                        </button>
                    </div>

                    <div class="question-category">
                        <h3>비용 관리</h3>
                        <button
                            @click="
                                askExampleQuestion(
                                    '지난 달 대비 이번 달 비용이 가장 많이 증가한 서비스 3가지를 알려주세요.',
                                )
                            "
                            class="example-question"
                        >
                            지난 달 대비 이번 달 비용이 가장 많이 증가한 서비스 3가지를 알려주세요.
                        </button>
                        <button
                            @click="
                                askExampleQuestion(
                                    '비용 최적화를 위해 삭제 가능한 미사용 리소스가 있나요?',
                                )
                            "
                            class="example-question"
                        >
                            비용 최적화를 위해 삭제 가능한 미사용 리소스가 있나요?
                        </button>
                    </div>

                    <div class="question-category">
                        <h3>권한 관리</h3>
                        <button
                            @click="
                                askExampleQuestion(
                                    '지난 30일간 IAM 권한이 변경된 사용자 목록을 보여주세요.',
                                )
                            "
                            class="example-question"
                        >
                            지난 30일간 IAM 권한이 변경된 사용자 목록을 보여주세요.
                        </button>
                        <button
                            @click="
                                askExampleQuestion('최소 권한 원칙에 위배되는 IAM 정책이 있나요?')
                            "
                            class="example-question"
                        >
                            최소 권한 원칙에 위배되는 IAM 정책이 있나요?
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </AppLayout>
</template>

<script lang="ts">
    import { defineComponent, nextTick, onMounted, ref } from 'vue';
    import { useRouter } from 'vue-router';
    import AppLayout from '@/layouts/AppLayout.vue';
    import { useChatHistoryStore } from '@/stores/chatHistoryStore';
    import { useModelsStore } from '@/stores/models.ts';

    export default defineComponent({
        name: 'StartChatPage',
        components: {
            AppLayout,
        },

        setup() {
            const router = useRouter();
            const chatHistoryStore = useChatHistoryStore();
            const messageText = ref('');
            const isNavOpen = ref(false);
            const inputRef = ref<HTMLTextAreaElement | null>(null);

            const showDeleteAllConfirm = ref(false);

            onMounted(async () => {
                if (chatHistoryStore.sessions.length === 0) {
                    try {
                        await chatHistoryStore.fetchSessions();
                    } catch (error) {
                        console.error('세션 로드 중 오류 발생:', error);
                    }
                }
            });

            const toggleNav = () => {
                isNavOpen.value = !isNavOpen.value;
            };

            const loadSessions = async () => {
                try {
                    await chatHistoryStore.fetchSessions();
                } catch (error) {
                    console.error('세션 로드 중 오류 발생:', error);
                }
            };

            const selectAndGoToChat = async (sessionId: string) => {
                try {
                    await chatHistoryStore.selectSession(sessionId);
                    router.push('/chat');
                } catch (error) {
                    console.error('세션 선택 중 오류 발생:', error);
                }
            };

            const handleKeydown = (e: KeyboardEvent) => {
                if (e.key === 'Enter') {
                    if (e.shiftKey) {
                        return;
                    } else {
                        e.preventDefault();
                        startNewChat();
                    }
                }
            };

            const autoResize = () => {
                if (!inputRef.value) return;

                inputRef.value.style.height = 'auto';

                const newHeight = Math.min(inputRef.value.scrollHeight, 150);
                inputRef.value.style.height = `${newHeight}px`;
            };

            const startNewChat = async () => {
                if (!messageText.value.trim()) return;

                try {
                    sessionStorage.setItem('pendingQuestion', messageText.value);
                    sessionStorage.setItem('createNewSession', 'true');

                    router.push('/chat');
                } catch (error) {
                    console.error('새 대화 시작 중 오류 발생:', error);
                    alert('새 대화를 시작할 수 없습니다. 다시 시도해 주세요.');
                }
            };

            const askExampleQuestion = (question: string) => {
                messageText.value = question;

                nextTick(() => {
                    autoResize();
                });

                startNewChat();
            };

            const goToEnhancedChat = async () => {
                if (messageText.value.trim()) {
                    sessionStorage.setItem('pendingQuestion', messageText.value);
                }

                sessionStorage.setItem('createNewSession', 'true');

                router.push('/chat');
            };

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

            const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';

            const modelsStore = useModelsStore();
            const getHealth = async () => {
                try {
                    await modelsStore.fetchModels();
                    console.log('Models loaded:', modelsStore.models);
                } catch (error) {
                    console.error('Health check / Models load error:', error);
                }
            };

            const confirmDeleteAllSessions = () => {
                showDeleteAllConfirm.value = true;
            };

            const cancelDeleteAll = () => {
                showDeleteAllConfirm.value = false;
            };

            const confirmDeleteAll = async () => {
                try {
                    await chatHistoryStore.deleteAllSessions();
                    showDeleteAllConfirm.value = false;
                    console.log('모든 대화가 성공적으로 삭제되었습니다.');
                } catch (error) {
                    console.error('전체 세션 삭제 오류:', error);
                    alert('전체 대화 삭제 중 오류가 발생했습니다. 다시 시도해 주세요.');
                }
            };

            return {
                messageText,
                chatHistoryStore,
                isNavOpen,
                inputRef,
                showDeleteAllConfirm,
                toggleNav,
                loadSessions,
                selectAndGoToChat,
                startNewChat,
                askExampleQuestion,
                goToEnhancedChat,
                formatDate,
                getHealth,
                handleKeydown,
                autoResize,
                confirmDeleteAllSessions,
                cancelDeleteAll,
                confirmDeleteAll,
            };
        },
    });
</script>

<style scoped>
    .start-chat-container {
        max-width: 900px;
        margin: 0 auto;
        padding: 2rem;
        display: flex;
        flex-direction: column;
        align-items: center;
    }

    .start-chat-header {
        text-align: center;
        margin-bottom: 2rem;
        width: 100%;
    }

    .header-content {
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
    }

    .start-chat-header h1 {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
        color: #232f3e;
        cursor: grab;
    }

    .start-chat-description {
        font-size: 1.2rem;
        color: #666;
    }

    .start-chat-input-container {
        width: 100%;
        max-width: 768px;
        display: flex;
        margin-bottom: 3rem;
        position: relative;
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
        border-radius: 12px;
        transition: all 0.3s ease;
    }

    .start-chat-input-container:focus-within {
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
        transform: translateY(-2px);
    }

    .start-chat-input {
        flex: 1;
        padding: 1.25rem 1.5rem;
        font-size: 1rem;
        border: 1px solid #e0e0e0;
        border-radius: 12px 0 0 12px;
        resize: none;
        height: auto;
        min-height: 60px;
        max-height: 150px;
        font-family: inherit;
        transition: border-color 0.3s;
        background-color: #fff;
        line-height: 1.5;
    }

    .start-chat-input:focus {
        outline: none;
        border-color: #007bff;
    }

    .send-button {
        padding: 0 1.8rem;
        background-color: #007bff;
        color: white;
        border: none;
        border-radius: 0 12px 12px 0;
        cursor: pointer;
        font-size: 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .send-button:hover:not(:disabled) {
        background-color: #0056b3;
    }

    .send-button:active:not(:disabled) {
        transform: scale(0.98);
    }

    .send-button:disabled {
        background-color: #b3d9ff;
        cursor: not-allowed;
    }

    .example-questions-container {
        width: 100%;
        margin-bottom: 3rem;
    }

    .example-questions-container h2 {
        text-align: center;
        margin-bottom: 1.5rem;
        color: #232f3e;
        font-weight: 600;
    }

    .example-questions {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
        gap: 1.5rem;
    }

    .question-category {
        background-color: #f8f9fa;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        transition: transform 0.3s ease;
    }

    .question-category:hover {
        transform: translateY(-4px);
    }

    .question-category h3 {
        margin-bottom: 1rem;
        color: #232f3e;
        font-size: 1.1rem;
        padding-bottom: 0.7rem;
        border-bottom: 1px solid #dee2e6;
        font-weight: 600;
    }

    .example-question {
        display: block;
        width: 100%;
        text-align: left;
        padding: 0.9rem 1.2rem;
        margin-bottom: 0.8rem;
        background-color: white;
        border: 1px solid #e6e6e6;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.3s ease;
        color: #333;
        font-size: 0.95rem;
        font-weight: 400;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
    }

    .example-question:hover:not(:disabled) {
        background-color: #e1f0ff;
        border-color: #99caff;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        color: #0056b3;
    }

    .example-question:active {
        transform: translateY(0);
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        background-color: #d4e7ff;
    }

    .example-question:disabled {
        opacity: 0.6;
        cursor: not-allowed;
        transform: none;
        box-shadow: none;
    }

    .nav-toggle-button {
        position: absolute;
        left: 0;
        top: 50%;
        transform: translateY(-50%);
        background: none;
        border: none;
        color: #232f3e;
        font-size: 1.5rem;
        cursor: pointer;
        padding: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        transition: background-color 0.3s;
    }

    .nav-toggle-button:hover {
        background-color: rgba(0, 0, 0, 0.05);
    }

    .nav-sidebar {
        position: fixed;
        left: 0;
        top: 0;
        width: 320px;
        height: 100vh;
        background-color: #fff;
        z-index: 1000;
        box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .nav-header {
        padding: 20px;
        border-bottom: 1px solid #eee;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .nav-header h2 {
        margin: 0;
        font-size: 1.5rem;
        color: #232f3e;
    }

    .close-nav-button {
        background: none;
        border: none;
        font-size: 1.5rem;
        cursor: pointer;
        color: #666;
        padding: 5px 10px;
        border-radius: 5px;
        transition: background-color 0.3s;
    }

    .close-nav-button:hover {
        background-color: rgba(0, 0, 0, 0.05);
    }

    .nav-sessions {
        flex: 1;
        overflow-y: auto;
        padding: 15px;
        display: flex;
        flex-direction: column;
        position: relative;
    }

    .nav-sessions-list {
        flex: 1;
        padding-bottom: 72px;
    }

    .nav-session-item {
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        cursor: pointer;
        transition: all 0.2s;
        background-color: #f8f9fa;
        border: 1px solid #eaeaea;
    }

    .nav-session-item:hover {
        background-color: #e9f5ff;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
    }

    .session-title {
        font-weight: 500;
        margin-bottom: 6px;
        word-break: break-word;
    }

    .session-date {
        font-size: 0.8rem;
        color: #666;
    }

    .nav-loading {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 30px;
        color: #666;
    }

    .nav-spinner {
        width: 40px;
        height: 40px;
        border: 4px solid rgba(0, 123, 255, 0.2);
        border-top: 4px solid #007bff;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-bottom: 15px;
    }

    @keyframes spin {
        0% {
            transform: rotate(0deg);
        }
        100% {
            transform: rotate(360deg);
        }
    }

    .nav-empty {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 20px;
        color: #666;
    }

    .nav-refresh-button {
        margin-top: 15px;
        padding: 8px 16px;
        background-color: #007bff;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        transition: background-color 0.3s;
    }

    .nav-refresh-button:hover {
        background-color: #0056b3;
    }

    .nav-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(0, 0, 0, 0.5);
        z-index: 999;
        opacity: 1;
        transition: opacity 0.3s ease;
    }

    .delete-all-button {
        position: absolute;
        bottom: 0;
        left: 20px;
        bottom: 20px;
        width: 280px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        height: 60px;
        margin: 0;
        background-color: #f8f9fa;
        border: 1px solid #dc3545;
        border-radius: 8px;
        color: #dc3545;
        cursor: pointer;
        font-weight: 500;
        font-size: 0.95rem;
        transition: all 0.2s ease;
        z-index: 10;
        box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
    }

    .delete-all-button:hover:not(:disabled) {
        background-color: #dc3545;
        color: white;
        box-shadow: 0 -4px 15px rgba(220, 53, 69, 0.3);
    }

    .delete-all-button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
    }

    .delete-all-button svg {
        flex-shrink: 0;
    }

    .delete-modal {
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

    .delete-modal-content {
        background-color: white;
        padding: 24px;
        border-radius: 12px;
        width: 90%;
        max-width: 400px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    }

    .delete-modal-content h3 {
        margin-top: 0;
        margin-bottom: 16px;
    }

    .delete-actions {
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

    .delete-confirm-button {
        padding: 8px 16px;
        background-color: #dc3545;
        color: white;
        border: none;
        border-radius: 6px;
        cursor: pointer;
    }

    .cancel-button:hover {
        background-color: #e0e0e0;
    }

    .delete-confirm-button:hover {
        background-color: #c82333;
    }

    .warning {
        color: #dc3545;
        font-size: 0.9rem;
        margin-bottom: 20px;
    }

    @media (max-width: 768px) {
        .example-questions {
            grid-template-columns: 1fr;
        }

        .start-chat-input-container {
            flex-direction: column;
            box-shadow: none;
        }

        .start-chat-input {
            border-radius: 12px;
            border: 1px solid #e0e0e0;
            margin-bottom: 0.5rem;
            min-height: 50px;
            max-height: 120px;
            padding: 1rem 1.2rem;
        }

        .send-button {
            width: 100%;
            padding: 0.8rem;
            border-radius: 12px;
        }

        .nav-sidebar {
            width: 85%;
            max-width: 320px;
        }

        .start-chat-header h1 {
            font-size: 2rem;
        }

        .delete-all-button {
            height: 55px;
            font-size: 0.9rem;
            width: 260px;
        }

        .nav-sessions-list {
            padding-bottom: 68px;
        }

        .delete-modal-content {
            padding: 16px;
            width: 95%;
        }
    }

    .slide-enter-active,
    .slide-leave-active {
        transition:
            transform 0.3s ease,
            opacity 0.3s ease;
    }

    .slide-enter-from,
    .slide-leave-to {
        transform: translateX(-100%);
        opacity: 0;
    }

    .slide-enter-to,
    .slide-leave-from {
        transform: translateX(0);
        opacity: 1;
    }
</style>
