# The AEGIS dashboard as a container image, in two stages ("multi-stage build").
# Build:  docker build -t aegis-web ./frontend

# Stage 1: build. Needs Node.js and all the build tools.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci                      # exact versions from package-lock.json
COPY . .
# Empty = call the API on the same address (/api), which nginx forwards below.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build               # type-check, then produce static files in dist/

# Stage 2: serve. Only the built files + a tiny web server. Node.js, the source
# code and node_modules are left behind in stage 1, so the final image is small.
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
