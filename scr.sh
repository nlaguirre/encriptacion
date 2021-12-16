#!/bin/bash
DATE=`date +"%d%m%y"`
TAR=*.$DATE.sql
DUMP_PATH=/home/ec2-user/dumps/
DUMP_NAME=.dump.${DATE}.sql
ALL_DUMPS=all_dumps.${DATE}.tar
DBNAME="base1 base2 base3 base4 base5"
BUCKET=s3://aurorasnapshot-to-s3
SCRIPTS_PATH=/home/ec2-user/encriptacion/
export KEY_ID=`aws secretsmanager get-secret-value --secret-id bastion/kms --query SecretString --output text | jq -r .key_id`
export KEY_ARN=`aws secretsmanager get-secret-value --secret-id bastion/kms --query SecretString --output text | jq -r .key_arn`
export PGUSER=`aws secretsmanager get-secret-value --secret-id prod/auroraserverless --query SecretString --output text | jq -r .username`
export PGPASSWORD=`aws secretsmanager get-secret-value --secret-id prod/auroraserverless --query SecretString --output text | jq -r .password`
export PGHOST=`aws secretsmanager get-secret-value --secret-id prod/auroraserverless --query SecretString --output text | jq -r .host`

for i in $DBNAME;
do
   /usr/bin/pg_dump -d ${i} -f ${DUMP_PATH}${i}${DUMP_NAME}
done
echo $TAR
/usr/bin/tar -cvf ${DUMP_PATH}${ALL_DUMPS} ${DUMP_PATH}$TAR
/usr/bin/gzip ${DUMP_PATH}${ALL_DUMPS}
${SCRIPTS_PATH}cypher.py ${DUMP_PATH}${ALL_DUMPS}.gz encrypt

if [ -f ${DUMP_PATH}${ALL_DUMPS}.gz.encrypted ]
then
    aws s3 cp ${DUMP_PATH}${ALL_DUMPS}.gz.encrypted ${BUCKET}
    rm ${DUMP_PATH}*dump*
else
    echo "ERROR: No existe el archivo ${DUMP_PATH}dump.sql.${DATE}.gz.encrypted."
fi
