SYSTEM_CONFIG=config.env
SYSTEM_SECRETS=secrets.env

# Load both files into Make variables.
# -include means Make won't error if secrets.env is absent (it will fail later
# at the Docker Compose step with a clearer message about missing variables).
include  $(SYSTEM_CONFIG)
-include $(SYSTEM_SECRETS)
export

# Shared --env-file flags for all docker compose calls
ENV_FILES=--env-file $(SYSTEM_CONFIG) --env-file $(SYSTEM_SECRETS)


# --- Host bootstrap
bootstrap-pi:
	./bootstrap_pi.sh


# --- System: Tailscale (host, not docker)
tailscale-status:
	@sudo tailscale status || true
	@echo ""
	@echo "Tailscale IPs:"
	@tailscale ip -4 2>/dev/null || true
	@tailscale ip -6 2>/dev/null || true

tailscale-up:
	@sudo systemctl enable --now tailscaled
	@sudo tailscale up

tailscale-down:
	@sudo tailscale down


# region --- Platform
# --- Platform: Postgres
PG_DIR=../02_Platform/01_Postgres

PG_COMPOSE=docker compose \
	-f $(PG_DIR)/compose.yml \
	$(ENV_FILES)

pg-up:
	$(PG_COMPOSE) up -d

pg-down:
	$(PG_COMPOSE) down

# this only works because it is just commands. If you ever add cd or variables, you'll want .ONESHELL
pg-reboot:
	$(PG_COMPOSE) down
	$(PG_COMPOSE) up -d

pg-ps:
	$(PG_COMPOSE) ps

pg-logs:
	$(PG_COMPOSE) logs -f

pg-shell:
	$(PG_COMPOSE) exec -it postgres psql -U $(ATLAS_PG_USER) -d $(ATLAS_PG_DB)

pg-data-check:
	@echo "Host path ($(DATA_ROOT)/postgres):"
	@sudo ls -la $(DATA_ROOT)/postgres | head -n 20
	@echo ""
	@echo "Container path (/var/lib/postgresql/data):"
	@$(PG_COMPOSE) exec -T postgres ls -la /var/lib/postgresql/data | head -n 20


# --- Platform: Postgres - Schemas
PG_SCHEMA=../03_Application/WorkoutTracker/schema.sql
PG_SCHEMA_TASK=../03_Application/TaskTracker/schema.sql
PG_SCHEMA_FOOD=../03_Application/FoodTracker/schema.sql

schema:
	@test -n "$(ATLAS_PG_USER)" || (echo "ATLAS_PG_USER missing" && exit 1)
	@test -n "$(ATLAS_PG_DB)"   || (echo "ATLAS_PG_DB missing" && exit 1)
	$(PG_COMPOSE) exec -T postgres psql -v ON_ERROR_STOP=1 -U $(ATLAS_PG_USER) -d $(ATLAS_PG_DB) < $(PG_SCHEMA)

schema-task:
	@test -n "$(ATLAS_PG_USER)" || (echo "ATLAS_PG_USER missing" && exit 1)
	@test -n "$(ATLAS_PG_DB)"   || (echo "ATLAS_PG_DB missing" && exit 1)
	$(PG_COMPOSE) exec -T postgres psql -v ON_ERROR_STOP=1 -U $(ATLAS_PG_USER) -d $(ATLAS_PG_DB) < $(PG_SCHEMA_TASK)

schema-food:
	@test -n "$(ATLAS_PG_USER)" || (echo "ATLAS_PG_USER missing" && exit 1)
	@test -n "$(ATLAS_PG_DB)"   || (echo "ATLAS_PG_DB missing" && exit 1)
	$(PG_COMPOSE) exec -T postgres psql -v ON_ERROR_STOP=1 -U $(ATLAS_PG_USER) -d $(ATLAS_PG_DB) < $(PG_SCHEMA_FOOD)

pg-wait:
	@echo "==> Waiting for Postgres to be ready..."
	@for i in $$(seq 1 30); do \
		$(PG_COMPOSE) exec -T postgres pg_isready -U $(ATLAS_PG_USER) -d $(ATLAS_PG_DB) \
		  >/dev/null 2>&1 && echo "Postgres is ready." && exit 0; \
		echo "  ...not ready yet ($$i/30), retrying in 2s..."; \
		sleep 2; \
	done; \
	echo "ERROR: Postgres did not become ready after 60s." && exit 1

# endregion


# region --- Application: TaskTracker
TASK_DIR=../03_Application/TaskTracker

