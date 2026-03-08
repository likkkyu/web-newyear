import os
import uuid
from pathlib import Path
from typing import Any, Optional

try:
    import boto3  # type: ignore
except Exception:  # pragma: no cover
    boto3 = None  # type: ignore

try:
    import oss2  # type: ignore
except Exception:  # pragma: no cover
    oss2 = None  # type: ignore


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


class StorageProvider(object):
    """对象存储 Provider 抽象接口。

    这里主要负责把后端生成或接收到的二进制内容落盘，并返回前端可访问的 URL。
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def save_bytes(self, data: bytes, filename: str, category: str = "uploads") -> str:
        """保存二进制数据并返回 URL（例如 /static/xxx.png）。"""

        raise NotImplementedError


class LocalStorageProvider(StorageProvider):
    """本地静态文件存储实现。

    会把文件保存在 backend/static 目录下，并通过 FastAPI 的 /static 挂载暴露。"""

    def __init__(self) -> None:
        super(LocalStorageProvider, self).__init__(name="local")

    def save_bytes(self, data: bytes, filename: str, category: str = "uploads") -> str:
        STATIC_DIR.mkdir(exist_ok=True)
        # 将 category 作为前缀拼到文件名中，方便后续区分来源
        safe_name = "%s_%s" % (category, filename)
        path = STATIC_DIR / safe_name
        with path.open("wb") as f:
            f.write(data)
        return "/static/%s" % safe_name


class SimpleHTTPStorageProvider(LocalStorageProvider):
    """预留给云存储（如 S3、OSS、火山对象存储）的 Provider。

    当前仍然写入本地 static 目录，接入真实对象存储时可以在这里改造逻辑，
    仍旧保持对外返回一个可公开访问的 URL。
    """

    def __init__(self, provider_name: str, api_key: Optional[str]) -> None:
        super(SimpleHTTPStorageProvider, self).__init__()
        self.name = provider_name
        self.api_key = api_key
        # 可以增加 bucket、region 等配置


class S3StorageProvider(StorageProvider):
    """S3 兼容对象存储实现（适用于 AWS S3 / Cloudflare R2 / MinIO / 火山引擎 TOS 的 S3 接口等）。

    需要环境变量：
    - STORAGE_S3_ENDPOINT（可选：S3 兼容 endpoint，例如 https://s3.amazonaws.com 或自建 endpoint）
    - STORAGE_S3_REGION（可选）
    - STORAGE_S3_BUCKET（必填）
    - STORAGE_S3_ACCESS_KEY_ID（必填）
    - STORAGE_S3_SECRET_ACCESS_KEY（必填）
    - STORAGE_S3_PUBLIC_BASE_URL（可选：拼接公开访问 URL 的前缀，例如 https://cdn.example.com）
    """

    def __init__(self, provider_name: str) -> None:
        super(S3StorageProvider, self).__init__(name=provider_name or "s3")
        if boto3 is None:
            raise RuntimeError("boto3 未安装，无法启用 S3StorageProvider")

        self.bucket = os.getenv("STORAGE_S3_BUCKET", "").strip()
        self.access_key_id = os.getenv("STORAGE_S3_ACCESS_KEY_ID", "").strip()
        self.secret_access_key = os.getenv("STORAGE_S3_SECRET_ACCESS_KEY", "").strip()
        self.region = os.getenv("STORAGE_S3_REGION", "").strip() or None
        self.endpoint = os.getenv("STORAGE_S3_ENDPOINT", "").strip() or None
        self.public_base_url = os.getenv("STORAGE_S3_PUBLIC_BASE_URL", "").strip() or None

        if not self.bucket or not self.access_key_id or not self.secret_access_key:
            raise RuntimeError("S3 存储缺少必要环境变量：STORAGE_S3_BUCKET / ACCESS_KEY_ID / SECRET_ACCESS_KEY")

        session = boto3.session.Session()
        self.client = session.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
        )

    def save_bytes(self, data: bytes, filename: str, category: str = "uploads") -> str:
        safe_name = "%s_%s" % (uuid.uuid4().hex, (filename or "file"))
        key = "%s/%s" % (category or "uploads", safe_name)

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType="application/octet-stream",
        )

        if self.public_base_url:
            return "%s/%s" % (self.public_base_url.rstrip("/"), key)

        # 无 public_base_url 时，尽量返回 endpoint + bucket + key 的可用形式
        if self.endpoint:
            return "%s/%s/%s" % (self.endpoint.rstrip("/"), self.bucket, key)

        return "https://%s.s3.amazonaws.com/%s" % (self.bucket, key)


class AliyunOSSStorageProvider(StorageProvider):
    """阿里云 OSS 存储。环境变量：ALIYUN_OSS_ACCESS_KEY_ID, ALIYUN_OSS_ACCESS_KEY_SECRET, ALIYUN_OSS_BUCKET, ALIYUN_OSS_ENDPOINT（如 oss-cn-hangzhou.aliyuncs.com）, ALIYUN_OSS_PUBLIC_BASE_URL（可选，公网访问前缀）。"""

    def __init__(self) -> None:
        super(AliyunOSSStorageProvider, self).__init__(name="aliyun")
        if oss2 is None:
            raise RuntimeError("oss2 未安装，无法启用 AliyunOSSStorageProvider")
        self.access_key_id = os.getenv("ALIYUN_OSS_ACCESS_KEY_ID", "").strip()
        self.access_key_secret = os.getenv("ALIYUN_OSS_ACCESS_KEY_SECRET", "").strip()
        self.bucket_name = os.getenv("ALIYUN_OSS_BUCKET", "").strip()
        endpoint = os.getenv("ALIYUN_OSS_ENDPOINT", "").strip() or "oss-cn-hangzhou.aliyuncs.com"
        if not endpoint.startswith("http"):
            endpoint = "https://" + endpoint
        self.endpoint = endpoint.rstrip("/")
        self.public_base_url = os.getenv("ALIYUN_OSS_PUBLIC_BASE_URL", "").strip() or None
        if not self.access_key_id or not self.access_key_secret or not self.bucket_name:
            raise RuntimeError("阿里云 OSS 缺少环境变量：ALIYUN_OSS_ACCESS_KEY_ID / ACCESS_KEY_SECRET / BUCKET")
        auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        self.bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)

    def save_bytes(self, data: bytes, filename: str, category: str = "uploads") -> str:
        safe_name = "%s_%s" % (uuid.uuid4().hex, (filename or "file"))
        key = "%s/%s" % (category or "uploads", safe_name)
        self.bucket.put_object(key, data)
        if self.public_base_url:
            return "%s/%s" % (self.public_base_url.rstrip("/"), key)
        return "https://%s.%s/%s" % (
            self.bucket_name,
            self.endpoint.replace("https://", ""),
            key,
        )


_STORAGE_PROVIDER_SINGLETON: Optional[StorageProvider] = None


def get_storage_provider() -> StorageProvider:
    global _STORAGE_PROVIDER_SINGLETON
    if _STORAGE_PROVIDER_SINGLETON is not None:
        return _STORAGE_PROVIDER_SINGLETON

    provider_name = os.getenv("STORAGE_PROVIDER", "local").strip().lower()
    api_key = os.getenv("STORAGE_API_KEY")

    if provider_name in ("local", "mock", "filesystem", "file") or (not provider_name):
        _STORAGE_PROVIDER_SINGLETON = LocalStorageProvider()
    elif provider_name in ("aliyun", "oss"):
        _STORAGE_PROVIDER_SINGLETON = AliyunOSSStorageProvider()
    elif provider_name in ("s3", "tos", "r2", "minio"):
        _STORAGE_PROVIDER_SINGLETON = S3StorageProvider(provider_name)
    else:
        # 兼容旧逻辑：当你使用自定义 storage 服务时，可在此扩展
        _STORAGE_PROVIDER_SINGLETON = SimpleHTTPStorageProvider(provider_name, api_key)

    return _STORAGE_PROVIDER_SINGLETON
