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

# Database connection parameters for the Dockerized PostgreSQL
DB_CONFIG = {
    'dbname': 'clinmatch_aact',
    'user': 'postgres',
    'password': 'password',  # Matches the password set in Docker
    'host': 'localhost',     # Container port mapped to host
    'port': '5432'           # Default PostgreSQL port mapped to host
}

df_cancer_snomed_ct_tree = pd.read_json('./Data/SNOMED_CT_TREE.json')
cui_df_cancer_snomed_ct_tree = [cui for cui in list(df_cancer_snomed_ct_tree['cui'])]
cui_df_cancer_snomed_ct_tree = set(cui_df_cancer_snomed_ct_tree)

def connect_to_db():
    """Establishes a connection to the PostgreSQL database in the Docker container."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Successfully connected to the database")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to the database: {e}")
        raise


def fetch_study_data(conn, status) -> List[Dict]:
    """Fetches clinical trial data from the database."""
    query = f"""
    SELECT 
        s.nct_id,
        s.official_title,
        s.brief_title,
        s.updated_at,
        s.overall_status,
        dd.description AS detailed_description,
        bs.description AS brief_summary,
        e.criteria,
        ARRAY_AGG(bc.downcase_mesh_term) AS mesh_terms
    FROM studies s
    LEFT JOIN detailed_descriptions dd ON s.nct_id = dd.nct_id
    LEFT JOIN brief_summaries bs ON s.nct_id = bs.nct_id
    LEFT JOIN eligibilities e ON s.nct_id = e.nct_id
    LEFT JOIN browse_conditions bc ON s.nct_id = bc.nct_id
    WHERE s.overall_status = '{status}'
    GROUP BY 
        s.nct_id, s.official_title, s.brief_title, s.updated_at, s.overall_status,
        dd.description, bs.description, e.criteria
    ORDER BY s.nct_id;
    """
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        logger.info(f"Fetched {len(results)} records from the database")
        return results
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        raise

def merge_data_to_text(record: Dict) -> str:
    """Merges a record's fields into a single text string."""
    nct_id = record['nct_id'] or ''
    official_title = record['official_title'] or ''
    brief_title = record['brief_title'] or ''
    updated_at = str(record['updated_at']) if record['updated_at'] else ''
    detailed_description = record['detailed_description'] or ''
    brief_summary = record['brief_summary'] or ''
    criteria = record['criteria'] or ''
    mesh_terms = ', '.join([term for term in (record['mesh_terms'] or []) if term]) or ''

    text = (
        f"NCT ID: {nct_id}\n"
        f"Official Title: {official_title}\n"
        f"Brief Title: {brief_title}\n"
        f"Updated At: {updated_at}\n"
        f"Detailed Description: {detailed_description}\n"
        f"Brief Summary: {brief_summary}\n"
        f"Criteria: {criteria}\n"
        f"Mesh Terms: {mesh_terms}\n"
        "----------------------------------------\n"
    )
    return text


def invoke_lambda(payload: Dict) -> Dict:
    """Invokes the AWS Lambda function with the given payload."""
    try:
        lambda_client = boto3.Session(aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'), aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')).client('lambda', region_name=AWS_REGION, )
        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        response_payload = json.loads(response['Payload'].read().decode('utf-8'))
        logger.info("Successfully invoked Lambda function")
        return response_payload
    except Exception as e:
        logger.error(f"Error invoking Lambda function: {e}")
        raise

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

def main():

    # Step 2: Connect to the database
    conn = connect_to_db()
    try:
        """ 
            ACTIVE_NOT_RECRUITING
            APPROVED_FOR_MARKETING
            AVAILABLE
            COMPLETED
            ENROLLING_BY_INVITATION
            NO_LONGER_AVAILABLE
            NOT_YET_RECRUITING
            RECRUITING
            SUSPENDED
            TEMPORARILY_NOT_AVAILABLE
            TERMINATED
            UNKNOWN
            WITHDRAWN
            WITHHELD
        """
        # Step 3: Fetch data from the Dockerized database
        records = fetch_study_data(conn, 'AVAILABLE')
        
        for record in tqdm(records, total=len(records)):
            # Step 4: Merge records into text
            merged_text = merge_data_to_text(record)
        
            # Step 5: Prepare Lambda payload
            payload = {
                'text': merged_text
            }
            
            # Step 6: Invoke Lambda
            try:
                lambda_response = invoke_lambda(payload)

                # Step 7: Extract Lambda results
                lambda_results = lambda_response.get('result', [])
                lambda_response_len = len(lambda_results)
                logger.info(f"Lambda response cnt: {lambda_response_len}")

                for metamap_result in lambda_results: 
                    metamap_result['onco_tag'] = metamap_result['cui'] in cui_df_cancer_snomed_ct_tree

                # Step 8: Write to DynamoDB
                nct_id = record.get('nct_id')
                updated_at = record.get('updated_at')
                write_to_dynamodb(nct_id, updated_at, lambda_results)
            except Exception as e:
                logger.error(f"Error processing record with nct_id {record['nct_id']}: {e}")
                # log failed record with id in a log.txt file
                failed_id = record.get('nct_id')
                with open('failed_ids.txt', 'a') as log_file: 
                    log_file.write(f"{failed_id}\n")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise

    finally:
        conn.close()
        logger.info("Database connection closed")

if __name__ == "__main__":
    main()