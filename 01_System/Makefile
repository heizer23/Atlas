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
	@sudo tailscale status >/dev/null 2>&1 || sudo tailscale up --accept-dns=false

tailscale-down:
	@sudo tailscale down

# --- System: tmux sessions
tmux-ls:
	@tmux ls 2>/dev/null || echo "No tmux sessions."

# --- System: SystemMonitoring (Netdata)
MONITOR_DIR=../01_System/SystemMonitoring

monitor-install:
	chmod +x $(MONITOR_DIR)/install.sh
	$(MONITOR_DIR)/install.sh

monitor-status:
	@sudo systemctl status netdata --no-pager || true

monitor-start:
	@sudo systemctl start netdata

monitor-stop:
	@sudo systemctl stop netdata

monitor-restart:
	@sudo systemctl restart netdata

monitor-logs:
	@sudo journalctl -u netdata -f


# region --- System: Chronos
CHRONOS_DIR=../01_System/Chronos

CHRONOS_COMPOSE=docker compose \
	-f $(CHRONOS_DIR)/compose.yml \
	$(ENV_FILES)

chronos-init:
	@if [ -f "$(CHRONOS_STATE_DIR)/openclaw.json" ]; then \
	  echo "$(CHRONOS_STATE_DIR)/openclaw.json already exists — skipping. Delete it first to re-init."; \
	else \
	  cp $(CHRONOS_DIR)/openclaw-init.json $(CHRONOS_STATE_DIR)/openclaw.json; \
	  echo "Wrote $(CHRONOS_STATE_DIR)/openclaw.json"; \
	  echo "Token is injected from CHRONOS_TOKEN in secrets.env — no manual edit needed."; \
	fi

chronos-up:
	$(CHRONOS_COMPOSE) up -d

chronos-down:
	$(CHRONOS_COMPOSE) down

chronos-logs:
	$(CHRONOS_COMPOSE) logs -f

chronos-reboot:
	$(CHRONOS_COMPOSE) down
	$(CHRONOS_COMPOSE) up -d

chronos-ps:
	$(CHRONOS_COMPOSE) ps

chronos-pair:
	$(CHRONOS_COMPOSE) exec chronos openclaw devices approve --latest \
	  --token $$(python3 -c "import json; print(json.load(open('$(CHRONOS_STATE_DIR)/openclaw.json'))['gateway']['auth']['token'])")

# endregion




# region --- Platform
# --- Platform: Postgres
PG_DIR=../02_Platform/Postgres

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
PG_SCHEMA_CHRONICLE=../00_Blueprint/SharedViews/chronicle.sql

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

schema-chronicle:
	@test -n "$(ATLAS_PG_USER)" || (echo "ATLAS_PG_USER missing" && exit 1)
	@test -n "$(ATLAS_PG_DB)"   || (echo "ATLAS_PG_DB missing" && exit 1)
	$(PG_COMPOSE) exec -T postgres psql -v ON_ERROR_STOP=1 -U $(ATLAS_PG_USER) -d $(ATLAS_PG_DB) < $(PG_SCHEMA_CHRONICLE)

migrate:
	@python3 ../02_Platform/Postgres/migrate.py

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


# region --- Application: FoodTracker
FOOD_DIR=../03_Application/FoodTracker

FOOD_COMPOSE=docker compose \
	-f $(FOOD_DIR)/compose.yml \
	$(ENV_FILES)

food-build:
	$(FOOD_COMPOSE) build food-tracker

food-up:
	$(FOOD_COMPOSE) up -d food-tracker

food-down:
	$(FOOD_COMPOSE) down

food-logs:
	$(FOOD_COMPOSE) logs -f food-tracker

food-reboot:
	$(FOOD_COMPOSE) stop food-tracker
	$(FOOD_COMPOSE) up -d food-tracker

food-test-up:
	$(FOOD_COMPOSE) up -d food-tracker-test

food-test-down:
	$(FOOD_COMPOSE) stop food-tracker-test

# endregion


# region --- Application: Chronicle
CHRONICLE_DIR=../03_Application/Chronicle

CHRONICLE_COMPOSE=docker compose \
	-f $(CHRONICLE_DIR)/compose.yml \
	$(ENV_FILES)

