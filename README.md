# Biological_Database

Flask application for single-cell analysis: account registration, data upload, quality control, clustering, CellTypist annotation, gene scoring, ORA and GSEA.

## Local setup

1. Create a Python 3.11 environment and install `pip install -r requirements.txt`. Dependencies were inferred from imports; original version pins were not provided.
2. Provision a MySQL database. The archive does not contain database schema migrations or a database dump; required tables must be prepared separately.
3. Set process environment variables using `.env.example` as a reference. The application does not automatically load `.env` files. Generate a fresh Flask secret and use a new database password.
4. Download the required CellTypist models and optionally set `CELLTYPIST_MODEL_DIR`.
5. Run `python app.py` for local development.

## Data and public source

IDE settings, bytecode, caches, uploaded data, generated analysis outputs and bundled biological datasets were excluded. Obtain appropriate datasets separately and check their redistribution terms. Data-loading scripts require database tables and input CSV files; `load_new_data.py` clears existing gene-set tables and `save_libraries.py` replaces the library table.

The database schema, input data and models are missing from the original archive. Python syntax was checked; end-to-end execution has not been validated. This is a research project, and publishing its source does not deploy a live website. Before hosting for multiple users, review shared pipeline state, uploaded archive extraction and user-data isolation.

