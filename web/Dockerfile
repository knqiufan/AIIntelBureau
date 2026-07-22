FROM node:22-alpine AS build
WORKDIR /web
COPY docs/my/demo/ai_intel_bureau/web/package.json docs/my/demo/ai_intel_bureau/web/package-lock.json ./
RUN npm ci
COPY docs/my/demo/ai_intel_bureau/web ./
RUN npm run build

FROM nginx:1.27-alpine
COPY docs/my/demo/ai_intel_bureau/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 8080
