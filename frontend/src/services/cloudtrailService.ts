// src/services/cloudTrailService.ts
import axios from 'axios';

// CloudTrail 로그 인터페이스
export interface CloudTrailEvent {
    EventId: string;
    EventName: string;
    EventTime: string;
    Username: string;
    Resources: any[];
    CloudTrailEvent: string;
    // 추가 속성...
}

export interface CloudTrailResponse {
    Events: CloudTrailEvent[];
    NextToken?: string;
}

class CloudTrailService {
    private apiUrl: string;

    constructor() {
        this.apiUrl = import.meta.env.API_URL || 'http://localhost:8000';
    }

    /**
     * CloudTrail 로그 가져오기
     * @param maxResults 최대 결과 수
     * @returns CloudTrail 이벤트 목록
     */
    async getCloudTrailLogs(maxResults: number = 50): Promise<CloudTrailEvent[]> {
        try {
            const response = await axios.get<CloudTrailResponse>(`${this.apiUrl}/cloudtrail/logs`, {
                params: { max_results: maxResults },
                withCredentials: true,
            });

            return response.data.Events;
        } catch (error: any) {
            console.error('Error fetching CloudTrail logs:', error);
            throw new Error(
                error.response?.data?.detail ||
                    'CloudTrail 로그를 가져오는 중 오류가 발생했습니다.',
            );
        }
    }

    /**
     * CloudTrail 로그 분석
     * @param maxResults 최대 결과 수
     * @param outputBucketName (선택) 결과 저장 S3 버킷 이름
     * @param outputFileKey (선택) 결과 저장 S3 파일 키
     * @returns 분석 결과
     */
    async analyzeCloudTrailLogs(
        maxResults: number = 10,
        outputBucketName?: string,
        outputFileKey?: string,
    ): Promise<any> {
        try {
            const response = await axios.get(`${this.apiUrl}/cloudtrail/analyze-logs`, {
                params: {
                    max_results: maxResults,
                    output_bucket_name: outputBucketName,
                    output_file_key: outputFileKey,
                },
                withCredentials: true,
            });

            return response.data;
        } catch (error: any) {
            console.error('Error analyzing CloudTrail logs:', error);
            throw new Error(
                error.response?.data?.detail || 'CloudTrail 로그 분석 중 오류가 발생했습니다.',
            );
        }
    }

    /**
     * GCP 로그 가져오기
     * @param maxResults 최대 결과 수
     * @returns GCP 로그 목록
     */
    async getGcpLogs(maxResults: number = 50): Promise<any[]> {
        try {
            const response = await axios.get(`${this.apiUrl}/gcp/logs`, {
                params: { max_results: maxResults },
                withCredentials: true,
            });

            return response.data;
        } catch (error: any) {
            console.error('Error fetching GCP logs:', error);
            throw new Error(
                error.response?.data?.detail || 'GCP 로그를 가져오는 중 오류가 발생했습니다.',
            );
        }
    }

    /**
     * Azure 로그 가져오기
     * @param maxResults 최대 결과 수
     * @returns Azure 로그 목록
     */
    async getAzureLogs(maxResults: number = 50): Promise<any[]> {
        try {
            const response = await axios.get(`${this.apiUrl}/azure/logs`, {
                params: { max_results: maxResults },
                withCredentials: true,
            });

            return response.data;
        } catch (error: any) {
            console.error('Error fetching Azure logs:', error);
            throw new Error(
                error.response?.data?.detail || 'Azure 로그를 가져오는 중 오류가 발생했습니다.',
            );
        }
    }
}

export default new CloudTrailService();
