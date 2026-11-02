# ingest.py
# סקריפט הטעינה (Offline / Ingestion):
# Documents ← Nodes ← Embeddings ← שמירה ב-ChromaDB
# מריצים אותו בכל פעם שמשנים את הקבצים בתיקייה data.

import os
from dotenv import load_dotenv

import chromadb
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, Settings, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

# טעינת המפתח מקובץ .env
load_dotenv()

# הגדרת מודל ה-Embeddings (בקורס: OpenAIEmbedding, בפרויקט: Gemini)
Settings.embed_model = GoogleGenAIEmbedding(
    model_name="gemini-embedding-001",
    api_key=os.getenv("GEMINI_API_KEY"),
)

# טעינה וחלוקה למקטעים
docs = SimpleDirectoryReader("./data").load_data()
splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
nodes = splitter.get_nodes_from_documents(docs)
print("Documents:", len(docs), "Nodes:", len(nodes))

# חיבור ל-ChromaDB
db = chromadb.PersistentClient(path="./chroma_db")

# מחיקת ה-collection הקיים (אם יש), כדי שלא יישארו מקטעים ישנים או כפולים
try:
    db.delete_collection("family")
    print("ה-collection הישן נמחק")
except Exception:
    print("לא היה collection קודם")

chroma_collection = db.get_or_create_collection("family")
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)

# יצירת ה-Embeddings ושמירתם ב-ChromaDB
index = VectorStoreIndex(nodes, storage_context=storage_context)
print("נשמרו במאגר:", chroma_collection.count(), "מקטעים")
