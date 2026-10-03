"""Verify MiniLM loads through the C: junction after the D: move."""
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
v = m.encode("saturday cleanup check")
print(f"MiniLM OK dim={len(v)}", flush=True)
