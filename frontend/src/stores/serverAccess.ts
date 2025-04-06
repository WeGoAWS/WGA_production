// src/stores/serverAccess.ts
import { defineStore } from 'pinia';

interface ServerAccessLog {
  id: number;
  username: string;
  ipAddress: string;
  timestamp: string;
  action: string;
  server: string;
  status: 'success' | 'failed';
}

interface ServerAccessState {
  loading: boolean;
  error: string;
  accessLogs: ServerAccessLog[];
  selectedDateRange: { startDate: string; endDate: string } | null;
  selectedServer: string | null;
  selectedUser: string | null;
}

export const useServerAccessStore = defineStore('serverAccess', {
  state: (): ServerAccessState => ({
    loading: false,
    error: '',
    accessLogs: [],
    selectedDateRange: null,
    selectedServer: null,
    selectedUser: null,
  }),

  getters: {
    hasLogs: (state) => state.accessLogs.length > 0,
    
    filteredLogs: (state) => {
      let logs = [...state.accessLogs];
      
      // 서버 필터링
      if (state.selectedServer) {
        logs = logs.filter(log => log.server === state.selectedServer);
      }
      
      // 사용자 필터링
      if (state.selectedUser) {
        logs = logs.filter(log => log.username === state.selectedUser);
      }
      
      // 날짜 범위 필터링
      if (state.selectedDateRange) {
        const startDate = new Date(state.selectedDateRange.startDate).getTime();
        const endDate = new Date(state.selectedDateRange.endDate).getTime();
        
        logs = logs.filter(log => {
          const logDate = new Date(log.timestamp).getTime();
          return logDate >= startDate && logDate <= endDate;
        });
      }
      
      return logs;
    },
  },

  actions: {
    // 서버 접근 로그 데이터 가져오기
    async fetchAccessLogs() {
      this.loading = true;
      this.error = '';

      try {
        // API 호출을 통해 서버 접근 로그 데이터를 가져오는 로직
        // 여기서는 간단한 시뮬레이션 데이터
        await new Promise(resolve => setTimeout(resolve, 800));
        
        const currentDate = new Date();
        
        this.accessLogs = [
          {
            id: 1,
            username: 'admin@example.com',
            ipAddress: '192.168.1.100',
            timestamp: new Date(currentDate.getTime() - 3600000).toISOString(), // 1시간 전
            action: 'LOGIN',
            server: 'web-server-01',
            status: 'success'
          },
          {
            id: 2,
            username: 'developer1@example.com',
            ipAddress: '192.168.1.101',
            timestamp: new Date(currentDate.getTime() - 7200000).toISOString(), // 2시간 전
            action: 'FILE_UPLOAD',
            server: 'file-server-01',
            status: 'success'
          },
          {
            id: 3,
            username: 'developer1@example.com',
            ipAddress: '192.168.1.101',
            timestamp: new Date(currentDate.getTime() - 10800000).toISOString(), // 3시간 전
            action: 'LOGIN',
            server: 'db-server-01',
            status: 'failed'
          },
        ];
      } catch (err: any) {
        console.error('서버 접근 로그 가져오기 오류:', err);
        this.error = err.message || '서버 접근 로그를 불러오는 중 오류가 발생했습니다.';
      } finally {
        this.loading = false;
      }
    },

    // 날짜 필터 설정
    setDateFilter(dateRange: { startDate: string; endDate: string } | null) {
      this.selectedDateRange = dateRange;
    },

    // 서버 필터 설정
    setServerFilter(server: string | null) {
      this.selectedServer = server;
    },

    // 사용자 필터 설정
    setUserFilter(username: string | null) {
      this.selectedUser = username;
    },

    // 상태 초기화
    resetState() {
      this.loading = false;
      this.error = '';
      this.accessLogs = [];
      this.selectedDateRange = null;
      this.selectedServer = null;
      this.selectedUser = null;
    }
  }
});