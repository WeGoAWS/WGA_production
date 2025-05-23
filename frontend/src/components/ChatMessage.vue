<template>
    <div
        class="message"
        :class="{
            'user-message': message.sender === 'user',
            'bot-message': message.sender === 'assistant',
            typing: message.isTyping,
            'appear-animation': message.animationState === 'appear',
        }"
    >
        <div class="message-avatar">
            <div v-if="message.sender === 'user'" class="avatar user-avatar">
                <span>{{ getUserInitial() }}</span>
            </div>
            <div v-else class="avatar bot-avatar">
                <img src="@/assets/agent-logo.png" alt="Assistant" />
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

            <div v-if="message.elapsed_time || message.inference" class="query-metadata">
                <div v-if="message.elapsed_time" class="elapsed-time">
                    실행 시간: {{ message.elapsed_time }}
                </div>

                <div class="details-toggle" @click="toggleDetails">
                    <span>{{ showDetails ? '간략히 보기' : '자세히 보기' }}</span>
                    <span class="toggle-icon">{{ showDetails ? '▲' : '▼' }}</span>
                </div>

                <div v-if="showDetails" class="query-details">
                    <div v-if="message.query_string" class="query-section">
                        <h4>SQL 쿼리</h4>
                        <pre
                            class="sql-query"
                        ><code v-html="formatSqlQuery(message.query_string)"></code></pre>
                    </div>

                    <div
                        v-if="message.query_result && message.query_result.length > 0"
                        class="query-section"
                    >
                        <h4>쿼리 결과</h4>
                        <div class="query-result-table-container">
                            <table class="query-result-table">
                                <thead>
                                    <tr>
                                        <th v-for="(_, key) in message.query_result[0]" :key="key">
                                            {{ key }}
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr
                                        v-for="(row, rowIndex) in message.query_result"
                                        :key="rowIndex"
                                    >
                                        <td v-for="(value, key) in row" :key="`${rowIndex}-${key}`">
                                            {{
                                                typeof value === 'string'
                                                    ? value.replace(/\\n/g, ' ')
                                                    : value
                                            }}
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div v-if="message.inference" class="query-section">
                        <h4>추론 데이터</h4>
                        <pre
                            class="inference-data"
                        ><code v-html="formatInferenceData(message.inference)"></code></pre>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script lang="ts">
    import type { PropType } from 'vue';
    import { defineComponent, ref } from 'vue';
    import { parseMarkdown } from '@/utils/markdown';
    import type { ChatMessageType } from '@/types/chat.ts';

    export default defineComponent({
        name: 'ChatMessage',

        props: {
            message: {
                type: Object as PropType<ChatMessageType>,
                required: true,
            },
        },

        setup() {
            const showDetails = ref(false);

            const toggleDetails = () => {
                showDetails.value = !showDetails.value;
            };

            const formatSqlQuery = (sql: string | any) => {
                if (!sql) return '';

                return sql
                    .replace(
                        /\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|GROUP BY|ORDER BY|HAVING|LIMIT|OFFSET|AS|ON|AND|OR|NOT|IN|BETWEEN|LIKE|IS|NULL|TRUE|FALSE|DESC|ASC|COUNT|SUM|AVG|MIN|MAX|date_parse)\b/gi,
                        (match: any) => `<span class="sql-keyword">${match}</span>`,
                    )
                    .replace(/\n/g, '<br>')
                    .replace(/('[^']*')/g, `<span class="sql-string">$1</span>`);
            };

            const formatInferenceData = (inference: any): string => {
                try {
                    if (typeof inference === 'string') {
                        try {
                            const obj = JSON.parse(inference);
                            return JSON.stringify(obj, null, 2)
                                .replace(
                                    /"([^"]+)":/g,
                                    '"<span style="color: #0033b3; font-weight: bold;">$1</span>":',
                                )
                                .replace(
                                    /: "([^"]*)"/g,
                                    ': "<span style="color: #014325;">$1</span>"',
                                );
                        } catch (e) {
                            return inference;
                        }
                    }

                    const jsonStr = JSON.stringify(inference, null, 2);
                    return jsonStr
                        .replace(
                            /"([^"]+)":/g,
                            '"<span style="color: #0033b3; font-weight: bold;">$1</span>":',
                        )
                        .replace(/: "([^"]*)"/g, ': "<span style="color: #014325;">$1</span>"');
                } catch (error) {
                    console.error('Inference 데이터 포맷팅 오류:', error);
                    return String(inference);
                }
            };

            const getUserInitial = (): string => {
                const userName = localStorage.getItem('userName') || 'User';
                return userName.charAt(0).toUpperCase();
            };

            const formatMessageContent = (content: string): string => {
                if (!content) return '';

                const escapeHtml = (text: string) => {
                    return text
                        .replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;')
                        .replace(/"/g, '&quot;')
                        .replace(/'/g, '&#039;');
                };

                const escapedContent = escapeHtml(content);

                const htmlContent = parseMarkdown(escapedContent);

                const urlPattern = /(https?:\/\/[^\s<>"]+[^.\s<>",.;:!?）)}\]]*)/g;

                const processed = htmlContent.replace(urlPattern, (url) => {
                    if (/<a[^>]*>[^<]*url[^<]*<\/a>/i.test(url)) {
                        return url;
                    }
                    return `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`;
                });

                return processed;
            };

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
                formatSqlQuery,
                formatInferenceData,
                showDetails,
                toggleDetails,
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
        overflow-wrap: break-word;
    }

    .message-content {
        padding: 8px 16px;
        border-radius: 18px;
        position: relative;
        white-space: pre-wrap;
        overflow-wrap: break-word;
        word-break: break-word;
        max-width: 100%;
        overflow-x: auto;
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
        max-width: 100%;
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
        max-width: 100%;
        white-space: pre-wrap;
    }

    :deep(.markdown-content pre code) {
        background: none;
        padding: 0;
        white-space: pre-wrap;
        word-break: break-word;
    }

    :deep(.markdown-content strong) {
        font-weight: bold;
    }

    :deep(.markdown-content em) {
        font-style: italic;
    }

    :deep(.message-content a) {
        color: #0d6efd;
        text-decoration: underline;
        word-break: break-all;
    }

    :deep(.user-message .message-content a) {
        color: #0a58ca;
    }

    .query-metadata {
        margin-top: 10px;
        font-size: 0.85rem;
    }

    .elapsed-time {
        color: #888;
        margin-bottom: 4px;
    }

    .details-toggle {
        display: inline-flex;
        align-items: center;
        color: #007bff;
        cursor: pointer;
        user-select: none;
        font-weight: 500;
        margin-top: 4px;
    }

    .toggle-icon {
        margin-left: 4px;
        font-size: 0.75rem;
    }

    .query-details {
        margin-top: 10px;
        border-top: 1px solid #eee;
        padding-top: 10px;
        width: 100%;
    }

    .query-section {
        margin-bottom: 15px;
    }

    .query-section h4 {
        font-size: 0.9rem;
        margin-bottom: 8px;
        color: #555;
    }

    .sql-query {
        background-color: #f5f5f5;
        padding: 12px;
        border-radius: 4px;
        overflow-x: auto;
        font-family: 'Courier New', monospace;
        font-size: 0.9rem;
        line-height: 1.5;
        white-space: pre-wrap;
        word-wrap: break-word;
        word-break: break-word;
        max-width: 100%;
    }

    .inference-data {
        background-color: #f8f8f8;
        padding: 12px;
        border-radius: 4px;
        overflow-x: auto;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        line-height: 1.5;
        border: 1px solid #eaeaea;
        max-width: 100%;
        white-space: pre-wrap;
        word-wrap: break-word;
        word-break: break-word;
        color: #333;
    }

    .inference-data code {
        background: none;
        font-family: 'Courier New', monospace;
        color: #0a3253;
    }

    :deep(.sql-keyword) {
        color: #0033b3;
        font-weight: bold;
    }

    :deep(.sql-string) {
        color: #014325;
    }

    .query-result-table-container {
        overflow-x: auto;
        margin-top: 8px;
        max-width: 100%;
    }

    .query-result-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85rem;
        table-layout: auto;
    }

    .query-result-table th,
    .query-result-table td {
        border: 1px solid #ddd;
        padding: 8px;
        text-align: left;
        word-break: break-word;
        max-width: 250px;
        overflow-wrap: break-word;
    }

    .query-result-table th {
        background-color: #f2f2f2;
        font-weight: 600;
    }

    .query-result-table tr:nth-child(even) {
        background-color: #f9f9f9;
    }
</style>
