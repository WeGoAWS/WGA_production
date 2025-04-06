// src/stores/weeklyReport.ts
import { defineStore } from 'pinia';

interface ReportItem {
  id: string;
  title: string;
  date: string;
  summary: string;
  details: string;
  status: 'new' | 'viewed' | 'archived';
}

interface WeeklyReportState {
  loading: boolean;
  error: string;
  reports: ReportItem[];
  selectedReport: ReportItem | null;
  selectedWeek: string | null; // YYYY-WW 형식 (ex: 2023-01 = 2023년 1주차)
}

export const useWeeklyReportStore = defineStore('weeklyReport', {
  state: (): WeeklyReportState => ({
    loading: false,
    error: '',
    reports: [],
    selectedReport: null,
    selectedWeek: null,
  }),

  getters: {
    hasReports: (state) => state.reports.length > 0,
    
    filteredReports: (state) => {
      if (!state.selectedWeek) {
        return state.reports;
      }
      
      // 선택된 주차의 보고서만 필터링
      return state.reports.filter(report => {
        const reportDate = new Date(report.date);
        const year = reportDate.getFullYear();
        
        // 해당 날짜가 몇 주차인지 계산
        const startOfYear = new Date(year, 0, 1);
        const days = Math.floor((reportDate.getTime() - startOfYear.getTime()) / (24 * 60 * 60 * 1000));
        const weekNumber = Math.ceil((days + startOfYear.getDay() + 1) / 7);
        
        // YYYY-WW 형식으로 변환
        const reportWeek = `${year}-${weekNumber.toString().padStart(2, '0')}`;
        
        return reportWeek === state.selectedWeek;
      });
    },
    
    // 사용 가능한 모든 주차 목록
    availableWeeks: (state) => {
      const weeksSet = new Set<string>();
      
      state.reports.forEach(report => {
        const reportDate = new Date(report.date);
        const year = reportDate.getFullYear();
        
        // 해당 날짜가 몇 주차인지 계산
        const startOfYear = new Date(year, 0, 1);
        const days = Math.floor((reportDate.getTime() - startOfYear.getTime()) / (24 * 60 * 60 * 1000));
        const weekNumber = Math.ceil((days + startOfYear.getDay() + 1) / 7);
        
        // YYYY-WW 형식으로 변환
        const reportWeek = `${year}-${weekNumber.toString().padStart(2, '0')}`;
        
        weeksSet.add(reportWeek);
      });
      
      // 정렬된 배열로 변환
      return Array.from(weeksSet).sort().reverse();
    }
  },

  actions: {
    // 주간 보고서 데이터 가져오기
    async fetchReports() {
      this.loading = true;
      this.error = '';

      try {
        // API 호출을 통해 주간 보고서 데이터를 가져오는 로직
        // 여기서는 간단한 시뮬레이션 데이터
        await new Promise(resolve => setTimeout(resolve, 600));
        
        this.reports = [
          {
            id: '1',
            title: '2023년 1주차 보안 감사 보고서',
            date: '2023-01-07T00:00:00Z',
            summary: '이번 주 보안 감사 결과 요약입니다.',
            details: '이번 주 동안 총 5건의 보안 이벤트가 발생했으며, 그 중 2건은 중요도 높음으로 분류되었습니다. AWS IAM 권한 관련 이슈가 주요 발견사항이었습니다.',
            status: 'viewed'
          },
          {
            id: '2',
            title: '2023년 2주차 보안 감사 보고서',
            date: '2023-01-14T00:00:00Z',
            summary: '이번 주 보안 감사 결과 요약입니다.',
            details: '이번 주 동안 총 3건의 보안 이벤트가 발생했으며, 모두 중요도 낮음으로 분류되었습니다. 특별한 조치가 필요없는 상태입니다.',
            status: 'new'
          },
          {
            id: '3',
            title: '2023년 3주차 보안 감사 보고서',
            date: '2023-01-21T00:00:00Z',
            summary: '이번 주 보안 감사 결과 요약입니다.',
            details: '이번 주 동안 총 7건의 보안 이벤트가 발생했으며, 그 중 1건은 중요도 높음, 3건은 중요도 중간으로 분류되었습니다. GCP 접근 권한 관련 이슈가 주요 발견사항이었습니다.',
            status: 'new'
          },
        ];
      } catch (err: any) {
        console.error('주간 보고서 가져오기 오류:', err);
        this.error = err.message || '주간 보고서를 불러오는 중 오류가 발생했습니다.';
      } finally {
        this.loading = false;
      }
    },

    // 주차 선택
    selectWeek(week: string | null) {
      this.selectedWeek = week;
    },

    // 보고서 선택
    selectReport(reportId: string) {
      this.selectedReport = this.reports.find(r => r.id === reportId) || null;
      
      // 선택한 보고서를 '읽음' 상태로 변경
      if (this.selectedReport && this.selectedReport.status === 'new') {
        this.updateReportStatus(reportId, 'viewed');
      }
    },

    // 보고서 상태 업데이트
    updateReportStatus(reportId: string, status: 'new' | 'viewed' | 'archived') {
      const report = this.reports.find(r => r.id === reportId);
      if (report) {
        report.status = status;
      }
    },

    // 상태 초기화
    resetState() {
      this.loading = false;
      this.error = '';
      this.reports = [];
      this.selectedReport = null;
      this.selectedWeek = null;
    }
  }
});