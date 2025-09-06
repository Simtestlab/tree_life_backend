# services/persons_pic.py
import os
import io
from typing import Union
from dotenv import load_dotenv

# boto imports are optional if AWS isn't configured locally
try:
    import boto3
    from botocore.exceptions import NoCredentialsError, ClientError
except Exception:  # pragma: no cover - boto not required for local dev
    boto3 = None
    NoCredentialsError = Exception
    ClientError = Exception

# Load environment variables from .env (if present)
load_dotenv()

BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# Local fallback directory for development when AWS is not configured
LOCAL_UPLOAD_DIR = os.getenv("LOCAL_UPLOAD_DIR", os.path.join(os.getcwd(), "uploads"))
os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)


def _aws_configured() -> bool:
    return bool(BUCKET_NAME and AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and boto3)


def _get_s3_client():
    if not _aws_configured():
        return None
    return boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )


def _ensure_fileobj(file_obj) -> io.BytesIO:
    """Normalize different input types to a file-like object.

    Accepts:
    - FastAPI UploadFile (has .file)
    - file-like objects with read()
    - bytes
    - io.BytesIO
    """
    # FastAPI UploadFile
    if hasattr(file_obj, "file"):
        return file_obj.file

    # bytes
    if isinstance(file_obj, (bytes, bytearray)):
        return io.BytesIO(file_obj)

    # already file-like
    if hasattr(file_obj, "read"):
        return file_obj

    raise TypeError("file_obj must be bytes, file-like, or UploadFile")


def upload_person_pic(file_obj: Union[bytes, io.IOBase, object], filename: str) -> dict:
    """Upload a person's picture to S3 if configured, otherwise save to local uploads dir.

    Returns a dict with at least 'status' and either 'filename' or 'path' or 'error'.
    """
    filelike = _ensure_fileobj(file_obj)

    # AWS path
    if _aws_configured():
        s3 = _get_s3_client()
        try:
            # boto3 expects a file-like object positioned at start
            if hasattr(filelike, "seek"):
                filelike.seek(0)
            s3.upload_fileobj(filelike, BUCKET_NAME, filename)
            return {"status": "uploaded", "storage": "s3", "filename": filename}
        except NoCredentialsError:
            return {"status": "error", "error": "AWS credentials not found"}
        except ClientError as e:
            return {"status": "error", "error": str(e)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # Local fallback
    try:
        local_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
        # ensure parent dir exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as out_f:
            # read and write in chunks
            if hasattr(filelike, "seek"):
                try:
                    filelike.seek(0)
                except Exception:
                    pass

            chunk = filelike.read(1024 * 64)
            while chunk:
                out_f.write(chunk)
                chunk = filelike.read(1024 * 64)

        return {"status": "uploaded", "storage": "local", "path": local_path}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_person_pic_url(filename: str, expiration: int = 3600) -> Union[str, dict]:
    """Return a presigned S3 URL when AWS configured, otherwise return local file path.

    On error returns a dict with 'error'.
    """
    if _aws_configured():
        s3 = _get_s3_client()
        try:
            url = s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": BUCKET_NAME, "Key": filename},
                ExpiresIn=expiration,
            )
            return url
        except ClientError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}

    # Local fallback: return file:// path for manual testing
    local_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
    if os.path.exists(local_path):
        return f"file://{os.path.abspath(local_path)}"
    return {"error": "file not found", "path": local_path}
