"""
Day 4 manual test — run with: poetry run python tests/test_week2_manual.py
Integrates: clone -> parse -> embed -> store (Qdrant)
"""
from pathlib import Path
from dotenv import load_dotenv

# 1. Load your local API keys and environment variables
load_dotenv()

from lumora.ingestion.clone import clone_repo
from lumora.ingestion.walker import walk_files
from lumora.parsing.python_parser import extract_functions_and_classes
from lumora.embeddings.qdrant_store import create_collection
from lumora.embeddings.pipeline import embed_and_store

REPO_URL = "https://github.com/psf/requests"
DEST = "test_repos/requests"

# 2. Clone the repository safely
repo_path = Path(DEST) if Path(DEST).exists() else clone_repo(REPO_URL, DEST)

all_items = []

# 3. Walk and parse python files
print("Scanning and parsing files...")
for file_path in walk_files(str(repo_path)):
    if file_path.suffix == ".py":
        try:
            items = extract_functions_and_classes(str(file_path), repo_root=str(repo_path))
            all_items.extend(items)
        except Exception as e:
            print(f"Skipping corrupt or unparseable file: {file_path} (Error: {e})")

print(f"Total structured code elements found to embed: {len(all_items)}")

# 4. Set up the vector store
print("Recreating Qdrant collection 'requests_repo'...")
# Uses default 1024-dimension size we set up for Voyage AI
create_collection("requests_repo", force_recreate=True)

# 5. Run the full embedding and loading pipeline
print("Ingesting items into vector database...")
embed_and_store(all_items, "requests_repo", batch_size=50,delay_between_batches=0.5)

print("\n--- Pipeline Completed Successfully ---")
print("Done. Check your local Qdrant dashboard (http://localhost:6333/dashboard) for the final point count.")