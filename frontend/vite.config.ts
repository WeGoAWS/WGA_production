// vite.config.ts
import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';


// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
    // 환경 변수 로드 (접두사 없이)
    const env = loadEnv(mode, process.cwd(), '');

    return {
        plugins: [vue()],
        resolve: {
            alias: {
                '@': path.resolve(__dirname, './src'),
            },
        },
        server: {
            port: 5173, // 리다이렉트 URI와 일치하도록 변경
            proxy: {
                '/api': {  //#1. axios라이브러리 등으로 http 요청인데 api로 시작하면,
                  target: env.API_DEST,  //#2. 이쪽 주소로 매핑하여 백그라운드로 보내라.
                  changeOrigin: true,
                  rewrite: (path) => path.replace(/^\/api/, ''),
                  secure: false,
                  ws: true
                }
            }
        },
        // 환경 변수를 클라이언트에 노출
        define: {
            'import.meta.env.AWS_REGION': JSON.stringify(env.AWS_REGION),
            'import.meta.env.USER_POOL_ID': JSON.stringify(env.USER_POOL_ID),
            'import.meta.env.COGNITO_CLIENT_ID': JSON.stringify(env.COGNITO_CLIENT_ID),
            'import.meta.env.COGNITO_REDIRECT_URI': JSON.stringify(env.COGNITO_REDIRECT_URI),
            'import.meta.env.COGNITO_DOMAIN': JSON.stringify(env.COGNITO_DOMAIN),
            'import.meta.env.API_URL': JSON.stringify(env.API_URL),
            // 민감한 정보는 필요할 때만 노출
            'import.meta.env.COGNITO_CLIENT_SECRET': JSON.stringify(env.COGNITO_CLIENT_SECRET),
            'import.meta.env.AWS_ACCESS_KEY_ID': JSON.stringify(env.AWS_ACCESS_KEY_ID),
            'import.meta.env.AWS_SECRET_ACCESS_KEY': JSON.stringify(env.AWS_SECRET_ACCESS_KEY),
            'import.meta.env.COGNITO_IDENTITY_POOL_ID': JSON.stringify(
                env.COGNITO_IDENTITY_POOL_ID,
            ),
            'import.meta.env.API_DEST': JSON.stringify(env.API_DEST)
        },
    };
});
