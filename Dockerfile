# PostgreSQL 16 + pgvector + PostGIS Dockerfile
# Base image: Official pgvector image based on Debian Bookworm (Debian 12) with PostgreSQL 16
FROM pgvector/pgvector:pg16

# Set non-interactive mode for apt package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install PostGIS from the official PostgreSQL APT repository (bookworm-pgdg)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16-postgis-3 \
        postgresql-16-postgis-3-scripts \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Metadata labels
LABEL maintainer="Hyperlocal Marketplace DevOps Team"
LABEL description="PostgreSQL 16 engine with PostGIS (geospatial) and pgvector (vector search) extensions"
