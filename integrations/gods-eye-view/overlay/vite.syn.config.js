import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import { BROWSER_HEADERS, createBrowserViteConfig } from './build/vite.js';

/** Syn profile: no environment loading, provider routes, MCP or remote basemap. */
export default defineConfig(({ command }) => {
  const config = createBrowserViteConfig({ command, host: '127.0.0.1', port: 5173, publicDir: false });
  config.envFile = false;
  const headers = { ...BROWSER_HEADERS,
    'Content-Security-Policy': BROWSER_HEADERS['Content-Security-Policy'].replace(
      "connect-src 'self' blob: data: https: wss: ws:",
      "connect-src 'self' blob: data: http://127.0.0.1:8765",
    ),
  };
  config.server = { ...config.server, strictPort: true, headers };
  config.preview = { ...config.preview, host: '127.0.0.1', port: 5173, strictPort: true, headers };
  config.build = { ...config.build, rollupOptions: {
    input: fileURLToPath(new URL('./syn.html', import.meta.url)),
  } };
  return config;
});
