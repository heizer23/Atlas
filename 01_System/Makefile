SYSTEM_SECRETS=secrets.env

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

pg-ps:
	$(PG_COMPOSE) ps

pg-logs:
	$(PG_COMPOSE) logs -f

pg-shell:
	docker exec -it atlas-postgres psql -U atlas -d atlas


# --- Platform: Postgres - Schemas
PG_SCHEMA=../02_Platform/01_Postgres/ObjectSchemas/workout_schema.sql

schema:
	docker exec -i atlas-postgres \
	  psql -U atlas -d atlas \
	  < $(PG_SCHEMA)

# endregion