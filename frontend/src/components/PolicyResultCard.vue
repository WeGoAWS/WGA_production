<!-- src/components/PolicyResultCard.vue -->
<template>
    <div class="analysis-card">
        <div class="card-header">
            <h3>{{ title || `분석 결과 #${index + 1}` }}</h3>
            <div class="metadata">
                <span class="date">{{ formatDate(result.date) }}</span>
                <span class="user">사용자: {{ formatUserName(result.user) }}</span>
                <span class="log-count">분석 로그: {{ result.log_count }}개</span>
            </div>
        </div>

        <div class="card-body">
            <div class="risk-info">
                <div
                    v-if="result.risk_classification"
                    :class="['risk-badge', getRiskClass(result.risk_classification)]"
                >
                    {{ result.risk_classification }}
                </div>
                <div
                    v-if="result.severity"
                    :class="['severity-badge', getSeverityClass(result.severity)]"
                >
                    {{ result.severity }}
                </div>
            </div>

            <div class="analysis-comment">
                <h4>요약</h4>
                <div
                    v-markdown="
                        result.summary || result.analysis_comment || '요약 정보가 없습니다.'
                    "
                ></div>
            </div>

            <div class="policy-recommendations">
                <h4>정책 추천</h4>

                <div class="recommendation-group">
                    <h5 class="remove-title">제거 권장 권한</h5>
                    <div
                        v-if="
                            result.policy_recommendation &&
                            result.policy_recommendation.REMOVE &&
                            result.policy_recommendation.REMOVE.length > 0
                        "
                        class="permission-list"
                    >
                        <div
                            v-for="(perm, idx) in result.policy_recommendation.REMOVE"
                            :key="idx"
                            class="permission-item remove"
                            @click="copyToClipboard(perm)"
                            title="클릭하여 복사"
                        >
                            <span class="permission-name">{{ perm }}</span>
                        </div>
                    </div>
                    <p v-else class="empty-list">제거 권장 권한이 없습니다.</p>
                </div>

                <div class="recommendation-group">
                    <h5 class="add-title">추가 권장 권한</h5>
                    <div
                        v-if="
                            result.policy_recommendation &&
                            result.policy_recommendation.ADD &&
                            result.policy_recommendation.ADD.length > 0
                        "
                        class="permission-list"
                    >
                        <div
                            v-for="(perm, idx) in result.policy_recommendation.ADD"
                            :key="idx"
                            class="permission-item add"
                            @click="copyToClipboard(perm)"
                            title="클릭하여 복사"
                        >
                            <span class="permission-name">{{ perm }}</span>
                        </div>
                    </div>
                    <p v-else class="empty-list">추가 권장 권한이 없습니다.</p>
                </div>

                <div
                    v-if="result.policy_recommendation && result.policy_recommendation.Reason"
                    class="reason"
                >
                    <h5>추천 이유</h5>
                    <div v-markdown="result.policy_recommendation.Reason"></div>
                </div>
            </div>

            <div class="card-actions">
                <button @click="saveResult" class="save-button" v-if="showSaveButton">
                    {{ savingResult ? '저장 중...' : '결과 저장' }}
                </button>
                <button @click="toggleExpanded" class="toggle-button">
                    {{ expanded ? '접기' : '더 보기' }}
                </button>
            </div>
        </div>
    </div>
</template>

