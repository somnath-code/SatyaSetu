CREATE OR REPLACE TEMP VIEW claims_by_status AS
SELECT status, COUNT(*) AS claims
FROM claim_reviews
GROUP BY status;

CREATE OR REPLACE TEMP VIEW claims_by_rule AS
SELECT reason, COUNT(*) AS claims
FROM claim_reviews
LATERAL VIEW EXPLODE(review_reasons) rules AS reason
GROUP BY reason;
