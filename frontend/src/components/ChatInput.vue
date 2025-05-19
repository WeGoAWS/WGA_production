<template>
    <div class="chat-input-container">
        <textarea
            v-model="messageText"
            class="chat-input"
            placeholder="질문을 입력하세요..."
            @keydown.enter.prevent="handleEnterKey"
            @keydown.esc="handleEscKey"
            :disabled="disabled"
            ref="inputRef"
            rows="1"
            @input="autoResize"
        ></textarea>

        <button
            @click="disabled ? cancelRequest() : sendMessage()"
            class="send-button"
            :disabled="!messageText.trim() && !disabled"
            :class="{ loading: disabled, 'cancel-mode': disabled }"
            @mouseenter="showCancelIcon = true"
            @mouseleave="showCancelIcon = false"
        >
            <span v-if="disabled && !showCancelIcon" class="loading-indicator">
                <span class="loading-dot"></span>
                <span class="loading-dot"></span>
                <span class="loading-dot"></span>
            </span>
            <span v-else-if="disabled && showCancelIcon" class="cancel-icon">
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
</template>

<script lang="ts">
    import { defineComponent, nextTick, onMounted, ref } from 'vue';

    export default defineComponent({
        name: 'ChatInput',

        props: {
            disabled: {
                type: Boolean,
                default: false,
            },

            initialText: {
                type: String,
                default: '',
            },

            autoFocus: {
                type: Boolean,
                default: true,
            },
        },

        emits: ['send', 'cancel'],

        setup(props, { emit }) {
            const messageText = ref(props.initialText || '');
            const inputRef = ref<HTMLTextAreaElement | null>(null);
            const showCancelIcon = ref(false);

            // 메시지 전송
            const sendMessage = () => {
                if (!messageText.value.trim() || props.disabled) return;

                emit('send', messageText.value);
                messageText.value = '';

                // 텍스트 에어리어 높이 초기화
                if (inputRef.value) {
                    inputRef.value.style.height = 'auto';
                }
            };

            // 요청 취소
            const cancelRequest = () => {
                emit('cancel');
                showCancelIcon.value = false;
            };

            // Enter 키 처리 (Shift+Enter는 줄바꿈)
            const handleEnterKey = (e: KeyboardEvent) => {
                if (e.shiftKey) return; // Shift+Enter는 줄바꿈

                if (props.disabled) {
                    // 요청 중이면 취소
                    cancelRequest();
                } else {
                    // 아니면 메시지 전송
                    sendMessage();
                }
            };

            // ESC 키 처리 (요청 취소)
            const handleEscKey = () => {
                if (props.disabled) {
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

            // 컴포넌트 마운트 시 자동 포커스 및 크기 조절
            onMounted(() => {
                if (props.autoFocus && inputRef.value) {
                    inputRef.value.focus();
                }

                // 초기 텍스트가 있는 경우 크기 조절
                if (props.initialText) {
                    nextTick(() => {
                        autoResize();
                    });
                }
            });

            return {
                messageText,
                inputRef,
                showCancelIcon,
                sendMessage,
                cancelRequest,
                handleEnterKey,
                handleEscKey,
                autoResize,
            };
        },
    });
</script>

<style scoped>
    .chat-input-container {
        display: flex;
        align-items: center;
        background-color: #fff;
        border: 1px solid #e0e0e0;
        border-radius: 24px;
        padding: 8px 8px 8px 16px;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
        transition: all 0.3s;
    }

    .chat-input-container:focus-within {
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
        margin-left: 8px;
        cursor: pointer;
        transition: all 0.2s;
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
</style>
