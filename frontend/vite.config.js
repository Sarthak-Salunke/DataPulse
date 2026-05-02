import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig(function (_a) {
    var mode = _a.mode;
    var env = loadEnv(mode, '.', '');
    return {
        // Server configuration
        server: {
            port: 3000,
            host: '0.0.0.0',
            open: true, // Auto-open browser
        },
        // React plugin
        plugins: [react()],
        // Environment variables (optional - for custom use)
        define: {
            'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
            'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY)
        },
        // Path aliases - COMPLETE SET
        resolve: {
            alias: {
                '@': path.resolve(__dirname, './src'),
                '@components': path.resolve(__dirname, './src/components'),
                '@services': path.resolve(__dirname, './src/services'),
                '@hooks': path.resolve(__dirname, './src/hooks'),
                '@types': path.resolve(__dirname, './src/types'),
                '@utils': path.resolve(__dirname, './src/utils'),
                '@styles': path.resolve(__dirname, './src/styles'),
            },
        },
        // Build configuration
        build: {
            outDir: 'dist',
            sourcemap: true,
            // Optimize chunks
            rollupOptions: {
                output: {
                    manualChunks: {
                        'react-vendor': ['react', 'react-dom'],
                        'recharts-vendor': ['recharts'],
                    },
                },
            },
        },
    };
});
