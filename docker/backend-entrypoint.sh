#!/bin/sh
set -e

STORAGE=/app/environment/frontend_server/storage
SEED=$STORAGE/ed_sim_n5
CURR=$STORAGE/curr_sim

if [ ! -d "$CURR" ]; then
    if [ -d "$SEED" ]; then
        echo "[entrypoint] Seeding curr_sim from ed_sim_n5..."
        cp -r "$SEED" "$CURR"
    else
        echo "[entrypoint] WARNING: ed_sim_n5 seed data not found. Mount storage volume or provide seed data before running the simulation."
    fi
fi

exec "$@"
