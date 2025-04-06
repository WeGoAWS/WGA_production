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
                <label for="user-select">사용자 ARN 선택:</label>
                <select id="user-select" v-model="selectedUserArn" class="select-input">
                    <option value="">사용자 선택...</option>
                    <option v-for="arn in userArns" :key="arn" :value="arn">{{ arn }}</option>
                </select>
            </div>

            <div v-if="selectedUserArn" class="changes-section">
                <div class="add-permissions">
                    <h4>추가할 권한</h4>
                    <div v-if="addPermissions.length > 0" class="permission-list">
                        <div
                            v-for="(perm, index) in addPermissions"
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
                    <div v-if="removePermissions.length > 0" class="permission-list">
                        <div
                            v-for="(perm, index) in removePermissions"
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
                사용자를 선택하여 권한 변경사항을 적용하세요.
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
    import policyService from '@/services/policyService';
    import type { PermissionChange, PolicyUpdates } from '@/services/policyService';

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
            const selectedUserArn = ref('');

            // 선택된 사용자에 대한 추가/제거 권한 목록
            const addPermissions = ref<PermissionChange[]>([]);
            const removePermissions = ref<PermissionChange[]>([]);

            // 적용할 변경사항이 있는지 확인
            const hasChangesToApply = computed(() => {
                return (
                    addPermissions.value.some((p) => p.apply) ||
                    removePermissions.value.some((p) => p.apply)
                );
            });

            // 권한 변경사항 적용
            const applyChanges = async () => {
                if (!selectedUserArn.value || !hasChangesToApply.value) return;

                submitting.value = true;
                error.value = '';
                successMessage.value = '';

                try {
                    // 선택된 권한들만 필터링
                    const addSelected = addPermissions.value.filter((p) => p.apply);
                    const removeSelected = removePermissions.value.filter((p) => p.apply);

                    // 변경사항 객체 생성
                    const policyUpdates: PolicyUpdates = {
                        user_arn: selectedUserArn.value,
                        add_permissions: addSelected,
                        remove_permissions: removeSelected,
                    };

                    // 백엔드로 변경사항 전송
                    const result = await policyService.applyPolicyChanges([policyUpdates]);

                    successMessage.value = '권한 변경사항이 성공적으로 적용되었습니다.';

                    // 성공 후 체크박스 초기화
                    addPermissions.value.forEach((p) => (p.apply = false));
                    removePermissions.value.forEach((p) => (p.apply = false));
                } catch (err: any) {
                    console.error('권한 변경 적용 오류:', err);
                    error.value = err.message || '권한 변경 적용 중 오류가 발생했습니다.';
                } finally {
                    submitting.value = false;
                }
            };

            // 분석 결과에서 권한 추출
            const extractPermissionsFromResults = (userArn: string) => {
                // 선택된 사용자와 관련된 결과만 필터링
                const userResults = props.analysisResults.filter(
                    (result: any) => result.user === userArn || result.user.includes(userArn),
                );

                if (userResults.length === 0) {
                    addPermissions.value = [];
                    removePermissions.value = [];
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

                addPermissions.value = addPerms;
                removePermissions.value = removePerms;
            };

            // 사용자 ARN 변경 감시
            const watchUserArn = (userArn: string) => {
                if (userArn) {
                    extractPermissionsFromResults(userArn);
                } else {
                    addPermissions.value = [];
                    removePermissions.value = [];
                }
            };

            // selectedUserArn을 감시하는 watch 함수 설정
            watch(selectedUserArn, (newValue) => {
                if (newValue !== undefined) {
                    watchUserArn(newValue);
                }
            });

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
                } catch (err: any) {
                    console.error('사용자 ARN 목록 로드 오류:', err);
                    error.value = '사용자 목록을 불러오는 중 오류가 발생했습니다.';

                    // 오류 발생 시 분석 결과에서 사용자 추출
                    const users = new Set<string>();
                    props.analysisResults.forEach((result: any) => {
                        if (result.user) users.add(result.user);
                    });
                    userArns.value = Array.from(users);
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
                selectedUserArn,
                addPermissions,
                removePermissions,
                hasChangesToApply,
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

    .user-selection {
        margin-bottom: 20px;
    }

    .select-input {
        display: block;
        width: 100%;
        padding: 8px 12px;
        border: 1px solid #ced4da;
        border-radius: 4px;
        margin-top: 5px;
        font-size: 1rem;
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
