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
                <img src="@/assets/agent-logo.png" alt="Bot" />
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
                class="message-content markdown-content"
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
    import { parseMarkdown } from '@/utils/markdown';

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

            // 메시지 내용 포맷팅 (마크다운, URL, 줄바꿈 등)
            const formatMessageContent = (content: string): string => {
                if (!content) return '';

                // 1. 안전하게 HTML 엔티티 이스케이프 처리 (XSS 방지)
                const escapeHtml = (text: string) => {
                    return text
                        .replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;')
                        .replace(/"/g, '&quot;')
                        .replace(/'/g, '&#039;');
                };

                // 내용을 이스케이프 처리
                const escapedContent = escapeHtml(content);

                // 2. 마크다운을 HTML로 변환 (기존 parseMarkdown 함수 활용)
                // parseMarkdown 함수는 이스케이프된 HTML을 다루기 때문에 XSS 방지 이후에 적용
                const htmlContent = parseMarkdown(escapedContent);

                // 3. URL 패턴 정규식 - 마크다운 변환 후 남아있는 일반 URL 처리
                const urlPattern = /(https?:\/\/[^\s<>"]+[^.\s<>",.;:!?）)}\]]*)/g;

                // URL을 링크로 변환 (마크다운 처리 후 남은 평문 URL에 대해)
                const processed = htmlContent.replace(urlPattern, (url) => {
                    // 이미 <a> 태그 내부에 있는 URL은 변환하지 않음
                    if (/<a[^>]*>[^<]*url[^<]*<\/a>/i.test(url)) {
                        return url;
                    }
                    return `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`;
                });

                return processed;
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
        border-top-left-radius: 4px;
    }

    .bot-message .message-content {
        background-color: #f5f5f5;
        color: #333;
        border-top-left-radius: 4px;
    }

    .typing-indicator {
        display: flex;
        align-items: center;
        padding: 12px 16px;
        background-color: #f5f5f5;
        border-radius: 18px;
        border-top-left-radius: 4px;
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

    /* 마크다운 스타일링 */
    :deep(.markdown-content h1) {
        font-size: 1.5rem;
        margin: 0.8rem 0;
        border-bottom: 1px solid #eee;
        padding-bottom: 0.3rem;
    }

    :deep(.markdown-content h2) {
        font-size: 1.3rem;
        margin: 0.7rem 0;
    }

    :deep(.markdown-content h3) {
        font-size: 1.1rem;
        margin: 0.6rem 0;
    }

    :deep(.markdown-content p) {
        margin: 0.5rem 0;
    }

    :deep(.markdown-content ul),
    :deep(.markdown-content ol) {
        padding-left: 1.5rem;
        margin: 0.5rem 0;
    }

    :deep(.markdown-content li) {
        margin: 0.3rem 0;
    }

    :deep(.markdown-content code) {
        background-color: rgba(0, 0, 0, 0.05);
        padding: 0.1rem 0.3rem;
        border-radius: 3px;
        font-family: monospace;
        font-size: 0.9em;
    }

    :deep(.markdown-content pre) {
        background-color: rgba(0, 0, 0, 0.05);
        padding: 0.8rem;
        border-radius: 4px;
        overflow-x: auto;
        margin: 0.7rem 0;
    }

    :deep(.markdown-content pre code) {
        background: none;
        padding: 0;
        white-space: pre;
    }

    :deep(.markdown-content strong) {
        font-weight: bold;
    }

    :deep(.markdown-content em) {
        font-style: italic;
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
