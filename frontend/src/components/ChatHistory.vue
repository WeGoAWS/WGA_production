<template>
    <div class="chat-history" :class="{ 'disabled-chat-history': disabled }">
        <div class="sidebar-header">
            <h2>대화 목록</h2>
            <button @click="createNewChat" class="new-chat-button" :disabled="disabled">
                <span class="icon">+</span>
                <span>새 대화</span>
            </button>
        </div>

        <div v-if="store.loading" class="sidebar-loading">
            <div class="spinner"></div>
            <span>로딩 중...</span>
        </div>

        <div v-else-if="store.hasSessions" class="chat-sessions">
            <div
                v-for="session in store.sessions"
                :key="session.sessionId"
                class="chat-session-item"
                :class="{
                    active: store.currentSession?.sessionId === session.sessionId,
                    disabled: disabled,
                }"
                @click="selectSession(session.sessionId)"
            >
                <div class="session-title">{{ session.title }}</div>
                <div class="session-date">{{ formatDate(session.updatedAt) }}</div>
                <div class="session-actions" v-if="!disabled">
                    <button
                        class="action-button rename-button"
                        @click.stop="startRenameSession(session)"
                        title="이름 변경"
                    >
                        <span class="icon">✏️</span>
                    </button>
                    <button
                        class="action-button delete-button"
                        @click.stop="confirmDeleteSession(session.sessionId)"
                        title="삭제"
                    >
                        <span class="icon">🗑️</span>
                    </button>
                </div>
            </div>
        </div>

        <div v-else class="empty-sessions">
            <p>대화 내역이 없습니다.</p>
            <button @click="fetchSessions" class="refresh-button" :disabled="disabled">
                새로고침
            </button>
        </div>

        <!-- 세션 이름 변경 모달 -->
        <div v-if="isRenaming" class="rename-modal">
            <div class="rename-modal-content">
                <h3>대화 이름 변경</h3>
                <input
                    type="text"
                    v-model="newSessionTitle"
                    class="rename-input"
                    @keyup.enter="confirmRename"
                    placeholder="새 대화 이름 입력"
                    ref="renamingInput"
                />
                <div class="rename-actions">
                    <button @click="cancelRename" class="cancel-button">취소</button>
                    <button @click="confirmRename" class="confirm-button">변경</button>
                </div>
            </div>
        </div>

        <!-- 세션 삭제 확인 모달 -->
        <div v-if="showDeleteConfirm" class="delete-modal">
            <div class="delete-modal-content">
                <h3>대화 삭제 확인</h3>
                <p>이 대화를 삭제하시겠습니까?</p>
                <p class="warning">이 작업은 되돌릴 수 없습니다.</p>
                <div class="delete-actions">
                    <button @click="cancelDelete" class="cancel-button">취소</button>
                    <button @click="confirmDelete" class="delete-confirm-button">삭제</button>
                </div>
            </div>
        </div>
    </div>
</template>

