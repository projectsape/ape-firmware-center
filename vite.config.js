import { copyFileSync } from "node:fs";
import { defineConfig } from "vite";

// Ships THIRD_PARTY_LICENSES.md with the built site, so the licensing and
// corresponding-source notice sits beside the binaries it describes.
const copyLicenses = () => ({
  name: "copy-licenses",
  closeBundle() {
    copyFileSync("THIRD_PARTY_LICENSES.md", "dist/THIRD_PARTY_LICENSES.md");
  },
});

// base: './' => relative asset paths so the site works under GitHub Pages
// project subpath (user/repo) and a future custom domain (flash.ape…) alike.
export default defineConfig({
  base: "./",
  plugins: [copyLicenses()],
  build: {
    outDir: "dist",
    target: "es2020",
  },
});
