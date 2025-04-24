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
from boto3.dynamodb.conditions import Attr

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# AWS Lambda function details (replace with your own)
LAMBDA_FUNCTION_NAME = 'clinmatch-dev-metamapParser'  # Your Lambda function name
DYNAMODB_TABLE_NAME = 'clinmatch-AACT-metamap'
AWS_REGION = 'ap-east-1'

dynamodb = boto3.Session(aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'), aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')).resource('dynamodb', region_name=AWS_REGION)

table = dynamodb.Table(DYNAMODB_TABLE_NAME)

# response = table.meta.client.describe_table(TableName=table.name)

# item_count = response['Table']['ItemCount']

# #####################################################3

# response = table.scan(Select='COUNT')

# item_count = response['Count']

# print(item_count)
try:
    # List to store all matching items
    items = []
    
    # Initial scan with filter expression
    response = table.scan(
        FilterExpression='attribute_type(metamap_result, :list_type) AND size(metamap_result) = :zero',
        ExpressionAttributeValues={
            ':list_type': {'S': 'L'},  # 'L' indicates a list type in DynamoDB
            ':zero': {'N': '0'}       # '0' as a number for size comparison
        }
    )
    
    # Add items from the first response
    items.extend(response['Items'])
    
    # Continue scanning if more items exist
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            FilterExpression='attribute_type(metamap_result, :list_type) AND size(metamap_result) = :zero',
            ExpressionAttributeValues={
                ':list_type': {'S': 'L'},
                ':zero': {'N': '0'}
            },
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        items.extend(response['Items'])
    
    # At this point, 'items' contains all matching items
    print(f"Found {len(items)} items where metamap_result is an empty list.")
    for item in items:
        print(item)

except ClientError as e:
    print(f"Error scanning DynamoDB: {e}")

import pickle
import datetime

# Generate a unique filename with a timestamp
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"items_{timestamp}.pkl"

# Save the items to the pickle file
with open(filename, 'wb') as f:
    pickle.dump(items, f)

# Print a confirmation message
print(f"Saved {len(items)} items to {filename}")