<script lang="ts">
    import type { PropType } from 'vue';
    import { defineComponent, ref } from 'vue';
    import type { AnalysisResult } from '@/services/policyService';

    export default defineComponent({
        name: 'PolicyResultCard',

        props: {
            result: {
                type: Object as PropType<AnalysisResult>,
                required: true,
            },
            index: {
                type: Number,
                required: true,
            },
            title: {
                type: String,
                default: '',
            },
            showSaveButton: {
                type: Boolean,
                default: false,
            },
        },

        emits: ['save'],

        setup(props, { emit }) {
            const expanded = ref(false);
            const savingResult = ref(false);

            // 날짜 포맷팅 함수
            const formatDate = (dateString: string): string => {
                try {
                    const date = new Date(dateString);
                    return date.toLocaleString('ko-KR', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                    });
                } catch (e) {
                    return dateString;
                }
            };

            // ARN 형식의 사용자 정보를 보기 좋게 변환
            const formatUserName = (user: string): string => {
                if (user && user.startsWith('arn:aws:')) {
                    // ARN에서 역할 이름만 추출
                    const parts = user.split('/');
                    if (parts.length > 1) {
                        return parts[parts.length - 1];
                    }
                }
                return user || 'Unknown';
            };

            // 위험 분류에 따른 클래스 반환
            const getRiskClass = (risk: string): string => {
                if (!risk) return 'normal-risk';

                switch (risk.toLowerCase()) {
                    case 'high':
                        return 'high-risk';
                    case 'medium':
                        return 'medium-risk';
                    case 'low':
                        return 'low-risk';
                    case 'normal':
                    default:
                        return 'normal-risk';
                }
            };

            // 심각도에 따른 클래스 반환
            const getSeverityClass = (severity: string): string => {
                if (!severity) return 'low-severity';

                switch (severity.toLowerCase()) {
                    case 'high':
                        return 'high-severity';
                    case 'medium':
                        return 'medium-severity';
                    case 'low':
                    default:
                        return 'low-severity';
                }
            };

            const toggleExpanded = () => {
                expanded.value = !expanded.value;
            };

            const copyToClipboard = (text: string) => {
                navigator.clipboard
                    .writeText(text)
                    .then(() => {
                        alert(`복사됨: ${text}`);
                    })
                    .catch((err) => {
                        console.error('클립보드 복사 실패:', err);
                    });
            };

            const saveResult = async () => {
                savingResult.value = true;

                try {
                    // 저장 이벤트 발생
                    emit('save', props.result);
                } catch (error) {
                    console.error('결과 저장 중 오류:', error);
                } finally {
                    savingResult.value = false;
                }
            };

            return {
                expanded,
                savingResult,
                formatDate,
                formatUserName,
                getRiskClass,
                getSeverityClass,
                toggleExpanded,
                copyToClipboard,
                saveResult,
            };
        },
    });
</script>

