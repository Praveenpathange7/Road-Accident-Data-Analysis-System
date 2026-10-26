# Roadwise — Road Accident Data Analysis System

A Flask and pandas application for exploring officially reported road accident statistics in India. It includes a national dashboard, State/UT comparisons, latest data, search, CSV/PDF reports, safety information, and source links.

## Data and database

- `data/india_annual_trends_2015_2024.csv` provides national accident, fatality, and injury totals.
- `data/state_accidents_2015_2024.csv` provides State/UT accident totals.
- `data/state_casualties_2017_2023.csv` provides State/UT killed/injured figures where published. Missing values remain `NULL`; they are not treated as zero.
- `data/india_road_accidents_2022.csv` contains the independently published 2022 State/UT snapshot.
- `road_accident_database.sql` creates the MySQL schema and loads the national and State/UT annual series used by the app. The records are aggregates, not individual crash records.
- `road_accident_demo_database.sql` is a smaller 2022-only demo database. Use `road_accident_database.sql` for deployment.

The database builder reads the bundled source files and regenerates the complete schema and seed SQL:

```powershell
python build_database_sql.py
```

The app's production data source is MySQL. In production (`APP_ENV=production`) the app always connects to MySQL; it does not switch to CSV when credentials, connectivity, or database rows are missing. Those conditions produce an explicit HTTP 503 and an application log entry. CSV is available only for local development (`DATA_SOURCE=csv`).

## Run locally

Requires Python 3.10 or newer and MySQL 8+ for MySQL mode.

1. Create and activate a virtual environment.
2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. For the default CSV-only local preview, start the app:

   ```powershell
   python app.py
   ```

   Open `http://127.0.0.1:5000`. CSV mode is intended for local development only.

4. To test against MySQL, import `road_accident_database.sql` into a MySQL 8 database and create a local `.env` from `.env.example`. Set `DATA_SOURCE=mysql`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`. `.env` is ignored by Git. Never commit it or paste database passwords into source files.

## MySQL host

Render's managed database product is PostgreSQL, not MySQL. Use a separate MySQL 8-compatible provider, for example Aiven for MySQL, AWS RDS for MySQL, or DigitalOcean Managed MySQL. Choose a service that:

- provides a standard MySQL 8 endpoint reachable from a Render web service;
- supports TLS and gives you a hostname, port, database name, username, and password;
- lets you configure network access for Render (allowlist the current Render outbound IP range if your provider requires it).

Create a fresh database named `road_accident_db` and a dedicated application user with permissions limited to that database. Import `road_accident_database.sql` using the provider's SQL console or MySQL Workbench. The script creates the database and tables and inserts all bundled annual statistics. The seed is repeatable against this schema, but it is not a migration for the earlier 2022-only schema; use a fresh database rather than importing over the demo database. Some managed providers do not grant `CREATE DATABASE`; in that case, create/select the database in the provider console and run the SQL after removing its first `CREATE DATABASE ...` and `USE road_accident_db;` statements.

## Deploy to Render

The included `render.yaml` defines the Python web service, dependency install, Gunicorn command, `/health` check, and non-secret environment variables. Secret values are marked for entry in Render and are not stored in the repository.

1. Push this project to a GitHub repository. Do not add `.env`, database exports containing credentials, or secret values. `.gitignore` excludes `.env`.
2. Provision the MySQL database and import `road_accident_database.sql` as described above. Copy its connection details; do not put the password in GitHub.
3. In Render, choose **New → Blueprint** and connect the GitHub repository containing `render.yaml` (or create a Python Web Service with build command `pip install -r requirements.txt` and start command `gunicorn --bind 0.0.0.0:$PORT --access-logfile - app:app`).
4. In the Render service's Environment settings, enter `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` from the MySQL provider. Use the exact assigned port (Aiven commonly uses a port other than 3306). For Aiven TLS, upload its CA certificate under **Environment → Secret Files** with filename `aiven-ca.pem`, then set `DB_SSL_CA=/etc/secrets/aiven-ca.pem`. Keep `APP_ENV=production` and `DATA_SOURCE=mysql`.
5. Ensure the MySQL provider permits connections from Render and that TLS/network rules are satisfied. Deploy and check the Render build and runtime logs; `/health` must return HTTP 200 after the database is reachable.
6. Set the service's instance plan in Render. The free plan may spin down after inactivity; choose a paid always-on plan if you require the service to stay warm. No hosting provider can guarantee uninterrupted availability.
7. Once Render reports a successful deployment, it shows the public `https://<service-name>.onrender.com` URL. The URL does not exist until you create and deploy the service in your own Render account.

The repository can be public or private; a public website does not require publishing database credentials or making the source repository public.
