<!-- src/components/DateRangeFilter.vue -->
<template>
    <div class="date-range-filter">
        <div class="filter-header">
            <h3>날짜 범위 필터</h3>
            <button @click="toggleFilter" class="toggle-button">
                {{ expanded ? '접기' : '펼치기' }}
            </button>
        </div>

        <div v-if="expanded" class="filter-body">
            <div class="date-inputs">
                <div class="date-field">
                    <label for="start-date">시작일</label>
                    <input
                        type="date"
                        id="start-date"
                        v-model="startDate"
                        :max="endDate || today"
                    />
                </div>

                <div class="date-field">
                    <label for="end-date">종료일</label>
                    <input
                        type="date"
                        id="end-date"
                        v-model="endDate"
                        :min="startDate"
                        :max="today"
                    />
                </div>
            </div>

            <div class="filter-actions">
                <button
                    @click="applyFilter"
                    class="apply-button"
                    :disabled="!startDate || !endDate || loading"
                >
                    {{ loading ? '적용 중...' : '적용하기' }}
                </button>

                <button @click="clearFilter" class="clear-button" :disabled="loading">
                    초기화
                </button>
            </div>

            <div class="quick-selections">
                <button
                    v-for="(option, index) in quickOptions"
                    :key="index"
                    @click="() => selectQuickOption(option.days)"
                    class="quick-option"
                    :disabled="loading"
                >
                    {{ option.label }}
                </button>
            </div>
        </div>
    </div>
</template>

<script lang="ts">
    import { computed, defineComponent, ref } from 'vue';

    export default defineComponent({
        name: 'DateRangeFilter',

        props: {
            loading: {
                type: Boolean,
                default: false,
            },
        },

        emits: ['filter'],

        setup(props, { emit }) {
            const expanded = ref(false);
            const startDate = ref('');
            const endDate = ref('');

            // 오늘 날짜 계산 (YYYY-MM-DD 형식)
            const today = computed(() => {
                const date = new Date();
                return date.toISOString().split('T')[0];
            });

            // 날짜 범위 빠른 선택 옵션
            const quickOptions = [
                {
                    label: '최근 7일',
                    days: 7,
                },
                {
                    label: '최근 30일',
                    days: 30,
                },
                {
                    label: '최근 90일',
                    days: 90,
                },
            ];

            // 필터 토글
            const toggleFilter = () => {
                expanded.value = !expanded.value;
            };

            // 필터 적용
            const applyFilter = () => {
                if (startDate.value && endDate.value) {
                    emit('filter', {
                        startDate: startDate.value,
                        endDate: endDate.value,
                    });
                }
            };

            // 필터 초기화
            const clearFilter = () => {
                startDate.value = '';
                endDate.value = '';
                emit('filter', null);
            };

            // 빠른 선택 옵션 처리
            const selectQuickOption = (days: number) => {
                const end = new Date();
                const start = new Date();
                start.setDate(start.getDate() - days);

                endDate.value = end.toISOString().split('T')[0];
                startDate.value = start.toISOString().split('T')[0];

                // 자동으로 필터 적용
                applyFilter();
            };

            return {
                expanded,
                startDate,
                endDate,
                today,
                quickOptions,
                toggleFilter,
                applyFilter,
                clearFilter,
                selectQuickOption,
            };
        },
    });
</script>

<style scoped>
    .date-range-filter {
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

    .date-inputs {
        display: flex;
        gap: 15px;
        margin-bottom: 15px;
    }

    .date-field {
        flex: 1;
        display: flex;
        flex-direction: column;
    }

    label {
        font-size: 0.9rem;
        margin-bottom: 5px;
        color: #555;
    }

    input[type='date'] {
        padding: 8px 10px;
        border: 1px solid #ced4da;
        border-radius: 4px;
        font-size: 0.9rem;
    }

    .filter-actions {
        display: flex;
        gap: 10px;
        margin-bottom: 15px;
    }

    .apply-button,
    .clear-button,
    .quick-option {
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

    .quick-selections {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
    }

    .quick-option {
        background-color: #e9ecef;
        color: #495057;
        border: 1px solid #ced4da;
        font-size: 0.8rem;
    }

    .quick-option:hover:not(:disabled) {
        background-color: #dee2e6;
    }

    button:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }
</style>
