# clinmatch_AACT 

This repo contains source code and pipelines to process and ingest AACT dataset into AWS DynamoDB for storage and analysis. The latest AACT image is pulled and ingested locally into a docker-based PostgreSQL database. From this dataset, a subset of clinical trials is selected based on specific criteria: trials with a study_type of "interventional" and an overall_status of "not_yet_recruiting," "active_not_recruiting," or "recruiting." The selected fields for these trials include the official trial title, brief trial title, brief description, detailed description, and eligibility criteria. 

The eligibility criteria are processed using Metamap, which is deployed as an AWS Lambda function to extract relevant medical concepts and metadata. The processed Metamap results, along with the selected trial fields, are then ingested into a DynamoDB table for efficient storage and querying. This workflow ensures that semi-structured data is readily available for downstream analysis and applications.  


### Data Ingestion Workflow 

AACT Data Ingestion into Postgres 
Source: The latest AACT dataset image is pulled from ClinicalTrials.gov. 
Process: The AACT dataset is ingested locally into a PostgreSQL database for initial storage and querying. 
Details: The dataset is stored in a structured relational format to facilitate filtering and extraction. PostgreSQL serves as the initial data store for subsequent processing. 

Trial Selection 
Criteria: A subset of trials is selected based on the following conditions: 
study_type: Interventional 
overall_status: [Not Yet Recruiting, Active Not Recruiting, Recruiting]  
Selected Fields: 
Trial Title, Brief Description, Detailed Description, Eligibility Criteria 
Purpose: These fields contain relevant clinical information for further processing by Metamap. 

Metamap Processing  
Tool: Metamap, a natural language processing tool for extracting clinical concepts, is deployed as an AWS Lambda function. 
Input: The eligibility criteria and descriptions (brief and detailed) from the selected trials are processed by Metamap. 
Output: Metamap extracts clinical terms and concepts, which are structured for storage.  

Data Storage in AWS DynamoDB   
Metamap Results: 
The processed output from Metamap (clinical terms and concepts extracted from trial fields) is ingested into a DynamoDB table. 
Metamap Results Table: Stores extracted clinical terms linked to trial IDs, including fields such as title, brief description, detailed description, and criteria.  

 
### Architecture Summary  
PostgreSQL: Local storage for initial AACT dataset ingestion and filtering. 
AWS Lambda (Metamap): Processes trial descriptions and criteria to extract clinical concepts. 
AWS DynamoDB: Stores Metamap-processed results for scalable access.  