import os
from dotenv import load_dotenv
import chromadb
import streamlit as st
from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

# ההוראות לבוט נמצאות ב-prompts.py (משותף גם לממשק ה-React)
from prompts import system_prompt, context_prompt, condense_prompt
from family_calendar import CalendarPostprocessor


@st.cache_resource
def load_engine():
    # רץ פעם אחת בלבד, ולא בכל שאלה. משותף לכל המשתמשים, ולכן מחזיר רק את המאגר (בלי זיכרון שיחה)
    load_dotenv()
    # temperature: כמה הבוט יצירתי. בין 0 (מדויק וקבוע) ל-2 (יצירתי מאוד)
    Settings.llm = GoogleGenAI(model="gemini-3.5-flash-lite", api_key=os.getenv("GEMINI_API_KEY"), temperature=1.3)
    Settings.embed_model = GoogleGenAIEmbedding(model_name="gemini-embedding-001", api_key=os.getenv("GEMINI_API_KEY"))
    db = chromadb.PersistentClient(path="./chroma_db")
    chroma_collection = db.get_or_create_collection("family")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    index = VectorStoreIndex.from_vector_store(vector_store)
    return index


st.set_page_config(page_title="הבוט המשפחתי", page_icon="🏠")
# כיוון מימין לשמאל: לכל הדף, ולכל רכיב בתוך בועות הצ'אט (כולל רשימות ותבליטים)
st.markdown("""<style>
.stApp {direction: rtl; text-align: right;}
[data-testid='stChatMessage'] * {direction: rtl; text-align: right;}
[data-testid='stChatMessage'] ul, [data-testid='stChatMessage'] ol {padding-right: 1.5em; padding-left: 0;}
</style>""", unsafe_allow_html=True)
st.title("🏠 הבוט של משפחת רביץ")
st.caption("שאלו אותי על ימי הולדת, תחביבים, קשרים משפחתיים ועוד")

index = load_engine()

# מנוע שיחה עם זיכרון, נפרד לכל סשן (לשונית דפדפן). רענון הדף מתחיל שיחה חדשה
if "chat_engine" not in st.session_state:
    st.session_state.chat_engine = index.as_chat_engine(
        chat_mode="condense_plus_context",
        memory=ChatMemoryBuffer.from_defaults(token_limit=3000),
        similarity_top_k=5,
        system_prompt=system_prompt,
        context_prompt=context_prompt,
        condense_prompt=condense_prompt,
        # מוסיף לכל שאלה את התאריך העברי של היום ואת ימי ההולדת וימי הנישואים ב-7 הימים הקרובים
        node_postprocessors=[CalendarPostprocessor()],
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

if st.sidebar.button("🔄 שיחה חדשה"):
    st.session_state.chat_engine.reset()
    st.session_state.messages = []
    st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("מה תרצו לדעת על המשפחה?")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("מחפש במאגר..."):
            try:
                response = st.session_state.chat_engine.chat(question)
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
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
