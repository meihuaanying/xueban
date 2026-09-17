"""应用配置：统一从环境变量读取（含 .env 兜底）。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# 向量维度（bge-m3：1024）
EMBEDDING_DIMS = 1024


class Settings(BaseSettings):
    """运行期配置项。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ----- 基础 -----
    app_name: str = "xueban-api"
    environment: str = "development"
    api_base_url: str = "http://localhost:8000"

    # ----- 数据库 -----
    database_url: str = "postgresql+asyncpg://xueban:change-me@localhost:5432/xueban"
    redis_url: str = "redis://localhost:6379/0"
    # 连接池（按副本配置）：pool_size + max_overflow 不得超过 PG max_connections / 副本数
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout_seconds: float = 10.0
    db_pool_recycle_seconds: int = 1800
    # 连接预检：跨地域/易断链路的保险；本地/容器内网直连时可关闭以省一次往返
    db_pool_pre_ping: bool = False

    # ----- 认证 -----
    jwt_secret: str = "dev-only-jwt-secret-please-change-0123456789abcdef"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # ----- 短信（mock 先行） -----
    sms_provider: str = "mock"
    sms_code_ttl_seconds: int = 300
    sms_code_max_attempts: int = 5

    # ----- 内容安全 -----
    safety_provider: str = "mock"
    safety_fallback_local: bool = True
    yidun_secret_id: str = ""
    yidun_secret_key: str = ""

    # ----- LLM 网关 -----
    # litellm：真实网关（默认）；mock：确定性离线输出（E2E/CI/无 Key 环境）
    llm_provider: str = "litellm"
    litellm_base_url: str = "http://localhost:4000"
    litellm_master_key: str = "sk-xueban-dev"
    llm_default_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    llm_retry_backoff_seconds: float = 0.5

    # ----- 观测 -----
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3100"

    # ----- TTS（微课音频） -----
    tts_provider: str = "mock"
    tts_api_key: str = ""
    micro_lesson_min_chars: int = 600
    micro_lesson_max_chars: int = 1000

    # ----- Embedding / Rerank（RAG） -----
    # mock：本地词面哈希向量（离线开发）；siliconflow：真实 bge-m3 / bge-reranker-v2-m3
    embedding_provider: str = "mock"
    rerank_provider: str = "mock"
    siliconflow_api_key: str = ""
    rerank_top_n: int = 5

    # ----- OCR / 口语评测（M8 V3） -----
    # OCR：service（调用 services/ocr 服务）/ mock（离线确定性）
    ocr_provider: str = "service"
    ocr_base_url: str = "http://localhost:8100"
    ocr_timeout_seconds: float = 10.0
    # 口语评测：mock 先行，接入口语评测供应商时切换
    speaking_provider: str = "mock"

    # ----- 运营后台与告警（M7） -----
    alert_webhook_url: str = ""
    alert_webhook_timeout_seconds: float = 5.0
    inspection_sample_size: int = 50
    inspection_threshold: float = 0.03
    # 开发环境自动创建的管理员（CI/E2E 使用；生产留空则不创建）
    dev_admin_phone: str = ""
    dev_admin_password: str = ""

    # ----- CORS（官网 / 桌面端 / 移动端 WebView 直连） -----
    # 逗号分隔的允许来源；生产由网关同源代理时可留空
    cors_allow_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://127.0.0.1:4173,http://localhost:4173,"
        "http://tauri.localhost,tauri://localhost"
    )

    # ----- 对象存储 -----
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "xueban-minio"
    s3_secret_key: str = "change-me-please"
    s3_bucket: str = "xueban"
    s3_region: str = "auto"
    presign_expire_seconds: int = 900

    @property
    def is_development(self) -> bool:
        """开发/测试环境（开放 dev 辅助接口）。"""
        return self.environment in ("development", "testing")


@lru_cache
def get_settings() -> Settings:
    """带缓存的配置读取（进程内单例）。"""
    return Settings()


settings = get_settings()
