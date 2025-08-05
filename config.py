# config.py

from keyvault_helper import get_secret

class Config:
    SEARCH_SERVICE_NAME = "antares-genie-search"
    ADMIN_KEY = get_secret("Antares-Lumina-SearchKey")
    AZURE_STORAGE_CONNECTION_STRING = get_secret("Antares-Lumina-AzureStorageConnString")
    DEPLOYMENT_NAME = "gpt-4o"
    API_VERSION = "2021-04-30-Preview"
    AZURE_STORAGE_CONNECTION_STRING = get_secret("Antares-Lumina-AzureStorageConnString")
    AZURE_OPENAI_ENDPOINT = "https://deployment-agent.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview"
    AZURE_OPENAI_API_KEY = get_secret("Antares-Lumina-OpenAIKey")
    AZURE_STORAGE_CONTAINER_NAME = "feedback-logs"
