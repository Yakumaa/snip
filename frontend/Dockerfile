FROM node:20-alpine AS dev

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

# Vite dev server — bind to 0.0.0.0 so Docker port mapping works
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ── Production build stage (optional, uncomment when needed) ──────────────────
# FROM node:20-alpine AS build
# WORKDIR /app
# COPY package*.json ./
# RUN npm ci
# COPY . .
# RUN npm run build
#
# FROM nginx:alpine AS prod
# COPY --from=build /app/dist /usr/share/nginx/html
# EXPOSE 80
