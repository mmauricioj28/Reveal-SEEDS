-- Crash DB: tables + keys, loaded from the processed parquets (data/processed/crash/, built by crash_build_parquet.py)
-- Paths are relative to the repo root. Run with: python Python/database/build_crash_db.py  (it rebuilds the .duckdb from scratch)
--
-- Keys
--   crash          PK crash_key                          (= report_number + '_' + report_date)
--   crash_vehicle  PK crash_id       FK crash_key -> crash
--   crash_carrier  PK crash_id       FK crash_id  -> crash_vehicle
--   crash_event    PK (crash_id, event_seq)  FK crash_id -> crash_vehicle
--   *_id / code columns  FK -> dim_* (code)
-- No FK on purpose:
--   crash.county_fips             ~1% are not real counties (see county_fips_valid)
--   vehicle_lic_state, crash_carrier_state   include Canadian/Mexican/other codes not in dim_state
-- Tables are created parents first, so every FK target exists before it is referenced.

-- ================================================================ lookups
CREATE TABLE dim_state (
    state            VARCHAR PRIMARY KEY,
    state_fips       VARCHAR NOT NULL UNIQUE,
    state_name       VARCHAR NOT NULL,
    is_50_states_dc  BOOLEAN NOT NULL
);

CREATE TABLE dim_county (
    county_fips  VARCHAR PRIMARY KEY,
    state        VARCHAR NOT NULL REFERENCES dim_state (state),
    state_fips   VARCHAR NOT NULL,
    county_code  VARCHAR NOT NULL,
    county_name  VARCHAR NOT NULL
);

