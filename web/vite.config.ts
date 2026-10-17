import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

// `pnpm dev` proxies /api to a running `ibank.py web` reader; put its quoted launch URL in web/.env.local:
//   IBANK_URL="http://127.0.0.1:<port>/#token=…"
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const launch = env.IBANK_URL ? new URL(env.IBANK_URL) : null;
  const token = launch ? new URLSearchParams(launch.hash.slice(1)).get("token") ?? "" : "";
  return {
    base: "./",
    plugins: [react(), tailwindcss()],
    resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
    // The reader ships prebuilt inside the skill: users and servers need Python only, never Node.
    build: {
      outDir: fileURLToPath(new URL("../skills/interview-bank/assets/web", import.meta.url)),
      emptyOutDir: true,
      assetsDir: "assets",
      sourcemap: false,
      rollupOptions: {
        input: {
          index: fileURLToPath(new URL("./index.html", import.meta.url)),
          login: fileURLToPath(new URL("./login.html", import.meta.url)),
        },
        output: {
          manualChunks: (id) => (/node_modules\/(react|react-dom|scheduler)\//.test(id) ? "react" : undefined),
        },
      },
    },
    server: {
      port: 5173,
      proxy: launch
        ? {
            "/api": {
              target: launch.origin,
              changeOrigin: true,
              // The reader accepts only its own Origin; a proxied request carries the reader's.
              headers: { "X-Interview-Token": token, Origin: launch.origin },
            },
          }
        : undefined,
    },
  };
});
