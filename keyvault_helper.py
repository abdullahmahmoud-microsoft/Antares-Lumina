# keyvault_helper.py

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

KEYVAULT_URI = "https://antarestest.vault.azure.net"
credential = DefaultAzureCredential()
kv_client = SecretClient(vault_url=KEYVAULT_URI, credential=credential)

def get_secret(name):
    return kv_client.get_secret(name).value