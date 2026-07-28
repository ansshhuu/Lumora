"""
Manual test for Embedding Pipeline
Run with: poetry run python tests/test_pipeline_manual.py
"""
from dotenv import load_dotenv
load_dotenv()

from lumora.embeddings.qdrant_store import create_collection
from lumora.embeddings.pipeline import embed_and_store

def test_pipeline():
    # 1. Ensure we have a fresh collection configured for 1024 dimensions
    print("Recreating Qdrant collection...")
    create_collection("test_pipeline_repo", force_recreate=True)
    
    # 2. Mock parsed data structure representing output from your parser
    mock_parsed_items = [
        {
            "type": "function",
            "name": "calculate_gravity",
            "file_path": "physics/mechanics.py",
            "docstring": "Calculates force based on mass.",
            "code": "def calculate_gravity(m):\n    return m * 9.81",
            "start_line": 5,
            "end_line": 7
        },
        {
            "type": "class",
            "name": "Spacecraft",
            "file_path": "physics/vehicles.py",
            "docstring": "Represents an orbital capsule.",
            "code": "class Spacecraft:\n    def __init__(self):\n        self.fuel = 100",
            "start_line": 1,
            "end_line": 4
        }
    ]
    
    # 3. Run the pipeline
    embed_and_store(mock_parsed_items, collection_name="test_pipeline_repo")

if __name__ == "__main__":
    test_pipeline()