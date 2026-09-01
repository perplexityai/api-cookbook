CREATE USER IF NOT EXISTS customer_enrichment_app;
GRANT SELECT ON customer_enrichment.customers TO customer_enrichment_app;
GRANT SELECT, INSERT ON customer_enrichment.customer_enrichment_runs TO customer_enrichment_app;
GRANT SELECT ON customer_enrichment.latest_customer_enrichment TO customer_enrichment_app;
