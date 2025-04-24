import psycopg2
import boto3
from psycopg2.extras import RealDictCursor
import json
import logging
from typing import List, Dict
from dotenv import load_dotenv
import os
import pandas as pd
from tqdm import tqdm
from botocore.exceptions import ClientError

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# AWS Lambda function details (replace with your own)
LAMBDA_FUNCTION_NAME = 'clinmatch-dev-metamapParser'  # Your Lambda function name
DYNAMODB_TABLE_NAME = 'clinmatch-AACT-metamap'
AWS_REGION = 'ap-east-1'


def write_to_dynamodb(nct_id: str, updated_at: str, lambda_result: Dict):
    """Writes the Lambda result to DynamoDB along with nct_id and updated_at."""
    try:
        dynamodb = boto3.Session(aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'), aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')).resource('dynamodb', region_name=AWS_REGION)
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)

        # Ensure updated_at is a string
        updated_at_str = str(updated_at)

        # Prepare the item to write
        item = {
            'nct_id': nct_id,
            'updated_at': updated_at_str,
            'metamap_result': lambda_result
        }

        # Write to DynamoDB
        table.put_item(Item=item)
        logger.info(f"Successfully wrote data for nct_id: {nct_id} to DynamoDB")
        
    except ClientError as e:
        logger.error(f"Error writing to DynamoDB: {e}")
        raise

if __name__ == '__main__':

    # phase = 'phase2_failed' # phase2_failed phase3_failed phase4_failed
    phase = 'phase2' #'phase2' # phase3 phase4
    input_root_dir = f'Data/metamap_result_processed/{phase}'

    dynamodb = boto3.Session(aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'), aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')).resource('dynamodb', region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)

    # for each json file in input_root_dir, call remove_duplicate_cuis
    json_files = os.listdir(input_root_dir)
    for filename in tqdm(json_files):
        if filename.endswith('.json'):
            input_file_path = os.path.join(input_root_dir, filename)
            with open(input_file_path, 'r') as f: 
                item = json.load(f)
            try:
                # Write to DynamoDB
                table.put_item(Item=item)
                nct_id = filename.split('.')[0]
                logger.info(f"Successfully wrote data for nct_id: {nct_id} to DynamoDB")
                
            except ClientError as e:
                logger.error(f"Error writing to DynamoDB: {e}")
                raise