chronicle-build:
	$(CHRONICLE_COMPOSE) build

chronicle-up:
	$(CHRONICLE_COMPOSE) up -d

chronicle-down:
	$(CHRONICLE_COMPOSE) down

chronicle-logs:
	$(CHRONICLE_COMPOSE) logs -f

chronicle-reboot:
	$(CHRONICLE_COMPOSE) down
	$(CHRONICLE_COMPOSE) up -d

# endregion


# region --- Application: StorageTracker
STORAGE_DIR=../03_Application/StorageTracker

STORAGE_COMPOSE=docker compose \
	-f $(STORAGE_DIR)/compose.yml \
	$(ENV_FILES)

storage-build:
	$(STORAGE_COMPOSE) build

storage-up:
	$(STORAGE_COMPOSE) up -d

storage-down:
	$(STORAGE_COMPOSE) down

storage-logs:
	$(STORAGE_COMPOSE) logs -f

storage-reboot:
	$(STORAGE_COMPOSE) down
	$(STORAGE_COMPOSE) up -d

storage-schema:
	@test -n "$(ATLAS_PG_USER)" || (echo "ATLAS_PG_USER missing" && exit 1)
	@test -n "$(ATLAS_PG_DB)"   || (echo "ATLAS_PG_DB missing" && exit 1)
	$(PG_COMPOSE) exec -T postgres psql -v ON_ERROR_STOP=1 -U $(ATLAS_PG_USER) -d $(ATLAS_PG_DB) < $(STORAGE_DIR)/00_architecture/schema.sql

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


# region --- Platform: Notifications
NOTIF_DIR=../02_Platform/Notifications

NOTIF_COMPOSE=docker compose \
	-f $(NOTIF_DIR)/compose.yml \
	$(ENV_FILES)

notif-build:
	$(NOTIF_COMPOSE) build

notif-up:
	$(NOTIF_COMPOSE) up -d

notif-down:
	$(NOTIF_COMPOSE) down

notif-logs:
	$(NOTIF_COMPOSE) logs -f

notif-reboot:
	$(NOTIF_COMPOSE) down
	$(NOTIF_COMPOSE) up -d

notif-schema:
	@test -n "$(ATLAS_PG_USER)" || (echo "ATLAS_PG_USER missing" && exit 1)
	@test -n "$(ATLAS_PG_DB)"   || (echo "ATLAS_PG_DB missing" && exit 1)
	$(PG_COMPOSE) exec -T postgres psql -v ON_ERROR_STOP=1 -U $(ATLAS_PG_USER) -d $(ATLAS_PG_DB) < $(NOTIF_DIR)/20_Data/schema.sql

# endregion


# region --- Platform: CalendarConnector
CALENDAR_DIR=../02_Platform/CalendarConnector

CALENDAR_COMPOSE=docker compose \
	-f $(CALENDAR_DIR)/compose.yml \
	$(ENV_FILES)

calendar-build:
	$(CALENDAR_COMPOSE) build

calendar-up:
	$(CALENDAR_COMPOSE) up -d

calendar-down:
	$(CALENDAR_COMPOSE) down

calendar-logs:
	$(CALENDAR_COMPOSE) logs -f

calendar-reboot:
	$(CALENDAR_COMPOSE) down
	$(CALENDAR_COMPOSE) up -d

calendar-schema:
	@test -n "$(ATLAS_PG_USER)" || (echo "ATLAS_PG_USER missing" && exit 1)
	@test -n "$(ATLAS_PG_DB)"   || (echo "ATLAS_PG_DB missing" && exit 1)
	$(PG_COMPOSE) exec -T postgres psql -v ON_ERROR_STOP=1 -U $(ATLAS_PG_USER) -d $(ATLAS_PG_DB) < $(CALENDAR_DIR)/migrations/001_init.sql

# endregion


# region --- Platform: Atlas Shell
SHELL_DIR=../02_Platform/Atlas_Shell

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


# region --- Platform: LabelEngine
LABEL_DIR=../02_Platform/LabelEngine

LABEL_COMPOSE=docker compose \
	-f $(LABEL_DIR)/compose.yml \
	$(ENV_FILES)

label-build:
	$(LABEL_COMPOSE) build

