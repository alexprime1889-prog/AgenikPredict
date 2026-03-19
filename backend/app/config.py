"""
Configuration management
Loads configuration from the project root .env file
"""

import os
from dotenv import load_dotenv

# Load .env file from project root
# Path: AgenikPredict/.env (relative to backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # If no root .env, try loading environment variables (for production)
    load_dotenv(override=True)


class Config:
    """Flask configuration class"""

    VALID_SERVICE_ROLES = ('web', 'worker')
    VALID_TASK_STORE_MODES = ('memory', 'dual', 'db')
    VALID_TASK_READ_SOURCES = ('memory', 'db', 'fallback')
    VALID_TASK_EXECUTION_MODES = ('inline', 'worker')
    VALID_ARTIFACT_STORAGE_MODES = ('local', 'shared_fs', 'object_store')

    SERVICE_ROLE = os.environ.get('SERVICE_ROLE', 'web').lower()
    WORKER_STANDBY = os.environ.get('WORKER_STANDBY', 'false').lower() == 'true'

    # Flask config
    SECRET_KEY = os.environ.get('SECRET_KEY', '')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    # Auth config
    JWT_SECRET = os.environ.get('JWT_SECRET', SECRET_KEY)
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
    RESEND_FROM_EMAIL = os.environ.get('RESEND_FROM_EMAIL', 'AgenikPredict <noreply@agenikpredict.com>')
    APP_URL = os.environ.get('APP_URL', 'http://localhost:3000')

    # JSON config - disable ASCII escaping for proper Unicode display
    JSON_AS_ASCII = False

    # Primary LLM (Claude Sonnet — for report generation)
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.anthropic.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'claude-sonnet-4-20250514')

    # Fallback LLM (Gemini 3.1 Pro — backup for report generation)
    LLM_FALLBACK_API_KEY = os.environ.get('LLM_FALLBACK_API_KEY')
    LLM_FALLBACK_BASE_URL = os.environ.get('LLM_FALLBACK_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta/openai')
    LLM_FALLBACK_MODEL_NAME = os.environ.get('LLM_FALLBACK_MODEL_NAME', 'gemini-3.1-pro-preview')

    # Secondary LLM (GLM-5 Turbo — cheap model for chat, ontology)
    LLM_SECONDARY_API_KEY = os.environ.get('LLM_SECONDARY_API_KEY')
    LLM_SECONDARY_BASE_URL = os.environ.get('LLM_SECONDARY_BASE_URL', 'https://api.z.ai/api/paas/v4')
    LLM_SECONDARY_MODEL_NAME = os.environ.get('LLM_SECONDARY_MODEL_NAME', 'glm-5-turbo')

    # Stripe billing
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_5 = os.environ.get('STRIPE_PRICE_5')
    STRIPE_PRICE_20 = os.environ.get('STRIPE_PRICE_20')
    STRIPE_PRICE_50 = os.environ.get('STRIPE_PRICE_50')
    STRIPE_PRICE_100 = os.environ.get('STRIPE_PRICE_100')

    # OpenAI direct (for Whisper transcription — separate from OpenRouter)
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

    # Zep config
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')

    # File upload config
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200MB (video files can be large)
    DEFAULT_UPLOAD_FOLDER = os.path.abspath(
        os.environ.get(
            'RAILWAY_VOLUME_MOUNT_PATH',
            os.path.join(os.path.dirname(__file__), '../uploads'),
        )
    )
    ARTIFACT_STORAGE_MODE = os.environ.get('ARTIFACT_STORAGE_MODE', 'local').lower()
    ARTIFACT_ROOT = os.path.abspath(os.environ.get('ARTIFACT_ROOT', DEFAULT_UPLOAD_FOLDER))
    UPLOAD_FOLDER = ARTIFACT_ROOT
    REPORTS_DIR = os.path.join(ARTIFACT_ROOT, 'reports')
    PROJECTS_DIR = os.path.join(ARTIFACT_ROOT, 'projects')
    ARTIFACT_OBJECT_BUCKET = os.environ.get('ARTIFACT_BUCKET', os.environ.get('ARTIFACT_OBJECT_BUCKET', ''))
    ARTIFACT_OBJECT_PREFIX = os.environ.get('ARTIFACT_PREFIX', os.environ.get('ARTIFACT_OBJECT_PREFIX', 'agenikpredict'))
    ARTIFACT_OBJECT_ENDPOINT_URL = os.environ.get('ARTIFACT_ENDPOINT', os.environ.get('ARTIFACT_OBJECT_ENDPOINT_URL'))
    ARTIFACT_OBJECT_REGION = os.environ.get('ARTIFACT_REGION', os.environ.get('ARTIFACT_OBJECT_REGION', 'us-east-1'))
    ARTIFACT_OBJECT_ACCESS_KEY_ID = os.environ.get(
        'ARTIFACT_ACCESS_KEY_ID',
        os.environ.get('ARTIFACT_OBJECT_ACCESS_KEY_ID', os.environ.get('AWS_ACCESS_KEY_ID', ''))
    )
    ARTIFACT_OBJECT_SECRET_ACCESS_KEY = os.environ.get(
        'ARTIFACT_SECRET_ACCESS_KEY',
        os.environ.get('ARTIFACT_OBJECT_SECRET_ACCESS_KEY', os.environ.get('AWS_SECRET_ACCESS_KEY', ''))
    )
    ARTIFACT_OBJECT_FORCE_PATH_STYLE = os.environ.get('ARTIFACT_OBJECT_FORCE_PATH_STYLE', 'true').lower() == 'true'
    ARTIFACT_OBJECT_CONNECT_TIMEOUT_SECONDS = float(
        os.environ.get('ARTIFACT_OBJECT_CONNECT_TIMEOUT_SECONDS', '5')
    )
    ARTIFACT_OBJECT_READ_TIMEOUT_SECONDS = float(
        os.environ.get('ARTIFACT_OBJECT_READ_TIMEOUT_SECONDS', '10')
    )
    ARTIFACT_SCRATCH_DIR = os.path.abspath(
        os.environ.get('ARTIFACT_SCRATCH_DIR', os.path.join('/tmp', 'agenikpredict-artifacts'))
    )
    ARTIFACT_PROBE_ON_STARTUP = os.environ.get('ARTIFACT_PROBE_ON_STARTUP', 'true').lower() == 'true'
    ALLOWED_EXTENSIONS = {
        'pdf', 'md', 'txt', 'markdown',
        'jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp',
        'mp4', 'mov', 'avi', 'webm', 'mkv',
    }
    IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp'}
    VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'webm', 'mkv'}

    # Text processing config
    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_CHUNK_OVERLAP = 50

    # OASIS simulation config
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(ARTIFACT_ROOT, 'simulations')

    # OASIS platform available actions
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]

    # Report Agent config
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    # Market data config
    TWELVE_DATA_API_KEY = os.environ.get('TWELVE_DATA_API_KEY')
    PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')
    LIVE_EVIDENCE_ENABLED = os.environ.get('LIVE_EVIDENCE_ENABLED', 'true').lower() == 'true'
    LIVE_NEWS_TIMEOUT_SECONDS = float(os.environ.get('LIVE_NEWS_TIMEOUT_SECONDS', '4'))
    LIVE_NEWS_MAX_ITEMS = int(os.environ.get('LIVE_NEWS_MAX_ITEMS', '5'))
    LIVE_EVIDENCE_CACHE_TTL_SECONDS = int(os.environ.get('LIVE_EVIDENCE_CACHE_TTL_SECONDS', '300'))

    # Task store cutover flags
    TASK_STORE_MODE = os.environ.get('TASK_STORE_MODE', 'dual').lower()
    TASK_READ_SOURCE = os.environ.get('TASK_READ_SOURCE', 'fallback').lower()
    TASK_LEASE_SECONDS = int(os.environ.get('TASK_LEASE_SECONDS', '180'))
    TASK_HEARTBEAT_INTERVAL_SECONDS = int(os.environ.get('TASK_HEARTBEAT_INTERVAL_SECONDS', '30'))
    TASK_WORKER_ID = os.environ.get('TASK_WORKER_ID')
    TASK_EXECUTION_MODE = os.environ.get('TASK_EXECUTION_MODE', 'inline').lower()
    TASK_WORKER_POLL_INTERVAL_SECONDS = float(os.environ.get('TASK_WORKER_POLL_INTERVAL_SECONDS', '2'))
    TASK_WORKER_BATCH_SIZE = int(os.environ.get('TASK_WORKER_BATCH_SIZE', '10'))
    WORKER_HEALTHCHECK_URL = os.environ.get('WORKER_HEALTHCHECK_URL', '').strip()
    WORKER_HEALTHCHECK_TIMEOUT_SECONDS = float(
        os.environ.get('WORKER_HEALTHCHECK_TIMEOUT_SECONDS', '2.5')
    )

    @classmethod
    def validate_standby(cls):
        """Validate structural config needed even for standby workers."""
        errors = []
        if cls.SERVICE_ROLE not in cls.VALID_SERVICE_ROLES:
            errors.append("SERVICE_ROLE must be either 'web' or 'worker'")
        if cls.TASK_STORE_MODE not in cls.VALID_TASK_STORE_MODES:
            errors.append(
                "TASK_STORE_MODE must be one of: "
                + ", ".join(cls.VALID_TASK_STORE_MODES)
            )
        if cls.TASK_READ_SOURCE not in cls.VALID_TASK_READ_SOURCES:
            errors.append(
                "TASK_READ_SOURCE must be one of: "
                + ", ".join(cls.VALID_TASK_READ_SOURCES)
            )
        if cls.TASK_EXECUTION_MODE not in cls.VALID_TASK_EXECUTION_MODES:
            errors.append(
                "TASK_EXECUTION_MODE must be one of: "
                + ", ".join(cls.VALID_TASK_EXECUTION_MODES)
            )
        if cls.ARTIFACT_STORAGE_MODE not in cls.VALID_ARTIFACT_STORAGE_MODES:
            errors.append(
                "ARTIFACT_STORAGE_MODE must be one of: "
                + ", ".join(cls.VALID_ARTIFACT_STORAGE_MODES)
            )
        if cls.TASK_EXECUTION_MODE == 'worker' and cls.TASK_STORE_MODE == 'memory':
            errors.append("TASK_STORE_MODE=memory is not supported when TASK_EXECUTION_MODE=worker")
        if cls.TASK_EXECUTION_MODE == 'worker' and cls.TASK_STORE_MODE != 'db':
            errors.append("TASK_STORE_MODE must be 'db' when TASK_EXECUTION_MODE=worker")
        if cls.TASK_EXECUTION_MODE == 'worker' and cls.TASK_READ_SOURCE != 'db':
            errors.append("TASK_READ_SOURCE must be 'db' when TASK_EXECUTION_MODE=worker")
        if cls.TASK_EXECUTION_MODE == 'worker' and cls.ARTIFACT_STORAGE_MODE == 'local':
            errors.append(
                "ARTIFACT_STORAGE_MODE=local is not safe when TASK_EXECUTION_MODE=worker; "
                "use a real shared_fs path for active worker cutover"
            )
        if cls.ARTIFACT_STORAGE_MODE == 'object_store':
            missing_object_store = []
            if not cls.ARTIFACT_OBJECT_BUCKET:
                missing_object_store.append('ARTIFACT_BUCKET')
            if not cls.ARTIFACT_OBJECT_ACCESS_KEY_ID:
                missing_object_store.append('ARTIFACT_ACCESS_KEY_ID')
            if not cls.ARTIFACT_OBJECT_SECRET_ACCESS_KEY:
                missing_object_store.append('ARTIFACT_SECRET_ACCESS_KEY')
            if missing_object_store:
                errors.append(
                    "ARTIFACT_STORAGE_MODE=object_store requires: "
                    + ", ".join(missing_object_store)
                )
        if cls.SERVICE_ROLE == 'worker' and cls.TASK_EXECUTION_MODE != 'worker' and not cls.WORKER_STANDBY:
            errors.append(
                "Worker service requires TASK_EXECUTION_MODE=worker unless WORKER_STANDBY=true is set explicitly"
            )
        if (
            cls.SERVICE_ROLE == 'web'
            and cls.TASK_EXECUTION_MODE == 'worker'
            and not cls.WORKER_HEALTHCHECK_URL
        ):
            errors.append(
                "WORKER_HEALTHCHECK_URL must be set when SERVICE_ROLE=web and TASK_EXECUTION_MODE=worker"
            )
        return errors

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = cls.validate_standby()
        if cls.TASK_EXECUTION_MODE == 'worker' and not cls.DEBUG and not os.environ.get('DATABASE_URL'):
            errors.append("DATABASE_URL must be set for active worker cutover in production")
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY is not configured")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY is not configured")
        if not cls.DEBUG and (
            not cls.JWT_SECRET or
            cls.JWT_SECRET in ('agenikpredict-jwt-secret', 'agenikpredict-secret-key')
        ):
            errors.append("JWT_SECRET must be set to a stable production value")
        return errors
