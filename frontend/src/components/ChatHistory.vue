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
            <div>
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
            <button
                @click="confirmDeleteAllSessions"
                class="delete-all-button"
                :disabled="disabled"
            >
                <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                >
                    <polyline points="3,6 5,6 21,6"></polyline>
                    <path
                        d="m19,6v14a2,2 0 0,1 -2,2H7a2,2 0 0,1 -2,-2V6m3,0V4a2,2 0 0,1 2,-2h4a2,2 0 0,1 2,2v2"
                    ></path>
                    <line x1="10" y1="11" x2="10" y2="17"></line>
                    <line x1="14" y1="11" x2="14" y2="17"></line>
                </svg>
                <span>대화 전체 삭제</span>
            </button>
        </div>

        <div v-else class="empty-sessions">
            <p>대화 내역이 없습니다.</p>
            <button @click="fetchSessions" class="refresh-button" :disabled="disabled">
                새로고침
            </button>
        </div>

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

        <div v-if="showDeleteAllConfirm" class="delete-modal">
            <div class="delete-modal-content">
                <h3>⚠️ 전체 대화 삭제 확인</h3>
                <p>모든 대화를 삭제하시겠습니까?</p>
                <p class="warning">
                    이 작업은 되돌릴 수 없으며, 모든 대화 내역이 영구적으로 삭제됩니다.
                </p>
                <div class="delete-actions">
                    <button @click="cancelDeleteAll" class="cancel-button">취소</button>
                    <button @click="confirmDeleteAll" class="delete-confirm-button">
                        전체 삭제
                    </button>
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

            const isRenaming = ref(false);
            const renamingSession = ref<any>(null);
            const newSessionTitle = ref('');
            const renamingInput = ref<HTMLInputElement | null>(null);

            const showDeleteConfirm = ref(false);
            const sessionToDelete = ref<string | null>(null);

            const showDeleteAllConfirm = ref(false);

            const fetchSessions = async () => {
                if (props.disabled) return;
                await store.fetchSessions();
            };

            const createNewChat = async () => {
                if (props.disabled) return;
                await store.createNewSession();
            };

            const selectSession = async (sessionId: string) => {
                if (props.disabled) return;

                emit('session-click', sessionId);
            };

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

            const startRenameSession = (session: any) => {
                if (props.disabled) return;

                renamingSession.value = session;
                newSessionTitle.value = session.title;
                isRenaming.value = true;

                nextTick(() => {
                    if (renamingInput.value) {
                        renamingInput.value.focus();
                    }
                });
            };

            const cancelRename = () => {
                isRenaming.value = false;
                renamingSession.value = null;
                newSessionTitle.value = '';
            };

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

            const confirmDeleteSession = (sessionId: string) => {
                if (props.disabled) return;

                sessionToDelete.value = sessionId;
                showDeleteConfirm.value = true;
            };

            const cancelDelete = () => {
                showDeleteConfirm.value = false;
                sessionToDelete.value = null;
            };

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

            const confirmDeleteAllSessions = () => {
                if (props.disabled) return;
                showDeleteAllConfirm.value = true;
            };

            const cancelDeleteAll = () => {
                showDeleteAllConfirm.value = false;
            };

            const confirmDeleteAll = async () => {
                try {
                    await store.deleteAllSessions();
                    showDeleteAllConfirm.value = false;
                    console.log('모든 대화가 성공적으로 삭제되었습니다.');
                } catch (error) {
                    console.error('전체 세션 삭제 오류:', error);
                    alert('전체 대화 삭제 중 오류가 발생했습니다. 다시 시도해 주세요.');
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
                showDeleteAllConfirm,
                confirmDeleteAllSessions,
                cancelDeleteAll,
                confirmDeleteAll,
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
        justify-content: space-between;
        overflow-y: auto;
        padding: 12px;
        display: flex;
        flex-direction: column;
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
        padding-right: 60px;
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

    .delete-all-button {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        width: 100%;
        height: 50px;
        margin-top: 12px;
        background-color: #f8f9fa;
        border: 1px solid #dc3545;
        border-radius: 8px;
        color: #dc3545;
        cursor: pointer;
        font-weight: 500;
        font-size: 0.95rem;
        transition: all 0.2s ease;
    }

    .delete-all-button:hover:not(:disabled) {
        background-color: #dc3545;
        color: white;
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(220, 53, 69, 0.2);
    }

    .delete-all-button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
        box-shadow: none;
    }

    .delete-all-button svg {
        flex-shrink: 0;
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

        .delete-all-button {
            height: 45px;
            font-size: 0.9rem;
        }
    }
</style>
