FROM node:24-alpine AS build
WORKDIR /app
# Dependencies first so code changes do not invalidate this layer.
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build && npm prune --omit=dev

FROM node:24-alpine
ENV NODE_ENV=production \
    PORT=3000 \
    FINANZFUCHS_DATABASE=/app/data/finanzfuchs.db \
    NODE_OPTIONS=--disable-warning=ExperimentalWarning
WORKDIR /app
COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/build ./build
# The compose file runs it as the host user that owns the data folder.
USER node
EXPOSE 3000
CMD ["node_modules/.bin/react-router-serve", "./build/server/index.js"]