label-up:
	$(LABEL_COMPOSE) up -d

label-down:
	$(LABEL_COMPOSE) down

label-logs:
	$(LABEL_COMPOSE) logs -f

label-reboot:
	$(LABEL_COMPOSE) down
	$(LABEL_COMPOSE) up -d

label-schema:
	@test -n "$(ATLAS_PG_USER)" || (echo "ATLAS_PG_USER missing" && exit 1)
	@test -n "$(ATLAS_PG_DB)"   || (echo "ATLAS_PG_DB missing" && exit 1)
	$(PG_COMPOSE) exec -T postgres psql -v ON_ERROR_STOP=1 -U $(ATLAS_PG_USER) -d $(ATLAS_PG_DB) < "$(LABEL_DIR)/Spint01- First labels/20_Data/schema.sql"

# endregion


# region --- Platform: PreferenceStore
PREF_DIR=../02_Platform/PreferenceStore

PREF_COMPOSE=docker compose \
	-f $(PREF_DIR)/compose.yml \
	$(ENV_FILES)

pref-build:
	$(PREF_COMPOSE) build

pref-up:
	$(PREF_COMPOSE) up -d

pref-down:
	$(PREF_COMPOSE) down

pref-logs:
	$(PREF_COMPOSE) logs -f

pref-reboot:
	$(PREF_COMPOSE) down
	$(PREF_COMPOSE) up -d

pref-schema:
	@test -n "$(ATLAS_PG_USER)" || (echo "ATLAS_PG_USER missing" && exit 1)
	@test -n "$(ATLAS_PG_DB)"   || (echo "ATLAS_PG_DB missing" && exit 1)
	$(PG_COMPOSE) exec -T postgres psql -v ON_ERROR_STOP=1 -U $(ATLAS_PG_USER) -d $(ATLAS_PG_DB) < $(PREF_DIR)/00_architecture/schema.sql

# endregion


# region --- Application: NumericSeries
NUMERIC_DIR=../03_Application/NumericSeries

NUMERIC_COMPOSE=docker compose \
	-f $(NUMERIC_DIR)/compose.yml \
	$(ENV_FILES)

numeric-build:
	$(NUMERIC_COMPOSE) build

numeric-up:
	$(NUMERIC_COMPOSE) up -d

numeric-down:
	$(NUMERIC_COMPOSE) down

numeric-logs:
	$(NUMERIC_COMPOSE) logs -f

numeric-reboot:
	$(NUMERIC_COMPOSE) down
	$(NUMERIC_COMPOSE) up -d

numeric-schema:
	@test -n "$(ATLAS_PG_USER)" || (echo "ATLAS_PG_USER missing" && exit 1)
	@test -n "$(ATLAS_PG_DB)"   || (echo "ATLAS_PG_DB missing" && exit 1)
	$(PG_COMPOSE) exec -T postgres psql -v ON_ERROR_STOP=1 -U $(ATLAS_PG_USER) -d $(ATLAS_PG_DB) < $(NUMERIC_DIR)/Sprint01/20_Data/schema.sql

# endregion


# region --- Platform: LinkingEngine
LINKING_DIR=../02_Platform/LinkingEngine

LINKING_COMPOSE=docker compose \
	-f $(LINKING_DIR)/compose.yml \
	$(ENV_FILES)

linking-build:
	$(LINKING_COMPOSE) build

linking-up:
	$(LINKING_COMPOSE) up -d

linking-down:
	$(LINKING_COMPOSE) down

linking-logs:
	$(LINKING_COMPOSE) logs -f

linking-reboot:
	$(LINKING_COMPOSE) down
	$(LINKING_COMPOSE) up -d

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



# region --- System: Cloudflared tunnel
CLOUDFLARED_DIR=Access/cloudflared

CLOUDFLARED_COMPOSE=docker compose \
	-f $(CLOUDFLARED_DIR)/compose.yml \
	--env-file $(SYSTEM_SECRETS)

cloudflared-up:
	$(CLOUDFLARED_COMPOSE) up -d

cloudflared-down:
	$(CLOUDFLARED_COMPOSE) down

cloudflared-logs:
	$(CLOUDFLARED_COMPOSE) logs -f

