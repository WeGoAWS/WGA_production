<!-- src/components/ApplyPermissionChanges.vue -->
<template>
    <div class="apply-changes-container">
        <h3 class="section-title">정책 변경사항 적용</h3>

        <div v-if="loading" class="loading-spinner">
            <div class="spinner"></div>
            <p>처리 중...</p>
        </div>

        <div v-else>
            <div class="user-selection" v-if="userArns.length > 0">
                <!-- 다중 선택 기능을 위한 체크박스 그룹 -->
                <div class="selection-header">
                    <h4>사용자 ARN 선택:</h4>
                    <div class="selection-controls">
                        <button @click="selectAllUsers" class="select-all-button">
                            {{ isAllSelected ? '전체 해제' : '전체 선택' }}
                        </button>
                    </div>
                </div>
                
                <div class="users-container">
                    <div 
                        v-for="arn in userArns" 
                        :key="arn" 
                        class="user-checkbox-item"
                    >
                        <input 
                            type="checkbox" 
                            :id="`user-${arn}`" 
                            :value="arn" 
                            v-model="selectedUserArns"
                            @change="handleUserSelectionChange"
                        />
                        <label :for="`user-${arn}`" class="user-arn-label">{{ formatUserName(arn) }}</label>
                    </div>
                </div>
            </div>

            <div v-if="selectedUserArns.length > 0" class="changes-info">
                <p>{{ selectedUserArns.length }}명의 사용자에게 권한 변경사항이 적용됩니다.</p>
            </div>
            
            <div v-if="selectedUserArns.length > 0" class="changes-section">
                <div class="add-permissions">
                    <h4>추가할 권한</h4>
                    <div v-if="combinedAddPermissions.length > 0" class="permission-list">
                        <div
                            v-for="(perm, index) in combinedAddPermissions"
                            :key="index"
                            class="permission-item"
                        >
                            <input type="checkbox" :id="`add-${index}`" v-model="perm.apply" />
                            <label :for="`add-${index}`">{{ perm.action }}</label>
                        </div>
                    </div>
                    <p v-else class="empty-message">추가할 권한이 없습니다.</p>
                </div>

                <div class="remove-permissions">
                    <h4>제거할 권한</h4>
                    <div v-if="combinedRemovePermissions.length > 0" class="permission-list">
                        <div
                            v-for="(perm, index) in combinedRemovePermissions"
                            :key="index"
                            class="permission-item"
                        >
                            <input type="checkbox" :id="`remove-${index}`" v-model="perm.apply" />
                            <label :for="`remove-${index}`">{{ perm.action }}</label>
                        </div>
                    </div>
                    <p v-else class="empty-message">제거할 권한이 없습니다.</p>
                </div>

                <button
                    @click="applyChanges"
                    class="apply-button"
                    :disabled="!hasChangesToApply || submitting"
                >
                    {{ submitting ? '적용 중...' : '변경사항 적용' }}
                </button>
            </div>

            <div v-else-if="userArns.length > 0" class="instruction">
                적용할 사용자를 선택하세요.
            </div>

            <div v-else class="empty-message">사용자 ARN 목록을 가져올 수 없습니다.</div>
        </div>

        <div v-if="error" class="error-message">
            {{ error }}
        </div>

        <div v-if="successMessage" class="success-message">
            {{ successMessage }}
        </div>
    </div>
</template>

