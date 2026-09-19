import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

function inlineWebUI(): Plugin {
  return {
    name: 'inline-olivos-webui',
    enforce: 'post',
    generateBundle(_options, bundle) {
      const html = Object.values(bundle).find(
        item => item.type === 'asset' && item.fileName.endsWith('.html'),
      );
      if (!html || html.type !== 'asset' || typeof html.source !== 'string') {
        throw new Error('Vite did not emit the OlivaDice WebUI HTML entry');
      }
      let source = html.source;
      for (const [fileName, item] of Object.entries(bundle)) {
        if (item.type === 'chunk' && item.isEntry) {
          const pattern = new RegExp(`<script[^>]+src=["']\\./${escapeRegExp(fileName)}["'][^>]*></script>`);
          const code = item.code.replace(/<\/script/gi, '<\\/script');
          source = source.replace(pattern, () => `<script type="module">${code}</script>`);
          delete bundle[fileName];
        } else if (item.type === 'asset' && fileName.endsWith('.css')) {
          const pattern = new RegExp(`<link[^>]+href=["']\\./${escapeRegExp(fileName)}["'][^>]*>`);
          const css = String(item.source).replace(/<\/style/gi, '<\\/style');
          source = source.replace(pattern, () => `<style>${css}</style>`);
          delete bundle[fileName];
        }
      }
      html.source = source;
      if (/\b(?:src|href)=["']\.\/assets\//.test(source)) {
        const external = source.match(/[^>]+\b(?:src|href)=["']\.\/assets\/[^>]+/g) || [];
        throw new Error(`WebUI build still contains external assets: ${external.join(' | ')}`);
      }
    },
  };
}

export default defineConfig(({ mode }) => {
  const standalone = mode === 'standalone';
  return {
    plugins: [react(), ...(standalone ? [] : [inlineWebUI()])],
    base: './',
    define: { 'import.meta.env.VITE_WEBUI_MODE': JSON.stringify(standalone ? 'standalone' : 'official') },
    resolve: { alias: { '@': path.resolve(__dirname, './src') } },
    publicDir: false,
    build: {
      outDir: standalone ? '../OlivaDiceWebUIStandalone/web' : '../OlivaDiceWebUI/webui',
      emptyOutDir: true,
      ...(standalone ? {} : { modulePreload: { polyfill: false } }),
      rollupOptions: { input: path.resolve(__dirname, 'olivadice.html') },
    },
  };
});
