import json
import os

from pymongo import MongoClient
from pymongo.operations import SearchIndexModel


COLLECTION = "digits_demo_memory_minilm"
INDEX = "digits_minilm_evidence_v1"
EMBEDDING = "sentence-transformers/all-MiniLM-L6-v2"
QUERY = (
    "What past image classification experiments tested ways to improve "
    "accuracy when training a deep network without adding parameters?"
)


def mongo_client():
    return MongoClient(os.environ["MEMORY_ATLAS_URI"], serverSelectionTimeoutMS=8000)


def embed(value):
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBEDDING, device="cpu")
    return model.encode(value, normalize_embeddings=True).tolist()


def seed_memory(seed_path):
    evidence = json.loads(seed_path.read_text(encoding="utf-8-sig"))
    fields = {"id", "source", "dataset", "finding"}
    if (
        not isinstance(evidence, dict)
        or evidence.keys() != fields
        or any(not isinstance(value, str) or not value.strip() for value in evidence.values())
    ):
        raise ValueError("Seed JSON must contain nonempty id, source, dataset, and finding strings.")
    vector = embed(evidence["dataset"] + ". " + evidence["finding"])

    with mongo_client() as mongo:
        collection = mongo[os.environ["MEMORY_ATLAS_DB"]][COLLECTION]
        collection.update_one(
            {"_id": evidence["id"]},
            {"$setOnInsert": {"evidence": evidence, "embedding": vector}},
            upsert=True,
        )
        indexes = list(collection.list_search_indexes(INDEX))
        if not indexes:
            collection.create_search_index(SearchIndexModel(
                name=INDEX,
                type="vectorSearch",
                definition={"fields": [{
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": 384,
                    "similarity": "cosine",
                }]},
            ))
    return {"index": INDEX, "note": "Wait for the index to be queryable."}


def retrieve():
    vector = embed(QUERY)
    with mongo_client() as mongo:
        collection = mongo[os.environ["MEMORY_ATLAS_DB"]][COLLECTION]
        if not any(index.get("queryable") for index in collection.list_search_indexes(INDEX)):
            raise RuntimeError("Atlas index is not queryable yet. Wait and retry memory on.")
        hits = collection.aggregate([
            {"$vectorSearch": {
                "index": INDEX,
                "path": "embedding",
                "queryVector": vector,
                "numCandidates": 60,
                "limit": 3,
            }},
            {"$project": {"_id": 1}},
        ])
        records = []
        for hit in hits:
            record = collection.find_one({"_id": hit["_id"]}, {"evidence": 1})
            if record:
                records.append(record["evidence"])
    if not records:
        raise RuntimeError("Atlas returned no experiment evidence. Check the seed and index.")
    return records
