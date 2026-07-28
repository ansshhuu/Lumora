"""
Day 5 Multi-Query Test — run with: poetry run python tests/test_search_multi.py
"""
from dotenv import load_dotenv
load_dotenv()

from lumora.embeddings.search import search_code

# The 4 new semantic test questions
test_queries = [
    "How are SSL certificates verified or configured?",
    "Where does the code handle basic authentication or credentials?",
    "How are cookies prepared, set, or merged in a request session?",
    "Where are custom headers or default user-agent strings defined?"
]

def run_multi_test():
    for idx, query in enumerate(test_queries, start=2): # Starting at #2 since "timeouts" was #1
        print("=" * 60)
        print(f"🔍 TEST QUERY #{idx}: '{query}'")
        print("=" * 60)
        
        results = search_code(query, collection_name="requests_repo", limit=1)
        
        if not results:
            print("No matches found.\n")
            continue
            
        res = results[0]
        payload = res['payload']
        print(f"Match Found! (Semantic Score: {res['score']:.4f})")
        print(f"Location: {payload['file_path']}")
        print(f"Structure: {payload['type']} | Name: {payload['name']}")
        if payload.get('docstring'):
            print(f"Docstring: {payload['docstring'].strip()}")
        print("-" * 40)
        
        # Print the first 8 lines of the matching code
        code_lines = payload['code'].split('\n')[:8]
        print("\n".join(code_lines))
        print("...\n")

if __name__ == "__main__":
    run_multi_test()