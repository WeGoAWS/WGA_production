# 프롬프트 slack to llm1
import json

def build_llm1_prompt(user_input):
    return [
        {
            "role": "system",
            "content": "You are an expert SQL query generator for relational databases. You generate ONLY SQL code with no explanation."
        },
        {
            "role": "user",
            "content": f'''
Task:
Convert the following natural language question into an SQL query.

Context information:
- Database Schema:
    - Table: cloudtrail_logs
        - eventVersion (VARCHAR)
        - userIdentity (STRUCT)
        - eventTime (TIMESTAMP)
        - eventSource (VARCHAR)
        - eventName (VARCHAR)
        - awsRegion (VARCHAR)
        - sourceIPAddress (VARCHAR)
        - userAgent (VARCHAR)
        - errorCode (VARCHAR)
        - errorMessage (VARCHAR)
        - requestParameters (VARCHAR)
        - responseElements (VARCHAR)
        - additionalEventData (VARCHAR)
        - requestID (VARCHAR)
        - eventID (VARCHAR)
        - resources (ARRAY<STRUCT>)
        - eventType (VARCHAR)
        - apiVersion (VARCHAR)
        - readOnly (VARCHAR)
        - recipientAccountId (VARCHAR)
        - serviceEventDetails (VARCHAR)
        - sharedEventID (VARCHAR)
        - vpcEndpointId (VARCHAR)
        - tlsDetails (STRUCT)
        - timestamp (DATE PARTITION)

    - STRUCT: userIdentity
        - type (VARCHAR)
        - principalId (VARCHAR)
        - arn (VARCHAR)
        - accountId (VARCHAR)
        - invokedBy (VARCHAR)
        - accessKeyId (VARCHAR)
        - userName (VARCHAR)
        - sessionContext (STRUCT)

    - STRUCT: sessionContext
        - attributes (STRUCT)
            - mfaAuthenticated (VARCHAR)
            - creationDate (VARCHAR)
        - sessionIssuer (STRUCT)
            - type (VARCHAR)
            - principalId (VARCHAR)
            - arn (VARCHAR)
            - accountId (VARCHAR)
            - userName (VARCHAR)
        - ec2RoleDelivery (VARCHAR)
        - webIdFederationData (STRUCT)
            - federatedProvider (VARCHAR)
            - attributes (MAP<STRING, STRING>)

    - ARRAY<STRUCT>: resources
        - arn (VARCHAR)
        - accountId (VARCHAR)
        - type (VARCHAR)

    - STRUCT: tlsDetails
        - tlsVersion (VARCHAR)
        - cipherSuite (VARCHAR)
        - clientProvidedHostHeader (VARCHAR)

Model Instructions:
    # DB Rules:
        - Use only the tables and columns provided in the schema.
        - For struct fields, use dot notation to access subfields. For example, use `userIdentity.userName`, `userIdentity.sessionContext.sessionIssuer.accountId`, etc.
        - For array<struct> fields (like `resources`), you may need to use UNNEST or LATERAL VIEW EXPLODE depending on query context.
        - Fields such as `requestParameters`, `responseElements`, and `serviceEventDetails` are stored as JSON strings. Use JSON functions to parse them if specific fields are needed.
        - For date-based filtering, you can use the `timestamp` partition field in addition to `eventTime`.
        - Do not confuse `eventID` with `requestID`, or `eventSource` with `eventName`. Use exact matches from the schema.
        - Avoid referencing internal fields like `raw_event` or deeply nested session metadata unless explicitly requested.
        - Do not use SELECT *; explicitly list the required columns based on the user question.
        - If the question implies filtering (e.g., by user, region, error), include a proper WHERE clause.
        - If the question requires aggregation, use appropriate functions (e.g., COUNT, MAX) and GROUP BY when necessary.
        - Use ISO 8601 format (e.g., '2025-04-01') when filtering by date.
        - Use LIMIT 100 if the question does not specify how many rows to return.

    # Question Rules:
        - If the question implies date or time filtering, use the `eventTime` or `created_at` fields.
        - If the question asks about a specific user, use `userIdentity.userName` or `sessionContext.sessionIssuer.userName`.
        - If the question refers to time or date ranges, filter using `eventTime` or `timestamp` (partition).
        - If the question involves source IP, use `sourceIPAddress`.
        - If the question is about specific AWS services or API calls, use `eventSource` and `eventName`.
        - If the question implies error or failure, check `errorCode` and `errorMessage`.
        - If the region matters, refer to `awsRegion`.
        - If the question is about accessed resources, use the `resources` field and its subfields like `arn` or `type`.
        - If the question asks about authentication method, use `sessionContext.attributes.mfaAuthenticated`.
        - If the question asks about client or agent, refer to `userAgent`.
        - If the question asks for counts or summaries, use aggregate functions and `GROUP BY` with appropriate fields.
        
    # Return Rules:
        - Return only SQL query, no explanation.

User Question:
{user_input}
'''
        }
    ]

def build_llm2_prompt(user_input, query_result):
    return [
        {
            "role": "system",
            "content": "You are an assistant that provides clear and accurate natural language explanations based on database query results."
        },
        {
            "role": "user",
            "content": f'''
Task:
Generate a human-readable answer based on the original user question and the SQL query result.

Original User Question:
{user_input}

SQL Query Result (as JSON):
{json.dumps(query_result, indent=2)}

Instructions:
- Be specific using the data.
- Use concise, professional language.
- Do not ask user for clarification.
'''
        }
    ]

