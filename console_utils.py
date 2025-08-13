# console_utils.py

import re
import uuid
from ai_utils import upload_feedback_to_container, store_conversation
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

conversation_id = f"console-session-{uuid.uuid4()}"
conversation_history = []

def print_feedback_options():
    print("\nHow was the response?")
    print("1. 👍 (positive)")
    print("2. 👎 (negative)")
    print("3. Submit written feedback")
    print("4. Skip feedback")

def handle_feedback():
    print_feedback_options()
    choice = input("Choose an option: ").strip()

    if choice == "1":
        upload_feedback_to_container(history=conversation_history, feedbackType="positive")
        print("\nThank you for your positive feedback!")

    elif choice == "2":
        upload_feedback_to_container(history=conversation_history, feedbackType="negative")
        print("\nThank you for your feedback!")
        written = input("Optional: Add written feedback: ").strip()
        if written:
            upload_feedback_to_container(history=conversation_history, written=written)
            print("\nWritten feedback received.")

    elif choice == "3":
        written = input("Write your feedback: ").strip()
        if written:
            upload_feedback_to_container(history=conversation_history, written=written)
            print("\nThank you for your written feedback!")

    else:
        print("\nSkipping feedback.")

    return True

def print_intro():
    print("""
        Welcome to Antares Lumina!

        💬 What you can do:
        - Ask me anything Antares! If I don't know the answer, please feed it to me so I can learn for next time or the next person. 
        - Paste eng hub documentation links and Lumina will read, scrape, and store all the knowledge within the contents of the link.
            - You can also paste links to EngHubLinks.txt and ask me to process them all by saying "upload links from EngHubLinks.txt".
        - Type 'store/upload/save this in the knowledge base' to pull up a prompt to enter knowledge or context. Type 'END' on a new line when you're finished.
        - Type 'upload meeting transcript' to process all .txt files in the local MeetingTranscripts folder.
        - Type 'feedback' to provide feedback on Lumina's last response. We use this to improve the system!
          
        To display my capabilities at any time, type 'help'.

        - Lumina searches across indexed documentation, release notes, and transcripts.
        - Context-aware memory and input from dozens of users daily helps it refine answers over time.
        - Please make sure to provide feedback on my responses so I can improve!
        - Note: Lumina is only as good as your data. Please make sure your data is clean, clear, and useful, so that you and others can benefit. 
        

        In this dogfood release version, I will be like a new engineer on your team, learning from your feedback and interactions. So please be patient with me :)

        I'm constantly getting updates! Make sure to sync with latest changes from git
        
        For any issues or feedback, please reach out to aaboumahmoud & shenry
    """)

def print_shortcuts():
    print("\n\nShortcuts:")
    print("1. Type 'upload meeting transcript' to process all files in the local MeetingTranscripts folder.")
    print("2. Type 'store/upload/save this in the knowledge base' to pull up a prompt to enter knowledge or context. Type 'END' on a new line when you're finished.")
    print("3. Type 'feedback' to provide feedback on Lumina's last response.")
    print("4. Type 'exit' or 'quit' to end the session.")


def handle_knowledge_storage(user_text):
    if re.search(r'\b(upload|store|save|add|ingest)\b.*(note|knowledge|context|info|information|this)', user_text, re.IGNORECASE):
        print("\nEnter your knowledge/note below.")
        print("Use arrow keys to navigate and edit.")
        print("Type 'END' on a new line when finished.\n")
        
        session = PromptSession(history=InMemoryHistory())
        lines = []
        
        while True:
            try:
                line = session.prompt("> ")
                if line.strip().upper() == "END":
                    break
                lines.append(line)
            except KeyboardInterrupt:
                print("\nCancelled input.")
                return True
        
        if lines:  # Only store if there's actual content
            knowledge = "\n".join(lines)
            store_conversation(conversation_id, knowledge)
            print(f"\nStored!\n")
        return True
    return False