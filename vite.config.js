import { defineConfig } from "vite";

// base: './' => relative asset paths so the site works under GitHub Pages
// project subpath (user/repo) and a future custom domain (flash.ape…) alike.
export default defineConfig({
  base: "./",
  build: {
    outDir: "dist",
    target: "es2020",
  },
});
