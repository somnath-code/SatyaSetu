#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
volume="${1:?Usage: bash deployment/databricks/upload_inputs.sh dbfs:/Volumes/catalog/schema/volume}"
if ! [[ "$volume" =~ ^dbfs:/Volumes/[a-zA-Z0-9_]+/[a-zA-Z0-9_]+/[a-zA-Z0-9_]+$ ]]; then
  echo 'Use an existing dbfs:/Volumes/catalog/schema/volume path.' >&2
  exit 2
fi
for archive in LLCP2023XPT.zip LLCP2024XPT.zip codebook23_llcp-v2-508.zip codebook24_llcp-v2-508.zip; do
  test -f "$repo_dir/data/raw/$archive"
done
databricks fs mkdir "$volume/brfss"
databricks fs mkdir "$volume/claims"
databricks fs mkdir "$volume/claims/policies"
for archive in LLCP2023XPT.zip LLCP2024XPT.zip codebook23_llcp-v2-508.zip codebook24_llcp-v2-508.zip SOURCE-MANIFEST.json; do
  databricks fs cp "$repo_dir/data/raw/$archive" "$volume/brfss/$archive"
done
for table in patients encounters claims; do
  databricks fs cp "$repo_dir/data/sample/claims/$table.csv" "$volume/claims/$table.csv"
done
databricks fs cp "$repo_dir/data/sample/claims/policies/fictional-claims-policy.md" \
  "$volume/claims/policies/fictional-claims-policy.md"
printf 'BRFSS: %s/brfss\nClaims: %s/claims\n' "$volume" "$volume"
