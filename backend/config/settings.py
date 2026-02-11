"""
Configuration management for Agentic Travel Dashboard

File Locations:
- .env: project_root/.env
- app_config.yaml: project_root/config/app_config.yaml
- This file: project_root/backend/config/settings.py

Priority: Environment Variables > .env > app_config.yaml > Defaults
"""
import os
import yaml
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class Settings:
    """Application configuration for Agentic Travel Dashboard"""
    
    def __init__(self):
        """Initialize with hardcoded defaults"""
        
        # =============================================================
        # Application
        # =============================================================
        self.app_name: str = "Agentic Travel Dashboard"
        self.environment: str = "development"
        self.debug: bool = True
        self.log_level: str = "INFO"
        
        # =============================================================
        # API Server
        # =============================================================
        self.api_host: str = "0.0.0.0"
        self.api_port: int = 8000
        self.api_reload: bool = True
        self.api_prefix: str = "/api"
        
        # =============================================================
        # CORS
        # =============================================================
        self.cors_origins: list[str] = [
            "http://localhost:3000",
            "http://localhost:5173"
        ]
        
        # =============================================================
        # Supabase
        # =============================================================
        self.supabase_url: Optional[str] = None
        self.supabase_anon_key: Optional[str] = None
        
        # =============================================================
        # OpenAI
        # =============================================================
        self.openai_api_key: Optional[str] = None
        self.llm_model: str = "gpt-4o-mini"
        self.embedding_model: str = "text-embedding-3-small"
        
        # =============================================================
        # Weather API
        # =============================================================
        self.weather_api_key: Optional[str] = None
        self.weather_provider: str = "openweather"
        
        # =============================================================
        # Amadeus API (supports both naming conventions)
        # =============================================================
        self.amadeus_client_id: Optional[str] = None
        self.amadeus_client_secret: Optional[str] = None
        
        # =============================================================
        # Optional External APIs
        # =============================================================
        self.google_places_api_key: Optional[str] = None
        self.xotelo_api_key: Optional[str] = None
        self.ticketmaster_api_key: Optional[str] = None
        
        # =============================================================
        # Autogen Configuration
        # =============================================================
        self.autogen_config_list: list = []
        self.autogen_cache_seed: int = 42
        self.autogen_timeout: int = 120
        
        # =============================================================
        # Agent Settings
        # =============================================================
        self.flight_agent_enabled: bool = True
        self.flight_agent_max_results: int = 10
        
        self.hotel_agent_enabled: bool = True
        
        self.weather_agent_enabled: bool = True
        self.weather_agent_forecast_days: int = 5
        
        self.events_agent_enabled: bool = True
        self.events_agent_max_results: int = 20
        
        self.places_agent_enabled: bool = True
        self.places_agent_max_results: int = 20
        
        self.orchestrator_agent_enabled: bool = True
        self.orchestrator_parallel_execution: bool = True
        
        # =============================================================
        # Caching
        # =============================================================
        self.cache_enabled: bool = True
        self.cache_ttl_seconds: int = 300
        self.cache_flight_ttl: int = 1800
        self.cache_weather_ttl: int = 3600
        self.cache_events_ttl: int = 86400
        
        logger.info("✅ Settings: Initialized with defaults")
    
    # =================================================================
    # LOAD (Entry Point)
    # =================================================================
    
    @classmethod
    def load(cls, config_file: str = None) -> "Settings":
        """
        Load configuration with priority order:
        
        1. Environment Variables (HIGHEST PRIORITY)
        2. .env file (project_root/.env)
        3. app_config.yaml (project_root/config/app_config.yaml)
        4. Hardcoded defaults (fallback)
        
        Args:
            config_file: Path to YAML config file. 
                         Defaults to project_root/config/app_config.yaml
        
        Returns:
            Settings instance
        """
        settings = cls()
        
        # Step 1: Load .env file if it exists
        settings._load_dotenv()
        
        # Step 2: Load defaults from YAML
        if config_file is None:
            config_file = str(settings._get_project_root() / "config" / "app_config.yaml")
        settings._load_from_yaml(config_file)
        
        # Step 3: Override with environment variables (highest priority)
        settings._load_from_environment()
        
        # Step 4: Validate
        settings.validate()
        
        return settings
    
    # =================================================================
    # Path Helpers
    # =================================================================
    
    def _get_project_root(self) -> Path:
        """
        Get project root directory.
        
        This file location: project_root/backend/config/settings.py
        Project root is 2 levels up: config/ -> backend/ -> project_root/
        """
        return Path(__file__).resolve().parent.parent.parent
    
    # =================================================================
    # Step 1: Load .env
    # =================================================================
    
    def _load_dotenv(self):
        """Load .env file from project root"""
        # Look for .env in project root
        env_file = self._get_project_root() / ".env"
        
        if env_file.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_file)
                logger.info(f"✅ Settings: Loaded .env from {env_file}")
            except ImportError:
                logger.warning("⚠️  python-dotenv not installed, skipping .env")
        else:
            logger.warning(f"⚠️  .env file not found at {env_file}")
    
    # =================================================================
    # Step 2: Load from YAML
    # =================================================================
    
    def _load_from_yaml(self, filepath: str):
        """Load configuration from YAML file"""
        config_file = Path(filepath)
        
        if not config_file.exists():
            logger.warning(f"⚠️  Config file not found: {filepath}")
            logger.info("   Using hardcoded defaults and .env values")
            return
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not data:
                logger.warning(f"⚠️  Config file is empty: {filepath}")
                return
            
            # --- Application ---
            if "app" in data:
                app = data["app"]
                self.app_name = app.get("name", self.app_name)
                self.environment = app.get("environment", self.environment)
                self.debug = app.get("debug", self.debug)
                self.log_level = app.get("log_level", self.log_level)
            
            # --- API Server ---
            if "api" in data:
                api = data["api"]
                self.api_host = api.get("host", self.api_host)
                self.api_port = api.get("port", self.api_port)
                self.api_reload = api.get("reload", self.api_reload)
                self.api_prefix = api.get("prefix", self.api_prefix)
            
            # --- CORS ---
            if "cors" in data:
                cors = data["cors"]
                self.cors_origins = cors.get("origins", self.cors_origins)
            
            # --- Supabase ---
            if "supabase" in data:
                supabase = data["supabase"]
                self.supabase_url = supabase.get("url", self.supabase_url)
                self.supabase_anon_key = supabase.get("anon_key", self.supabase_anon_key)
            
            # --- OpenAI ---
            if "openai" in data:
                openai = data["openai"]
                self.openai_api_key = openai.get("api_key", self.openai_api_key)
                self.llm_model = openai.get("llm_model", self.llm_model)
                self.embedding_model = openai.get("embedding_model", self.embedding_model)
            
            # --- Weather ---
            if "weather" in data:
                weather = data["weather"]
                self.weather_api_key = weather.get("api_key", self.weather_api_key)
                self.weather_provider = weather.get("provider", self.weather_provider)
            
            # --- Amadeus ---
            if "amadeus" in data:
                amadeus = data["amadeus"]
                self.amadeus_client_id = amadeus.get("client_id", self.amadeus_client_id)
                self.amadeus_client_secret = amadeus.get("client_secret", self.amadeus_client_secret)
            
            # --- External APIs ---
            if "external_apis" in data:
                external = data["external_apis"]
                self.google_places_api_key = external.get("google_places_key", self.google_places_api_key)
                self.xotelo_api_key = external.get("xotelo_key", self.xotelo_api_key)
                self.ticketmaster_api_key = external.get("ticketmaster_key", self.ticketmaster_api_key)
            
            # --- Autogen ---
            if "autogen" in data:
                autogen = data["autogen"]
                self.autogen_config_list = autogen.get("config_list", self.autogen_config_list)
                self.autogen_cache_seed = autogen.get("cache_seed", self.autogen_cache_seed)
                self.autogen_timeout = autogen.get("timeout", self.autogen_timeout)
            
            # --- Agents ---
            if "agents" in data:
                agents = data["agents"]
                
                if "flight" in agents:
                    flight = agents["flight"]
                    self.flight_agent_enabled = flight.get("enabled", self.flight_agent_enabled)
                    self.flight_agent_max_results = flight.get("max_results", self.flight_agent_max_results)
                
                if "weather" in agents:
                    weather = agents["weather"]
                    self.weather_agent_enabled = weather.get("enabled", self.weather_agent_enabled)
                    self.weather_agent_forecast_days = weather.get("forecast_days", self.weather_agent_forecast_days)
                
                if "events" in agents:
                    events = agents["events"]
                    self.events_agent_enabled = events.get("enabled", self.events_agent_enabled)
                    self.events_agent_max_results = events.get("max_results", self.events_agent_max_results)
                
                if "places" in agents:
                    places = agents["places"]
                    self.places_agent_enabled = places.get("enabled", self.places_agent_enabled)
                    self.places_agent_max_results = places.get("max_results", self.places_agent_max_results)
                
                if "orchestrator" in agents:
                    orchestrator = agents["orchestrator"]
                    self.orchestrator_agent_enabled = orchestrator.get("enabled", self.orchestrator_agent_enabled)
                    self.orchestrator_parallel_execution = orchestrator.get("parallel_execution", self.orchestrator_parallel_execution)
            
            # --- Caching ---
            if "cache" in data:
                cache = data["cache"]
                self.cache_enabled = cache.get("enabled", self.cache_enabled)
                self.cache_ttl_seconds = cache.get("ttl_seconds", self.cache_ttl_seconds)
                self.cache_flight_ttl = cache.get("flight_ttl", self.cache_flight_ttl)
                self.cache_weather_ttl = cache.get("weather_ttl", self.cache_weather_ttl)
                self.cache_events_ttl = cache.get("events_ttl", self.cache_events_ttl)
            
            logger.info(f"✅ Settings: Loaded from {filepath}")
            
        except Exception as e:
            logger.error(f"❌ Error loading YAML config: {e}")
            logger.info("   Using hardcoded defaults and .env values")
    
    # =================================================================
    # Step 3: Load from Environment Variables
    # =================================================================
    
    def _load_from_environment(self):
        """Load configuration from environment variables (highest priority)"""
        
        # --- Supabase ---
        if os.getenv("SUPABASE_URL"):
            self.supabase_url = os.getenv("SUPABASE_URL")
            logger.info("✓ SUPABASE_URL: Set from environment")
        
        if os.getenv("SUPABASE_ANON_KEY"):
            self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
            logger.info("✓ SUPABASE_ANON_KEY: Set from environment")
        
        # --- OpenAI ---
        if os.getenv("OPENAI_API_KEY"):
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
            logger.info("✓ OPENAI_API_KEY: Set from environment")
        
        if os.getenv("LLM_MODEL"):
            self.llm_model = os.getenv("LLM_MODEL")
            logger.info(f"✓ LLM_MODEL: {self.llm_model}")
        
        if os.getenv("EMBEDDING_MODEL"):
            self.embedding_model = os.getenv("EMBEDDING_MODEL")
            logger.info(f"✓ EMBEDDING_MODEL: {self.embedding_model}")
        
        # --- Weather API ---
        if os.getenv("WEATHER_API_KEY"):
            self.weather_api_key = os.getenv("WEATHER_API_KEY")
            logger.info("✓ WEATHER_API_KEY: Set from environment")
        
        # --- Amadeus (support both naming conventions) ---
        if os.getenv("AMADEUS_API_KEY"):
            self.amadeus_client_id = os.getenv("AMADEUS_API_KEY")
            logger.info("✓ AMADEUS_API_KEY: Set from environment")
        
        if os.getenv("AMADEUS_CLIENT_SECRET"):
            self.amadeus_client_secret = os.getenv("AMADEUS_CLIENT_SECRET")
            logger.info("✓ AMADEUS_CLIENT_SECRET: Set from environment")
        
        # --- Google Places API (THIS WAS MISSING!) ---
        if os.getenv("GOOGLE_PLACES_API_KEY"):
            self.google_places_api_key = os.getenv("GOOGLE_PLACES_API_KEY")
            # Mask the key for security (show first 10 chars)
            masked_key = self.google_places_api_key[:10] + "..." if len(self.google_places_api_key) > 10 else "***"
            logger.info(f"✓ GOOGLE_PLACES_API_KEY: Set from environment ({masked_key})")
        else:
            logger.warning("⚠️  GOOGLE_PLACES_API_KEY: NOT set in environment")
        
        # --- Xotelo API ---
        if os.getenv("XOTELO_API_KEY"):
            self.xotelo_api_key = os.getenv("XOTELO_API_KEY")
            logger.info("✓ XOTELO_API_KEY: Set from environment")
        else:
            logger.info("ℹ️  XOTELO_API_KEY: Not set (optional, using free tier)")
        
        # --- Ticketmaster API ---
        if os.getenv("TICKETMASTER_API_KEY"):
            self.ticketmaster_api_key = os.getenv("TICKETMASTER_API_KEY")
            logger.info("✓ TICKETMASTER_API_KEY: Set from environment")
        
        logger.info("✅ Settings: Loaded environment overrides")
    
    # =================================================================
    # Validation
    # =================================================================
    
    def validate(self) -> bool:
        """Validate configuration"""
        warnings = []
        errors = []
        
        # Critical checks (required for core functionality)
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY not set - LLM features will fail")
        
        # Optional but recommended
        if not self.weather_api_key:
            warnings.append("WEATHER_API_KEY not set - weather features will be limited")
        
        if not self.amadeus_client_id or not self.amadeus_client_secret:
            warnings.append("AMADEUS API not set - flight features will be limited")
        
        if not self.google_places_api_key:
            warnings.append("GOOGLE_PLACES_API_KEY not set - hotel search will use Amadeus fallback only")
        
        if not self.xotelo_api_key:
            warnings.append("XOTELO_API_KEY not set - using free tier (limited requests)")
        
        # Print errors
        if errors:
            logger.error("\n❌ Configuration Errors (Critical):")
            for error in errors:
                logger.error(f"   - {error}")
        
        # Print warnings
        if warnings:
            logger.warning("\n⚠️  Configuration Warnings:")
            for warning in warnings:
                logger.warning(f"   - {warning}")
        
        if not errors and not warnings:
            logger.info("✅ Settings: All recommended settings configured")
        elif not errors:
            logger.info("✅ Settings: Core settings configured (see warnings above)")
        
        return len(errors) == 0
    
    # =================================================================
    # Diagnostic Method
    # =================================================================
    
    def print_diagnostics(self):
        """Print detailed diagnostics for troubleshooting"""
        logger.info("\n" + "=" * 80)
        logger.info("🔍 SETTINGS DIAGNOSTICS")
        logger.info("=" * 80)
        
        def mask_key(key: Optional[str]) -> str:
            if not key:
                return "❌ NOT SET"
            if len(key) < 10:
                return "✅ SET (too short to mask)"
            return f"✅ SET ({key[:10]}...)"
        
        logger.info("\n📋 API Keys Status:")
        logger.info(f"   OpenAI API Key: {mask_key(self.openai_api_key)}")
        logger.info(f"   Google Places API Key: {mask_key(self.google_places_api_key)}")
        logger.info(f"   Xotelo API Key: {mask_key(self.xotelo_api_key)}")
        logger.info(f"   Amadeus Client ID: {mask_key(self.amadeus_client_id)}")
        logger.info(f"   Amadeus Client Secret: {mask_key(self.amadeus_client_secret)}")
        logger.info(f"   Weather API Key: {mask_key(self.weather_api_key)}")
        logger.info(f"   Ticketmaster API Key: {mask_key(self.ticketmaster_api_key)}")
        
        logger.info("\n📋 LLM Configuration:")
        logger.info(f"   Model: {self.llm_model}")
        logger.info(f"   Embedding Model: {self.embedding_model}")
        
        logger.info("\n📋 Environment:")
        logger.info(f"   Environment: {self.environment}")
        logger.info(f"   Debug Mode: {self.debug}")
        logger.info(f"   Log Level: {self.log_level}")
        
        logger.info("\n" + "=" * 80)
    
    # =================================================================
    # Properties
    # =================================================================
    
    @property
    def WEATHER_API_KEY(self) -> Optional[str]:
        return self.weather_api_key
    
    @property
    def OPENAI_API_KEY(self) -> Optional[str]:
        return self.openai_api_key
    
    @property
    def SUPABASE_URL(self) -> Optional[str]:
        return self.supabase_url
    
    @property
    def SUPABASE_ANON_KEY(self) -> Optional[str]:
        return self.supabase_anon_key
    
    @property
    def LLM_MODEL(self) -> str:
        return self.llm_model
    
    @property
    def EMBEDDING_MODEL(self) -> str:
        return self.embedding_model
    
    @property
    def GOOGLE_PLACES_API_KEY(self) -> Optional[str]:
        return self.google_places_api_key
    
    @property
    def XOTELO_API_KEY(self) -> Optional[str]:
        return self.xotelo_api_key
    
    @property
    def TICKETMASTER_API_KEY(self) -> Optional[str]:
        return self.ticketmaster_api_key
    
    @property
    def AUTOGEN_CONFIG_LIST(self) -> list:
        return self.autogen_config_list
    
    @property
    def API_HOST(self) -> str:
        return self.api_host
    
    @property
    def API_PORT(self) -> int:
        return self.api_port
    
    @property
    def API_RELOAD(self) -> bool:
        return self.api_reload
    
    @property
    def CORS_ORIGINS(self) -> list[str]:
        return self.cors_origins


# =================================================================
# Global settings instance
# =================================================================
settings = Settings.load()

# Print diagnostics on startup (helps with debugging)
if __name__ != "__main__":
    settings.print_diagnostics()