// src/stores/logAnalysis.ts
import { defineStore } from 'pinia';
import type { AnalysisResult } from '@/services/policyService';
import policyService from '@/services/policyService';

interface LogAnalysisState {
    analysisResults: AnalysisResult[];
    loading: boolean;
    error: string;
    selectedUser: string | null;
    selectedDateRange: { startDate: string; endDate: string } | null;
    cloudProvider: 'aws' | 'gcp' | 'azure';
}

export const useLogAnalysisStore = defineStore('logAnalysis', {
    state: (): LogAnalysisState => ({
        analysisResults: [],
        loading: false,
        error: '',
        selectedUser: null,
        selectedDateRange: null,
        cloudProvider: 'aws',
    }),

    getters: {
        showResults: (state) => state.analysisResults && state.analysisResults.length > 0,
    },

    actions: {
        // 클라우드 제공자 설정
        setCloudProvider(provider: 'aws' | 'gcp' | 'azure') {
            this.cloudProvider = provider;
        },

        // 사용자 필터 설정
        setUserFilter(username: string | null) {
            this.selectedUser = username;
        },

        // 날짜 필터 설정
        setDateFilter(dateRange: { startDate: string; endDate: string } | null) {
            this.selectedDateRange = dateRange;
        },

        // 분석 데이터 가져오기
        async getAnalysisData() {
            this.loading = true;
            this.error = '';

            try {
                // 실제 API 호출
                let results: AnalysisResult[] = [];

                // 사용자 필터가 있는 경우
                if (this.selectedUser) {
                    results = await policyService.analyzeUserLogs(this.selectedUser);
                } 
                // 날짜 필터가 있는 경우
                else if (this.selectedDateRange) {
                    results = await policyService.analyzeLogsByDateRange(
                        this.selectedDateRange.startDate,
                        this.selectedDateRange.endDate
                    );
                } 
                // 필터 없는 경우 기본 분석 데이터 가져오기
                else {
                    results = await policyService.getDemoAnalysis();
                }

                // 오류 방지를 위해 results가 배열인지 확인
                this.analysisResults = Array.isArray(results) ? results : [];
            } catch (err: any) {
                console.error('API 호출 오류:', err);
                this.error = err.message || '데이터를 가져오는 중 오류가 발생했습니다.';
                this.analysisResults = []; // 오류 발생 시 빈 배열로 초기화
            } finally {
                this.loading = false;
            }
        },

        // 분석 결과 저장
        async saveAnalysisResult(result: AnalysisResult) {
            try {
                await policyService.saveAnalysisResult(result);
                return true;
            } catch (error: any) {
                console.error('저장 오류:', error);
                return false;
            }
        },

        // 상태 초기화 (필요 시 사용)
        resetState() {
            this.analysisResults = [];
            this.loading = false;
            this.error = '';
            this.selectedUser = null;
            this.selectedDateRange = null;
            this.cloudProvider = 'aws';
        }
    }
});