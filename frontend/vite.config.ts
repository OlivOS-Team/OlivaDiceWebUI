import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  base: './',
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  publicDir: false,
  build: {
    outDir: '../OlivaDiceWebUI/web',
    emptyOutDir: true,
    rollupOptions: { input: path.resolve(__dirname, 'olivadice.html') },
  },
});
