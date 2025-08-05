# app.py

import traceback
from console_utils import print_intro, print_shortcuts, handle_feedback, handle_knowledge_storage, conversation_history
from ai_utils import handle_meeting_transcripts, query_search_indices, generate_response, handle_link_knowledge_upload

def handle_user_input():
    print_intro()

    print(f"\n\nLumina: Hi how can I help you today? (Type 'exit' to quit, or help for shortcuts)")

    while True:
        try:
            user_text = input("\nYou: ").strip()
            if user_text.lower() in ["exit", "quit"]:
                print("\nGoodbye!")
                break

            if user_text.lower() == "help":
                print_shortcuts()
                continue

            if handle_meeting_transcripts(user_text=user_text):
                continue

            if handle_link_knowledge_upload(user_text):
                continue

            if handle_knowledge_storage(user_text):
                continue

            search_results = query_search_indices(user_text)
            assistant_reply = generate_response(user_text, search_results, conversation_history)

            conversation_history.append((user_text, assistant_reply))

            print(f"\n\nLumina: {assistant_reply}")
            handle_feedback()

        except Exception as e:
            print(f"\nAn error occurred while processing your message: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    handle_user_input()
