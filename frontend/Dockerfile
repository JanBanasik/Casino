FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
# Env-templated config: the nginx image runs envsubst over /etc/nginx/templates
# at startup. Defaults below keep local docker-compose working; Render overrides
# BACKEND_URL (its own backend URL) and PORT (its assigned port).
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
ENV BACKEND_URL=http://backend:8000 \
    PORT=80 \
    NGINX_ENVSUBST_FILTER=^(BACKEND_URL|PORT)$
EXPOSE 80
