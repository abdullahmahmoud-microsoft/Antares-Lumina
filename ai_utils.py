# ai_utils.py

import ast
import json
import os
import re
import requests
import hashlib
import time
from config import Config
from datetime import datetime, timezone
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.storage.blob import BlobServiceClient
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError, ResourceModifiedError

config = Config()

session_history = {}

def generate_index_name(url_or_identifier):
    slug = url_or_identifier.replace("https://", "").replace("http://", "").replace("_", "-").lower()
    slug = re.sub(r'[^a-z0-9-]', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    h = hashlib.md5(url_or_identifier.encode()).hexdigest()
    return f"{slug[:60]}-{h[:8]}"

def generate_valid_id(url_or_identifier, doc_index):
    index_name = generate_index_name(url_or_identifier)
    return f"{index_name}-{doc_index}"

def split_text_with_overlap(text, chunk_size=3000, overlap=300):
    """
    Split text into chunks with a specified overlap between chunks.
    """
    chunks = []
    start = 0
    text_length = len(text)
    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap if end < text_length else text_length
    return chunks

def scrape_authenticated_page(url):
    options = webdriver.EdgeOptions()

    local_driver_path = os.path.join(os.getcwd(), "drivers", "msedgedriver.exe")

    if os.path.exists(local_driver_path):
        print(f"Using local Edge WebDriver: {local_driver_path}")
        service = EdgeService(local_driver_path)
    else:
        print("No local Edge WebDriver found. Attempting to download...")
        try:
            service = EdgeService(EdgeChromiumDriverManager().install())
        except Exception as e:
            raise RuntimeError(
                "Could not download Edge WebDriver. "
                "Please ensure internet access or place msedgedriver.exe in the 'drivers' folder."
            ) from e

    driver = webdriver.Edge(options=options, service=service)
    driver.get(url)

    try:
        WebDriverWait(driver, 20).until(lambda d: d.find_element(By.ID, "_content"))
    except Exception as e:
        print("Warning: Main content not detected; proceeding anyway.", e)

    html = driver.page_source
    driver.quit()
    return html

def extract_title(html):
    soup = BeautifulSoup(html, 'html.parser')
    return soup.title.get_text().strip() if soup.title else ""

def extract_main_content(html):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.find('article', id="_content")
    if article:
        for unwanted in article.find_all(['nav', 'header', 'footer', 'aside', 'script', 'style']):
            unwanted.decompose()
        return article.get_text(separator="\n").strip()
    else:
        paragraphs = soup.find_all('p')
        texts = [p.get_text(separator=" ").strip() for p in paragraphs if p.get_text().strip()]
        return "\n".join(texts) if texts else soup.get_text(separator="\n").strip()

def extract_sections_from_article(html):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.find('article', id="_content")
    sections = []
    if article:
        for unwanted in article.find_all(['nav', 'header', 'footer', 'aside', 'script', 'style']):
            unwanted.decompose()
        h2_containers = article.find_all("div", class_=lambda x: x and "h2-container" in x)
        if h2_containers:
            for i, container in enumerate(h2_containers):
                h_heading = container.find(['h1','h2','h3','h4','h5','h6'])
                sec_title = h_heading.get_text(strip=True) if h_heading else f"Section {i+1}"
                if h_heading:
                    h_heading.decompose()
                sec_content = container.get_text(separator="\n", strip=True)
                sections.append({"title": sec_title, "content": sec_content})
        else:
            headings = article.find_all(['h1','h2','h3','h4','h5','h6'])
            if headings:
                for i, heading in enumerate(headings):
                    sec_title = heading.get_text(strip=True)
                    content_parts = []
                    for sibling in heading.find_next_siblings():
                        if sibling.name in ['h1','h2','h3','h4','h5','h6']:
                            break
                        text = sibling.get_text(separator=" ", strip=True)
                        if text:
                            content_parts.append(text)
                    sec_content = "\n".join(content_parts).strip()
                    if not sec_title:
                        sec_title = f"Section {i+1}"
                    sections.append({"title": sec_title, "content": sec_content})
            else:
                full_text = article.get_text(separator="\n").strip()
                sections.append({"title": "Untitled Section", "content": full_text})
    else:
        paragraphs = soup.find_all('p')
        for i, p in enumerate(paragraphs):
            text = p.get_text(separator=" ", strip=True)
            if text:
                sections.append({"title": f"Section {i+1}", "content": text})
        if not sections:
            full_text = soup.get_text(separator="\n").strip()
            sections.append({"title": "Untitled Section", "content": full_text})
    return sections

def generate_qa_pairs(text_chunk, identifier, max_retries=3):
    target_min = max(10, int(len(text_chunk) / 1000) * 2)
    target_max = target_min + 10
    prompt = (
        "Based solely on the **Content** provided below (ignore navigation menus, headers, footers, sidebars, and extraneous UI elements), "
        f"Generate between {target_min} and {target_max} highly relevant question-answer pairs. Ensure coverage of all key topics and sections presented in the content."
        "Each Q&A pair must be specific and accurate. If the text does not provide a clear, definitive answer, skip generating that pair. "
        "Replace any user-specific details (such as IDs, GUIDs, or personal information) with placeholders. "
        "Return your answer in JSON format as a list of objects, each with a 'question' field and an 'answer' field.\n\n"
        "Content:\n" + text_chunk
    )
    headers = {"Content-Type": "application/json", "api-key": config.AZURE_OPENAI_API_KEY}
    data = {
        "model": config.DEPLOYMENT_NAME,
        "messages": [
            {"role": "system", "content": "You are an AI assistant that generates detailed Q&A pairs from provided content."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4000
    }
    attempt = 0
    while attempt < max_retries:
        response = requests.post(config.AZURE_OPENAI_ENDPOINT, headers=headers, json=data)
        if response.status_code == 429:
            wait_time = 21
            try:
                error_msg = response.json().get("error", {}).get("message", "")
                match = re.search(r"after (\d+) seconds", error_msg)
                if match:
                    wait_time = int(match.group(1))
            except Exception:
                pass
            print(f"Rate limit exceeded. Waiting for {wait_time} seconds...")
            time.sleep(wait_time)
            attempt += 1
            continue
        try:
            response_json = response.json()
        except Exception as e:
            print("Error parsing JSON:", e)
            return []
        message_content = response_json.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if message_content.startswith("```json"):
            message_content = message_content[len("```json"):].strip()
        if message_content.endswith("```"):
            message_content = message_content[:-3].strip()
        message_content_clean = re.sub(r'[\x00-\x1F]+', ' ', message_content)
        try:
            qa_pairs = json.loads(message_content_clean)
            if isinstance(qa_pairs, str):
                qa_pairs = json.loads(qa_pairs)
            if isinstance(qa_pairs, list) and all(isinstance(item, dict) for item in qa_pairs):
                return qa_pairs
            else:
                print("Parsed Q&A pairs not in expected format:", qa_pairs)
                return []
        except Exception as e:
            print("Error parsing Q&A pairs:", e)
            try:
                qa_pairs = ast.literal_eval(message_content_clean)
                if isinstance(qa_pairs, list) and all(isinstance(item, dict) for item in qa_pairs):
                    return qa_pairs
                else:
                    print("AST literal_eval parsed Q&A pairs not in expected format:", qa_pairs)
                    return []
            except Exception as e2:
                print("Error parsing Q&A pairs with ast.literal_eval:", e2)
                match = re.search(r'\[.*\]', message_content_clean, re.DOTALL)
                if match:
                    trimmed = match.group(0)
                    try:
                        qa_pairs = json.loads(trimmed)
                        if isinstance(qa_pairs, list) and all(isinstance(item, dict) for item in qa_pairs):
                            return qa_pairs
                    except Exception as e3:
                        print("Error parsing trimmed Q&A pairs:", e3)
                return []
    print("Max retries reached for", identifier)
    return []

def clean_transcript_text(raw_text):
    cleaned = re.sub(r'\d+:\d+:\d+|\d+:\d+', '', raw_text)
    cleaned = re.sub(r'^[A-Za-z][A-Za-z0-9\s]*:', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def enhance_text_via_ai(text, identifier, max_retries=3):
    prompt = (
        "You are an AI assistant that improves text by correcting grammar, punctuation, and filling in missing words based on context, "
        "without altering the original meaning. Remove any side conversations or filler talk such as the friendly banter at the beginning and end of every meeting. Improve the following text and return the result as plain text:\n\n" + text
    )
    headers = {"Content-Type": "application/json", "api-key": config.AZURE_OPENAI_API_KEY}
    data = {
        "model": config.DEPLOYMENT_NAME,
        "messages": [
            {"role": "system", "content": "You are an assistant that cleans up text."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4000
    }
    attempt = 0
    while attempt < max_retries:
        response = requests.post(config.AZURE_OPENAI_ENDPOINT, headers=headers, json=data)
        if response.status_code == 429:
            wait_time = 21
            try:
                error_msg = response.json().get("error", {}).get("message", "")
                match = re.search(r"after (\d+) seconds", error_msg)
                if match:
                    wait_time = int(match.group(1))
            except Exception:
                pass
            print(f"Rate limit exceeded (enhancement). Waiting for {wait_time} seconds...")
            time.sleep(wait_time)
            attempt += 1
            continue
        try:
            response_json = response.json()
            improved_text = response_json.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            return improved_text
        except Exception as e:
            print("Error enhancing text via AI:", e)
            attempt += 1
    print("Max retries reached for text enhancement", identifier)
    return text

def get_indices():
    endpoint = f"https://{config.SEARCH_SERVICE_NAME}.search.windows.net"
    credential = AzureKeyCredential(config.ADMIN_KEY)
    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)
    return [index.name for index in index_client.list_indexes()]

INDICES = get_indices()

def query_search_indices(query):

    INDICES = get_indices()

    endpoint = f"https://{config.SEARCH_SERVICE_NAME}.search.windows.net"
    credential = AzureKeyCredential(config.ADMIN_KEY)
    all_results = []

    for index in INDICES:
        search_client = SearchClient(endpoint=endpoint, index_name=index, credential=credential)
        results = search_client.search(
            search_text=query,
            query_type="semantic",
            semantic_configuration_name="default",
            top=4,
            search_fields=["title", "content"]
        )
        for result in results:
            doc_type = result.get("doc_type", "unknown")
            title = result.get("title", "No Title")
            content = result.get("content", "")
            if content:
                all_results.append(f"[{index}][{doc_type}] {title}: {content}")
    return all_results
 
config = Config()

def generate_response(user_input, context, history):
    headers = {
        "Content-Type": "application/json",
        "api-key": config.AZURE_OPENAI_API_KEY
    }

    history_text = "\n".join([f"{role.capitalize()}: {content}" for role, content in history])
    prompt = (
        "Your name is Lumina. You are a technical knowledge assistant for the Azure App Service Team, led by Bilal Alam.\n"
        "Answer the question below using ONLY the provided context and contextually relevant parts of the provided Conversation History. Do not invent or guess information.\n\n"
        "Follow these formatting rules:\n"
        "Keep specific names of Kusto tables, PowerShell commands, build/version labels, and UI labels as they appear in the context.\n"
        "Generalize or replace tenant names, GUIDs, IDs, email addresses, and anything user/environment-specific with placeholder text.\n"
        "Do not hallucinate acronyms, make up context, or make up something in general if you’re not confident.\n"
        "If you absolutely cannot find the answer from context, respond with: \"I'm sorry, I couldn't find an exact answer based on the available information.\"\n\n"
        f"Context:\n{context}\n\n"
        f"Conversation History:\n{history_text}\n\n"
        f"Question:\n{user_input}"
    )

    messages = [
        {"role": "system", "content": "You are an AI assistant. Use the provided context as your primary guide. Do not invent details if the context is insufficient."},
        {"role": "user", "content": prompt}
    ]

    data = {"model": config.DEPLOYMENT_NAME, "messages": messages, "max_tokens": 1000}
    response = requests.post(config.AZURE_OPENAI_ENDPOINT, headers=headers, json=data)

    try:
        return response.json().get("choices", [{}])[0].get("message", {}).get("content", "No response.")
    except Exception as e:
        print("Error processing OpenAI response:", e)
        return "No response."

def create_or_replace_index(service_name, admin_key, index_name):
    """
    Create an index tailored for transcript and URL content.
    This schema includes documents for:
      - Q&A pairs (doc_type: "qa")
      - Raw content chunks (doc_type: "content")
    The semantic configuration prioritizes the 'title' field (if available) and 'content' field.
    """
    url = f"https://{service_name}.search.windows.net/indexes/{index_name}?api-version={config.API_VERSION}"
    headers = {"Content-Type": "application/json", "api-key": admin_key}
    
    fields = [
        {"name": "id", "type": "Edm.String", "searchable": True, "filterable": True,
         "retrievable": True, "sortable": True, "facetable": True, "key": True, "synonymMaps": []},
        {"name": "doc_type", "type": "Edm.String", "searchable": True, "filterable": True,
         "retrievable": True, "sortable": False, "facetable": False, "key": False, "synonymMaps": []},
        {"name": "page_title", "type": "Edm.String", "searchable": True, "filterable": True,
         "retrievable": True, "sortable": True, "facetable": False, "key": False, "synonymMaps": []},
        {"name": "title", "type": "Edm.String", "searchable": True, "filterable": True,
         "retrievable": True, "sortable": True, "facetable": True, "key": False, "synonymMaps": []},
        {"name": "content", "type": "Edm.String", "searchable": True, "filterable": True,
         "retrievable": True, "sortable": False, "facetable": False, "key": False, "synonymMaps": []},
        {"name": "file_name", "type": "Edm.String", "searchable": True, "filterable": True,
         "retrievable": True, "sortable": True, "facetable": True, "key": False, "synonymMaps": []},
        {"name": "upload_date", "type": "Edm.DateTimeOffset", "searchable": False, "filterable": True,
         "retrievable": True, "sortable": True, "facetable": True, "key": False, "synonymMaps": []}
    ]
    
    semantic_config = {
        "configurations": [
            {"name": "default",
             "prioritizedFields": {
                 "titleField": {"fieldName": "title"},
                 "prioritizedContentFields": [{"fieldName": "content"}],
                 "prioritizedKeywordsFields": []}
             }
        ]
    }
    
    index_definition = {
        "name": index_name,
        "fields": fields,
        "semantic": semantic_config,
        "scoringProfiles": [],
        "suggesters": [],
        "analyzers": [],
        "normalizers": [],
        "tokenizers": [],
        "tokenFilters": [],
        "charFilters": [],
        "similarity": {"@odata.type": "#Microsoft.Azure.Search.BM25Similarity"}
    }
    
    delete_response = requests.delete(url, headers=headers)
    if delete_response.status_code in [200, 204]:
        print(f"Deleted existing index {index_name}")
    else:
        print(f"No existing index {index_name} or delete failed: {delete_response.text}")
    
    create_response = requests.put(url, headers=headers, json=index_definition)
    if create_response.status_code == 201:
        print(f"Created index {index_name} with semantic configuration.")
    else:
        print(f"Failed to create index {index_name}: {create_response.text}")

def upload_documents(service_name, admin_key, index_name, documents):
    endpoint = f"https://{service_name}.search.windows.net"
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential
    credential = AzureKeyCredential(admin_key)
    search_client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)
    results = search_client.upload_documents(documents=documents)
    print(f"Uploaded {len(documents)} documents to index {index_name}")
    print("Upload results:", results)
    return results

def get_existing_ids(service_name, admin_key, index_name):
    from azure.search.documents import SearchClient
    endpoint = f"https://{service_name}.search.windows.net"
    credential = AzureKeyCredential(admin_key)
    search_client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)

    existing_ids = set()
    try:
        results = search_client.search(search_text="*", select=["id"], top=1000)
        for doc in results:
            existing_ids.add(doc["id"])
    except Exception as e:
        print(f"Warning: Could not fetch existing IDs for index '{index_name}':", e)
    return existing_ids

def should_replace_index(index_name):
    answer = input(f"Do you want to replace the existing index '{index_name}'? [y/N]: ").strip().lower()
    return answer == 'y'

def upsert_documents(service_name, admin_key, index_name, documents):
    # if should_replace_index(index_name):
    #     create_or_replace_index(service_name, admin_key, index_name)
    # else:
    print(f"Appending to existing index '{index_name}'...")
    existing_ids = get_existing_ids(service_name, admin_key, index_name)
    before = len(documents)
    documents = [doc for doc in documents if doc["id"] not in existing_ids]
    print(f"Filtered out {before - len(documents)} duplicate document(s).")

    if documents:
        upload_documents(service_name, admin_key, index_name, documents)
    else:
        print(f"No new documents to upload to index '{index_name}'.")

def store_conversation(conversation_id, conversation_history):
    convo_lines = []
    
    for item in conversation_history:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            role, content = item
            convo_lines.append(f"{str(role).capitalize()}: {str(content)}")
        else:
            convo_lines.append(str(item))

    convo_text = "\n".join(convo_lines)
    print("Storing conversation....")

    qa_pairs = generate_qa_pairs(convo_text, f"manual-knowledge-1")
    if not qa_pairs:
        print("No QA pairs were generated.")
        return False

    documents = []
    doc_index = 0
    page_title = f"Conversation from {conversation_id}"
    
    for qa in qa_pairs:
        if not isinstance(qa, dict):
            print("Skipping non-dict QA pair:", qa)
            continue
        question = " ".join(qa.get("question", "").split())
        answer = " ".join(qa.get("answer", "").split())
        if not question or not answer:
            continue
        doc = {
            "id": f"{conversation_id}-{doc_index}",
            "doc_type": "qa",
            "page_title": page_title,
            "title": question,
            "content": f"Question: {question}\nAnswer: {answer}",
            "file_name": f"conversation-{conversation_id}",
            "upload_date":  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        documents.append(doc)
        doc_index += 1

    content_chunks = split_text_with_overlap(convo_text, chunk_size=3000, overlap=300)
    for idx, chunk in enumerate(content_chunks):
        doc = {
            "id": f"{conversation_id}-content-{idx}",
            "doc_type": "content",
            "page_title": page_title,
            "title": f"Conversation from {conversation_id} - Content Part {idx+1}",
            "content": chunk,
            "file_name": f"conversation-{conversation_id}",
            "upload_date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        documents.append(doc)
        doc_index += 1

    index_name = "manual-knowledge-1"
    endpoint = f"https://{config.SEARCH_SERVICE_NAME}.search.windows.net"
    credential = AzureKeyCredential(config.ADMIN_KEY)
    search_client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)

    try:
        search_client.get_index()
        print(f"Index {index_name} exists. Appending to it...")
        upsert_documents(config.SEARCH_SERVICE_NAME, config.ADMIN_KEY, index_name, documents)
    except Exception:
        print(f"Index {index_name} does not exist. Creating a new index...")
        create_or_replace_index(config.SEARCH_SERVICE_NAME, config.ADMIN_KEY, index_name)
        upload_documents(config.SEARCH_SERVICE_NAME, config.ADMIN_KEY, index_name, documents)

    print("Conversation stored to knowledge base.")
    return True

def handle_link_knowledge_upload(user_text):
    file_match = re.search(r'\b(upload|store|save|add|ingest)\b.*\b(file|txt|EngHubLinks\.txt)\b', user_text, re.IGNORECASE)
    if file_match:
        file_path = "EngHubLinks.txt"
        if not os.path.exists(file_path):
            print(f"Could not find the file '{file_path}'. Please make sure it exists.")
            return True

        with open(file_path, "r") as f:
            raw_links = f.readlines()

        urls = [line.strip() for line in raw_links if re.match(r'https?://', line.strip())]
        if not urls:
            print(f"No valid URLs found in '{file_path}'. Please check its contents.")
            return True

        success = add_link_contents_to_index(urls)
        print(f"{len(urls)} links have been stored!" if success else "Failed to store one or more URLs. Please try again.")
        return True

    if re.search(r'\b(upload|store|save|add|ingest)\b.*https?://', user_text, re.IGNORECASE):
        normalized_input = re.sub(r'[,\n]', ' ', user_text)
        urls = re.findall(r'https?://[^\s]+', normalized_input)

        if not urls:
            print("No valid URLs found in the message. Please provide a valid URL.")
            return True

        success = add_link_contents_to_index(urls)
        print("Knowledge has been stored!" if success else "Failed to store URL contents. Please try again.")
        return True

    return False
    
def add_link_contents_to_index(urls):
    qa_documents = []
    content_documents = []
    doc_index = 0

    try:
        for url in urls:
            html = scrape_authenticated_page(url)
            if html:
                page_title = extract_title(html)
                main_content = extract_main_content(html)
                
                qa_pairs = generate_qa_pairs(main_content, url)
                for qa in qa_pairs:
                    if not isinstance(qa, dict):
                        continue
                    question = " ".join(qa.get("question", "").split())
                    answer = " ".join(qa.get("answer", "").split())
                    if not question or not answer:
                        continue
                    doc = {
                        "id": generate_valid_id(url, doc_index),
                        "doc_type": "qa",
                        "page_title": page_title,
                        "title": question,
                        "content": f"Question: {question}\nAnswer: {answer}",
                        "file_name": url,
                        "upload_date": datetime.now(timezone.utc).isoformat(),
                    }
                    qa_documents.append(doc)
                    doc_index += 1

                content_chunks = split_text_with_overlap(main_content, chunk_size=3000, overlap=300)
                for idx, chunk in enumerate(content_chunks):
                    doc = {
                        "id": generate_valid_id(url, f"content-{idx}"),
                        "doc_type": "content",
                        "page_title": page_title,
                        "title": f"{page_title} - Content Part {idx+1}",
                        "content": chunk,
                        "file_name": url,
                        "upload_date": datetime.now(timezone.utc).isoformat(),
                    }
                    content_documents.append(doc)
                    doc_index += 1

                if qa_documents:
                    qa_index_name = generate_index_name("qa")
                    upsert_documents(config.SEARCH_SERVICE_NAME, config.ADMIN_KEY, qa_index_name, qa_documents)

                if content_documents:
                    content_index_name = generate_index_name("content")
                    upsert_documents(config.SEARCH_SERVICE_NAME, config.ADMIN_KEY, content_index_name, content_documents)
    except Exception as e:
        print(f"Error processing URL {url}: {e}")
        return False
    
def handle_storage_command(conversation_id, user_text):
    if re.search(r'store\s+.*(knowledge base|index)', user_text, re.IGNORECASE):
        success = store_conversation(conversation_id, user_text)
        return "Knowledge has been stored!" if success else "Failed to store conversation. Please try again."
    return

def handle_meeting_transcripts(user_text, path="MeetingTranscripts"):
    if user_text.lower() == "upload meeting transcript":
        try:
            if not os.path.isdir(path):
                return f"Folder '{path}' not found."

            transcript_files = [f for f in os.listdir(path) if f.endswith(('.txt', '.vtt'))]
            if not transcript_files:
                return "No transcript files (.txt or .vtt) found."

            for file_name in transcript_files:
                file_path = os.path.join(path, file_name)
                with open(file_path, 'r', encoding='utf-8') as f:
                    raw_transcript = f.read()

                cleaned_text = clean_transcript_text(raw_transcript)
                chunks = split_text_with_overlap(cleaned_text, chunk_size=3000, overlap=300)
                print(f"Transcript '{file_name}' split into {len(chunks)} chunk(s) with overlap.")

                transcript_documents = []
                for idx, chunk in enumerate(chunks):
                    print(f"Enhancing chunk {idx+1}/{len(chunks)} for {file_name} (length: {len(chunk)})...")
                    improved_chunk = enhance_text_via_ai(chunk, f"{file_name}-chunk{idx}")
                    if not improved_chunk:
                        print(f"Warning: Chunk {idx+1} for {file_name} returned empty result.")
                        continue

                    doc = {
                        "id": generate_valid_id(file_name, f"{idx}"),
                        "doc_type": "transcript_chunk",
                        "page_title": file_name,
                        "title": f"{file_name} - Part {idx+1}",
                        "content": improved_chunk,
                        "file_name": file_name,
                        "upload_date": datetime.now(timezone.utc).isoformat(),
                    }
                    transcript_documents.append(doc)

                if transcript_documents:
                    transcript_index_name = generate_index_name("meeting-transcripts")
                    upsert_documents(config.SEARCH_SERVICE_NAME, config.ADMIN_KEY, transcript_index_name, transcript_documents)
                    print(f"Uploaded {len(transcript_documents)} transcript document(s) to index '{transcript_index_name}'.")

            print("All valid meeting transcripts have been processed and stored.")
            return True

        except Exception as e:
            print(f"Error processing meeting transcripts: {e}")
            return False
        
    return False

def upload_feedback_to_container(history=None, written=None, feedbackType=None):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING)
        container_name = config.AZURE_STORAGE_CONTAINER_NAME
        container_client = blob_service_client.get_container_client(container_name)

        if not container_client.exists():
            container_client.create_container()

        timestamp = datetime.now(timezone.utc).isoformat()

        if written:
            feedback_data = {
                "timestamp": timestamp,
                "type": "written",
                "feedback": written,
                "history": history
            }

            blob_name = f"feedback/written-{timestamp}.json"
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.upload_blob(json.dumps(feedback_data, indent=2), overwrite=True)
            print(f"Written feedback saved to {blob_name}")
            return

        elif feedbackType in ("positive", "negative"):
            stats_blob_name = "feedback-reaction-stats.json"
            stats_blob_client = container_client.get_blob_client(stats_blob_name)

            try:
                existing_data = stats_blob_client.download_blob().readall()
                stats = json.loads(existing_data)
                etag = stats_blob_client.get_blob_properties().etag
            except ResourceNotFoundError:
                stats = {"thumbs_up": 0, "thumbs_down": 0}
                etag = None

            max_retries = 3
            retry_delay = 0.3

            for attempt in range(max_retries):
                if feedbackType == "positive":
                    stats["thumbs_up"] += 1
                elif feedbackType == "negative":
                    stats["thumbs_down"] += 1

                stats["last_updated"] = timestamp
                new_data = json.dumps(stats, indent=2)

                try:
                    if etag:
                        stats_blob_client.upload_blob(new_data, overwrite=True, if_match=etag)
                    else:
                        stats_blob_client.upload_blob(new_data, overwrite=True)
                    print(f"Updated feedback stats in {stats_blob_name}")
                    return
                except ResourceModifiedError:
                    if attempt < max_retries - 1:
                        print(f"ETag conflict detected. Retrying... ({attempt+1}/{max_retries})")
                        time.sleep(retry_delay)
                        existing_data = stats_blob_client.download_blob().readall()
                        stats = json.loads(existing_data)
                        etag = stats_blob_client.get_blob_properties().etag
                    else:
                        print("Feedback update failed due to concurrent modification.")
                        return

        else:
            print("No valid feedback provided. Either 'written' or 'feedbackType' is required.")
            return

    except Exception as e:
        print(f"Error uploading feedback: {e}")
        return False