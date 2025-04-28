import requests
import boto3
from boto3.dynamodb.conditions import Key
import json
import logging
from typing import List, Dict
from datetime import datetime, date
from tqdm import tqdm


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

def get_previous_month_09th(year, month):
    if month == 1:
        prev_year = year - 1
        prev_month = 12
    else:
        prev_year = year
        prev_month = month - 1
    return date(prev_year, prev_month, 9).strftime("%Y-%m-%d")

def lambda_handler(event, context):

    DYNAMODB_TABLE_NAME = event.get("DYNAMODB_TABLE_NAME", 'clinmatch-dev-AACT-metamap')
    AWS_REGION = event.get('AWS_REGION', 'ap-east-1')

    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    s3 = boto3.client('s3', region_name=AWS_REGION)
    # Define the bucket name and prefix
    bucket_name = 'codex-data-medical'
    prefix = 'aact-metamap-monthly-updates/'

    ##############################################################
    ### Retrieving all updated studies from clinicaltrials.gov ###
    ##############################################################
    now = datetime.now()

    if "date_cut" in event:
        date_cut = event["date_cut"]
    else:   
        date_cut = get_previous_month_09th(int(now.strftime("%Y")), int(now.strftime("%m")))

    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        # "query.term": "AREA[LastUpdatePostDate]RANGE[2025-04-09,MAX] AND (AREA[Phase]PHASE1 OR AREA[Phase]PHASE2 OR AREA[Phase]PHASE3 OR AREA[Phase]PHASE4 OR AREA[Phase]EARLY_PHASE1)",
        # "query.term": "AREA[StudyType]INTERVENTIONAL",
        # LastUpdateSubmitDate LastUpdatePostDate
        "query.term": f"AREA[LastUpdatePostDate]RANGE[{date_cut},MAX] AND AREA[StudyType]INTERVENTIONAL AND (AREA[Phase]PHASE1 OR AREA[Phase]PHASE2 OR AREA[Phase]PHASE3 OR AREA[Phase]PHASE4 OR AREA[Phase]EARLY_PHASE1)",
        # "filter.overallStatus": "NOT_YET_RECRUITING|RECRUITING|ACTIVE_NOT_RECRUITING",
        "countTotal": "true",
        "pageSize": "1000"
    }
    headers = {
        "accept": "application/json"
    }

    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        data = response.json()
        # print(data)
    else:
        logger.error(f"Error: {response.status_code}")

    all_updated_studies = [] 
    all_updated_studies.extend(data['studies'])

    while 'nextPageToken' in data.keys():

        params["pageToken"] = data["nextPageToken"]
        response = requests.get(url, params=params, headers=headers)

        if response.status_code == 200:
            data = response.json()
            all_updated_studies.extend(data['studies'])
        else:
            logger.error(f"Error: {response.status_code}")

    logger.info(f"Total number of updated studies: {len(all_updated_studies)}")


    ###############################################
    ### Write updated raw trials from API to S3 ###
    ###############################################

    def query_dynamodb(table_name, nct_id):
        """
        Queries a DynamoDB table for items with a specific partition key (nct_id)
        and a sort key (updated_at) greater than or equal to a specified value.

        :param table_name: The name of the DynamoDB table
        :param nct_id: The value of the partition key to query
        :param updated_at_min: The minimum value for the sort key
        :return: A list of items matching the query
        """

        table = dynamodb.Table(table_name)
        
        try:
            # Perform the query using KeyConditionExpression
            response = table.query(
                KeyConditionExpression=Key('nct_id').eq(nct_id)
            )
            
            # Extract the items from the response
            items = response['Items']
            
            return items
        except Exception as e:
            # Print error message if something goes wrong
            logger.error(f"An error occurred: {e}")
            return []

    def upload_to_s3(s3, bucket_name, file_key, json_data): 

        # Upload the JSON file
        
        try:
            s3.put_object(Bucket=bucket_name, Key=file_key, Body=json_data, ContentType='application/json')
            # print(f"Uploaded JSON file to: {file_key}")
        except Exception as e:
            logger.error(f"Error uploading JSON file: {e}")

    update_cnt = 0
    remove_cnt = 0
    add_cnt = 0
    do_nothing_cnt = 0

    # get date.now() in yyyy-mm-dd format
    now = datetime.now()
    date_folder = now.strftime("%Y-%m-%d")
    date_folder_key = f"{prefix}{date_folder}/"

    try:
        s3.put_object(Bucket=bucket_name, Key=date_folder_key)
        logger.info(f"Root folder created: {date_folder_key}")
    except Exception as e:
        logger.error(f"Error creating folder: {e}")

    folders = ['update', 'remove', 'add', 'do_nothing']

    for folder in folders:
        # Create the folder object
        folder_key = f"{date_folder_key}{folder}/"
        logger.info(f"Creating folder: {folder_key}")
        try:
            s3.put_object(Bucket=bucket_name, Key=folder_key)
            logger.info(f"Folder created: {folder_key}")
        except Exception as e:
            logger.error(f"Error creating folder: {e}")

    for updated_study in tqdm(all_updated_studies):
        nct_id = updated_study['protocolSection']['identificationModule']['nctId']
        status = updated_study['protocolSection']['statusModule']['overallStatus']

        items = query_dynamodb(DYNAMODB_TABLE_NAME, nct_id)
    
        if items and status in ["ACTIVE_NOT_RECRUITING", "RECRUITING", "ACTIVE_NOT_RECRUITING"]:
            # Update DynamoDB item
            update_cnt+=1
            file_key = f"{date_folder_key}update/{nct_id}.json"
            upload_to_s3(s3, bucket_name, file_key, json.dumps(updated_study))

        elif items and status not in ["ACTIVE_NOT_RECRUITING", "RECRUITING", "ACTIVE_NOT_RECRUITING"]:
            # Remove DynamoDB item
            remove_cnt+=1
            file_key = f"{date_folder_key}remove/{nct_id}.json"
            upload_to_s3(s3, bucket_name, file_key, json.dumps(updated_study))
        
        elif len(items) == 0 and status in ["ACTIVE_NOT_RECRUITING", "RECRUITING", "ACTIVE_NOT_RECRUITING"]:
            # Add new DynamoDB item
            add_cnt+=1
            file_key = f"{date_folder_key}add/{nct_id}.json"
            upload_to_s3(s3, bucket_name, file_key, json.dumps(updated_study))

        else: # len(items) == 0 and status not in ["ACTIVE_NOT_RECRUITING", "RECRUITING", "ACTIVE_NOT_RECRUITING"]
            do_nothing_cnt+=1
            file_key = f"{date_folder_key}do_nothing/{nct_id}.json"
            upload_to_s3(s3, bucket_name, file_key, json.dumps(updated_study))

    file_key = f"{date_folder_key}metadata_{now.strftime("%Y-%m-%d")}.json"
    metadata = {
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date_cut": date_cut,
        "aact_update_total ": len(all_updated_studies), 
        "update_cnt": update_cnt, 
        "remove_cnt": remove_cnt, 
        "add_cnt": add_cnt, 
        "do_nothing_cnt": do_nothing_cnt
    }
    upload_to_s3(s3, bucket_name, file_key, json.dumps(metadata))
