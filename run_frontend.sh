#!/bin/bash

FRONTEND_SCRIPT_PATH="environment/frontend_server"
FRONTEND_SCRIPT_FILE="manage.py"
CONDA_ENV="simulacra"

FILE_NAME="Bash-Script-Frontend"
echo "(${FILE_NAME}): Running frontend server"
cd ${FRONTEND_SCRIPT_PATH}
source C:/Users/guldb/anaconda3/etc/profile.d/conda.sh ${CONDA_ENV}

PORT=8000
if [ -z "$1" ]
then
    echo "(${FILE_NAME}): No port provided. Using default port: ${PORT}"
else
    PORT=$1
fi

python ${FRONTEND_SCRIPT_FILE} runserver ${PORT}