-- Replace the example Unity Catalog volume path with the claims demo output path.
CREATE OR REPLACE TEMP VIEW claim_reviews
USING json
OPTIONS (path '/Volumes/demo/health/output/claims/gold/reviews');
