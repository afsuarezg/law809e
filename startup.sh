#!/usr/bin/env bash
streamlit run review_app.py \
  --server.port=$PORT \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --server.enableXsrfProtection=true \
  --browser.gatherUsageStats=false
