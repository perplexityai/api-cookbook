CREATE DATABASE IF NOT EXISTS customer_enrichment;

CREATE TABLE IF NOT EXISTS customer_enrichment.customers
(
    customer_id String,
    full_name String,
    company String,
    title Nullable(String),
    location Nullable(String),
    known_profile_url Nullable(String),
    is_demo UInt8,
    created_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY customer_id;

CREATE TABLE IF NOT EXISTS customer_enrichment.customer_enrichment_runs
(
    customer_id String,
    run_id UUID,
    status LowCardinality(String),
    matched_name Nullable(String),
    current_title Nullable(String),
    current_company Nullable(String),
    location Nullable(String),
    match_explanation String,
    selected_source_result_id Nullable(String),
    resolved_profile_url Nullable(String),
    supporting_source_result_ids Array(String),
    supporting_urls Array(String),
    supporting_snippets Array(String),
    people_search_queries Array(String),
    raw_people_search_json String,
    actual_model String,
    agent_response_ids Array(String),
    error_category Nullable(String),
    error_message Nullable(String),
    enriched_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (customer_id, enriched_at, run_id)
SETTINGS non_replicated_deduplication_window = 1000;

ALTER TABLE customer_enrichment.customer_enrichment_runs
MODIFY SETTING non_replicated_deduplication_window = 1000;

CREATE OR REPLACE VIEW customer_enrichment.latest_customer_enrichment AS
SELECT
    customer_id,
    tupleElement(latest, 1) AS run_id,
    tupleElement(latest, 2) AS status,
    tupleElement(latest, 3) AS matched_name,
    tupleElement(latest, 4) AS current_title,
    tupleElement(latest, 5) AS current_company,
    tupleElement(latest, 6) AS location,
    tupleElement(latest, 7) AS match_explanation,
    tupleElement(latest, 8) AS resolved_profile_url,
    tupleElement(latest, 9) AS actual_model,
    tupleElement(latest, 10) AS agent_response_ids,
    latest_enriched_at AS enriched_at
FROM
(
    SELECT
        customer_id,
        argMax(
            tuple(
                run_id,
                status,
                matched_name,
                current_title,
                current_company,
                location,
                match_explanation,
                resolved_profile_url,
                actual_model,
                agent_response_ids
            ),
            tuple(enriched_at, run_id)
        ) AS latest,
        max(enriched_at) AS latest_enriched_at
    FROM customer_enrichment.customer_enrichment_runs
    WHERE status IN ('matched', 'ambiguous', 'not_found', 'error')
    GROUP BY customer_id
);
