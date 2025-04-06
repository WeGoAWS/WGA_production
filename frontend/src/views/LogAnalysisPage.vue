<!-- src/views/LogAnalysisPage.vue -->
<template>
    <AppLayout>
        <div class="log-analysis-container">
            <div class="page-header">
                <h1>로그분석</h1>
                <p class="description">
                    AWS CloudTrail, GCP, Azure 로그를 분석하여 IAM 정책 권한 추천을 제공합니다.
                </p>
                <div class="cloud-selector">
                    <button
                        @click="setCloudProvider('aws')"
                        class="cloud-button"
                        :class="{ active: store.cloudProvider === 'aws' }"
                    >
                        AWS
                    </button>
                    <button
                        @click="setCloudProvider('gcp')"
                        class="cloud-button"
                        :class="{ active: store.cloudProvider === 'gcp' }"
                    >
                        GCP
                    </button>
                    <button
                        @click="setCloudProvider('azure')"
                        class="cloud-button"
                        :class="{ active: store.cloudProvider === 'azure' }"
                    >
                        Azure
                    </button>
                </div>
            </div>

            <div class="controls">
                <div class="filter-section">
                    <DateRangeFilter :loading="store.loading" @filter="handleDateFilter" />
                    <UserFilter :loading="store.loading" @filter="handleUserFilter" />
                </div>
                <button @click="startAnalysis" class="analyze-button" :disabled="store.loading">
                    <span v-if="store.loading">분석 중...</span>
                    <span v-else>로그 분석 시작</span>
                </button>
            </div>

            <div v-if="store.error" class="error-message">
                {{ store.error }}
            </div>

            <!-- 로딩 상태 표시 -->
            <div v-if="store.loading" class="loading-container">
                <div class="spinner"></div>
                <p>로그 분석 중입니다. 잠시만 기다려주세요...</p>
            </div>

            <!-- 결과가 있을 때 -->
            <div v-if="store.showResults" class="results-container">
                <div v-for="(result, index) in store.analysisResults" :key="index">
                    <PolicyResultCard
                        :result="result"
                        :index="index"
                        :show-save-button="true"
                        @save="saveAnalysisResult"
                    />
                </div>

                <!-- 정책 변경사항 적용 안내 -->
                <div v-if="store.analysisResults.length > 0" class="apply-changes-info">
                    <div class="info-box">
                        <h3>정책 변경사항 적용</h3>
                        <p>분석 결과에 따른 권한 변경사항을 적용하려면 권한 관리 페이지의 "정책 변경사항 적용" 탭으로 이동하세요.</p>
                        <button @click="goToPermissionsPage" class="navigate-button">권한 관리 페이지로 이동</button>
                    </div>
                </div>
            </div>

            <!-- 결과가 없을 때 -->
            <div v-if="!store.loading && !store.showResults" class="no-results">
                <p>
                    아직 분석 결과가 없습니다. '로그 분석 시작' 버튼을 클릭하여 분석을 시작하세요.
                </p>
            </div>
        </div>
    </AppLayout>
</template>