<script lang="ts">
    import { defineComponent, nextTick, ref } from 'vue';
    import { useChatHistoryStore } from '@/stores/chatHistoryStore';

    export default defineComponent({
        name: 'ChatHistory',

        props: {
            disabled: {
                type: Boolean,
                default: false,
            },
        },

        emits: ['session-click'],

        setup(props, { emit }) {
            const store = useChatHistoryStore();

            // 세션 이름 변경 관련 상태
            const isRenaming = ref(false);
            const renamingSession = ref<any>(null);
            const newSessionTitle = ref('');
            const renamingInput = ref<HTMLInputElement | null>(null);

            // 세션 삭제 확인 관련 상태
            const showDeleteConfirm = ref(false);
            const sessionToDelete = ref<string | null>(null);

            // 세션 목록 가져오기
            const fetchSessions = async () => {
                if (props.disabled) return; // 비활성화 상태면 실행하지 않음
                await store.fetchSessions();
            };

            // 새 채팅 세션 생성
            const createNewChat = async () => {
                if (props.disabled) return; // 비활성화 상태면 실행하지 않음
                await store.createNewSession();
            };

            // 채팅 세션 선택
            const selectSession = async (sessionId: string) => {
                if (props.disabled) return; // 비활성화 상태면 실행하지 않음

                // 세션 클릭 이벤트 발생
                emit('session-click', sessionId);
            };

            // 날짜 포맷팅 (YYYY년 MM월 DD일)
            const formatDate = (dateString: string): string => {
                try {
                    const date = new Date(dateString);
                    return date.toLocaleDateString('ko-KR', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                    });
                } catch (e) {
                    return dateString;
                }
            };

            // 세션 이름 변경 시작
            const startRenameSession = (session: any) => {
                if (props.disabled) return; // 비활성화 상태면 실행하지 않음

                renamingSession.value = session;
                newSessionTitle.value = session.title;
                isRenaming.value = true;

                // 다음 틱에서 입력 필드에 포커스
                nextTick(() => {
                    if (renamingInput.value) {
                        renamingInput.value.focus();
                    }
                });
            };

            // 세션 이름 변경 취소
            const cancelRename = () => {
                isRenaming.value = false;
                renamingSession.value = null;
                newSessionTitle.value = '';
            };

            // 세션 이름 변경 확인
            const confirmRename = async () => {
                if (renamingSession.value && newSessionTitle.value.trim()) {
                    try {
                        await store.updateSessionTitle(
                            renamingSession.value.sessionId,
                            newSessionTitle.value.trim(),
                        );
                        isRenaming.value = false;
                        renamingSession.value = null;
                    } catch (error) {
                        console.error('세션 이름 변경 오류:', error);
                    }
                }
            };

            // 세션 삭제 확인 모달 표시
            const confirmDeleteSession = (sessionId: string) => {
                if (props.disabled) return; // 비활성화 상태면 실행하지 않음

                sessionToDelete.value = sessionId;
                showDeleteConfirm.value = true;
            };

            // 세션 삭제 취소
            const cancelDelete = () => {
                showDeleteConfirm.value = false;
                sessionToDelete.value = null;
            };

            // 세션 삭제 확인
            const confirmDelete = async () => {
                if (sessionToDelete.value) {
                    try {
                        await store.deleteSession(sessionToDelete.value);
                        showDeleteConfirm.value = false;
                        sessionToDelete.value = null;
                    } catch (error) {
                        console.error('세션 삭제 오류:', error);
                    }
                }
            };

            return {
                store,
                fetchSessions,
                createNewChat,
                selectSession,
                formatDate,
                isRenaming,
                renamingSession,
                newSessionTitle,
                renamingInput,
                startRenameSession,
                cancelRename,
                confirmRename,
                showDeleteConfirm,
                sessionToDelete,
                confirmDeleteSession,
                cancelDelete,
                confirmDelete,
            };
        },
    });
</script>

