import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  base: './',
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  publicDir: false,
  build: {
    outDir: '../OlivaDiceWebUI/webui',
    emptyOutDir: true,
    modulePreload: { polyfill: false },
    rollupOptions: { input: path.resolve(__dirname, 'olivadice.html') },
  },
});
