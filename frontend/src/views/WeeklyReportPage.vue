<!-- src/views/WeeklyReportPage.vue -->
<template>
    <AppLayout>
        <div class="weekly-report-container">
            <h1>주간 레포트</h1>
            <p class="description">보안 이벤트와 정책 위반에 대한 주간 요약 레포트를 확인합니다.</p>

            <div class="report-controls">
                <div v-if="store.availableWeeks.length > 0" class="week-selector">
                    <label>주차 선택:</label>
                    <select v-model="selectedWeek" @change="selectWeek">
                        <option value="">모든 주차</option>
                        <option v-for="week in store.availableWeeks" :key="week" :value="week">
                            {{ formatWeek(week) }}
                        </option>
                    </select>
                </div>

                <button @click="fetchReports" class="refresh-button" :disabled="store.loading">
                    <span v-if="store.loading">로딩 중...</span>
                    <span v-else>새로고침</span>
                </button>
            </div>

            <div v-if="store.error" class="error-message">
                {{ store.error }}
            </div>

            <!-- 로딩 상태 표시 -->
            <div v-if="store.loading" class="loading-container">
                <div class="spinner"></div>
                <p>주간 레포트를 불러오는 중입니다...</p>
            </div>

            <!-- 레포트 목록과 상세 정보 -->
            <div v-else-if="store.hasReports" class="reports-content">
                <div class="reports-list">
                    <h2>레포트 목록</h2>
                    <div 
                        v-for="report in store.filteredReports" 
                        :key="report.id" 
                        class="report-item"
                        :class="{ 
                            active: store.selectedReport?.id === report.id,
                            'status-new': report.status === 'new',
                            'status-viewed': report.status === 'viewed',
                            'status-archived': report.status === 'archived'
                        }"
                        @click="selectReport(report.id)"
                    >
                        <div class="report-title">{{ report.title }}</div>
                        <div class="report-date">{{ formatDate(report.date) }}</div>
                        <div class="report-badge" v-if="report.status === 'new'">NEW</div>
                    </div>
                </div>

                <div class="report-detail" v-if="store.selectedReport">
                    <h2>{{ store.selectedReport.title }}</h2>
                    <div class="detail-date">{{ formatDate(store.selectedReport.date) }}</div>
                    
                    <div class="report-summary">
                        <h3>요약</h3>
                        <p>{{ store.selectedReport.summary }}</p>
                    </div>

                    <div class="report-details">
                        <h3>상세 내용</h3>
                        <p>{{ store.selectedReport.details }}</p>
                    </div>
                    
                    <div class="action-buttons">
                        <button class="archive-button" @click="archiveReport" v-if="store.selectedReport.status !== 'archived'">
                            보관하기
                        </button>
                    </div>
                </div>

                <div class="empty-selection" v-else>
                    <p>왼쪽 목록에서 레포트를 선택하세요.</p>
                </div>
            </div>

            <!-- 레포트가 없을 때 -->
            <div v-else class="empty-state">
                <p>주간 레포트가 없습니다.</p>
                <button @click="fetchReports" class="load-button">레포트 불러오기</button>
            </div>
        </div>
    </AppLayout>
</template>