<script lang="ts">
    import { computed, defineComponent, onMounted, ref, watch } from 'vue';
    import policyService, { PermissionChange, PolicyUpdates } from '@/services/policyService';

    export default defineComponent({
        name: 'ApplyPermissionChanges',

        props: {
            analysisResults: {
                type: Array,
                required: true,
            },
        },

        setup(props) {
            const loading = ref(true);
            const submitting = ref(false);
            const error = ref('');
            const successMessage = ref('');
            const userArns = ref<string[]>([]);
            
            // 다중 선택을 위한 배열로 변경
            const selectedUserArns = ref<string[]>([]);
            
            // 사용자별 권한 정보를 저장할 맵
            const userPermissionsMap = ref<Map<string, { add: PermissionChange[], remove: PermissionChange[] }>>(new Map());
            
            // 선택된 사용자들의 조합된 권한 목록
            const combinedAddPermissions = ref<PermissionChange[]>([]);
            const combinedRemovePermissions = ref<PermissionChange[]>([]);

            // 전체 선택 상태
            const isAllSelected = computed(() => {
                return selectedUserArns.value.length === userArns.value.length && userArns.value.length > 0;
            });

            // 적용할 변경사항이 있는지 확인
            const hasChangesToApply = computed(() => {
                return (
                    combinedAddPermissions.value.some((p) => p.apply) ||
                    combinedRemovePermissions.value.some((p) => p.apply)
                );
            });

            // 전체 사용자 선택/해제
            const selectAllUsers = () => {
                if (isAllSelected.value) {
                    // 전체 해제
                    selectedUserArns.value = [];
                } else {
                    // 전체 선택
                    selectedUserArns.value = [...userArns.value];
                }
                handleUserSelectionChange();
            };

            // 사용자 이름 포맷팅
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

            // 사용자 선택 변경 시 권한 목록 업데이트
            const handleUserSelectionChange = () => {
                if (selectedUserArns.value.length === 0) {
                    combinedAddPermissions.value = [];
                    combinedRemovePermissions.value = [];
                    return;
                }
                
                // 선택된 사용자들의 권한을 조합
                const addPermsMap = new Map<string, PermissionChange>();
                const removePermsMap = new Map<string, PermissionChange>();
                
                selectedUserArns.value.forEach(arn => {
                    const userPerms = userPermissionsMap.value.get(arn);
                    if (userPerms) {
                        // 추가 권한 처리
                        userPerms.add.forEach(perm => {
                            if (!addPermsMap.has(perm.action)) {
                                addPermsMap.set(perm.action, { ...perm, apply: false });
                            }
                        });
                        
                        // 제거 권한 처리
                        userPerms.remove.forEach(perm => {
                            if (!removePermsMap.has(perm.action)) {
                                removePermsMap.set(perm.action, { ...perm, apply: false });
                            }
                        });
                    }
                });
                
                combinedAddPermissions.value = Array.from(addPermsMap.values());
                combinedRemovePermissions.value = Array.from(removePermsMap.values());
            };

            // 정확한 사용자 이름 매칭을 위한 함수
            const exactUserMatch = (resultUser: string, targetUserArn: string): boolean => {
                // 정확히 일치하는 경우
                if (resultUser === targetUserArn) return true;
                
                // ARN 형식에서 사용자/역할 이름 추출 (마지막 부분)
                const getExactUserName = (arn: string): string => {
                    const parts = arn.split('/');
                    return parts.length > 1 ? parts[parts.length - 1] : arn;
                };
                
                // 추출된 정확한 사용자/역할 이름 비교
                const resultUserName = getExactUserName(resultUser);
                const targetUserName = getExactUserName(targetUserArn);
                
                return resultUserName === targetUserName;
            };

            // 권한 변경사항 적용
            const applyChanges = async () => {
                if (selectedUserArns.value.length === 0) return;

                submitting.value = true;
                error.value = '';
                successMessage.value = '';

                try {
                    // 각 사용자별 변경사항 생성
                    const policyUpdates: PolicyUpdates[] = [];
                    
                    // 각 사용자마다 해당 사용자의 권한 변경사항을 찾아서 적용
                    for (const userArn of selectedUserArns.value) {
                        const userPermissions = userPermissionsMap.value.get(userArn);
                        
                        if (userPermissions) {
                            // 해당 사용자의 권한 중 적용할 항목만 필터링
                            const addSelected = userPermissions.add.filter((p) => p.apply);
                            const removeSelected = userPermissions.remove.filter((p) => p.apply);
                            
                            // 적용할 권한이 있는 경우에만 업데이트 목록에 추가
                            if (addSelected.length > 0 || removeSelected.length > 0) {
                                policyUpdates.push({
                                    user_arn: userArn,
                                    add_permissions: addSelected,
                                    remove_permissions: removeSelected,
                                });
                            }
                        }
                    }

                    // 적용할 변경사항이 하나라도 있는 경우에만 API 호출
                    if (policyUpdates.length > 0) {
                        // 백엔드로 변경사항 전송 (다중 사용자 지원)
                        const result = await policyService.applyPolicyChanges(policyUpdates);

                        successMessage.value = `${policyUpdates.length}명의 사용자에게 권한 변경사항이 성공적으로 적용되었습니다.`;
                        
                        // 성공 후 해당 사용자들의 체크박스 초기화
                        for (const userArn of selectedUserArns.value) {
                            const userPermissions = userPermissionsMap.value.get(userArn);
                            if (userPermissions) {
                                userPermissions.add.forEach((p) => (p.apply = false));
                                userPermissions.remove.forEach((p) => (p.apply = false));
                            }
                        }
                        
                        // 조합된 권한 목록도 초기화
                        combinedAddPermissions.value.forEach((p) => (p.apply = false));
                        combinedRemovePermissions.value.forEach((p) => (p.apply = false));
                    } else {
                        error.value = "적용할 권한 변경사항이 없습니다. 변경할 권한을 선택해주세요.";
                    }
                } catch (err: any) {
                    console.error('권한 변경 적용 오류:', err);
                    error.value = err.message || '권한 변경 적용 중 오류가 발생했습니다.';
                } finally {
                    submitting.value = false;
                }
            };

            // 분석 결과에서 각 사용자별 권한 추출
            const extractAllUserPermissions = () => {
            // 사용자별 권한 맵 초기화
            userPermissionsMap.value.clear();
            
            // 각 사용자에 대한 권한 추출
            userArns.value.forEach(userArn => {
                // 정확한 매칭으로 해당 사용자의 결과만 필터링
                const userResults = props.analysisResults.filter(
                    (result: any) => {
                        if (!result || !result.user) return false;
                        return exactUserMatch(result.user, userArn);
                    }
                );

                if (userResults.length === 0) {
                    userPermissionsMap.value.set(userArn, { add: [], remove: [] });
                    return;
                }

                // 권한 목록 초기화
                const addPerms: PermissionChange[] = [];
                const removePerms: PermissionChange[] = [];

                // 각 분석 결과에서 권한 추출
                userResults.forEach((result: any) => {
                    if (result.policy_recommendation) {
                        // 추가 권한
                        result.policy_recommendation.ADD.forEach((action: string) => {
                            if (!addPerms.some((p) => p.action === action)) {
                                addPerms.push({
                                    action,
                                    apply: false,
                                    reason: result.policy_recommendation.Reason,
                                });
                            }
                        });

                        // 제거 권한
                        result.policy_recommendation.REMOVE.forEach((action: string) => {
                            if (!removePerms.some((p) => p.action === action)) {
                                removePerms.push({
                                    action,
                                    apply: false,
                                    reason: result.policy_recommendation.Reason,
                                });
                            }
                        });
                    }
                });

                // 사용자별 권한 맵에 저장
                userPermissionsMap.value.set(userArn, { add: addPerms, remove: removePerms });
            });
        };

            // 사용자 ARN 목록 로드
            const loadUserArns = async () => {
                loading.value = true;
                error.value = '';

                try {
                    // 실제 API에서 사용자 ARN 목록 가져오기
                    const arns = await policyService.getUserArns();

                    if (arns.length === 0) {
                        // API가 빈 목록을 반환하면 분석 결과에서 사용자 추출
                        const users = new Set<string>();
                        props.analysisResults.forEach((result: any) => {
                            if (result.user) users.add(result.user);
                        });
                        userArns.value = Array.from(users);
                    } else {
                        userArns.value = arns;
                    }
                    
                    // 모든 사용자의 권한 정보 추출
                    extractAllUserPermissions();
                } catch (err: any) {
                    console.error('사용자 ARN 목록 로드 오류:', err);
                    error.value = '사용자 목록을 불러오는 중 오류가 발생했습니다.';

                    // 오류 발생 시 분석 결과에서 사용자 추출
                    const users = new Set<string>();
                    props.analysisResults.forEach((result: any) => {
                        if (result.user) users.add(result.user);
                    });
                    userArns.value = Array.from(users);
                    
                    // 모든 사용자의 권한 정보 추출
                    extractAllUserPermissions();
                } finally {
                    loading.value = false;
                }
            };

            onMounted(() => {
                loadUserArns();
            });

            return {
                loading,
                submitting,
                error,
                successMessage,
                userArns,
                selectedUserArns,
                combinedAddPermissions,
                combinedRemovePermissions,
                hasChangesToApply,
                isAllSelected,
                selectAllUsers,
                formatUserName,
                handleUserSelectionChange,
                applyChanges,
            };
        },
    });
