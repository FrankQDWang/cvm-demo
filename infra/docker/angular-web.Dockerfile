# Pin the Node base image to avoid Docker Hub tag metadata drift during CI image verification.
FROM node:24-alpine@sha256:7fddd9ddeae8196abf4a3ef2de34e11f7b1a722119f91f28ddf1e99dcafdf114 AS build

WORKDIR /app

ARG APP_DIR=apps/web-user
ARG APP_NAME=web-user

RUN corepack enable

COPY . .

RUN pnpm install --frozen-lockfile
RUN ./tools/bootstrap/write-runtime-config.sh "${APP_DIR}"
RUN pnpm --dir "${APP_DIR}" run build

FROM nginx:1.27-alpine

ARG APP_DIR=apps/web-user
ARG APP_NAME=web-user

COPY infra/docker/nginx-spa.conf /etc/nginx/conf.d/default.conf
COPY infra/docker/render-runtime-config.sh /docker-entrypoint.d/40-runtime-config.sh
RUN chmod +x /docker-entrypoint.d/40-runtime-config.sh
COPY --from=build /app/${APP_DIR}/dist/${APP_NAME}/browser /usr/share/nginx/html

EXPOSE 80
