#!/usr/bin/env bash
set -e

# Materialize .streamlit/secrets.toml from Azure App Settings before launch.
python azure/write_secrets.py

exec streamlit run review_app.py \
  --server.port=$PORT \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --server.enableXsrfProtection=true \
  --browser.gatherUsageStats=false
