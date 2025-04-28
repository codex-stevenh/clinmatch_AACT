import boto3
import logging
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import os

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# AWS region (replace with your region)
AWS_REGION = 'ap-east-1'
table_name = 'clinmatch-dev-AACT-metamap'

def create_dynamodb_table(table_name):
    """
    Creates a DynamoDB table named 'table_name' with nct_id as partition key
    and updated_at as sort key.
    """
    try:
        dynamodb = boto3.Session(aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'), aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')).client('dynamodb', region_name=AWS_REGION)
        
        # # Check if the table already exists
        try:
            dynamodb.describe_table(TableName=table_name)
            logger.info(f"Table '{table_name}' already exists.")
            return
        except dynamodb.exceptions.ResourceNotFoundException:
            logger.info(f"Table '{table_name}' does not exist. Creating now...")

        # Create the table
        response = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'nct_id',
                    'KeyType': 'HASH'  # Partition key
                },
                {
                    'AttributeName': 'updated_at',
                    'KeyType': 'RANGE'  # Sort key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'nct_id',
                    'AttributeType': 'S'  # String
                },
                {
                    'AttributeName': 'updated_at',
                    'AttributeType': 'S'  # String
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5000,
                'WriteCapacityUnits': 5000
            }
        )

        # Wait for the table to become active
        waiter = dynamodb.get_waiter('table_exists')
        waiter.wait(TableName='clinmatch-dev-AACT-metamap')
        logger.info(f"Table '{table_name}' created successfully.")
        
    except ClientError as e:
        logger.error(f"Error creating DynamoDB table: {e}")
        raise

create_dynamodb_table(table_name)