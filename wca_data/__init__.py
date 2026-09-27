"""WCA competition data, built from the WCA public results export into a SQLite database.

This package is shared data infrastructure, not part of the web app: it must never import
wca_records_analyser or anything web (tests/wca_data/test_isolation.py enforces this), so
another app can use it, or read the database file directly. See wca_data/SCHEMA.md.
"""
