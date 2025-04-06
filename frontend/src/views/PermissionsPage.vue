<!-- src/views/PermissionsPage.vue -->
<template>
    <AppLayout>
        <div class="permissions-container">
            <h1>권한 관리</h1>
            <p class="description">IAM 권한 정책을 관리하고 사용자별 권한을 설정합니다.</p>

            <div class="tabs">
                <button 
                    @click="activeTab = 'general'"
                    :class="{ active: activeTab === 'general' }"
                    class="tab-button"
                >
                    일반 권한 관리
                </button>
                <button 
                    @click="activeTab = 'policy-changes'"
                    :class="{ active: activeTab === 'policy-changes' }"
                    class="tab-button"
                >
                    정책 변경사항 적용
                </button>
            </div>

            <!-- 일반 권한 관리 탭 -->
            <div v-if="activeTab === 'general'" class="tab-content">
                <div v-if="store.error" class="error-message">
                    {{ store.error }}
                </div>

                <!-- 로딩 상태 표시 -->
                <div v-if="store.loading" class="loading-container">
                    <div class="spinner"></div>
                    <p>권한 정보를 불러오는 중입니다...</p>
                </div>

                <!-- 권한 목록이 있을 때 -->
                <div v-else-if="store.hasPermissions" class="permissions-content">
                    <div class="permissions-list">
                        <h2>권한 목록</h2>
                        <div 
                            v-for="permission in store.permissions" 
                            :key="permission.id" 
                            class="permission-item"
                            :class="{ active: store.selectedPermission?.id === permission.id }"
                            @click="selectPermission(permission)"
                        >
                            <div class="permission-name">{{ permission.name }}</div>
                            <div class="permission-description">{{ permission.description }}</div>
                        </div>
                    </div>

                    <div class="permission-details" v-if="store.selectedPermission">
                        <h2>권한 상세 정보</h2>
                        <div class="detail-item">
                            <span class="label">이름:</span>
                            <span class="value">{{ store.selectedPermission.name }}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">설명:</span>
                            <span class="value">{{ store.selectedPermission.description }}</span>
                        </div>
                        
                        <div class="action-buttons">
                            <button class="edit-button">권한 수정</button>
                            <button class="delete-button" @click="deletePermission">권한 삭제</button>
                        </div>
                    </div>

                    <div class="empty-selection" v-else>
                        <p>왼쪽 목록에서 권한을 선택하세요.</p>
                    </div>
                </div>

                <!-- 권한 목록이 없을 때 -->
                <div v-else class="empty-state">
                    <p>권한 정보가 없습니다.</p>
                    <button class="load-button" @click="fetchPermissions">권한 불러오기</button>
                </div>

                <!-- 권한 추가 버튼 -->
                <div class="add-permission">
                    <button class="add-button">새 권한 추가</button>
                </div>
            </div>

            <!-- 정책 변경사항 적용 탭 -->
            <div v-else-if="activeTab === 'policy-changes'" class="tab-content">
                <div class="policy-changes-container">
                    <h3 class="section-title">정책 변경사항 적용</h3>

                    <div v-if="store.loading" class="loading-spinner">
                        <div class="spinner"></div>
                        <p>처리 중...</p>
                    </div>

                    <div v-else>
                        <div class="policy-description">
                            <p>권한 분석 결과에 따른 권한 변경 추천 사항을 적용합니다.</p>
                            <button @click="fetchAnalysisResults" class="refresh-button">분석 결과 새로고침</button>
                        </div>

                        <div v-if="store.analysisResults.length === 0" class="empty-analysis">
                            <p>권한 분석 결과가 없습니다. 먼저 분석 결과를 가져와주세요.</p>
                            <button @click="fetchAnalysisResults" class="fetch-button">분석 결과 가져오기</button>
                        </div>

                        <div v-else>
                            <!-- 사용자 리스트 및 탭 형태 UI -->
                            <div class="users-tabs-container">
                                <div class="users-tabs">
                                    <button 
                                        v-for="arn in store.userArns" 
                                        :key="arn"
                                        class="user-tab"
                                        :class="{ active: activeUserTab === arn }"
                                        @click="selectUser(arn)"
                                    >
                                        {{ formatUserName(arn) }}
                                    </button>
                                </div>
                                
                                <!-- 현재 선택된 사용자의 권한 정보 -->
                                <div v-if="activeUserTab" class="user-permissions">
                                    <div class="user-header">
                                        <h3>{{ formatUserName(activeUserTab) }}의 권한 관리</h3>
                                    </div>
                                    
                                    <div class="permissions-grid">
                                        <div class="add-permissions">
                                            <h4>추가할 권한</h4>
                                            <div v-if="getUserPermissions(activeUserTab).add.length > 0" class="permission-list">
                                                <div
                                                    v-for="(perm, index) in getUserPermissions(activeUserTab).add"
                                                    :key="perm.id || index"
                                                    class="permission-item"
                                                >
                                                    <input 
                                                        type="checkbox" 
                                                        :id="`add-${activeUserTab}-${index}`" 
                                                        v-model="perm.apply" 
                                                        @change="(e) => handleCheckboxChange(e, perm, 'add', activeUserTab)"
                                                    />
                                                    <label :for="`add-${activeUserTab}-${index}`">{{ perm.action }}</label>
                                                    <div class="permission-reason" v-if="perm.reason">{{ perm.reason }}</div>
                                                </div>
                                            </div>
                                            <p v-else class="empty-message">추가할 권한이 없습니다.</p>
                                        </div>

                                        <div class="remove-permissions">
                                            <h4>제거할 권한</h4>
                                            <div v-if="getUserPermissions(activeUserTab).remove.length > 0" class="permission-list">
                                                <div
                                                    v-for="(perm, index) in getUserPermissions(activeUserTab).remove"
                                                    :key="perm.id || index"
                                                    class="permission-item"
                                                >
                                                    <input 
                                                        type="checkbox" 
                                                        :id="`remove-${activeUserTab}-${index}`" 
                                                        v-model="perm.apply" 
                                                        @change="(e) => handleCheckboxChange(e, perm, 'remove', activeUserTab)"
                                                    />
                                                    <label :for="`remove-${activeUserTab}-${index}`">{{ perm.action }}</label>
                                                    <div class="permission-reason" v-if="perm.reason">{{ perm.reason }}</div>
                                                </div>
                                            </div>
                                            <p v-else class="empty-message">제거할 권한이 없습니다.</p>
                                        </div>
                                    </div>
                                </div>
                                
                                <div v-else class="empty-selection">
                                    <p>권한을 관리할 사용자를 선택하세요.</p>
                                </div>
                            </div>
                            
                            <!-- 전체 변경사항 적용 버튼 -->
                            <div class="global-action-bar">
                                <button 
                                    @click="applyAllChanges" 
                                    class="apply-all-button"
                                    :disabled="!hasAnyChanges || store.submitting"
                                >
                                    {{ store.submitting ? '적용 중...' : '모든 변경사항 적용' }}
                                </button>
                            </div>
                            
                            <!-- 사용자별 변경사항 요약 -->
                            <div v-if="hasAnyChanges" class="changes-summary">
                                <h4>변경 예정 사항 요약</h4>
                                <div v-for="arn in store.userArns" :key="`summary-${arn}`" class="user-changes">
                                    <div v-if="hasChangesForUser(arn)" class="user-change-item">
                                        <strong>{{ formatUserName(arn) }}</strong>: 
                                        <span v-if="countChangesForUser(arn).addCount > 0" class="add-count">
                                            {{ countChangesForUser(arn).addCount }}개 권한 추가
                                        </span>
                                        <span v-if="countChangesForUser(arn).addCount > 0 && countChangesForUser(arn).removeCount > 0">
                                            , 
                                        </span>
                                        <span v-if="countChangesForUser(arn).removeCount > 0" class="remove-count">
                                            {{ countChangesForUser(arn).removeCount }}개 권한 제거
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div v-if="store.error" class="error-message">
                        {{ store.error }}
                    </div>

                    <div v-if="store.successMessage" class="success-message">
                        {{ store.successMessage }}
                    </div>
                </div>
            </div>
        </div>
    </AppLayout>
