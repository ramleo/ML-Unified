# Isolated Testwright test-execution service.
# Node base + Playwright's own browser installer keeps @playwright/test and the
# Chromium build version-locked — the single biggest cause of "browser not
# found" failures is a version mismatch, so we install browsers for the exact
# package version rather than pulling a prebuilt browser image on a fixed tag.
FROM node:20-bookworm

WORKDIR /app

# Install deps first for layer caching.
COPY package.json ./
RUN npm install --omit=dev

# Fetch Chromium + its system libraries for the installed Playwright version.
RUN npx playwright install --with-deps chromium

COPY . .

# HF Spaces (Docker) expose the app on 7860 by default.
ENV PORT=7860
ENV NODE_ENV=production
EXPOSE 7860

CMD ["node", "server.js"]
