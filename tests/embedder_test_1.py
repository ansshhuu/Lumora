"""
Manual test for Voyage AI Embeddings
Run with: poetry run python tests/test_embedder_manual.py
"""
import os
from dotenv import load_dotenv

# 1. Load your .env file containing VOYAGE_API_KEY
load_dotenv()

# 2. Import your refined embedder module
from lumora.embeddings.embedder import embed_batch

def test_manual():
    print("Testing Voyage AI Embeddings Connection...")
    test_text = "def foo(): pass"
    
    try:
        # Generate the embedding
        vectors = embed_batch([test_text], input_type="document")
        
        # Verify shape and type
        print("\n--- TEST SUCCESSFUL ---")
        print(f"Number of embeddings returned: {len(vectors)}")
        print(f"Embedding dimensions (expected 1024): {len(vectors[0])}")
        print(f"Data type: {type(vectors[0][0])}")
        print(f"Sample values (first 5 elements): {vectors[0][:5]}")
        
    except Exception as e:
        print("\n--- TEST FAILED ---")
        print(f"Error encountered: {e}")
        if not os.getenv("VOYAGE_API_KEY"):
            print("Tip: It looks like VOYAGE_API_KEY is not set in your environment.")

if __name__ == "__main__":
    test_manual()