<style scoped>
    .chat-history {
        height: 100%;
        display: flex;
        flex-direction: column;
        position: relative;
    }

    /* 비활성화 상태 스타일 */
    .disabled-chat-history {
        opacity: 0.7;
        position: relative;
    }

    .sidebar-header {
        padding: 16px;
        border-bottom: 1px solid rgba(0, 0, 0, 0.1);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .sidebar-header h2 {
        margin: 0;
        font-size: 1.2rem;
        font-weight: 600;
    }

    .new-chat-button {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 12px;
        background-color: #007bff;
        color: white;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        font-weight: 500;
        transition: background-color 0.2s;
    }

    .new-chat-button:hover:not(:disabled) {
        background-color: #0069d9;
    }

    .new-chat-button:disabled {
        background-color: #a3c8f1;
        cursor: not-allowed;
    }

    .new-chat-button .icon {
        font-size: 14px;
        font-weight: bold;
    }

    .sidebar-loading {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 32px 16px;
        gap: 12px;
        color: #666;
    }

    .spinner {
        width: 24px;
        height: 24px;
        border: 3px solid rgba(0, 123, 255, 0.2);
        border-top: 3px solid #007bff;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        0% {
            transform: rotate(0deg);
        }
        100% {
            transform: rotate(360deg);
        }
    }

    .chat-sessions {
        flex: 1;
        overflow-y: auto;
        padding: 12px;
    }

    .chat-session-item {
        position: relative;
        padding: 14px;
        border-radius: 8px;
        margin-bottom: 10px;
        cursor: pointer;
        transition: all 0.2s;
        background-color: #f8f9fa;
        border: 1px solid #eaeaea;
    }

    .chat-session-item:hover:not(.disabled) {
        background-color: #e9f5ff;
    }

    .chat-session-item.disabled {
        cursor: not-allowed;
    }

    .chat-session-item.active {
        background-color: #e3f2fd;
        border-color: #90caf9;
    }

    .session-title {
        font-weight: 500;
        margin-bottom: 6px;
        word-break: break-word;
        padding-right: 60px; /* 액션 버튼 공간 확보 */
    }

    .session-date {
        font-size: 0.8rem;
        color: #666;
    }

    .session-actions {
        position: absolute;
        right: 12px;
        top: 12px;
        display: flex;
        gap: 8px;
        opacity: 0;
        transition: opacity 0.2s;
    }

    .chat-session-item:hover .session-actions {
        opacity: 1;
    }

    .action-button {
        background: none;
        border: none;
        padding: 4px;
        cursor: pointer;
        border-radius: 4px;
        font-size: 12px;
    }

    .action-button:hover {
        background-color: rgba(0, 0, 0, 0.05);
    }

    .rename-button .icon {
        opacity: 0.6;
    }

    .delete-button .icon {
        opacity: 0.6;
    }

    .rename-button:hover .icon,
    .delete-button:hover .icon {
        opacity: 1;
    }

    .empty-sessions {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100%;
        padding: 20px;
        color: #666;
        text-align: center;
    }

    .refresh-button {
        margin-top: 16px;
        padding: 8px 16px;
        background-color: #f0f0f0;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        transition: background-color 0.2s;
    }

    .refresh-button:hover:not(:disabled) {
        background-color: #e0e0e0;
    }

    .refresh-button:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }

    /* 모달 스타일 */
    .rename-modal,
    .delete-modal {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
    }

    .rename-modal-content,
    .delete-modal-content {
        background-color: white;
        padding: 24px;
        border-radius: 12px;
        width: 90%;
        max-width: 400px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    }

    .rename-modal-content h3,
    .delete-modal-content h3 {
        margin-top: 0;
        margin-bottom: 16px;
    }

    .rename-input {
        width: 100%;
        padding: 10px 12px;
        border: 1px solid #ccc;
        border-radius: 6px;
        font-size: 1rem;
        margin-bottom: 20px;
    }

    .rename-actions,
    .delete-actions {
        display: flex;
        justify-content: flex-end;
        gap: 12px;
    }

    .cancel-button {
        padding: 8px 16px;
        background-color: #f0f0f0;
        border: none;
        border-radius: 6px;
        cursor: pointer;
    }

    .confirm-button,
    .delete-confirm-button {
        padding: 8px 16px;
        background-color: #007bff;
        color: white;
        border: none;
        border-radius: 6px;
        cursor: pointer;
    }

    .delete-confirm-button {
        background-color: #dc3545;
    }

    .cancel-button:hover {
        background-color: #e0e0e0;
    }

    .confirm-button:hover {
        background-color: #0069d9;
    }

    .delete-confirm-button:hover {
        background-color: #c82333;
    }

    .warning {
        color: #dc3545;
        font-size: 0.9rem;
        margin-bottom: 20px;
    }

    /* 반응형 스타일 */
    @media (max-width: 768px) {
        .sidebar-header {
            padding: 10px;
        }

        .new-chat-button {
            padding: 6px 10px;
            font-size: 0.9rem;
        }

        .chat-session-item {
            padding: 10px;
        }

        .rename-modal-content,
        .delete-modal-content {
            padding: 16px;
            width: 95%;
        }
    }
</style>
