ALTER TABLE customer_enrichment.customer_enrichment_runs
DELETE WHERE customer_id IN {demo_customer_ids:Array(String)}
SETTINGS mutations_sync = 2;

ALTER TABLE customer_enrichment.customers
DELETE WHERE is_demo = 1
  AND customer_id IN {demo_customer_ids:Array(String)}
SETTINGS mutations_sync = 2;
