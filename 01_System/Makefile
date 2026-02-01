SYSTEM_SECRETS=secrets.env

# Load env vars for Make (Compose already loads them via --env-file)
include $(SYSTEM_SECRETS)
export

# --- Host bootstrap
bootstrap-pi:
	./bootstrap_pi.sh


# region --- Platform 
# --- Platform: Postgres
PG_DIR=../02_Platform/01_Postgres

PG_COMPOSE=docker compose \
	-f $(PG_DIR)/compose.yml \
	--env-file $(SYSTEM_SECRETS)

pg-up:
	$(PG_COMPOSE) up -d

pg-down:
	$(PG_COMPOSE) down

# this only works because it is just commands. If you ever add cd or variables, you’ll want .ONESHELL
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
	@echo "Host path (/mnt/data/postgres):"
	@ls -la /mnt/data/postgres | head -n 20
	@echo ""
	@echo "Container path (/var/lib/postgresql/data):"
	@$(PG_COMPOSE) exec -T postgres ls -la /var/lib/postgresql/data | head -n 20


# --- Platform: Postgres - Schemas
PG_SCHEMA=../02_Platform/01_Postgres/ObjectSchemas/workout_schema.sql

schema:
	@test -n "$(ATLAS_PG_USER)" || (echo "ATLAS_PG_USER missing (check secrets.env + include)" && exit 1)
	@test -n "$(ATLAS_PG_DB)"   || (echo "ATLAS_PG_DB missing (check secrets.env + include)" && exit 1)
	$(PG_COMPOSE) exec -T postgres psql -v ON_ERROR_STOP=1 -U $(ATLAS_PG_USER) -d $(ATLAS_PG_DB) < $(PG_SCHEMA)


# endregion