cloudflared-reboot:
	$(CLOUDFLARED_COMPOSE) down
	$(CLOUDFLARED_COMPOSE) up -d

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
	@docker network connect atlas-net atlas-food-tracker   2>/dev/null || true
	@docker network connect atlas-net atlas-ui             2>/dev/null || true
	@docker network connect atlas-net atlas-cloudflared    2>/dev/null || true
	@docker network connect atlas-net atlas-notifications  2>/dev/null || true
	@docker network connect atlas-net atlas-calendar-connector 2>/dev/null || true
	@docker network connect atlas-net atlas-label-engine      2>/dev/null || true
	@docker network connect atlas-net atlas-linking-engine    2>/dev/null || true
	@docker network connect atlas-net atlas-preference-store  2>/dev/null || true
	@docker network connect atlas-net atlas-numeric-series    2>/dev/null || true
	@docker network connect atlas-net atlas-storagetracker    2>/dev/null || true

up:
	@test -f $(SYSTEM_SECRETS) || \
	  (echo "ERROR: $(SYSTEM_SECRETS) not found." && \
	   echo "Create it with at minimum:" && \
	   echo "  ATLAS_PG_PASSWORD=<password>" && \
	   echo "  DATA_ROOT=/mnt/data" && \
	   exit 1)
	$(MAKE) pg-up
	$(MAKE) pg-wait
	$(MAKE) migrate
	$(MAKE) schema-chronicle
	$(MAKE) notif-schema
	$(MAKE) task-build       task-up
	$(MAKE) app-build        app-up
	$(MAKE) food-build       food-up
	$(MAKE) chronicle-build  chronicle-up
	$(MAKE) notif-build      notif-up
	$(MAKE) calendar-build   calendar-up
	$(MAKE) label-schema
	$(MAKE) label-build      label-up
	$(MAKE) pref-schema
	$(MAKE) pref-build       pref-up
	$(MAKE) linking-build    linking-up
	$(MAKE) numeric-schema
	$(MAKE) numeric-build    numeric-up
	$(MAKE) storage-schema
	$(MAKE) storage-build    storage-up
	$(MAKE) cloudflared-up
	$(MAKE) net-connect
	$(MAKE) shell-build shell-up
	@echo ""
	@echo "Atlas stack is up. Shell available on port 80."

down:
	-$(MAKE) shell-down
	-$(MAKE) cloudflared-down
	-$(MAKE) numeric-down
	-$(MAKE) linking-down
	-$(MAKE) pref-down
	-$(MAKE) label-down
	-$(MAKE) calendar-down
	-$(MAKE) notif-down
	-$(MAKE) chronicle-down
	-$(MAKE) food-down
	-$(MAKE) app-down
	-$(MAKE) task-down
	-$(MAKE) storage-down
	-$(MAKE) pg-down
	@echo "Atlas stack is down."

# endregion


# region --- Test Stack
#
# Mirrors prod against atlas_test database (+1000 port offset).
# Shares the same atlas-postgres container and atlas-net network as prod.
# Tests use SQL fixtures — do not rely on prod data being present.
#
# test-up          start all test containers
# test-down        stop all test containers
# test-ps          show test container status
# test-sync-db     copy prod → atlas_test (for manual exploratory testing only)
# test-run         run pytest inside a component's test container
#                  Usage: make test-run COMPONENT=storagetracker
#                  Container: atlas-<COMPONENT>-test must be running

TEST_COMPOSE=docker compose \
	-f test/compose.test.yml \
	$(ENV_FILES)

test-up:
	$(TEST_COMPOSE) up -d

test-down:
	$(TEST_COMPOSE) down

test-ps:
	$(TEST_COMPOSE) ps

test-sync-db:
	@python3 test/sync_db.py

test-run:
	@test -n "$(COMPONENT)" || (echo "Usage: make test-run COMPONENT=storagetracker" && exit 1)
	@docker ps --filter name=atlas-$(COMPONENT)-test --format '{{.Names}}' | grep -q . \
	  || (echo "Container atlas-$(COMPONENT)-test is not running. Run: make test-up" && exit 1)
	docker exec atlas-$(COMPONENT)-test pytest tests/ -v

# endregion
