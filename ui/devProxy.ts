import express from 'express';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import type { Plugin } from 'vite';

export default function devProxy(): Plugin {
  return {
    name: 'dev-proxy-mocks',
    configureServer(server) {
      if (process.env.VITE_USE_MOCKS !== '1') return;

      const app = express();
      const mocksDir = fileURLToPath(new URL('./mocks', import.meta.url));

      app.post('/fast', (_req, res) => {
        const data = JSON.parse(
          readFileSync(path.join(mocksDir, 'fast-example.json'), 'utf-8')
        );
        res.json(data);
      });

      app.get('/chats/session', (_req, res) => {
        const data = JSON.parse(
          readFileSync(path.join(mocksDir, 'deep-session.json'), 'utf-8')
        );
        res.json(data);
      });

      app.get('/index/status', (_req, res) => {
        const data = JSON.parse(
          readFileSync(path.join(mocksDir, 'index-status.json'), 'utf-8')
        );
        res.json(data);
      });

      server.middlewares.use(app);
    },
  };
}
