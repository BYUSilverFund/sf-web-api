import boto3
import polars as pl
from io import BytesIO
from dotenv import load_dotenv
import os

load_dotenv(override=True)

aws_access_key_id = os.getenv("COGNITO_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("COGNITO_SECRET_ACCESS_KEY")
region_name = os.getenv("COGNITO_REGION")

client = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=region_name,
)


def get_parquet(bucket_name: str, file_key: str) -> pl.DataFrame:
    s3_object = client.get_object(Bucket=bucket_name, Key=file_key)

    file_content = s3_object["Body"].read()

    return pl.read_parquet(BytesIO(file_content))

def scan_parquet(bucket_name: str, file_key: str) -> pl.LazyFrame:
    storage_options = {
        "aws_access_key_id": aws_access_key_id,
        "aws_secret_access_key": aws_secret_access_key,
        "aws_region": region_name,
    }

    source = f"s3://{bucket_name}/{file_key}"

    return pl.scan_parquet(source, storage_options=storage_options)


def list_files(bucket_name: str):
    file_paths = []

    response = client.list_objects_v2(Bucket=bucket_name)

    for object in response["Contents"]:
        file_path = bucket_name + "/" + object["Key"]
        file_paths.append(file_path)

    return file_paths
