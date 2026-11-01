FROM python:3.14.9-slim-bookworm@sha256:945c2676dc2b18e0c1f16879244122c57c0ffede60006bf3df159c507a31bcae
RUN apt-get update && apt-get install -y --no-install-recommends rsyslog=8.2302.0-1+deb12u1 logrotate=3.21.0-1 && dpkg-query -W > /package-manifest.txt && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /logs /state /run/diagnostics && chown 1000:1000 /logs /state /run/diagnostics && chmod 0700 /logs /state && chmod 0711 /run/diagnostics
COPY --chmod=0555 rotate /usr/local/bin/rotate
COPY --chmod=0444 rsyslog.conf logrotate.conf /etc/opengym/
COPY --chmod=0444 run.py /usr/local/bin/diagnostics.py
RUN chmod 0555 /etc/opengym
USER 1000:1000
ENTRYPOINT ["python", "/usr/local/bin/diagnostics.py"]