</template>

<script lang="ts">
    import { defineComponent, onMounted, ref, watch, computed, reactive, nextTick } from 'vue';
    import { useRouter, useRoute } from 'vue-router';
    import AppLayout from '@/layouts/AppLayout.vue';
    import { usePermissionsStore } from '@/stores/permissions';
    import type { PermissionChange } from '@/services/policyService';

    export default defineComponent({
        name: 'PermissionsPage',
        components: {
            AppLayout,
        },

        setup() {
            const store = usePermissionsStore();
            const router = useRouter();
            const route = useRoute();
            const activeTab = ref('general');
            const activeUserTab = ref(''); // 현재 선택된 사용자
            
            // 사용자별 권한 정보를 저장할 reactive 맵 추가
            const userPermissionsReactive = reactive(new Map());

            // URL 쿼리 파라미터 처리
            try {
                if (route.query && route.query.tab === 'policy-changes') {
                    activeTab.value = 'policy-changes';
                }
            } catch (err) {
                console.error('쿼리 파라미터 처리 오류:', err);
                activeTab.value = 'general';
            }

            onMounted(() => {
                try {
                    // 권한 데이터가 없는 경우에만 가져오기
                    if (!store.hasPermissions && activeTab.value === 'general') {
                        fetchPermissions();
                    }

                    // 정책 변경 탭이 활성화된 경우, 분석 결과 가져오기
                    if (activeTab.value === 'policy-changes' && store.analysisResults.length === 0) {
                        fetchAnalysisResults();
                    }
                } catch (err) {
                    console.error('컴포넌트 마운트 오류:', err);
                }
            });

            // activeTab 변경 감시
            watch(activeTab, (newValue) => {
                try {
                    // 정책 변경 탭으로 전환된 경우 분석 결과 가져오기
                    if (newValue === 'policy-changes' && store.analysisResults.length === 0) {
                        fetchAnalysisResults();
                    }
                } catch (err) {
                    console.error('탭 변경 감시 오류:', err);
                }
            });

            // 권한 데이터 가져오기
            const fetchPermissions = () => {
                try {
                    store.fetchPermissions();
                } catch (err) {
                    console.error('권한 데이터 가져오기 오류:', err);
                }
            };

            // 분석 결과 가져오기
            const fetchAnalysisResults = async () => {
                try {
                    await store.fetchAnalysisResults();
                    // 첫 번째 사용자를 기본 선택
                    if (store.userArns.length > 0) {
                        activeUserTab.value = store.userArns[0];
                    }
                } catch (err) {
                    console.error('분석 결과 가져오기 오류:', err);
                }
            };

            // 권한 선택
            const selectPermission = (permission: any) => {
                try {
                    store.selectPermission(permission);
                } catch (err) {
                    console.error('권한 선택 오류:', err);
                }
            };

            // 권한 삭제
            const deletePermission = () => {
                try {
                    if (store.selectedPermission) {
                        if (confirm('정말 이 권한을 삭제하시겠습니까?')) {
                            store.deletePermission(store.selectedPermission.id);
                        }
                    }
                } catch (err) {
                    console.error('권한 삭제 오류:', err);
                }
            };

            // 사용자 선택
            const selectUser = (userArn: string) => {
                activeUserTab.value = userArn;
            };

            // 특정 사용자의 권한 정보 가져오기 함수 수정
            const getUserPermissions = (userArn: string) => {
                if (!userArn) return { add: [], remove: [] };
                
                // 이미 저장된 reactive 객체가 있으면 반환
                if (userPermissionsReactive.has(userArn)) {
                    return userPermissionsReactive.get(userArn);
                }
                
                // userPermissionsMap에서 해당 사용자의 권한 정보만 가져옴
                const userPerms = store.userPermissionsMap.get(userArn);
                
                // 해당 사용자의 권한 정보가 없으면 빈 객체 반환
                if (!userPerms) {
                    const emptyPerms = { add: [], remove: [] };
                    userPermissionsReactive.set(userArn, emptyPerms);
                    return emptyPerms;
                }
                
                // 사용자의 권한 정보를 reactive 객체로 변환
                const reactivePerms = {
                    add: userPerms.add.map(perm => ({
                        ...perm,
                        // 고유 ID가 없는 경우 생성 (추가적인 독립성 보장)
                        id: perm.id || `${userArn}-add-${perm.action}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
                    })),
                    remove: userPerms.remove.map(perm => ({
                        ...perm,
                        // 고유 ID가 없는 경우 생성 (추가적인 독립성 보장)
                        id: perm.id || `${userArn}-remove-${perm.action}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
                    }))
                };
                
                // 변환된 객체를 reactive 맵에 저장
                userPermissionsReactive.set(userArn, reactivePerms);
                
                return reactivePerms;
            };

            // 체크박스 변경 감지 함수 수정
            const handleCheckboxChange = (event: Event, permission: any, type: 'add' | 'remove', userArn: string) => {
                console.log(`체크박스 변경: ${userArn}, ${type}, ${permission.action}, 상태: ${permission.apply}`);
                
                // reactive 객체가 직접 업데이트됨, 추가 처리 필요 없음
                nextTick(() => {
                    // 업데이트 이후 필요한 작업이 있다면 여기에 추가
                });
            };

            // 특정 사용자에 대해 변경사항이 있는지 확인 - 수정
            const hasChangesForUser = (userArn: string) => {
                const userPerms = getUserPermissions(userArn);
                return userPerms.add.some(p => p.apply) || userPerms.remove.some(p => p.apply);
            };

            // 특정 사용자의 변경사항 개수 세기
            const countChangesForUser = (userArn: string) => {
                const userPerms = getUserPermissions(userArn);
                const addCount = userPerms.add.filter(p => p.apply).length;
                const removeCount = userPerms.remove.filter(p => p.apply).length;
                return { addCount, removeCount };
            };

            // 모든 사용자에 대해 변경사항이 있는지 확인
            const hasAnyChanges = computed(() => {
                return store.userArns.some(arn => hasChangesForUser(arn));
            });

            // 모든 변경사항 적용
            const applyAllChanges = async () => {
                try {
                    // 변경사항이 있는 모든 사용자에 대해 적용
                    const usersWithChanges = store.userArns.filter(arn => hasChangesForUser(arn));
                    if (usersWithChanges.length === 0) {
                        console.log('적용할 변경사항이 없습니다.');
                        return;
                    }
                    
                    // 각 사용자에 대한 변경 사항을 일괄 처리하기 위한 배열 준비
                    const policyUpdates = [];
                    
                    // 각 사용자별로 변경사항 수집
                    for (const userArn of usersWithChanges) {
                        const userPerms = getUserPermissions(userArn);
                        
                        // 해당 사용자의 선택된 권한만 필터링
                        const addPermissions = userPerms.add.filter(p => p.apply);
                        const removePermissions = userPerms.remove.filter(p => p.apply);
                        
                        // 권한 객체에서 필요 없는 ID 필드 제거 및 포맷 맞추기
                        const formattedAddPermissions = addPermissions.map(({id, ...rest}) => rest);
                        const formattedRemovePermissions = removePermissions.map(({id, ...rest}) => rest);
                        
                        // 사용자별 변경사항을 배열에 추가
                        policyUpdates.push({
                            user_arn: userArn,
                            add_permissions: formattedAddPermissions,
                            remove_permissions: formattedRemovePermissions
                        });
                    }
                    
                    console.log('적용할 변경사항:', policyUpdates);
                    
                    // 백엔드 API 호출하여 변경사항 적용
                    await store.applyPolicyChanges(policyUpdates);
                    
                    console.log('모든 변경사항 적용 완료');
                } catch (err) {
                    console.error('변경사항 적용 오류:', err);
                }
            };

            // ARN 형식의 사용자 정보를 보기 좋게 변환
            const formatUserName = (user: string): string => {
                try {
                    if (user && user.startsWith('arn:aws:')) {
                        // ARN에서 역할 이름만 추출
                        const parts = user.split('/');
                        if (parts.length > 1) {
                            return parts[parts.length - 1];
                        }
                    }
                    return user || 'Unknown';
                } catch (err) {
                    console.error('사용자명 포맷 오류:', err);
                    return user || 'Unknown';
                }
            };

            return {
                store,
                activeTab,
                activeUserTab,
                fetchPermissions,
                fetchAnalysisResults,
                selectPermission,
                deletePermission,
                selectUser,
                getUserPermissions,
                hasChangesForUser,
                countChangesForUser,
                hasAnyChanges,
                handleCheckboxChange,
                applyAllChanges,
                formatUserName,
                userPermissionsReactive
            };
        },
    });
