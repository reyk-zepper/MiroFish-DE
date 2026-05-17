"""
配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os

try:
    from dotenv import load_dotenv
except ImportError:  # Allows lightweight config tests before dependencies are installed.
    def load_dotenv(*args, **kwargs):
        return False

# 加载项目根目录的 .env 文件
# 路径: MiroFish/.env (相对于 backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # 如果根目录没有 .env，尝试加载环境变量（用于生产环境）
    load_dotenv(override=True)


class Config:
    """Flask配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON配置 - 禁用ASCII转义，让中文直接显示（而不是 \uXXXX 格式）
    JSON_AS_ASCII = False
    
    # LLM configuration (OpenAI-compatible API format)
    # Backwards compatible with the original LLM_* variables, plus provider profiles
    # for local inference, OpenAI API, OpenRouter, and custom endpoints.
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'custom').lower()

    _PROVIDER_CONFIGS = {
        'local': {
            'api_key': os.environ.get('LOCAL_LLM_API_KEY', os.environ.get('LLM_API_KEY', 'dummy')),
            'base_url': os.environ.get('LOCAL_LLM_BASE_URL', os.environ.get('LLM_BASE_URL', 'http://localhost:11434/v1')),
            'model': os.environ.get('LOCAL_LLM_MODEL', os.environ.get('LLM_MODEL_NAME', 'qwen2.5:7b-instruct')),
        },
        'openai': {
            'api_key': os.environ.get('OPENAI_API_KEY', os.environ.get('LLM_API_KEY')),
            'base_url': os.environ.get('OPENAI_BASE_URL', os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')),
            'model': os.environ.get('OPENAI_MODEL', os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')),
        },
        'openrouter': {
            'api_key': os.environ.get('OPENROUTER_API_KEY', os.environ.get('LLM_API_KEY')),
            'base_url': os.environ.get('OPENROUTER_BASE_URL', os.environ.get('LLM_BASE_URL', 'https://openrouter.ai/api/v1')),
            'model': os.environ.get('OPENROUTER_MODEL', os.environ.get('LLM_MODEL_NAME', 'openai/gpt-4o-mini')),
        },
        'custom': {
            'api_key': os.environ.get('LLM_API_KEY'),
            'base_url': os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1'),
            'model': os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini'),
        },
    }

    _ACTIVE_LLM_CONFIG = _PROVIDER_CONFIGS.get(LLM_PROVIDER, _PROVIDER_CONFIGS['custom'])
    LLM_API_KEY = _ACTIVE_LLM_CONFIG['api_key']
    LLM_BASE_URL = _ACTIVE_LLM_CONFIG['base_url']
    LLM_MODEL_NAME = _ACTIVE_LLM_CONFIG['model']
    
    # Graph memory provider configuration
    # MiroFish-DE defaults to a local Neo4j/Graphiti-compatible provider.
    # zep_cloud remains available as a legacy upstream-compatible provider.
    GRAPH_PROVIDER = os.environ.get('GRAPH_PROVIDER', 'graphiti_neo4j').lower()
    SUPPORTED_GRAPH_PROVIDERS = {'zep_cloud', 'graphiti_neo4j'}

    # Zep配置
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')

    # Local graph provider / Neo4j configuration
    NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', 'change-me')
    NEO4J_DATABASE = os.environ.get('NEO4J_DATABASE', 'neo4j')
    EMBEDDING_PROVIDER = os.environ.get('EMBEDDING_PROVIDER', 'local').lower()
    LOCAL_EMBEDDING_MODEL = os.environ.get('LOCAL_EMBEDDING_MODEL', 'nomic-embed-text')
    LOCAL_EMBEDDING_BASE_URL = os.environ.get('LOCAL_EMBEDDING_BASE_URL', os.environ.get('LOCAL_LLM_BASE_URL', 'http://localhost:11434/v1'))
    LOCAL_EMBEDDING_API_KEY = os.environ.get('LOCAL_EMBEDDING_API_KEY', 'ollama')
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # 文本处理配置
    DEFAULT_CHUNK_SIZE = 500  # 默认切块大小
    DEFAULT_CHUNK_OVERLAP = 50  # 默认重叠大小
    
    # OASIS模拟配置
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS平台可用动作配置
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent配置
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    @classmethod
    def validate(cls):
        """验证必要配置"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append(f"LLM API key is not configured for provider '{cls.LLM_PROVIDER}'")
        if cls.LLM_PROVIDER not in cls._PROVIDER_CONFIGS:
            errors.append(f"Unknown LLM_PROVIDER '{cls.LLM_PROVIDER}'. Use one of: local, openai, openrouter, custom")
        if cls.GRAPH_PROVIDER not in cls.SUPPORTED_GRAPH_PROVIDERS:
            errors.append(f"Unknown GRAPH_PROVIDER '{cls.GRAPH_PROVIDER}'. Use one of: zep_cloud, graphiti_neo4j")
        if cls.GRAPH_PROVIDER == 'zep_cloud' and not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY is not configured")
        if cls.GRAPH_PROVIDER == 'graphiti_neo4j':
            if not cls.NEO4J_URI:
                errors.append("NEO4J_URI is not configured")
            if not cls.NEO4J_USER:
                errors.append("NEO4J_USER is not configured")
            if not cls.NEO4J_PASSWORD:
                errors.append("NEO4J_PASSWORD is not configured")
            if not cls.NEO4J_DATABASE:
                errors.append("NEO4J_DATABASE is not configured")
        return errors

