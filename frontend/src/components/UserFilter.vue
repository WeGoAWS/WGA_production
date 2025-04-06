<!-- src/components/UserFilter.vue -->
<template>
    <div class="user-filter">
        <div class="filter-header">
            <h3>사용자 필터</h3>
            <button @click="toggleFilter" class="toggle-button">
                {{ expanded ? '접기' : '펼치기' }}
            </button>
        </div>

        <div v-if="expanded" class="filter-body">
            <div class="search-field">
                <input
                    type="text"
                    v-model="searchTerm"
                    placeholder="사용자 이름으로 검색..."
                    class="search-input"
                    @input="handleInput"
                />
                <button v-if="searchTerm" @click="clearSearch" class="clear-search">✕</button>
            </div>

            <div v-if="filteredUsers.length > 0" class="users-list">
                <div
                    v-for="(user, index) in filteredUsers"
                    :key="index"
                    class="user-item"
                    :class="{ selected: user === selectedUser }"
                    @click="selectUser(user)"
                >
                    {{ user }}
                </div>
            </div>

            <div v-else-if="searchTerm && !loading" class="no-results">검색 결과가 없습니다.</div>

            <div v-if="loading" class="loading">
                <div class="mini-spinner"></div>
                <span>로딩 중...</span>
            </div>

            <div class="filter-actions">
                <button
                    @click="applyFilter"
                    class="apply-button"
                    :disabled="!selectedUser || loading"
                >
                    {{ loading ? '적용 중...' : '적용하기' }}
                </button>

                <button @click="clearFilter" class="clear-button" :disabled="loading">
                    초기화
                </button>
            </div>
        </div>
    </div>
</template>

<script lang="ts">
    import { computed, defineComponent, ref } from 'vue';

    export default defineComponent({
        name: 'UserFilter',

        props: {
            loading: {
                type: Boolean,
                default: false,
            },
        },

        emits: ['filter'],

        setup(props, { emit }) {
            const expanded = ref(false);
            const searchTerm = ref('');
            const selectedUser = ref('');

            // 예시 사용자 목록 - 실제로는 API에서 가져올 수 있음
            const allUsers = ref([
                'ML_dataset_role18',
                'ML_dataset_role6',
                'ML_dataset_role5',
                'ML_dataset_role10',
                'admin@example.com',
                'developer1@example.com',
            ]);

            // 필터링된 사용자 목록
            const filteredUsers = computed(() => {
                if (!searchTerm.value) {
                    return allUsers.value;
                }

                const search = searchTerm.value.toLowerCase();
                return allUsers.value.filter((user) => user.toLowerCase().includes(search));
            });

            // 필터 토글
            const toggleFilter = () => {
                expanded.value = !expanded.value;
            };

            // 입력 처리
            const handleInput = () => {
                // 필요한 경우 디바운스 처리
            };

            // 검색어 지우기
            const clearSearch = () => {
                searchTerm.value = '';
            };

            // 사용자 선택
            const selectUser = (user: string) => {
                selectedUser.value = user;
            };

            // 필터 적용
            const applyFilter = () => {
                if (selectedUser.value) {
                    emit('filter', selectedUser.value);
                }
            };

            // 필터 초기화
            const clearFilter = () => {
                selectedUser.value = '';
                searchTerm.value = '';
                emit('filter', null);
            };

            // API에서 사용자 목록 가져오기 (필요한 경우 구현)
            const fetchUsers = async () => {
                // const response = await api.getUsers();
                // allUsers.value = response.data;
            };

            // 컴포넌트 마운트 시 사용자 목록 로드 (필요한 경우 활성화)
            // onMounted(() => {
            //   fetchUsers();
            // });

            return {
                expanded,
                searchTerm,
                selectedUser,
                filteredUsers,
                toggleFilter,
                handleInput,
                clearSearch,
                selectUser,
                applyFilter,
                clearFilter,
            };
        },
    });
</script>

<style scoped>
    .user-filter {
        background-color: #f8f9fa;
        border-radius: 8px;
        margin-bottom: 20px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }

    .filter-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 15px;
        background-color: #eaedef;
        cursor: pointer;
    }

    .filter-header h3 {
        margin: 0;
        font-size: 1rem;
        color: #333;
    }

    .toggle-button {
        background: none;
        border: none;
        color: #0066cc;
        cursor: pointer;
        font-size: 0.9rem;
    }

    .filter-body {
        padding: 15px;
        border-top: 1px solid #dee2e6;
    }

    .search-field {
        position: relative;
        margin-bottom: 15px;
    }

    .search-input {
        width: 100%;
        padding: 8px 30px 8px 10px;
        border: 1px solid #ced4da;
        border-radius: 4px;
        font-size: 0.9rem;
    }

    .clear-search {
        position: absolute;
        right: 10px;
        top: 50%;
        transform: translateY(-50%);
        background: none;
        border: none;
        color: #6c757d;
        cursor: pointer;
        font-size: 0.8rem;
    }

    .users-list {
        max-height: 200px;
        overflow-y: auto;
        margin-bottom: 15px;
        border: 1px solid #dee2e6;
        border-radius: 4px;
    }

    .user-item {
        padding: 8px 12px;
        cursor: pointer;
        transition: background-color 0.2s;
        border-bottom: 1px solid #f1f3f5;
    }

    .user-item:last-child {
        border-bottom: none;
    }

    .user-item:hover {
        background-color: #e9ecef;
    }

    .user-item.selected {
        background-color: #007bff;
        color: white;
    }

    .no-results {
        padding: 10px;
        text-align: center;
        color: #6c757d;
        font-style: italic;
    }

    .loading {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 10px;
        gap: 8px;
    }

    .mini-spinner {
        width: 16px;
        height: 16px;
        border: 2px solid #f3f3f3;
        border-top: 2px solid #007bff;
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

    .filter-actions {
        display: flex;
        gap: 10px;
    }

    .apply-button,
    .clear-button {
        padding: 8px 15px;
        border-radius: 4px;
        font-size: 0.9rem;
        cursor: pointer;
        transition: background-color 0.2s;
    }

    .apply-button {
        background-color: #007bff;
        color: white;
        border: none;
    }

    .apply-button:hover:not(:disabled) {
        background-color: #0069d9;
    }

    .clear-button {
        background-color: transparent;
        color: #6c757d;
        border: 1px solid #6c757d;
    }

    .clear-button:hover:not(:disabled) {
        background-color: #f8f9fa;
    }

    button:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }
</style>
