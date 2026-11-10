-- Census DB: FMCSA Company Census (MCMIS) tables + keys, loaded from the processed parquets
-- (FMCSA_data_processed/census/, built by census_build_parquet.py).
-- Paths are relative to the repo root. Run with: python SQL/build_census_db.py  (it rebuilds the .duckdb from scratch)
--
-- Keys
--   census_carrier         PK dot_number                 (one row per USDOT number - a SNAPSHOT of today)
--   census_cargo           PK (dot_number, cargo_code)   FK dot_number -> census_carrier, cargo_code -> dim_cargo
--   census_classification  PK (dot_number, class_code)   FK dot_number -> census_carrier, class_code -> dim_classification
--   code columns           FK -> dim_* (code)
-- No FK on purpose:
--   phy_state        includes Canadian provinces / Mexican states that aren't in dim_state
--   phy_county_fips  some US records have county codes that aren't real counties (see phy_county_fips_valid)
--
-- Joining to the crash DB: crash_vehicle.dot_number = census_carrier.dot_number
--   (crash_vehicle.dot_number is NULL for ~21% of crash vehicles, which therefore can't be linked)

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

CREATE TABLE dim_status            (code VARCHAR PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_carrier_operation (code VARCHAR PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_safety_rating     (code VARCHAR PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_review_type       (code VARCHAR PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_business_org      (code VARCHAR PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_entity_type       (code VARCHAR PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_classification    (code VARCHAR PRIMARY KEY, description VARCHAR NOT NULL);
CREATE TABLE dim_cargo             (code VARCHAR PRIMARY KEY, description VARCHAR NOT NULL);

CREATE TABLE dim_fleetsize (
    code             VARCHAR PRIMARY KEY,
    min_power_units  INTEGER NOT NULL,
    max_power_units  INTEGER                  -- NULL = no upper limit (Z = over 5000)
);

-- ================================================================ census_carrier (1 row per USDOT number)
CREATE TABLE census_carrier (
    dot_number                     BIGINT   PRIMARY KEY,
    status_code                    VARCHAR  REFERENCES dim_status (code),            -- A active / I inactive / P pending
    is_active_carrier              BOOLEAN  NOT NULL,                                -- status A and entity type includes Carrier
    carrier_operation              VARCHAR  REFERENCES dim_carrier_operation (code), -- A interstate / B intrastate hazmat / C intrastate
    carship                        VARCHAR,                                          -- raw entity types, e.g. 'C;S;B'
    is_carrier                     BOOLEAN  NOT NULL,
    is_shipper                     BOOLEAN  NOT NULL,
    is_broker                      BOOLEAN  NOT NULL,
    is_registrant                  BOOLEAN  NOT NULL,
    is_freight_forwarder           BOOLEAN  NOT NULL,
    is_intermodal_provider         BOOLEAN  NOT NULL,
    is_cargo_tank                  BOOLEAN  NOT NULL,
    business_org_id                VARCHAR  REFERENCES dim_business_org (code),
    hazmat                         BOOLEAN,
    add_date                       DATE,               -- created, reactivated OR systematically updated
    add_date_is_legacy             BOOLEAN  NOT NULL,  -- add_date = 1974-06-01 placeholder for legacy records
    add_year                       SMALLINT,
    add_month_start                DATE,
    mcs150_date                    DATE,               -- last MCS-150 registration update
    phy_city                       VARCHAR,
    phy_state                      VARCHAR,            -- principal place of business, not where trucks drive
    phy_state_fips                 VARCHAR,
    phy_zip5                       VARCHAR,
    phy_county_fips                VARCHAR,
    phy_county_fips_valid          BOOLEAN  NOT NULL,
    phy_country                    VARCHAR,
    is_us_50_dc                    BOOLEAN  NOT NULL,
    power_units                    BIGINT   CHECK (power_units >= 0),
    truck_units                    BIGINT   CHECK (truck_units >= 0),
    bus_units                      BIGINT   CHECK (bus_units >= 0),
    fleetsize                      VARCHAR  REFERENCES dim_fleetsize (code),
    fleet_bin                      VARCHAR  CHECK (fleet_bin IN ('0', '1', '2-5', '6-20', '21-100', '101+')),
    power_units_matches_fleetsize  BOOLEAN,            -- FALSE = power_units is suspect (e.g. 399,998)
    owntruck                       BIGINT,
    owntract                       BIGINT,
    owntrail                       BIGINT,
    owncoach                       BIGINT,
    total_drivers                  BIGINT   CHECK (total_drivers >= 0),
    total_cdl                      BIGINT   CHECK (total_cdl >= 0),
    driver_inter_total             BIGINT,
    total_intrastate_drivers       BIGINT,
    interstate_within_100_miles    BIGINT,
    interstate_beyond_100_miles    BIGINT,
    intrastate_within_100_miles    BIGINT,
    intrastate_beyond_100_miles    BIGINT,
    mcs150_mileage                 BIGINT   CHECK (mcs150_mileage >= 0),
    mcs150_mileage_year            SMALLINT,
    safety_rating                  VARCHAR  REFERENCES dim_safety_rating (code),     -- NULL = never rated
    safety_rating_date             DATE,
    review_type                    VARCHAR  REFERENCES dim_review_type (code),
    review_date                    DATE,
    docket1prefix                  VARCHAR,            -- MC / FF / MX
    docket1                        VARCHAR,
    cargo_count                    SMALLINT NOT NULL,
    crgo_cargoothr_desc            VARCHAR
);

-- ================================================================ multi-value children
CREATE TABLE census_cargo (
    dot_number  BIGINT  NOT NULL REFERENCES census_carrier (dot_number),
    cargo_code  VARCHAR NOT NULL REFERENCES dim_cargo (code),
    PRIMARY KEY (dot_number, cargo_code)
);

CREATE TABLE census_classification (
    dot_number  BIGINT  NOT NULL REFERENCES census_carrier (dot_number),
    class_code  VARCHAR NOT NULL REFERENCES dim_classification (code),
    PRIMARY KEY (dot_number, class_code)
);

-- ================================================================ rollups (US physical addresses only)
CREATE TABLE agg_census_state (
    phy_state                   VARCHAR PRIMARY KEY,
    entities                    BIGINT  NOT NULL,
    active_entities             BIGINT  NOT NULL,
    active_carriers             BIGINT  NOT NULL,
    active_interstate_carriers  BIGINT  NOT NULL,
    active_hazmat_carriers      BIGINT  NOT NULL,
    active_power_units          BIGINT,      -- excludes power_units values that don't match their FLEETSIZE code
    active_drivers              BIGINT
);

CREATE TABLE agg_census_added_month (
    phy_state        VARCHAR NOT NULL,
    add_month_start  DATE    NOT NULL,
    records_added    BIGINT  NOT NULL,   -- created OR reactivated that month (legacy 1974 placeholder excluded)
    carriers_added   BIGINT  NOT NULL,
    still_active     BIGINT  NOT NULL,   -- of those, still active today
    PRIMARY KEY (phy_state, add_month_start)
);

-- ================================================================ load data (BY NAME matches parquet columns to table columns)
INSERT INTO dim_state              BY NAME SELECT * FROM read_parquet('FMCSA_data_processed/census/dim_state.parquet');
INSERT INTO dim_county             BY NAME SELECT * FROM read_parquet('FMCSA_data_processed/census/dim_county.parquet');
INSERT INTO dim_status             BY NAME SELECT * FROM read_parquet('FMCSA_data_processed/census/dim_status.parquet');
INSERT INTO dim_carrier_operation  BY NAME SELECT * FROM read_parquet('FMCSA_data_processed/census/dim_carrier_operation.parquet');
INSERT INTO dim_safety_rating      BY NAME SELECT * FROM read_parquet('FMCSA_data_processed/census/dim_safety_rating.parquet');
INSERT INTO dim_review_type        BY NAME SELECT * FROM read_parquet('FMCSA_data_processed/census/dim_review_type.parquet');
INSERT INTO dim_business_org       BY NAME SELECT * FROM read_parquet('FMCSA_data_processed/census/dim_business_org.parquet');
INSERT INTO dim_entity_type        BY NAME SELECT * FROM read_parquet('FMCSA_data_processed/census/dim_entity_type.parquet');
INSERT INTO dim_classification     BY NAME SELECT * FROM read_parquet('FMCSA_data_processed/census/dim_classification.parquet');
INSERT INTO dim_cargo              BY NAME SELECT * FROM read_parquet('FMCSA_data_processed/census/dim_cargo.parquet');
INSERT INTO dim_fleetsize          BY NAME SELECT * FROM read_parquet('FMCSA_data_processed/census/dim_fleetsize.parquet');

INSERT INTO census_carrier         BY NAME SELECT * FROM read_parquet('FMCSA_data_processed/census/census_carrier.parquet');
INSERT INTO census_cargo           BY NAME SELECT * FROM read_parquet('FMCSA_data_processed/census/census_cargo.parquet');
INSERT INTO census_classification  BY NAME SELECT * FROM read_parquet('FMCSA_data_processed/census/census_classification.parquet');

INSERT INTO agg_census_state       BY NAME SELECT * FROM read_parquet('FMCSA_data_processed/census/agg_census_state.parquet');
INSERT INTO agg_census_added_month BY NAME SELECT * FROM read_parquet('FMCSA_data_processed/census/agg_census_added_month.parquet');
