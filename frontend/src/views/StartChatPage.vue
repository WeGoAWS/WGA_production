<!-- src/views/StartChatPage.vue -->
<template>
    <AppLayout>
        <div class="start-chat-container">
            <div class="start-chat-header">
                <h1 @click="getHealth">AWS Agent</h1>
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
    import { defineComponent, ref } from 'vue';
    import { useRouter } from 'vue-router';
    import AppLayout from '@/layouts/AppLayout.vue';
    import { useChatbotStore } from '@/stores/chatbot';
    import axios from 'axios';

    export default defineComponent({
        name: 'StartChatPage',
        components: {
            AppLayout,
        },

        setup() {
            const router = useRouter();
            const store = useChatbotStore();
            const messageText = ref('');

            const startNewChat = async () => {
                if (!messageText.value.trim()) return;

                // 새 채팅 세션 생성
                store.createNewSession();

                // 메시지 저장 - 세션 생성 후에 메시지를 채팅 스토어에 저장만 하고
                // 실제 전송은 여기서 하지 않음
                sessionStorage.setItem('pendingQuestion', messageText.value);

                // 채팅 페이지로 이동
                router.push('/chatbot');
            };

            const askExampleQuestion = (question: string) => {
                messageText.value = question;
                startNewChat();
            };

            const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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
                getHealth,
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
    }

    .start-chat-header h1 {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
        color: #232f3e;
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

    .send-button {
        padding: 0 1.5rem;
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
</style>
