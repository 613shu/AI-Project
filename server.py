import os
import uuid
import base64
import secrets
from dotenv import load_dotenv
import chromadb
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.llms import ChatMessage
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from prompts import system_prompt, context_prompt, condense_prompt
from family_calendar import CalendarPostprocessor

# שרת קטן שמחבר את ממשק ה-React (static/index.html) לאותו מנוע RAG של app.py
load_dotenv()
Settings.llm = GoogleGenAI(model="gemini-3.5-flash", api_key=os.getenv("GEMINI_API_KEY"), temperature=1.3)
Settings.embed_model = GoogleGenAIEmbedding(model_name="gemini-embedding-001", api_key=os.getenv("GEMINI_API_KEY"))
db = chromadb.PersistentClient(path="./chroma_db")
chroma_collection = db.get_or_create_collection("family")
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
index = VectorStoreIndex.from_vector_store(vector_store)

# מנוע שיחה עם זיכרון לכל סשן (לשונית דפדפן). המזהה נוצר בדפדפן
chat_engines = {}


def get_chat_engine(session_id, history):
    if session_id not in chat_engines:
        memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
        # שיחה ישנה מהרשימה בצד (למשל אחרי הפעלה מחדש של השרת): משחזרים את הזיכרון מההיסטוריה ששלח הדפדפן
        for item in history:
            memory.put(ChatMessage(role=item.role, content=item.content))
        chat_engines[session_id] = index.as_chat_engine(
            chat_mode="condense_plus_context",
            memory=memory,
            similarity_top_k=5,
            system_prompt=system_prompt,
            context_prompt=context_prompt,
            condense_prompt=condense_prompt,
            # מוסיף לכל שאלה את התאריך העברי של היום ואת ימי ההולדת וימי הנישואים ב-7 הימים הקרובים
            node_postprocessors=[CalendarPostprocessor()],
        )
    return chat_engines[session_id]


class HistoryItem(BaseModel):
    role: str  # "user" או "assistant"
    content: str


class ChatRequest(BaseModel):
    session_id: str = ""
    message: str
    history: list[HistoryItem] = []


class ResetRequest(BaseModel):
    session_id: str


app = FastAPI()

# סיסמה משפחתית: מוגדרת רק ב-Render (משתנה הסביבה FAMILY_PASSWORD). במחשב המקומי, בלי המשתנה, אין סיסמה
family_password = os.getenv("FAMILY_PASSWORD")


@app.middleware("http")
async def check_password(request: Request, call_next):
    if family_password:
        ok = False
        auth = request.headers.get("authorization", "")
        if auth.startswith("Basic "):
            try:
                password = base64.b64decode(auth[6:]).decode("utf-8").split(":", 1)[1]
                ok = secrets.compare_digest(password.encode("utf-8"), family_password.encode("utf-8"))
            except Exception:
                ok = False
        if not ok:
            return Response("נדרשת סיסמה", status_code=401, headers={"WWW-Authenticate": 'Basic realm="family"'})
    return await call_next(request)


@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.post("/api/chat")
def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    question = request.message.strip()
    try:
        response = get_chat_engine(session_id, request.history).chat(question)
        answer = str(response)
        # המקורות מודפסים רק בטרמינל, כדי שהמשפחה לא תראה אותם
        print("=" * 60)
        print("שאלה:", question)
        for source in response.source_nodes:
            print("score:", source.score, "| source:", source.node.metadata.get("file_name"))
            print(source.node.text[:400])
            print("-" * 30)
        print("תשובה:", answer)
    except Exception as e:
        print("שגיאה:", e)
        if "429" in str(e):
            answer = "הבוט קצת עמוס, נסו שוב בעוד רגע 🙂"
        else:
            answer = "משהו השתבש. נסו שוב."
    return {"session_id": session_id, "answer": answer}


@app.post("/api/reset")
def reset(request: ResetRequest):
    chat_engines.pop(request.session_id, None)
    return {"ok": True}


if __name__ == "__main__":
    # ב-Render הפורט מגיע ממשתנה הסביבה PORT; במחשב המקומי נשאר 8000
    port = int(os.getenv("PORT", 8000))
    print(f"הממשק פתוח בכתובת: http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
