"""
Configuration Template - Copy this to config.py and fill in your values
"""

# ============================================
# Azure OpenAI Configuration
# ============================================
# Get these from Azure Portal:
# 1. Go to your Azure OpenAI resource
# 2. Navigate to "Keys and Endpoint"
# 3. Copy the endpoint and one of the keys

AZURE_OPENAI_ENDPOINT = "https://your-resource-name.openai.azure.com/"
AZURE_OPENAI_API_KEY = "your-api-key-here"
AZURE_OPENAI_DEPLOYMENT = "gpt-4"  # Your deployment name (e.g., gpt-4, gpt-35-turbo)
AZURE_OPENAI_API_VERSION = "2024-02-15-preview"

# ============================================
# LLM Parameters
# ============================================
TEMPERATURE = 0.1      # Low temperature for accurate SQL generation
MAX_TOKENS = 4000      # Maximum response length

# ============================================
# Database Configuration
# ============================================
DATABASE_PATH = "database/business_data.db"
DATA_FOLDER = "Data"
SCHEMA_OUTPUT = "schema/schema_context.json"

# ============================================
# Query Settings
# ============================================
ALLOW_LIMIT_CLAUSE = False  # Keep False to return all data
