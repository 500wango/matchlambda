FROM node:20-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine

ENV NODE_ENV=production

# Create the runtime user before copying so the app tree can be owned in one
# copy instead of a second recursive chown pass over every file.
RUN adduser -D -u 10001 appuser
WORKDIR /app
COPY --from=build --chown=appuser:appuser /app /app
RUN chown appuser:appuser /app

USER appuser
# Strip devDependencies carried over from the build stage.
RUN npm prune --omit=dev

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -qO- http://127.0.0.1:3000/ >/dev/null 2>&1 || exit 1

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
