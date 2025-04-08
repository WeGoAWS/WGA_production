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
    - Table: cloudtrail
        - eventID (VARCHAR)
        - eventName (VARCHAR)
        - eventTime (TIMESTAMP)
        - userName (VARCHAR)
        - sourceIPAddress (VARCHAR)
        - awsRegion (VARCHAR)
        - errorCode (VARCHAR)
    - Table: sechub
        - id (INT)
        - created_at (TIMESTAMP)
        - user_id (VARCHAR)
        - action (VARCHAR)
        - status (VARCHAR)
        - resource_type (VARCHAR)

Model Instructions:
- Use only the tables and columns provided in the schema.
- If the question implies date or time filtering, use the `eventTime` or `created_at` fields.
- 추가로 스키마들이 추가 되면 다른 규칙들도 추가하면 좋을 듯
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

