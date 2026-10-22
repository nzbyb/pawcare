FROM node:20-alpine AS build

WORKDIR /app

# 国内服务器可传 --build-arg NPM_REGISTRY=https://registry.npmmirror.com
ARG NPM_REGISTRY=https://registry.npmjs.org
# 登录页的演示账号入口：设 false 可整体隐藏（Vite 变量在构建时固化）
ARG VITE_DEMO_ACCOUNTS=true
ENV VITE_DEMO_ACCOUNTS=$VITE_DEMO_ACCOUNTS

COPY package*.json ./
RUN npm ci --registry="$NPM_REGISTRY"

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
