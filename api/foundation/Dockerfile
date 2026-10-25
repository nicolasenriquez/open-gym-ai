ARG NODE_IMAGE=node:22.23.2-bookworm-slim@sha256:48e4b67d85f87bd551df43704e24d252f56cc5f8e9718841aace50f19948f0f9
FROM ${NODE_IMAGE} AS dependencies
ENV COREPACK_HOME=/opt/corepack
RUN corepack enable && corepack prepare pnpm@10.34.8 --activate
WORKDIR /app
RUN chown node:node /app
USER node
COPY --chown=node:node package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --ignore-scripts --engine-strict --package-import-method=copy

FROM postgres:18.6-trixie@sha256:edb0c08dc33befd0262ab3b5cf1c4f3f8cfd8b09e88c05b45adee29d6761ddb6
LABEL org.opengym.foundation=synthetic
COPY --from=dependencies /usr/local/bin/node /usr/local/bin/node
COPY --from=dependencies /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=dependencies /opt/corepack/ /opt/corepack/
ENV COREPACK_HOME=/opt/corepack
RUN ln -s ../lib/node_modules/corepack/dist/pnpm.js /usr/local/bin/pnpm
WORKDIR /app
COPY --from=dependencies --chown=1000:1000 /app/ ./
USER 1000:1000
COPY --chown=1000:1000 *.mjs versions.json dependency-licenses.json ./
COPY --chown=1000:1000 migrations/ ./migrations/
RUN pnpm run check:toolchain
ENTRYPOINT ["node", "run.mjs"]
CMD ["environment"]
