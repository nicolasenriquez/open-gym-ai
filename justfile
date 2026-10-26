set shell := ["sh", "-cu"]
set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command"]

instance := "docker compose --project-directory . --env-file .env -f docker-compose.yml -p opengym"
platform := "docker compose --project-directory . -f deploy/docker-compose.yml"
dev_compose := platform + " -f deploy/docker-compose.dev.yml -p opengym-dev"
prod_compose := platform + " -f deploy/docker-compose.prod.yml -p opengym-ops"
# Export parameters instead of interpolating user input into shell source.
env_arg := if os_family() == "windows" { "$env:env" } else { "\"$env\"" }
suite_arg := if os_family() == "windows" { "$env:suite" } else { "\"$suite\"" }
case_arg := if os_family() == "windows" { "$env:case" } else { "\"$case\"" }

# Show commands without starting services.
default:
    @just --list

# Build and start the current permanent Node instance.
up:
    {{instance}} up -d --build api web

# Preserve containers and data.
stop:
    {{instance}} stop

logs:
    {{instance}} logs -f api web

# Dev env-file: absolute path, independent secrets, PLATFORM_WEB_PORT=8081.
dev $env:
    node -e "if (!require('node:path').isAbsolute(process.env.env)) throw new Error('Use an absolute Dev env-file path')"
    {{dev_compose}} --env-file {{env_arg}} config --quiet
    {{dev_compose}} --env-file {{env_arg}} build web api bootstrap migrate
    {{dev_compose}} --env-file {{env_arg}} up -d --wait --wait-timeout 90 db
    {{dev_compose}} --env-file {{env_arg}} run --rm bootstrap
    {{dev_compose}} --env-file {{env_arg}} run --rm migrate
    {{dev_compose}} --env-file {{env_arg}} up -d --wait --wait-timeout 90 api web

# Preserve Dev containers and data.
dev-stop $env:
    {{dev_compose}} --env-file {{env_arg}} stop

# Inspect future permanent Python configuration without activating it.
prod-config $env:
    {{prod_compose}} --env-file {{env_arg}} config --quiet

test $suite:
    node scripts/platform.mjs verify {{suite_arg}}

test-case $suite $case:
    node scripts/platform.mjs verify {{suite_arg}} --case {{case_arg}}

# Read-only inventory of all Compose projects on this Docker host.
status:
    docker compose ls --all