<script lang="ts">
    import { defineComponent } from 'vue';
    import { useRouter } from 'vue-router';
    import AppLayout from '@/layouts/AppLayout.vue';
    import DateRangeFilter from '@/components/DateRangeFilter.vue';
    import UserFilter from '@/components/UserFilter.vue';
    import PolicyResultCard from '@/components/PolicyResultCard.vue';
    import type { AnalysisResult } from '@/services/policyService';
    import { useLogAnalysisStore } from '@/stores/logAnalysis';

    export default defineComponent({
        name: 'LogAnalysisPage',
        components: {
            AppLayout,
            DateRangeFilter,
            UserFilter,
            PolicyResultCard,
        },

        setup() {
            const store = useLogAnalysisStore();
            const router = useRouter();

            // 클라우드 제공자 설정
            const setCloudProvider = (provider: 'aws' | 'gcp' | 'azure') => {
                store.setCloudProvider(provider);
            };

            // 사용자 필터 처리
            const handleUserFilter = (username: string | null) => {
                store.setUserFilter(username);
            };

            // 날짜 필터 처리
            const handleDateFilter = (dateRange: { startDate: string; endDate: string } | null) => {
                store.setDateFilter(dateRange);
            };

            // 분석 시작
            const startAnalysis = () => {
                store.getAnalysisData();
            };

            // 권한 관리 페이지로 이동
            const goToPermissionsPage = () => {
                router.push({ 
                    path: '/permissions',
                    query: { tab: 'policy-changes' }
                });
            };

            // 분석 결과 저장
            const saveAnalysisResult = async (result: AnalysisResult) => {
                const success = await store.saveAnalysisResult(result);
                if (success) {
                    alert('결과가 저장되었습니다.');
                }
            };

            // 날짜 포맷팅 함수
            const formatDate = (dateString: string): string => {
                try {
                    const date = new Date(dateString);
                    return date.toLocaleString('ko-KR', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                    });
                } catch (e) {
                    return dateString;
                }
            };

            return {
                store,
                formatDate,
                handleUserFilter,
                handleDateFilter,
                setCloudProvider,
                startAnalysis,
                saveAnalysisResult,
                goToPermissionsPage,
            };
        },
    });
</script>

<style scoped>
    .log-analysis-container {
        padding: 20px;
        max-width: 1200px;
        margin: 0 auto;
    }

    .page-header {
        margin-bottom: 24px;
    }

    .page-header h1 {
        margin-bottom: 8px;
        color: #333;
    }

    .description {
        color: #666;
        line-height: 1.5;
    }

    .cloud-selector {
        display: flex;
        gap: 10px;
        margin-top: 15px;
    }

    .cloud-button {
        padding: 8px 16px;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        background-color: #f8f9fa;
        color: #495057;
        cursor: pointer;
        transition: all 0.2s;
    }

    .cloud-button:hover {
        background-color: #e9ecef;
    }

    .cloud-button.active {
        background-color: #007bff;
        color: white;
        border-color: #007bff;
    }

    .filter-section {
        display: flex;
        gap: 20px;
        margin-bottom: 20px;
    }

    @media (max-width: 768px) {
        .filter-section {
            flex-direction: column;
        }
    }

    .controls {
        margin-bottom: 20px;
    }

    .analyze-button {
        background-color: #ff9900;
        border: none;
        color: #232f3e;
        padding: 10px 20px;
        border-radius: 4px;
        font-weight: 600;
        cursor: pointer;
        transition: background-color 0.2s;
    }

    .analyze-button:hover {
        background-color: #ffa928;
    }

    .analyze-button:disabled {
        background-color: #ccc;
        cursor: not-allowed;
    }

    .error-message {
        background-color: #fce4e4;
        border: 1px solid #f8b8b8;
        color: #d63301;
        padding: 10px 15px;
        border-radius: 4px;
        margin-bottom: 20px;
    }

    .loading-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 40px;
    }

    .spinner {
        width: 50px;
        height: 50px;
        border: 4px solid #f3f3f3;
        border-top: 4px solid #ff9900;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-bottom: 20px;
    }

    @keyframes spin {
        0% {
            transform: rotate(0deg);
        }
        100% {
            transform: rotate(360deg);
        }
    }

    .results-container {
        display: flex;
        flex-direction: column;
        gap: 20px;
    }

    .no-results {
        text-align: center;
        padding: 40px;
        color: #666;
        background-color: #f8f9fa;
        border-radius: 8px;
    }

    .apply-changes-info {
        margin-top: 20px;
    }

    .info-box {
        background-color: #e9f5ff;
        border: 1px solid #b6dfff;
        border-radius: 8px;
        padding: 20px;
        text-align: center;
    }

    .info-box h3 {
        color: #0066cc;
        margin-top: 0;
        margin-bottom: 10px;
    }

    .navigate-button {
        margin-top: 10px;
        background-color: #0066cc;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 8px 16px;
        cursor: pointer;
        font-weight: 600;
        transition: background-color 0.2s;
    }

    .navigate-button:hover {
        background-color: #0056b3;
    }
</style>