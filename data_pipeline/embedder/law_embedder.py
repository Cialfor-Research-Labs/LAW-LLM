import json
import uuid
import torch
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance

INPUT_FILE = "../chunker/json_output/law_chunks.jsonl"
COLLECTION_NAME = "law_chunks"

BATCH_SIZE = 256


def select_device():
    """Allow user to select GPU"""

    if torch.cuda.is_available():

        gpu_count = torch.cuda.device_count()

        print("\nAvailable NVIDIA GPUs:\n")

        for i in range(gpu_count):
            print(f"[{i}] {torch.cuda.get_device_name(i)}")

        choice = input("\nSelect GPU index (or press Enter for 0): ")

        gpu_id = int(choice) if choice.strip() else 0

        device = f"cuda:{gpu_id}"

    else:
        print("No CUDA GPU detected. Using CPU.")
        device = "cpu"

    print(f"\nUsing device: {device}\n")

    return device


device = select_device()

# Load embedding model on chosen device
model = SentenceTransformer("BAAI/bge-large-en", device=device)

# Connect to Qdrant
client = QdrantClient(path="./qdrant_db")


def create_collection():

    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME not in existing:

        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=1024,
                distance=Distance.COSINE
            )
        )


def load_chunks():

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def embed_and_store():

    batch_texts = []
    batch_payloads = []
    inserted = 0

    for chunk in tqdm(load_chunks(), desc="Processing chunks"):

        batch_texts.append(chunk["text"])
        batch_payloads.append(chunk)

        if len(batch_texts) >= BATCH_SIZE:

            embeddings = model.encode(
                batch_texts,
                batch_size=BATCH_SIZE,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False
            )

            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=emb.tolist(),
                    payload=payload
                )
                for emb, payload in zip(embeddings, batch_payloads)
            ]

            client.upsert(
                collection_name=COLLECTION_NAME,
                points=points
            )

            inserted += len(points)

            batch_texts = []
            batch_payloads = []

    # Final batch
    if batch_texts:

        embeddings = model.encode(
            batch_texts,
            batch_size=BATCH_SIZE,
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=emb.tolist(),
                payload=payload
            )
            for emb, payload in zip(embeddings, batch_payloads)
        ]

        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )

        inserted += len(points)

    print(f"\nTotal vectors inserted: {inserted}")


def main():

    print("Creating vector collection...")
    create_collection()

    print("Starting embedding pipeline...")

    embed_and_store()

    print("Embedding completed!")


if __name__ == "__main__":
    main()