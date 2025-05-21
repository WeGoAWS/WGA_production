<!-- src/views/StartChatPage.vue -->
<template>
    <AppLayout>
        <!-- 새로 추가된 네비게이션 사이드바 -->
        <transition name="slide">
            <div v-if="isNavOpen" class="nav-sidebar">
                <div class="nav-header">
                    <h2>대화 내역</h2>
                    <button @click="toggleNav" class="close-nav-button">
                        <span>&times;</span>
                    </button>
                </div>

                <!-- 대화 내역 목록 -->
                <div v-if="chatHistoryStore.loading" class="nav-loading">
                    <div class="nav-spinner"></div>
                    <span>로딩 중...</span>
                </div>

                <div v-else-if="chatHistoryStore.hasSessions" class="nav-sessions">
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

                <div v-else class="nav-empty">
                    <p>대화 내역이 없습니다</p>
                    <button @click="loadSessions" class="nav-refresh-button">새로고침</button>
                </div>
            </div>
        </transition>

        <!-- 배경 오버레이 (모바일에서 네비게이션 열릴 때) -->
        <div v-if="isNavOpen" class="nav-overlay" @click="toggleNav"></div>

        <div class="start-chat-container">
            <div class="start-chat-header">
                <div class="header-content">
                    <!-- 새로 추가된 메뉴 버튼 -->
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
                    placeholder="AWS 클라우드 운영에 관한 질문을 입력하세요..."
                    @keydown.enter.prevent="startNewChat"
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
    import { defineComponent, onMounted, ref } from 'vue';
    import { useRouter } from 'vue-router';
    import AppLayout from '@/layouts/AppLayout.vue';
    import { useChatHistoryStore } from '@/stores/chatHistoryStore';
    import axios from 'axios';

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
                startNewChat();
            };

            const goToEnhancedChat = async () => {
                if (messageText.value.trim()) {
                    sessionStorage.setItem('pendingQuestion', messageText.value);
                }

                sessionStorage.setItem('createNewSession', 'true');

                router.push('/chat');
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

            const apiUrl = import.meta.env.VITE_API_DEST || 'http://localhost:8000';

            const getHealth = () => {
                axios.get(`${apiUrl}/health`, {
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    withCredentials: true,
                });
            };

            return {
                messageText,
                chatHistoryStore,
                isNavOpen,
                toggleNav,
                loadSessions,
                selectAndGoToChat,
                startNewChat,
                askExampleQuestion,
                goToEnhancedChat,
                formatDate,
                getHealth,
            };
        },
    });
</script>

<style scoped>
    /* 기존 스타일 */
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
        height: 60px;
        font-family: inherit;
        transition: border-color 0.3s;
        background-color: #fff;
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
        transition: all 0.3s ease; /* 전환 시간 0.2s에서 0.3s로 늘림 */
        color: #333;
        font-size: 0.95rem;
        font-weight: 400;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
    }

    .example-question:hover:not(:disabled) {
        background-color: #e1f0ff; /* 호버 시 좀 더 밝은 파란색 배경 */
        border-color: #99caff;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); /* 그림자 효과 강화 */
        color: #0056b3; /* 호버 시 텍스트 색상 변경 */
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

    /* 새로 추가된 네비게이션 토글 버튼 스타일 */
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

    /* 새로 추가된 네비게이션 사이드바 스타일 */
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

    /* 오버레이 스타일 */
    .nav-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(0, 0, 0, 0.5);
        z-index: 999;
        opacity: 0;
        transition: opacity 0.3s ease;
    }

    .nav-overlay {
        opacity: 1;
    }

    /* 애니메이션 트랜지션 스타일 추가 */
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

    /* 반응형 스타일 */
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
    }
</style>
