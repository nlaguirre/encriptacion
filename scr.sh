#!/bin/bash
DATE=`date +"%d%m%y"`
DUMP_PATH=/home/ec2-user/dumps/
DUMP_NAME=dump.${DATE}.sql
DBNAME=base1
BUCKET=s3://aurorasnapshot-to-s3
SCRIPTS_PATH=/home/ec2-user/dumps/
export PGUSER=`aws secretsmanager get-secret-value --secret-id prod/auroraserverless --query SecretString --output text | jq -r .username`
export PGPASSWORD=`aws secretsmanager get-secret-value --secret-id prod/auroraserverless --query SecretString --output text | jq -r .password`
export PGHOST=`aws secretsmanager get-secret-value --secret-id prod/auroraserverless --query SecretString --output text | jq -r .host`
/usr/bin/pg_dump -d ${DBNAME} -f ${DUMP_PATH}${DUMP_NAME}
/usr/bin/gzip ${DUMP_PATH}${DUMP_NAME}
${SCRIPTS_PATH}cypher.py ${DUMP_PATH}${DUMP_NAME}.gz encrypt

if [ -f ${DUMP_PATH}${DUMP_NAME}.gz.encrypted ]
then
    aws s3 cp ${DUMP_PATH}${DUMP_NAME}.gz.encrypted ${BUCKET}
else
    echo "ERROR: No existe el archivo ${DUMP_PATH}dump.sql.${DATE}.gz.encrypted."
fi
