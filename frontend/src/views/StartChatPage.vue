<!-- src/views/StartChatPage.vue -->
<template>
    <AppLayout>
        <div class="start-chat-container">
            <div class="start-chat-header">
                <h1 @click="getHealth">AWS Cloud Agent</h1>
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

            <!-- 새로운 향상된 챗봇 페이지로 이동하는 버튼 추가 -->
            <div class="enhanced-chat-button-container">
                <button @click="goToEnhancedChat" class="enhanced-chat-button">
                    <span class="enhanced-chat-icon">🚀</span>
                    향상된 대화 기능 사용하기
                </button>
                <p class="enhanced-chat-description">
                    대화 기록 저장, 세션 관리, 타이핑 이펙트 등 향상된 기능을 사용해보세요!
                </p>
            </div>
        </div>
    </AppLayout>
</template>

<script lang="ts">
    import { defineComponent, ref } from 'vue';
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
            // 요청 중복 방지를 위한 플래그
            const isProcessing = ref(false);

            // 새 대화 시작 함수
            const startNewChat = async () => {
                if (!messageText.value.trim() || isProcessing.value) return;

                try {
                    isProcessing.value = true;

                    // 새 세션 생성 (API 호출)
                    const newSession = await chatHistoryStore.createNewSession();

                    if (newSession) {
                        // 세션이 성공적으로 생성되면 질문을 저장하고 채팅 페이지로 이동
                        sessionStorage.setItem('pendingQuestion', messageText.value);
                        router.push('/chat');
                    } else {
                        console.error('새 세션 생성 실패');
                        alert('새 대화를 시작할 수 없습니다. 다시 시도해 주세요.');
                    }
                } catch (error) {
                    console.error('새 세션 생성 중 오류 발생:', error);
                    alert('새 대화를 시작할 수 없습니다. 다시 시도해 주세요.');
                } finally {
                    isProcessing.value = false;
                }
            };

            // 예시 질문 클릭 처리
            const askExampleQuestion = (question: string) => {
                messageText.value = question;
                startNewChat();
            };

            // 향상된 채팅 페이지로 이동하는 함수
            const goToEnhancedChat = async () => {
                try {
                    if (messageText.value.trim()) {
                        isProcessing.value = true;

                        // 새 세션 생성 후 채팅 페이지로 이동
                        const newSession = await chatHistoryStore.createNewSession();

                        if (newSession) {
                            // 세션이 생성되면 질문 저장 후 이동
                            sessionStorage.setItem('pendingQuestion', messageText.value);
                        }
                    }

                    // 채팅 페이지로 이동
                    router.push('/chat');
                } catch (error) {
                    console.error('향상된 채팅 페이지 이동 중 오류 발생:', error);
                    // 오류가 있어도 채팅 페이지로 이동
                    router.push('/chat');
                } finally {
                    isProcessing.value = false;
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
                startNewChat,
                askExampleQuestion,
                goToEnhancedChat,
                getHealth,
            };
        },
    });
</script>

<style scoped>
    /* 스타일은 변경하지 않음 */
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
        transition: all 0.2s ease;
        color: #333;
        font-size: 0.95rem;
        font-weight: 400;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
    }

    .example-question:hover {
        background-color: #f0f7ff;
        border-color: #b3d9ff;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
    }

    .example-question:active {
        transform: translateY(0);
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }

    /* 새로운 향상된 채팅 버튼 스타일 */
    .enhanced-chat-button-container {
        margin-top: 1.5rem;
        text-align: center;
    }

    .enhanced-chat-button {
        padding: 1rem 2rem;
        font-size: 1.1rem;
        font-weight: 600;
        color: white;
        background-color: #ff9900;
        border: none;
        border-radius: 50px;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(255, 153, 0, 0.3);
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
    }

    .enhanced-chat-button:hover {
        background-color: #f08c00;
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(255, 153, 0, 0.4);
    }

    .enhanced-chat-icon {
        font-size: 1.3rem;
    }

    .enhanced-chat-description {
        margin-top: 1rem;
        color: #666;
        font-size: 0.9rem;
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
        }

        .send-button {
            width: 100%;
            padding: 0.8rem;
            border-radius: 12px;
        }
    }
</style>