<script lang="ts">
    import { defineComponent, ref, onMounted } from 'vue';
    import AppLayout from '@/layouts/AppLayout.vue';
    import { useWeeklyReportStore } from '@/stores/weeklyReport';

    export default defineComponent({
        name: 'WeeklyReportPage',
        components: {
            AppLayout,
        },

        setup() {
            const store = useWeeklyReportStore();
            const selectedWeek = ref('');

            onMounted(() => {
                // 데이터가 없는 경우에만 가져오기
                if (store.reports.length === 0) {
                    fetchReports();
                }
                
                // 스토어에 저장된 필터 상태 복원
                if (store.selectedWeek) {
                    selectedWeek.value = store.selectedWeek;
                }
            });

            // 레포트 데이터 가져오기
            const fetchReports = () => {
                store.fetchReports();
            };

            // 주차 선택
            const selectWeek = () => {
                store.selectWeek(selectedWeek.value || null);
            };

            // 레포트 선택
            const selectReport = (reportId: string) => {
                store.selectReport(reportId);
            };

            // 레포트 보관 처리
            const archiveReport = () => {
                if (store.selectedReport) {
                    store.updateReportStatus(store.selectedReport.id, 'archived');
                    alert('레포트가 보관 처리되었습니다.');
                }
            };

            // 날짜 포맷팅
            const formatDate = (dateString: string): string => {
                try {
                    const date = new Date(dateString);
                    return date.toLocaleDateString('ko-KR', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric'
                    });
                } catch (e) {
                    return dateString;
                }
            };

            // 주차 포맷팅
            const formatWeek = (weekString: string): string => {
                const [year, week] = weekString.split('-');
                return `${year}년 ${parseInt(week)}주차`;
            };

            return {
                store,
                selectedWeek,
                fetchReports,
                selectWeek,
                selectReport,
                archiveReport,
                formatDate,
                formatWeek
            };
        },
    });
</script>

<style scoped>
    .weekly-report-container {
        padding: 20px;
        max-width: 1200px;
        margin: 0 auto;
    }

    .description {
        color: #666;
        margin-bottom: 20px;
    }

    .report-controls {
        display: flex;
        justify-content: space-between;
        margin-bottom: 20px;
        flex-wrap: wrap;
        gap: 10px;
    }

    .week-selector {
        display: flex;
        flex-direction: column;
        gap: 5px;
    }

    .week-selector label {
        font-weight: bold;
        font-size: 0.9rem;
    }

    select {
        padding: 8px;
        border-radius: 4px;
        border: 1px solid #ced4da;
        min-width: 200px;
    }

    .refresh-button, .load-button, .archive-button {
        padding: 8px 15px;
        border-radius: 4px;
        cursor: pointer;
        background-color: #007bff;
        color: white;
        border: none;
    }

    .refresh-button:disabled {
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

    .reports-content {
        display: grid;
        grid-template-columns: 1fr 2fr;
        gap: 20px;
        margin-bottom: 20px;
    }

    .reports-list {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 20px;
        max-height: 600px;
        overflow-y: auto;
    }

    .report-item {
        padding: 15px;
        border: 1px solid #e9ecef;
        border-radius: 5px;
        margin-bottom: 10px;
        cursor: pointer;
        transition: all 0.2s;
        position: relative;
    }

    .report-item:hover {
        background-color: #e9ecef;
    }

    .report-item.active {
        background-color: #007bff;
        color: white;
        border-color: #007bff;
    }

    .report-item.status-new {
        border-left: 4px solid #28a745;
    }

    .report-badge {
        position: absolute;
        top: 5px;
        right: 5px;
        background-color: #28a745;
        color: white;
        font-size: 0.7rem;
        padding: 2px 6px;
        border-radius: 10px;
    }

    .report-title {
        font-weight: bold;
        margin-bottom: 5px;
    }

    .report-date {
        font-size: 0.85rem;
        color: inherit;
        opacity: 0.8;
    }

    .report-detail {
        background-color: white;
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    .detail-date {
        color: #666;
        margin-bottom: 15px;
    }

    .report-summary, .report-details {
        margin-bottom: 20px;
    }

    .report-summary h3, .report-details h3 {
        margin-bottom: 10px;
        color: #333;
    }

    .action-buttons {
        margin-top: 20px;
    }

    .archive-button {
        background-color: #6c757d;
    }

    .empty-selection, .empty-state {
        background-color: #f8f9fa;
        padding: 30px;
        text-align: center;
        border-radius: 8px;
    }

    .load-button {
        margin-top: 10px;
        background-color: #28a745;
    }
</style>