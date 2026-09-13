# dags/Dockerfile — the one-container Airflow for the demonstration (Phase 10a).
# The official image on its Python-3.12 variant (the project pins 3.12; the
# image's default is 3.13), plus the two tools the DAG's tasks need and the
# image does not carry: `make` (no build-essential in the production image) by
# apt as root, `uv` (the project's pinned version) by pip as the airflow user —
# the documented extension pattern. Nothing of the repo is copied in: the
# compose mounts it read-only at /opt/friction-ledger; the mount point for the
# container-private data volume is created here, owned by airflow, so a fresh
# volume inherits that ownership.
FROM apache/airflow:3.3.1-python3.12
USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends make \
  && apt-get autoremove -yqq --purge \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* \
  && mkdir -p /opt/friction-ledger/data \
  && chown airflow:root /opt/friction-ledger/data
USER airflow
RUN pip install --no-cache-dir "uv==0.12.5"
