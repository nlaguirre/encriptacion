#!/usr/bin/env python3
# We need to receive a file as parametr
# Cypher the file before send it to s3
# send it to s3

# Copyright 2010-2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# This file is licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License. A copy of the
# License is located at
#
# http://aws.amazon.com/apache2.0/
#
# This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS
# OF ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

import base64
import logging
import boto3
import sys
import os
from botocore.exceptions import ClientError

# To perform the optional file encryption/decryption operations, the Python
# cryptography package must be installed.
#       pip install cryptography
from cryptography.fernet import Fernet

key_id=os.environ['KEY_ID']
key_arn=os.environ['KEY_ARN']

#bucket_name = 'bucket-name'
#key_id = 'fdaca60b-6470-4cee-8b7b-dd3e5a49ad31'
#key_arn = 'arn:aws:kms:us-east-1:753941739980:key/fdaca60b-6470-4cee-8b7b-dd3e5a49ad31'
file_name = sys.argv[1]
action = sys.argv[2]

def retrieve_cmk():
    """Retrieve an existing KMS CMK based on its description
    :param desc: Description of CMK specified when the CMK was created
    :return Tuple(KeyId, KeyArn) where:
        KeyId: CMK ID
        KeyArn: Amazon Resource Name of CMK
    :return Tuple(None, None) if a CMK with the specified description was
    not found
    """

    # Retrieve a list of existing CMKs
    # If more than 100 keys exist, retrieve and process them in batches
    kms_client = boto3.client('kms')
    #try:
    #    response = kms_client.list_keys()
    #except ClientError as e:
    #    logging.error(e)
    #    return None, None

    #done = False
    #while not done:
    #    for cmk in response['Keys']:
    # Get info about the key, including its description
    try:
        return key_id, key_arn
    except ClientError as e:
        logging.error(e)
        return None, None

    # Is this the key we're looking for?
    #if key_info['KeyMetadata']['Description'] == desc:
    #    return cmk['KeyId'], cmk['KeyArn']

        # Are there more keys to retrieve?
        #if not response['Truncated']:
            # No, the CMK was not found
        #    logging.debug('A CMK with the specified description was not found')
        #    done = True
        #else:
            # Yes, retrieve another batch
        #    try:
        #        response = kms_client.list_keys(Marker=response['NextMarker'])
        #    except ClientError as e:
        #        logging.error(e)
        #        return None, None

    # All existing CMKs were checked and the desired key was not found
    #return None, None

def create_cmk(desc='Customer Master Key'):
    """Create a KMS Customer Master Key
    The created CMK is a Customer-managed key stored in AWS KMS.
    :param desc: key description
    :return Tuple(KeyId, KeyArn) where:
        KeyId: AWS globally-unique string ID
        KeyArn: Amazon Resource Name of the CMK
    :return Tuple(None, None) if error
    """

    # Create CMK
    kms_client = boto3.client('kms')
    try:
        response = kms_client.create_key(Description=desc)
    except ClientError as e:
        logging.error(e)
        return None, None

    # Return the key ID and ARN
    return response['KeyMetadata']['KeyId'], response['KeyMetadata']['Arn']

def create_data_key(cmk_id, key_spec='AES_256'):
    """Generate a data key to use when encrypting and decrypting data
    :param cmk_id: KMS CMK ID or ARN under which to generate and encrypt the
    data key.
    data key.
    :param key_spec: Length of the data encryption key. Supported values:
        'AES_128': Generate a 128-bit symmetric key
        'AES_256': Generate a 256-bit symmetric key
    :return Tuple(EncryptedDataKey, PlaintextDataKey) where:
        EncryptedDataKey: Encrypted CiphertextBlob data key as binary string
        PlaintextDataKey: Plaintext base64-encoded data key as binary string
    :return Tuple(None, None) if error
    """

    # Create data key
    kms_client = boto3.client('kms')
    try:
        response = kms_client.generate_data_key(KeyId=cmk_id, KeySpec=key_spec)
    except ClientError as e:
        logging.error(e)
        return None, None

    # Return the encrypted and plaintext data key
    return response['CiphertextBlob'], base64.b64encode(response['Plaintext'])

