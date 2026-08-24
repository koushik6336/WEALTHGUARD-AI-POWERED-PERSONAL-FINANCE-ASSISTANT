import json
import boto3
import uuid
from opensearchpy import OpenSearch, RequestsHttpConnection
from botocore.config import Config
from requests_aws4auth import AWS4Auth

OPENSEARCH_ENDPOINT = "vpc-wealthguard-knowledge-fkmsjoivsnq37n2kswhurdnzee.ap-south-1.es.amazonaws.com"
INDEX_NAME = "wealthguard-knowledge"
REGION = "ap-south-1"
BEDROCK_MODEL = "amazon.titan-embed-text-v2:0"

bedrock = boto3.client(
    "bedrock-runtime",
    region_name=REGION,
    config=Config(
        connect_timeout=3,
        read_timeout=5,
        retries={"max_attempts": 1}
    )
)

credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    "es",
    session_token=credentials.token
)

os_client = OpenSearch(
    hosts=[{"host": OPENSEARCH_ENDPOINT, "port": 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=False,
    ssl_show_warn=False,
    connection_class=RequestsHttpConnection
)

TAX_KNOWLEDGE = open("/var/task/tax_knowledge.txt").read()
FRAUD_PATTERNS = open("/var/task/fraud_patterns.txt").read()
INVESTMENT_KNOWLEDGE = open("/var/task/investment_knowledge.txt").read()

DOCUMENTS = [
    {"text": TAX_KNOWLEDGE, "category": "tax"},
    {"text": FRAUD_PATTERNS, "category": "fraud"},
    {"text": INVESTMENT_KNOWLEDGE, "category": "investment"},
]

def get_embedding(text):
    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL,
            body=json.dumps({"inputText": text[:8000]})
        )
        result = json.loads(response["body"].read())
        return result["embedding"]
    except Exception as e:
        print(f"Embedding error: {e}")
        return [0.0] * 1024

def chunk_text(text, chunk_size=45):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i+chunk_size]))
    return chunks

def create_index():
    try:
        if os_client.indices.exists(index=INDEX_NAME):
            print("Index exists, deleting and recreating")
            os_client.indices.delete(index=INDEX_NAME)
        mapping = {
            "mappings": {
                "properties": {
                    "text": {"type": "text"},
                    "category": {"type": "keyword"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": 1024
                    }
                }
            },
            "settings": {
                "index": {"knn": True}
            }
        }
        os_client.indices.create(index=INDEX_NAME, body=mapping)
        print("Index created successfully")
    except Exception as e:
        print(f"Index creation error: {e}")
        raise

def load_documents():
    total = 0
    for doc in DOCUMENTS:
        chunks = chunk_text(doc["text"])
        print(f"Loading {len(chunks)} chunks for category: {doc['category']}")
        for i, chunk in enumerate(chunks):
            embedding = get_embedding(chunk)
            os_client.index(
                index=INDEX_NAME,
                id=str(uuid.uuid4()),
                body={
                    "text": chunk,
                    "category": doc["category"],
                    "embedding": embedding
                }
            )
            total += 1
            print(f"  Indexed chunk {i+1}/{len(chunks)}")
    return total

def lambda_handler(event, context):
    try:
        print("Starting knowledge base load with SigV4 auth")
        create_index()
        total = load_documents()
        os_client.indices.refresh(index=INDEX_NAME)
        count = os_client.count(index=INDEX_NAME)["count"]
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Knowledge base loaded successfully",
                "documents_indexed": total,
                "total_in_index": count
            })
        }
    except Exception as e:
        print(f"Error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