</script>

<style scoped>
    .permissions-container {
        padding: 20px;
        max-width: 1200px;
        margin: 0 auto;
    }

    .description {
        color: #666;
        margin-bottom: 20px;
    }

    .tabs {
        display: flex;
        margin-bottom: 20px;
        border-bottom: 1px solid #dee2e6;
    }

    .tab-button {
        padding: 10px 20px;
        background-color: transparent;
        border: none;
        cursor: pointer;
        font-size: 1rem;
        color: #495057;
        border-bottom: 3px solid transparent;
        transition: all 0.2s;
    }

    .tab-button.active {
        color: #007bff;
        border-bottom-color: #007bff;
    }

    .tab-content {
        margin-top: 20px;
    }

    .error-message {
        background-color: #fce4e4;
        border: 1px solid #f8b8b8;
        color: #d63301;
        padding: 10px 15px;
        border-radius: 4px;
        margin-bottom: 20px;
    }

    .loading-container, .loading-spinner {
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

    .permissions-content {
        display: grid;
        grid-template-columns: 1fr 2fr;
        gap: 20px;
        margin-bottom: 20px;
    }

    .permissions-list {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 20px;
    }

    .permission-item {
        padding: 10px;
        border: 1px solid #e9ecef;
        border-radius: 5px;
        margin-bottom: 10px;
        cursor: pointer;
        transition: all 0.2s;
    }

    .permission-item:hover {
        background-color: #e9ecef;
    }

    .permission-item.active {
        background-color: #007bff;
        color: white;
        border-color: #007bff;
    }

    .permission-name {
        font-weight: bold;
        margin-bottom: 5px;
    }

    .permission-description {
        font-size: 0.9rem;
        color: inherit;
    }

    .permission-details {
        background-color: white;
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    .detail-item {
        margin-bottom: 15px;
    }

    .label {
        font-weight: bold;
        display: inline-block;
        width: 80px;
    }

    .action-buttons {
        margin-top: 20px;
        display: flex;
        gap: 10px;
    }

    .edit-button, .delete-button, .add-button, .load-button, .fetch-button {
        padding: 8px 15px;
        border-radius: 4px;
        cursor: pointer;
    }

    .edit-button {
        background-color: #007bff;
        color: white;
        border: none;
    }

    .delete-button {
        background-color: #dc3545;
        color: white;
        border: none;
    }

    .empty-selection, .empty-state, .empty-analysis {
        background-color: #f8f9fa;
        padding: 30px;
        text-align: center;
        border-radius: 8px;
    }

    .add-permission {
        margin-top: 20px;
    }

    .add-button, .load-button, .fetch-button {
        background-color: #28a745;
        color: white;
        border: none;
    }

    /* 정책 변경 탭 스타일 */
    .policy-changes-container {
        background-color: white;
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    .section-title {
        margin-top: 0;
        margin-bottom: 20px;
        padding-bottom: 10px;
        border-bottom: 1px solid #e9ecef;
        color: #333;
    }

    .policy-description {
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 20px;
    }

    .refresh-button {
        padding: 8px 15px;
        background-color: #17a2b8;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    }
    
    /* 새로운 사용자별 권한 관리 스타일 */
    .users-tabs-container {
        margin-top: 20px;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        overflow: hidden;
    }

    .users-tabs {
        display: flex;
        overflow-x: auto;
        background-color: #f8f9fa;
        border-bottom: 1px solid #e9ecef;
        padding: 10px;
        gap: 8px;
    }

    .user-tab {
        padding: 8px 15px;
        background-color: #e9ecef;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        transition: all 0.2s;
        white-space: nowrap;
        color: #495057;
        font-size: 0.9rem;
    }

    .user-tab:hover {
        background-color: #dee2e6;
    }

    .user-tab.active {
        background-color: #007bff;
        color: white;
    }

    .user-permissions {
        padding: 20px;
    }

    .user-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }

    .user-header h3 {
        margin: 0;
        color: #333;
    }

    .global-action-bar {
        margin-top: 20px;
        display: flex;
        justify-content: center;
        padding: 15px;
        background-color: #f8f9fa;
        border-radius: 8px;
    }

    .apply-all-button {
        padding: 10px 25px;
        background-color: #007bff;
        color: white;
        border: none;
        border-radius: 4px;
        font-weight: bold;
        cursor: pointer;
        font-size: 1rem;
        transition: background-color 0.2s;
    }

    .apply-all-button:hover:not(:disabled) {
        background-color: #0069d9;
    }

    .apply-all-button:disabled {
        background-color: #cccccc;
        cursor: not-allowed;
    }

    .changes-summary {
        margin-top: 20px;
        padding: 15px;
        background-color: #f8f9fa;
        border-radius: 8px;
        border: 1px solid #e9ecef;
    }

    .changes-summary h4 {
        margin-top: 0;
        margin-bottom: 10px;
        color: #333;
    }

    .user-changes {
        margin-bottom: 8px;
    }

    .user-change-item {
        padding: 8px;
        background-color: #fff;
        border-radius: 4px;
        border: 1px solid #e9ecef;
    }

    .add-count {
        color: #28a745;
    }

    .remove-count {
        color: #dc3545;
    }

    .empty-selection {
        padding: 30px;
        text-align: center;
        color: #6c757d;
    }

    .permissions-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
    }

    @media (max-width: 768px) {
        .permissions-grid {
            grid-template-columns: 1fr;
        }
    }

    .add-permissions, .remove-permissions {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 4px;
        border: 1px solid #e9ecef;
    }

    .add-permissions h4 {
        color: #2e7d32;
        margin-top: 0;
        margin-bottom: 10px;
    }

    .remove-permissions h4 {
        color: #d63301;
        margin-top: 0;
        margin-bottom: 10px;
    }

    .permission-list {
        display: flex;
        flex-direction: column;
        gap: 8px;
        max-height: 300px;
        overflow-y: auto;
    }

    .permission-item {
        display: flex;
        align-items: flex-start;
        padding: 8px;
        border-radius: 4px;
        border: 1px solid #dee2e6;
    }

    .permission-item input[type='checkbox'] {
        margin-right: 10px;
    }

    .permission-reason {
        font-size: 0.85rem;
        color: #6c757d;
        margin-top: 5px;
        margin-left: 25px;
    }

    .empty-message {
        color: #6c757d;
        font-style: italic;
    }

    .success-message {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 10px 15px;
        border-radius: 4px;
        margin-top: 15px;
    }
</style>