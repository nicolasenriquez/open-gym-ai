ARG NODE_IMAGE=node:22.23.2-bookworm-slim@sha256:48e4b67d85f87bd551df43704e24d252f56cc5f8e9718841aace50f19948f0f9
FROM ${NODE_IMAGE}
LABEL org.opengym.foundation=synthetic
WORKDIR /app
RUN chown node:node /app
USER node
COPY --chown=node:node package.json package-lock.json ./
RUN npm ci --ignore-scripts --engine-strict --no-audit --no-fund
COPY --chown=node:node *.mjs versions.json ./
RUN npm run check:toolchain
ENTRYPOINT ["node", "run.mjs"]
CMD ["environment"]
