<template>
    <div
        class="message"
        :class="{
            'user-message': message.sender === 'user',
            'bot-message': message.sender === 'bot',
            typing: message.isTyping,
            'appear-animation': message.animationState === 'appear',
        }"
    >
        <div class="message-avatar">
            <div v-if="message.sender === 'user'" class="avatar user-avatar">
                <span>{{ getUserInitial() }}</span>
            </div>
            <div v-else class="avatar bot-avatar">
                <img src="@/assets/bot-avatar.svg" alt="Bot" />
            </div>
        </div>

        <div class="message-content-wrapper">
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
    </div>
</template>

<script lang="ts">
    import type { PropType } from 'vue';
    import { defineComponent } from 'vue';

    interface ChatMessage {
        id: string;
        sender: 'user' | 'bot';
        text: string;
        displayText?: string;
        timestamp: string;
        isTyping?: boolean;
        animationState?: 'appear' | 'typing' | 'complete';
    }

    export default defineComponent({
        name: 'ChatMessage',

        props: {
            message: {
                type: Object as PropType<ChatMessage>,
                required: true,
            },
        },

        setup() {
            // 사용자 이니셜 가져오기 (이름이 없으면 U 반환)
            const getUserInitial = (): string => {
                const userName = localStorage.getItem('userName') || 'User';
                return userName.charAt(0).toUpperCase();
            };

            // 메시지 내용 포맷팅 (URL, 줄바꿈 등)
            const formatMessageContent = (content: string): string => {
                if (!content) return '';

                // URL 패턴 정규식
                const urlPattern = /(https?:\/\/[^\s]+)/g;

                // 줄바꿈을 HTML <br>로 변환하고 URL을 링크로 변환
                return content
                    .replace(/\n/g, '<br>')
                    .replace(
                        urlPattern,
                        '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>',
                    );
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

            return {
                getUserInitial,
                formatMessageContent,
                formatMessageTime,
            };
        },
    });
</script>

<style scoped>
    .message {
        display: flex;
        margin-bottom: 20px;
        animation-duration: 0.3s;
        animation-fill-mode: both;
    }

    .user-message {
        animation-name: sendMessage;
    }

    .bot-message {
        animation-name: receiveMessage;
    }

    @keyframes sendMessage {
        0% {
            opacity: 0;
            transform: translateY(10px);
        }
        100% {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @keyframes receiveMessage {
        0% {
            opacity: 0;
            transform: translateY(10px);
        }
        100% {
            opacity: 1;
            transform: translateY(0);
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

    .message-avatar {
        margin-right: 12px;
        align-self: flex-start;
    }

    .avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        color: white;
    }

    .user-avatar {
        background-color: #007bff;
    }

    .bot-avatar {
        background-color: #6c757d;
        overflow: hidden;
    }

    .bot-avatar img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    .message-content-wrapper {
        flex: 1;
        max-width: calc(100% - 50px);
    }

    .message-content {
        padding: 12px 16px;
        border-radius: 18px;
        position: relative;
        white-space: pre-wrap;
        overflow-wrap: break-word;
        word-break: break-word;
    }

    .user-message .message-content {
        background-color: #e3f2fd;
        color: #0d47a1;
        border-bottom-left-radius: 4px;
    }

    .bot-message .message-content {
        background-color: #f5f5f5;
        color: #333;
        border-bottom-left-radius: 4px;
    }

    .typing-indicator {
        display: flex;
        align-items: center;
        padding: 12px 16px;
        background-color: #f5f5f5;
        border-radius: 18px;
        border-bottom-left-radius: 4px;
        gap: 4px;
        height: 44px;
    }

    .dot {
        width: 8px;
        height: 8px;
        background-color: #aaa;
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

    .message-time {
        font-size: 0.75rem;
        color: #888;
        margin-top: 4px;
        text-align: right;
        padding-right: 8px;
    }

    /* 링크 스타일 */
    :deep(.message-content a) {
        color: #0d6efd;
        text-decoration: underline;
    }

    :deep(.user-message .message-content a) {
        color: #0a58ca;
    }
</style>