def decrypt_data_key(data_key_encrypted):
    """Decrypt an encrypted data key
    :param data_key_encrypted: Encrypted ciphertext data key.
    :return Plaintext base64-encoded binary data key as binary string
    :return None if error
    """

    # Decrypt the data key
    kms_client = boto3.client('kms')
    try:
        response = kms_client.decrypt(CiphertextBlob=data_key_encrypted)
    except ClientError as e:
        logging.error(e)
        return None

    # Return plaintext base64-encoded binary data key
    return base64.b64encode((response['Plaintext']))

# Number of bytes used in the encrypted file to store the length of the
# encrypted data key. Used by encrypt_file() and decrypt_file().
NUM_BYTES_FOR_LEN = 4

def encrypt_file(filename, cmk_id):
    """Encrypt a file using an AWS KMS CMK
    A data key is generated and associated with the CMK.
    The encrypted data key is saved with the encrypted file. This enables the
    file to be decrypted at any time in the future and by any program that
    has the credentials to decrypt the data key.
    The encrypted file is saved to <filename>.encrypted
    Limitation: The contents of filename must fit in memory.
    :param filename: File to encrypt
    :param cmk_id: AWS KMS CMK ID or ARN
    :return: True if file was encrypted. Otherwise, False.
    """

    # Read the entire file into memory
    try:
        with open(filename, 'rb') as file:
            file_contents = file.read()
    except IOError as e:
        logging.error(e)
        return False

    # Generate a data key associated with the CMK
    # The data key is used to encrypt the file. Each file can use its own
    # data key or data keys can be shared among files.
    # Specify either the CMK ID or ARN
    data_key_encrypted, data_key_plaintext = create_data_key(cmk_id)
    if data_key_encrypted is None:
        return False
    logging.info('Created new AWS KMS data key')

    # Encrypt the file
    f = Fernet(data_key_plaintext)
    file_contents_encrypted = f.encrypt(file_contents)

    # Write the encrypted data key and encrypted file contents together
    try:
        with open(filename + '.encrypted', 'wb') as file_encrypted:
            file_encrypted.write(len(data_key_encrypted).to_bytes(NUM_BYTES_FOR_LEN,
                                                                  byteorder='big'))
            file_encrypted.write(data_key_encrypted)
            file_encrypted.write(file_contents_encrypted)
    except IOError as e:
        logging.error(e)
        return False

    # For the highest security, the data_key_plaintext value should be wiped
    # from memory. Unfortunately, this is not possible in Python. However,
    # storing the value in a local variable makes it available for garbage
    # collection.
    return True

def decrypt_file(filename):
    """Decrypt a file encrypted by encrypt_file()
    The encrypted file is read from <filename>.encrypted
    The decrypted file is written to <filename>.decrypted
    :param filename: File to decrypt
    :return: True if file was decrypted. Otherwise, False.
    """

    # Read the encrypted file into memory
    try:
        with open(filename, 'rb') as file:
            file_contents = file.read()
    except IOError as e:
        logging.error(e)
        return False

    # The first NUM_BYTES_FOR_LEN bytes contain the integer length of the
    # encrypted data key.
    # Add NUM_BYTES_FOR_LEN to get index of end of encrypted data key/start
    # of encrypted data.
    data_key_encrypted_len = int.from_bytes(file_contents[:NUM_BYTES_FOR_LEN],
                                            byteorder='big') \
                             + NUM_BYTES_FOR_LEN
    data_key_encrypted = file_contents[NUM_BYTES_FOR_LEN:data_key_encrypted_len]

    # Decrypt the data key before using it
    data_key_plaintext = decrypt_data_key(data_key_encrypted)
    if data_key_plaintext is None:
        logging.error("Cannot decrypt the data key")
        return False

    # Decrypt the rest of the file
    f = Fernet(data_key_plaintext)
    file_contents_decrypted = f.decrypt(file_contents[data_key_encrypted_len:])

    # Write the decrypted file contents
    try:
        with open(filename + '.decrypted', 'wb') as file_decrypted:
            file_decrypted.write(file_contents_decrypted)
    except IOError as e:
        logging.error(e)
        return False

    # The same security issue described at the end of encrypt_file() exists
    # here, too, i.e., the wish to wipe the data_key_plaintext value from
    # memory.
    return True