<style scoped>
    .analysis-card {
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        overflow: hidden;
        margin-bottom: 20px;
    }

    .card-header {
        background-color: #f8f9fa;
        padding: 15px 20px;
        border-bottom: 1px solid #e9ecef;
    }

    .card-header h3 {
        margin: 0 0 10px 0;
        color: #333;
    }

    .metadata {
        display: flex;
        flex-wrap: wrap;
        gap: 15px;
        font-size: 0.9rem;
        color: #666;
    }

    .card-body {
        padding: 20px;
    }

    .risk-info {
        display: flex;
        gap: 10px;
        margin-bottom: 15px;
    }

    .risk-badge,
    .severity-badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 600;
    }

    .high-risk {
        background-color: #ffebee;
        color: #c62828;
        border: 1px solid #ef9a9a;
    }

    .medium-risk {
        background-color: #fff3e0;
        color: #e65100;
        border: 1px solid #ffcc80;
    }

    .low-risk,
    .normal-risk {
        background-color: #e8f5e9;
        color: #2e7d32;
        border: 1px solid #a5d6a7;
    }

    .high-severity {
        background-color: #ffebee;
        color: #c62828;
        border: 1px solid #ef9a9a;
    }

    .medium-severity {
        background-color: #fff3e0;
        color: #e65100;
        border: 1px solid #ffcc80;
    }

    .low-severity {
        background-color: #e8f5e9;
        color: #2e7d32;
        border: 1px solid #a5d6a7;
    }

    .analysis-comment {
        margin-bottom: 20px;
    }

    .analysis-comment h4,
    .policy-recommendations h4,
    .recommendation-group h5,
    .reason h5 {
        margin-top: 0;
        margin-bottom: 10px;
        color: #333;
    }

    /* 마크다운 스타일 */
    [v-markdown] {
        line-height: 1.6;
    }

    [v-markdown] a {
        color: #007bff;
        text-decoration: none;
    }

    [v-markdown] a:hover {
        text-decoration: underline;
    }

    [v-markdown] code {
        background-color: #f8f9fa;
        padding: 2px 4px;
        border-radius: 3px;
        font-family: monospace;
        font-size: 0.9em;
        word-break: break-word; /* 긴 단어가 있을 경우 줄바꿈 */
        overflow-wrap: break-word; /* 단어가 너무 길 경우 줄바꿈 */
    }

    [v-markdown] pre {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 4px;
        overflow-x: auto; /* 이미 있지만 중요한 속성 */
        max-width: 100%; /* 최대 너비를 부모 요소에 맞춤 */
        word-wrap: break-word; /* 긴 단어가 있을 경우 줄바꿈 */
        white-space: pre-wrap; /* 줄바꿈 유지하면서 너비 조절 */
    }

    [v-markdown] pre code {
        background-color: transparent;
        white-space: pre-wrap; /* pre 안의 code는 줄바꿈 유지하면서 너비 조절 */
        padding: 0;
    }

    [v-markdown] ul,
    [v-markdown] ol {
        margin-top: 0.5rem;
        margin-bottom: 0.5rem;
        padding-left: 1.5rem;
    }

    [v-markdown] li {
        margin-bottom: 0.25rem;
    }

    [v-markdown] h1,
    [v-markdown] h2,
    [v-markdown] h3 {
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
    }

    [v-markdown] p {
        margin-top: 0;
        margin-bottom: 1rem;
    }

    .policy-recommendations {
        display: flex;
        flex-direction: column;
        gap: 15px;
    }

    .recommendation-group {
        padding: 15px;
        border-radius: 4px;
        background-color: #f8f9fa;
    }

    .remove-title {
        color: #d63301;
    }

    .add-title {
        color: #2e7d32;
    }

    .permission-list {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 10px;
    }

    .permission-item {
        padding: 5px 10px;
        border-radius: 4px;
        font-size: 0.9rem;
        cursor: pointer;
        transition: transform 0.2s;
    }

    .permission-item:hover {
        transform: scale(1.05);
    }

    .permission-item::after {
        content: '📋';
        margin-left: 5px;
        font-size: 0.8rem;
        opacity: 0.6;
    }

    .permission-item.remove {
        background-color: #ffebee;
        color: #d63301;
        border: 1px solid #f8b8b8;
    }

    .permission-item.add {
        background-color: #e8f5e9;
        color: #2e7d32;
        border: 1px solid #a5d6a7;
    }

    .empty-list {
        color: #666;
        font-style: italic;
        margin: 5px 0;
    }

    .reason {
        margin-top: 10px;
        padding: 15px;
        background-color: #fff8e1;
        border-radius: 4px;
        border-left: 4px solid #ffb300;
    }

    .reason p {
        margin: 0;
        line-height: 1.6;
    }

    .card-actions {
        display: flex;
        justify-content: flex-end;
        gap: 10px;
        margin-top: 20px;
        padding-top: 15px;
        border-top: 1px solid #e9ecef;
    }

    .save-button,
    .toggle-button {
        padding: 8px 15px;
        border-radius: 4px;
        font-size: 0.9rem;
        cursor: pointer;
        transition: background-color 0.2s;
    }

    .save-button {
        background-color: #28a745;
        color: white;
        border: none;
    }

    .save-button:hover {
        background-color: #218838;
    }

    .toggle-button {
        background-color: #f8f9fa;
        color: #6c757d;
        border: 1px solid #ced4da;
    }

    .toggle-button:hover {
        background-color: #e9ecef;
    }
</style>
