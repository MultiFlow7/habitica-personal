FROM node:20.20.2-bookworm-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends git python3 make g++ libkrb5-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV GIT_CONFIG_COUNT=2 \
    GIT_CONFIG_KEY_0=url.https://github.com/.insteadOf \
    GIT_CONFIG_VALUE_0=ssh://git@github.com/ \
    GIT_CONFIG_KEY_1=url.https://.insteadOf \
    GIT_CONFIG_VALUE_1=git:// \
    npm_config_registry=https://registry.npmjs.org
COPY . .
RUN python3 deploy/configure.py --output config.json && npm ci --no-audit --no-fund
RUN NODE_ENV=test npm run test:common
RUN APP_BASE_PATH=/habitica/ npm run client:build
RUN NODE_ENV=production ./node_modules/.bin/gulp build:prod
RUN npm prune --omit=dev --ignore-scripts --no-audit --no-fund

FROM node:20.20.2-bookworm-slim AS runtime
ARG REVISION
LABEL org.opencontainers.image.source="https://github.com/MultiFlow7/habitica-personal" \
      org.opencontainers.image.revision=$REVISION
WORKDIR /app
ENV NODE_ENV=production NODE_OPTIONS=--max-old-space-size=512
COPY --from=build --chown=node:node /app/node_modules ./node_modules
COPY --from=build --chown=node:node /app/package.json ./package.json
COPY --from=build --chown=node:node /app/website/transpiled-babel ./website/transpiled-babel
COPY --from=build --chown=node:node /app/website/common ./website/common
COPY --from=build --chown=node:node /app/website/client/dist ./website/client/dist
COPY --from=build --chown=node:node /app/content_cache ./content_cache
COPY --from=build --chown=node:node /app/i18n_cache ./i18n_cache
COPY --chown=node:node deploy/smoke.mjs ./deploy/smoke.mjs
COPY --chown=node:node deploy/check.mjs ./deploy/check.mjs
USER node
EXPOSE 3000
CMD ["node", "website/transpiled-babel/index.js"]
