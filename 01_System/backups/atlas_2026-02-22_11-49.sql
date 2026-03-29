--
-- PostgreSQL database dump
--

\restrict Iarwz0GPdTiEwAsfkqY5ExrQ50GMVHm9lCgGcdSi5CSlOeD3qfR9eeoHhGXULH5

-- Dumped from database version 16.11 (Debian 16.11-1.pgdg13+1)
-- Dumped by pg_dump version 16.11 (Debian 16.11-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: workout; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA workout;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: workout_log; Type: TABLE; Schema: workout; Owner: -
--

CREATE TABLE workout.workout_log (
    workout_log_id bigint NOT NULL,
    workout_id uuid NOT NULL,
    workout_date date NOT NULL,
    split text NOT NULL,
    exercise text NOT NULL,
    weight_kg numeric(10,3),
    pause_sec integer,
    set1_reps integer,
    set2_reps integer,
    set3_reps integer,
    set4_reps integer,
    set5_reps integer,
    comment text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_at_least_one_set CHECK (((set1_reps IS NOT NULL) OR (set2_reps IS NOT NULL) OR (set3_reps IS NOT NULL) OR (set4_reps IS NOT NULL) OR (set5_reps IS NOT NULL))),
    CONSTRAINT ck_pause_nonneg CHECK (((pause_sec IS NULL) OR (pause_sec >= 0))),
    CONSTRAINT ck_set_reps_nonneg CHECK ((((set1_reps IS NULL) OR (set1_reps >= 0)) AND ((set2_reps IS NULL) OR (set2_reps >= 0)) AND ((set3_reps IS NULL) OR (set3_reps >= 0)) AND ((set4_reps IS NULL) OR (set4_reps >= 0)) AND ((set5_reps IS NULL) OR (set5_reps >= 0)))),
    CONSTRAINT ck_weight_nonneg CHECK (((weight_kg IS NULL) OR (weight_kg >= (0)::numeric)))
);


--
-- Name: workout_log_workout_log_id_seq; Type: SEQUENCE; Schema: workout; Owner: -
--

CREATE SEQUENCE workout.workout_log_workout_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: workout_log_workout_log_id_seq; Type: SEQUENCE OWNED BY; Schema: workout; Owner: -
--

ALTER SEQUENCE workout.workout_log_workout_log_id_seq OWNED BY workout.workout_log.workout_log_id;


--
-- Name: workout_log workout_log_id; Type: DEFAULT; Schema: workout; Owner: -
--

ALTER TABLE ONLY workout.workout_log ALTER COLUMN workout_log_id SET DEFAULT nextval('workout.workout_log_workout_log_id_seq'::regclass);


--
-- Data for Name: workout_log; Type: TABLE DATA; Schema: workout; Owner: -
--

COPY workout.workout_log (workout_log_id, workout_id, workout_date, split, exercise, weight_kg, pause_sec, set1_reps, set2_reps, set3_reps, set4_reps, set5_reps, comment, created_at, updated_at) FROM stdin;
1	29eb5a39-8689-40d3-bcb8-250a60f76a8e	2026-02-18	Push	Straight-arm leg raise	\N	\N	15	15	10	7	\N	\N	2026-02-21 15:33:43.549058+00	2026-02-21 15:33:43.549058+00
2	29eb5a39-8689-40d3-bcb8-250a60f76a8e	2026-02-18	Push	Pull up	\N	\N	10	8	6	\N	\N	2 / 1 / 1	2026-02-21 15:34:27.654461+00	2026-02-21 15:34:27.654461+00
3	29eb5a39-8689-40d3-bcb8-250a60f76a8e	2026-02-18	Push	Squats	45.000	\N	12	12	12	\N	\N	\N	2026-02-21 15:34:41.951018+00	2026-02-21 15:34:41.951018+00
4	29eb5a39-8689-40d3-bcb8-250a60f76a8e	2026-02-18	Push	Dumbell Row	30.000	\N	8	8	7	\N	\N	\N	2026-02-21 15:35:10.947241+00	2026-02-21 15:35:10.947241+00
5	29eb5a39-8689-40d3-bcb8-250a60f76a8e	2026-02-18	Push	Revers Fly	10.000	\N	12	12	12	\N	\N	\N	2026-02-21 15:35:24.141679+00	2026-02-21 15:35:24.141679+00
6	ffd2d7d7-be36-4291-b305-c7da78ff12ab	2026-02-21	Push	Straight-arm leg raise	\N	\N	15	15	11	8	\N	\N	2026-02-21 15:35:38.492381+00	2026-02-21 15:45:02.132256+00
10	ffd2d7d7-be36-4291-b305-c7da78ff12ab	2026-02-21	Push	Revers Fly	7.500	\N	12	13	12	\N	\N	\N	2026-02-21 15:35:38.501802+00	2026-02-21 16:05:43.215903+00
7	ffd2d7d7-be36-4291-b305-c7da78ff12ab	2026-02-21	Push	Pull up	\N	\N	10	9	7	\N	\N	tseT2 / 1 / 1	2026-02-21 15:35:38.496661+00	2026-02-21 23:00:49.443689+00
\.


--
-- Name: workout_log_workout_log_id_seq; Type: SEQUENCE SET; Schema: workout; Owner: -
--

SELECT pg_catalog.setval('workout.workout_log_workout_log_id_seq', 10, true);


--
-- Name: workout_log workout_log_pkey; Type: CONSTRAINT; Schema: workout; Owner: -
--

ALTER TABLE ONLY workout.workout_log
    ADD CONSTRAINT workout_log_pkey PRIMARY KEY (workout_log_id);


--
-- Name: ix_workout_log_date; Type: INDEX; Schema: workout; Owner: -
--

CREATE INDEX ix_workout_log_date ON workout.workout_log USING btree (workout_date);


--
-- Name: ix_workout_log_exercise; Type: INDEX; Schema: workout; Owner: -
--

CREATE INDEX ix_workout_log_exercise ON workout.workout_log USING btree (exercise);


--
-- Name: ix_workout_log_split; Type: INDEX; Schema: workout; Owner: -
--

CREATE INDEX ix_workout_log_split ON workout.workout_log USING btree (split);


--
-- Name: ix_workout_log_workout_id; Type: INDEX; Schema: workout; Owner: -
--

CREATE INDEX ix_workout_log_workout_id ON workout.workout_log USING btree (workout_id);


--
-- PostgreSQL database dump complete
--

\unrestrict Iarwz0GPdTiEwAsfkqY5ExrQ50GMVHm9lCgGcdSi5CSlOeD3qfR9eeoHhGXULH5