TASK_COMPOSE=docker compose \
	-f $(TASK_DIR)/compose.yml \
	$(ENV_FILES)

task-build:
	$(TASK_COMPOSE) build

task-up:
	$(TASK_COMPOSE) up -d

task-down:
	$(TASK_COMPOSE) down

task-logs:
	$(TASK_COMPOSE) logs -f

task-reboot:
	$(TASK_COMPOSE) down
	$(TASK_COMPOSE) up -d

# endregion


# region --- Application: WorkoutTracker
APP_DIR=../03_Application/WorkoutTracker

APP_COMPOSE=docker compose \
	-f $(APP_DIR)/compose.yml \
	$(ENV_FILES)

app-build:
	$(APP_COMPOSE) build

app-up:
	$(APP_COMPOSE) up -d

app-down:
	$(APP_COMPOSE) down

app-logs:
	$(APP_COMPOSE) logs -f

app-reboot:
	$(APP_COMPOSE) down
	$(APP_COMPOSE) up -d

# endregion


# region --- Platform: Atlas Shell
SHELL_DIR=../02_Platform/02_Atlas_Shell

SHELL_COMPOSE=docker compose \
	-f $(SHELL_DIR)/compose.yml \
	$(ENV_FILES)

shell-build:
	$(SHELL_COMPOSE) build

shell-up:
	$(SHELL_COMPOSE) up -d

shell-down:
	$(SHELL_COMPOSE) down

shell-logs:
	$(SHELL_COMPOSE) logs -f

shell-reboot:
	$(SHELL_COMPOSE) down
	$(SHELL_COMPOSE) up -d

# endregion


# region --- Platform: UI (legacy — use shell targets for the SPA)
UI_DIR=../02_Platform/UI

UI_COMPOSE=docker compose \
	-f $(UI_DIR)/compose.yml \
	$(ENV_FILES)

ui-build:
	$(UI_COMPOSE) build

ui-up:
	$(UI_COMPOSE) up -d

ui-down:
	$(UI_COMPOSE) down

ui-logs:
	$(UI_COMPOSE) logs -f

ui-reboot:
	$(UI_COMPOSE) down
	$(UI_COMPOSE) up -d

# endregion


# region --- Platform: MCPGateway
MCP_DIR=../02_Platform/MCPGateway

MCP_COMPOSE=docker compose \
	-f $(MCP_DIR)/compose.yml \
	$(ENV_FILES)

mcp-build:
	$(MCP_COMPOSE) build

mcp-up:
	$(MCP_COMPOSE) up -d

mcp-down:
	$(MCP_COMPOSE) down

mcp-logs:
	$(MCP_COMPOSE) logs -f

mcp-reboot:
	$(MCP_COMPOSE) down
	$(MCP_COMPOSE) up -d

# endregion


# region --- Aggregate: full stack
# Usage:
#   make up    — build images and start the full stack (idempotent)
#   make down  — stop all services
#
# Prerequisites: secrets.env must exist alongside this Makefile.
# Minimum contents:
#   ATLAS_PG_PASSWORD=<your-db-password>
#   DATA_ROOT=/mnt/data

# Ensure all backend services are attached to atlas-net.
# Uses || true so re-running when already connected is silent and safe.
net-connect:
	@docker network connect atlas-net atlas-postgres        2>/dev/null || true
	@docker network connect atlas-net atlas-tasktracker    2>/dev/null || true
	@docker network connect atlas-net atlas-workout-tracker 2>/dev/null || true
	@docker network connect atlas-net atlas-ui             2>/dev/null || true
	@docker network connect atlas-net atlas-cloudflared    2>/dev/null || true

up:
	@test -f $(SYSTEM_SECRETS) || \
	  (echo "ERROR: $(SYSTEM_SECRETS) not found." && \
	   echo "Create it with at minimum:" && \
	   echo "  ATLAS_PG_PASSWORD=<password>" && \
	   echo "  DATA_ROOT=/mnt/data" && \
	   exit 1)
	$(MAKE) pg-up
	$(MAKE) pg-wait
	$(MAKE) schema schema-task
	$(MAKE) task-build task-up
	$(MAKE) app-build  app-up
	$(MAKE) net-connect
	$(MAKE) shell-build shell-up
	@echo ""
	@echo "Atlas stack is up. Shell available on port 80."

down:
	-$(MAKE) shell-down
	-$(MAKE) app-down
	-$(MAKE) task-down
	-$(MAKE) pg-down
	@echo "Atlas stack is down."

# endregion