CREATE TABLE dim_trafficway         (code SMALLINT PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_access_control     (code SMALLINT PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_road_surface       (code SMALLINT PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_weather            (code SMALLINT PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_light              (code SMALLINT PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_cargo_body         (code SMALLINT PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_gvw_rating         (code SMALLINT PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_vehicle_config     (code SMALLINT PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_event              (code SMALLINT PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_ci_status          (code VARCHAR  PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_carrier_interstate (code VARCHAR  PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_truck_bus          (code VARCHAR  PRIMARY KEY, description VARCHAR NOT NULL);

-- ================================================================ crash (1 row per crash)
CREATE TABLE crash (
    crash_key                  VARCHAR  PRIMARY KEY,
    report_number              VARCHAR  NOT NULL,
    report_state               VARCHAR  NOT NULL,
    report_date                DATE     NOT NULL,
    report_time                VARCHAR,
    report_hour                TINYINT  CHECK (report_hour BETWEEN 0 AND 23),
    state                      VARCHAR  NOT NULL REFERENCES dim_state (state),
    state_fips                 VARCHAR  NOT NULL,
    county_code                VARCHAR,
    county_fips                VARCHAR,
    county_fips_valid          BOOLEAN  NOT NULL,
    city                       VARCHAR,
    location                   VARCHAR,
    agency                     VARCHAR,
    trafficway_id              SMALLINT REFERENCES dim_trafficway (code),
    access_control_id          SMALLINT REFERENCES dim_access_control (code),
    road_surface_condition_id  SMALLINT REFERENCES dim_road_surface (code),
    weather_condition_id       SMALLINT REFERENCES dim_weather (code),
    light_condition_id         SMALLINT REFERENCES dim_light (code),
    vehicles_in_accident       SMALLINT NOT NULL,
    fatalities                 INTEGER  NOT NULL CHECK (fatalities >= 0),
    injuries                   INTEGER  NOT NULL CHECK (injuries >= 0),
    tow_away                   BOOLEAN  NOT NULL,
    federal_recordable         BOOLEAN  NOT NULL,
    state_recordable           BOOLEAN,
    cmv_count                  SMALLINT NOT NULL CHECK (cmv_count >= 1),
    truck_count                SMALLINT NOT NULL,
    bus_count                  SMALLINT NOT NULL,
    any_hazmat_placard         BOOLEAN,
    any_hazmat_released        BOOLEAN,
    carrier_count              SMALLINT NOT NULL,
    severity                   VARCHAR  NOT NULL CHECK (severity IN ('Fatal', 'Injury', 'Tow-away', 'Non-recordable')),
    is_fatal                   BOOLEAN  NOT NULL,
    report_year                SMALLINT NOT NULL,
    report_month               TINYINT  NOT NULL CHECK (report_month BETWEEN 1 AND 12),
    report_month_start         DATE     NOT NULL,
    report_dow                 TINYINT  NOT NULL CHECK (report_dow BETWEEN 0 AND 6),   -- 0 = Monday
    report_state_mismatch      BOOLEAN  NOT NULL,
    UNIQUE (report_number, report_date)
);

-- ================================================================ crash_vehicle (1 row per commercial vehicle in a crash)
CREATE TABLE crash_vehicle (
    crash_id                  BIGINT   PRIMARY KEY,
    crash_key                 VARCHAR  NOT NULL REFERENCES crash (crash_key),
    report_number             VARCHAR  NOT NULL,
    report_seq_no             SMALLINT NOT NULL,     -- not unique per crash: 651 repeats in the source
    dot_number                BIGINT,                -- NULL = no USDOT number (can't join to carrier census)
    truck_bus_ind             VARCHAR  NOT NULL REFERENCES dim_truck_bus (code),
    vehicle_configuration_id  SMALLINT REFERENCES dim_vehicle_config (code),
    cargo_body_type_id        SMALLINT REFERENCES dim_cargo_body (code),
    gvw_rating_id             SMALLINT REFERENCES dim_gvw_rating (code),
    vehicle_hazmat_placard    BOOLEAN,
    hazmat_released           BOOLEAN,
    vehicle_lic_state         VARCHAR,
    ci_status_code            VARCHAR  REFERENCES dim_ci_status (code),
    final_status_date         DATE,
    transaction_code          VARCHAR  NOT NULL CHECK (transaction_code IN ('A', 'C')),
    add_date                  TIMESTAMP NOT NULL,
    change_date               TIMESTAMP,
    upload_date               TIMESTAMP,
    has_dot_number            BOOLEAN  NOT NULL
);

-- ================================================================ crash_carrier (carrier as written on the report, 1:1 with crash_vehicle)
CREATE TABLE crash_carrier (
    crash_id                  BIGINT  PRIMARY KEY REFERENCES crash_vehicle (crash_id),
    crash_key                 VARCHAR NOT NULL REFERENCES crash (crash_key),
    crash_carrier_id          BIGINT  NOT NULL UNIQUE,
    dot_number                BIGINT,
    upload_dot_number         VARCHAR,
    upload_search_indicator   VARCHAR,
    crash_carrier_name        VARCHAR,
    crash_carrier_city        VARCHAR,
    crash_carrier_state       VARCHAR,
    crash_carrier_zip5        VARCHAR,
    docket_number             VARCHAR,
    crash_carrier_interstate  VARCHAR NOT NULL REFERENCES dim_carrier_interstate (code),
    no_id_flag                BOOLEAN,
    state_number              VARCHAR,
    state_issuing_number      VARCHAR
);

-- ================================================================ crash_event (sequence of harmful events per vehicle)
CREATE TABLE crash_event (
    crash_id        BIGINT   NOT NULL REFERENCES crash_vehicle (crash_id),
    crash_key       VARCHAR  NOT NULL REFERENCES crash (crash_key),
    event_seq       SMALLINT NOT NULL,
    event_id        SMALLINT NOT NULL REFERENCES dim_event (code),
    is_first_event  BOOLEAN  NOT NULL,
    event_desc_raw  VARCHAR,
    PRIMARY KEY (crash_id, event_seq)
);

-- ================================================================ dashboard rollups
CREATE TABLE agg_state_year (
    state                       VARCHAR  NOT NULL REFERENCES dim_state (state),
    report_year                 SMALLINT NOT NULL,
    crashes                     BIGINT   NOT NULL,
    fatal_crashes               BIGINT   NOT NULL,
    injury_crashes              BIGINT   NOT NULL,
    towaway_crashes             BIGINT   NOT NULL,
    fatalities                  BIGINT   NOT NULL,
    injuries                    BIGINT   NOT NULL,
    hazmat_placard_crashes      BIGINT   NOT NULL,
    hazmat_release_crashes      BIGINT   NOT NULL,
    bus_crashes                 BIGINT   NOT NULL,
    cmv_involved                BIGINT   NOT NULL,
    carriers_involved           BIGINT   NOT NULL,
    fatalities_per_100_crashes  DOUBLE,
    PRIMARY KEY (state, report_year)
);

CREATE TABLE agg_state_month (
    state                       VARCHAR  NOT NULL REFERENCES dim_state (state),
    report_month_start          DATE     NOT NULL,
    crashes                     BIGINT   NOT NULL,
    fatal_crashes               BIGINT   NOT NULL,
    injury_crashes              BIGINT   NOT NULL,
    towaway_crashes             BIGINT   NOT NULL,
    fatalities                  BIGINT   NOT NULL,
    injuries                    BIGINT   NOT NULL,
    hazmat_placard_crashes      BIGINT   NOT NULL,
    hazmat_release_crashes      BIGINT   NOT NULL,
    bus_crashes                 BIGINT   NOT NULL,
    cmv_involved                BIGINT   NOT NULL,
    carriers_involved           BIGINT   NOT NULL,
    fatalities_per_100_crashes  DOUBLE,
    PRIMARY KEY (state, report_month_start)
);

-- ================================================================ load data (BY NAME matches parquet columns to table columns)
INSERT INTO dim_state              BY NAME SELECT * FROM read_parquet('data/processed/crash/dim_state.parquet');
INSERT INTO dim_county             BY NAME SELECT * FROM read_parquet('data/processed/crash/dim_county.parquet');
INSERT INTO dim_trafficway         BY NAME SELECT * FROM read_parquet('data/processed/crash/dim_trafficway.parquet');
INSERT INTO dim_access_control     BY NAME SELECT * FROM read_parquet('data/processed/crash/dim_access_control.parquet');
INSERT INTO dim_road_surface       BY NAME SELECT * FROM read_parquet('data/processed/crash/dim_road_surface.parquet');
INSERT INTO dim_weather            BY NAME SELECT * FROM read_parquet('data/processed/crash/dim_weather.parquet');
INSERT INTO dim_light              BY NAME SELECT * FROM read_parquet('data/processed/crash/dim_light.parquet');
INSERT INTO dim_cargo_body         BY NAME SELECT * FROM read_parquet('data/processed/crash/dim_cargo_body.parquet');
INSERT INTO dim_gvw_rating         BY NAME SELECT * FROM read_parquet('data/processed/crash/dim_gvw_rating.parquet');
INSERT INTO dim_vehicle_config     BY NAME SELECT * FROM read_parquet('data/processed/crash/dim_vehicle_config.parquet');
INSERT INTO dim_event              BY NAME SELECT * FROM read_parquet('data/processed/crash/dim_event.parquet');
INSERT INTO dim_ci_status          BY NAME SELECT * FROM read_parquet('data/processed/crash/dim_ci_status.parquet');
INSERT INTO dim_carrier_interstate BY NAME SELECT * FROM read_parquet('data/processed/crash/dim_carrier_interstate.parquet');
INSERT INTO dim_truck_bus          BY NAME SELECT * FROM read_parquet('data/processed/crash/dim_truck_bus.parquet');

INSERT INTO crash                  BY NAME SELECT * FROM read_parquet('data/processed/crash/crash.parquet');
INSERT INTO crash_vehicle          BY NAME SELECT * FROM read_parquet('data/processed/crash/crash_vehicle.parquet');
INSERT INTO crash_carrier          BY NAME SELECT * FROM read_parquet('data/processed/crash/crash_carrier.parquet');
-- 9 event rows are empty (blank event text in the source) -> skipped, they can't satisfy the primary key
INSERT INTO crash_event            BY NAME SELECT * FROM read_parquet('data/processed/crash/crash_event.parquet')
                                           WHERE event_seq IS NOT NULL;

INSERT INTO agg_state_year         BY NAME SELECT * FROM read_parquet('data/processed/crash/agg_state_year.parquet');
INSERT INTO agg_state_month        BY NAME SELECT * FROM read_parquet('data/processed/crash/agg_state_month.parquet');