def upload_file(file_name, bucket, object_name=None):
    """Upload a file to an S3 bucket
    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = file_name

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(file_name, bucket, object_name)
        print(response)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def create_bucket(bucket_name, region=None):
    """Create an S3 bucket in a specified region
    If a region is not specified, the bucket is created in the S3 default
    region (us-east-1).
    :param bucket_name: Bucket to create
    :param region: String region to create bucket in, e.g., 'us-west-2'
    :return: True if bucket created, else False
    """

    # Create bucket
    try:
        if region is None:
            s3_client = boto3.client('s3')
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client = boto3.client('s3', region_name=region)
            location = {'LocationConstraint': region}
            s3_client.create_bucket(Bucket=bucket_name,
                                    CreateBucketConfiguration=location)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def bucket_exists(bucket_name):
    """Return the existence of a Bucket in s3 based on its name
    :param bucket_name: String with the bucket name
    :return True if it is found or False otherwise. 
    """
    s3_client = boto3.client('s3')
    response = s3_client.list_buckets()

    for i in response['Buckets']:
        if i['Name'] == bucket_name:
            return True
    return False

def main():
    """Exercise AWS KMS operations retrieve_cmk(), create_cmk(),
    create_data_key(), and decrypt_data_key().
    Also, use the various KMS keys to encrypt and decrypt a file.
    """

    # Specify the description for the CMK. If an existing CMK with this
    # description is found, it is used for subsequent operations.
    # Otherwise, a new CMK is created.
    cmk_description = 'My sample CMK'

    # Specify a filename to encrypt/decrypt. To skip these operations,
    # specify an empty string.
    file_to_encrypt = file_name
    upload_to_s3 = False

    # Set up logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)s: %(asctime)s: %(message)s')

    # Does the desired CMK already exist?
    cmk_id, cmk_arn = retrieve_cmk()
    if cmk_id is None:
        # No, create it
        cmk_id, cmk_arn = create_cmk(cmk_description)
        if cmk_id is None:
            exit(1)
        logging.info('Created new AWS KMS CMK')
    else:
        logging.info('Retrieved existing AWS KMS CMK')

    # Use the key to encrypt and decrypt a file
    if file_to_encrypt:
        # Encrypted file contents are written to <file_to_encrypt>.encrypted
        # An encrypted data key is also written to the output file.
        # The encrypted file can be decrypted at any time and by any program
        # that has the credentials to decrypt the data key.
        if action == "encrypt":
            if encrypt_file(file_to_encrypt, cmk_arn):
                logging.info(f'{file_to_encrypt} encrypted to '
                             f'{file_to_encrypt}.encrypted')
        
        elif action == "decrypt":
            # Decrypt the file
            if decrypt_file(file_to_encrypt):
                # Decrypted file contents are written to <file_to_encrypt>.decrypted
                logging.info(f'{file_to_encrypt}.encrypted decrypted to '
                             f'{file_to_encrypt}.decrypted')

        else:
            logging.info('Syntax to encrypt/decrypt: ./cypher filename encrypt  # could be decrypt instead')
            exit(1)
        # Upload file to s3 bucket
        if upload_to_s3:
            # Verify bucket exists, if not, create it.
            if not bucket_exists(bucket_name):
                if not create_bucket(bucket_name):
                    exit(1)
                logging.info('Created new S3 Bucket')
            # Upload the file.
            if not upload_file(file_to_encrypt+'.encrypted', bucket_name):
                exit(1)
            logging.info('Uploaded ' + file_to_encrypt+'.encrypted' + ' to S3 Bucket')

if __name__ == '__main__':
    main()
