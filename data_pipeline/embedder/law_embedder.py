import json
import uuid
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance

INPUT_FILE = "../chunker/json_output/law_chunks.jsonl"

COLLECTION_NAME = "law_chunks"

BATCH_SIZE = 64
MAX_THREADS = 6

# Load embedding model
model = SentenceTransformer("BAAI/bge-large-en")

# Connect to Qdrant
client = QdrantClient(path="./qdrant_db")


def create_collection():
    """Create Qdrant collection if not exists"""

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
    """Stream JSONL chunks"""

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def store_batch(texts, payloads):
    """Embed and insert batch into Qdrant"""

    embeddings = model.encode(
        texts,
        normalize_embeddings=True
    )

    points = []

    for emb, payload in zip(embeddings, payloads):

        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=emb.tolist(),
                payload=payload
            )
        )

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points
    )

    return len(points)


def embed_and_store():

    batches = []
    batch_texts = []
    batch_payloads = []

    # Prepare batches
    for chunk in load_chunks():

        batch_texts.append(chunk["text"])
        batch_payloads.append(chunk)

        if len(batch_texts) == BATCH_SIZE:

            batches.append((batch_texts, batch_payloads))
            batch_texts = []
            batch_payloads = []

    if batch_texts:
        batches.append((batch_texts, batch_payloads))

    print(f"Total batches: {len(batches)}")

    inserted = 0

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:

        futures = [
            executor.submit(store_batch, texts, payloads)
            for texts, payloads in batches
        ]

        for future in tqdm(as_completed(futures), total=len(futures)):
            inserted += future.result()

    print(f"Total vectors inserted: {inserted}")


def main():

    print("Creating vector collection...")
    create_collection()

    print("Starting embedding pipeline...")

    embed_and_store()

    print("Embedding completed!")


if __name__ == "__main__":
    main()