</script>

<style scoped>
    .apply-changes-container {
        background-color: white;
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        margin-top: 20px;
    }

    .section-title {
        margin-top: 0;
        margin-bottom: 20px;
        padding-bottom: 10px;
        border-bottom: 1px solid #e9ecef;
        color: #333;
    }

    .selection-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }

    .selection-header h4 {
        margin: 0;
    }

    .selection-controls {
        display: flex;
        gap: 10px;
    }

    .select-all-button {
        padding: 4px 8px;
        font-size: 0.9rem;
        background-color: #f8f9fa;
        border: 1px solid #ced4da;
        border-radius: 4px;
        cursor: pointer;
    }

    .select-all-button:hover {
        background-color: #e9ecef;
    }

    .users-container {
        max-height: 200px;
        overflow-y: auto;
        border: 1px solid #ced4da;
        border-radius: 4px;
        padding: 5px;
        margin-bottom: 15px;
    }

    .user-checkbox-item {
        padding: 5px 10px;
        display: flex;
        align-items: center;
        border-bottom: 1px solid #f1f1f1;
    }

    .user-checkbox-item:last-child {
        border-bottom: none;
    }

    .user-arn-label {
        margin-left: 8px;
        cursor: pointer;
    }

    .changes-info {
        background-color: #e8f4fd;
        padding: 10px 15px;
        border-radius: 4px;
        margin-bottom: 15px;
        color: #0066cc;
        font-weight: bold;
    }

    .changes-section {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
        margin-bottom: 20px;
    }

    @media (max-width: 768px) {
        .changes-section {
            grid-template-columns: 1fr;
        }
    }

    .add-permissions,
    .remove-permissions {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 4px;
    }

    .add-permissions h4 {
        color: #2e7d32;
        margin-top: 0;
    }

    .remove-permissions h4 {
        color: #d63301;
        margin-top: 0;
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
        align-items: center;
        padding: 6px 10px;
        background-color: white;
        border-radius: 4px;
        border: 1px solid #dee2e6;
    }

    .permission-item input[type='checkbox'] {
        margin-right: 10px;
    }

    .empty-message {
        color: #6c757d;
        font-style: italic;
    }

    .apply-button {
        padding: 10px 20px;
        background-color: #28a745;
        color: white;
        border: none;
        border-radius: 4px;
        font-weight: bold;
        cursor: pointer;
        margin-top: 15px;
        transition: background-color 0.2s;
    }

    .apply-button:hover:not(:disabled) {
        background-color: #218838;
    }

    .apply-button:disabled {
        background-color: #cccccc;
        cursor: not-allowed;
    }

    .loading-spinner {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 30px 0;
    }

    .spinner {
        width: 40px;
        height: 40px;
        border: 4px solid #f3f3f3;
        border-top: 4px solid #28a745;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-bottom: 15px;
    }

    @keyframes spin {
        0% {
            transform: rotate(0deg);
        }
        100% {
            transform: rotate(360deg);
        }
    }

    .error-message {
        background-color: #fce4e4;
        border: 1px solid #f8b8b8;
        color: #d63301;
        padding: 10px 15px;
        border-radius: 4px;
        margin-top: 15px;
    }

    .success-message {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 10px 15px;
        border-radius: 4px;
        margin-top: 15px;
    }

    .instruction {
        padding: 20px;
        text-align: center;
        color: #6c757d;
        background-color: #f8f9fa;
        border-radius: 4px;
    }
</style>