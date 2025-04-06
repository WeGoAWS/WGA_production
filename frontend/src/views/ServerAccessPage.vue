<!-- src/views/ServerAccessPage.vue -->
<template>
    <AppLayout>
        <div class="server-access-container">
            <h1>서버 접근 현황</h1>
            <p class="description">클라우드 서버 접근 로그를 확인하고 분석합니다.</p>

            <div class="filter-controls">
                <div class="filter-section">
                    <label>서버 필터:</label>
                    <select v-model="selectedServer" @change="applyServerFilter">
                        <option value="">모든 서버</option>
                        <option value="web-server-01">웹 서버</option>
                        <option value="db-server-01">DB 서버</option>
                        <option value="file-server-01">파일 서버</option>
                    </select>
                </div>

                <div class="filter-section">
                    <label>사용자 필터:</label>
                    <select v-model="selectedUser" @change="applyUserFilter">
                        <option value="">모든 사용자</option>
                        <option value="admin@example.com">admin@example.com</option>
                        <option value="developer1@example.com">developer1@example.com</option>
                    </select>
                </div>

                <button @click="loadAccessLogs" class="refresh-button" :disabled="store.loading">
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
                <p>서버 접근 로그를 불러오는 중입니다...</p>
            </div>

            <!-- 접근 로그 테이블 -->
            <div v-else-if="store.filteredLogs.length > 0" class="logs-table-container">
                <table class="logs-table">
                    <thead>
                        <tr>
                            <th>사용자</th>
                            <th>IP 주소</th>
                            <th>서버</th>
                            <th>작업</th>
                            <th>시간</th>
                            <th>상태</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="log in store.filteredLogs" :key="log.id" :class="{ 'failed': log.status === 'failed' }">
                            <td>{{ log.username }}</td>
                            <td>{{ log.ipAddress }}</td>
                            <td>{{ log.server }}</td>
                            <td>{{ log.action }}</td>
                            <td>{{ formatDate(log.timestamp) }}</td>
                            <td :class="'status-' + log.status">{{ formatStatus(log.status) }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- 로그가 없을 때 -->
            <div v-else class="empty-state">
                <p>서버 접근 로그가 없거나 필터 조건에 맞는 로그가 없습니다.</p>
                <button @click="resetFilters" class="reset-button">필터 초기화</button>
            </div>
        </div>
    </AppLayout>
</template>

<script lang="ts">
    import { defineComponent, ref, onMounted } from 'vue';
    import AppLayout from '@/layouts/AppLayout.vue';
    import { useServerAccessStore } from '@/stores/serverAccess';

    export default defineComponent({
        name: 'ServerAccessPage',
        components: {
            AppLayout,
        },

        setup() {
            const store = useServerAccessStore();
            const selectedServer = ref('');
            const selectedUser = ref('');

            onMounted(() => {
                // 데이터가 없는 경우에만 가져오기
                if (store.accessLogs.length === 0) {
                    loadAccessLogs();
                }
                
                // 스토어에 저장된 필터 상태 복원
                if (store.selectedServer) {
                    selectedServer.value = store.selectedServer;
                }
                
                if (store.selectedUser) {
                    selectedUser.value = store.selectedUser;
                }
            });

            // 접근 로그 가져오기
            const loadAccessLogs = () => {
                store.fetchAccessLogs();
            };

            // 서버 필터 적용
            const applyServerFilter = () => {
                store.setServerFilter(selectedServer.value);
            };

            // 사용자 필터 적용
            const applyUserFilter = () => {
                store.setUserFilter(selectedUser.value);
            };

            // 필터 초기화
            const resetFilters = () => {
                selectedServer.value = '';
                selectedUser.value = '';
                store.setServerFilter(null);
                store.setUserFilter(null);
            };

            // 날짜 포맷팅
            const formatDate = (dateString: string): string => {
                try {
                    const date = new Date(dateString);
                    return date.toLocaleString('ko-KR', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit'
                    });
                } catch (e) {
                    return dateString;
                }
            };

            // 상태 포맷팅
            const formatStatus = (status: string): string => {
                return status === 'success' ? '성공' : '실패';
            };

            return {
                store,
                selectedServer,
                selectedUser,
                loadAccessLogs,
                applyServerFilter,
                applyUserFilter,
                resetFilters,
                formatDate,
                formatStatus
            };
        },
    });
</script>

<style scoped>
    .server-access-container {
        padding: 20px;
        max-width: 1200px;
        margin: 0 auto;
    }

    .description {
        color: #666;
        margin-bottom: 20px;
    }

    .filter-controls {
        display: flex;
        gap: 20px;
        margin-bottom: 20px;
        flex-wrap: wrap;
        align-items: center;
    }

    .filter-section {
        display: flex;
        flex-direction: column;
        gap: 5px;
    }

    .filter-section label {
        font-weight: bold;
        font-size: 0.9rem;
    }

    select {
        padding: 8px;
        border-radius: 4px;
        border: 1px solid #ced4da;
        min-width: 200px;
    }

    .refresh-button, .reset-button {
        padding: 8px 15px;
        border-radius: 4px;
        cursor: pointer;
        background-color: #007bff;
        color: white;
        border: none;
        align-self: flex-end;
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

    .logs-table-container {
        overflow-x: auto;
    }

    .logs-table {
        width: 100%;
        border-collapse: collapse;
        border: 1px solid #dee2e6;
    }

    .logs-table th, .logs-table td {
        padding: 12px;
        text-align: left;
        border-bottom: 1px solid #dee2e6;
    }

    .logs-table th {
        background-color: #f8f9fa;
        font-weight: bold;
    }

    .logs-table tr:hover {
        background-color: #f2f2f2;
    }

    .logs-table tr.failed {
        background-color: #fff8f8;
    }

    .status-success {
        color: #28a745;
    }

    .status-failed {
        color: #dc3545;
    }

    .empty-state {
        background-color: #f8f9fa;
        padding: 30px;
        text-align: center;
        border-radius: 8px;
    }

    .reset-button {
        margin-top: 10px;
        background-color: #6c757d;
    }
</style>