from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
import numpy as np

model = SentenceTransformer("all-MiniLM-L6-v2")

def get_embedding(text: str) -> list:
    return model.encode(text).tolist()

def calculate_match_score(candidate_embedding: list, job_embedding: list) -> float:
    a = np.array(candidate_embedding).reshape(1, -1)
    b = np.array(job_embedding).reshape(1, -1)
    score = cosine_similarity(a, b)[0][0]
    return round(float(score) * 100, 2)

def cluster_candidates(embeddings: list, n_clusters: int = 5):
    if len(embeddings) < n_clusters:
        n_clusters = len(embeddings)
    matrix = np.array(embeddings)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
    labels = kmeans.fit_predict(matrix)
    return labels.tolist()