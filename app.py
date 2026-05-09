import streamlit as st
import requests
from pypdf import PdfReader


st.set_page_config(page_title="AI Study Assistant", page_icon="📚")

st.title("📚 AI Study Assistant")
st.write("A local GenAI app powered by Llama3 and Ollama")

task = st.selectbox(
    "Choose a task:",
    [
        "Summarize text",
        "Create study questions",
        "Explain like I'm a beginner"
    ]
)

uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])
manual_text = st.text_area("Or paste your study text here:", height=200)


def extract_text_from_pdf(file):
    reader = PdfReader(file)
    text = ""

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    return text


def ask_ai(text, task):
    prompt = f"""
You are an AI study assistant.
Answer clearly and helpfully.
You can answer in Hebrew or English.

Task: {task}

Text:
{text}
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        }
    )

    return response.json()["response"]


if st.button("Generate"):
    if uploaded_file is not None:
        text = extract_text_from_pdf(uploaded_file)
    else:
        text = manual_text

    if text.strip() == "":
        st.warning("Please upload a PDF or enter text first.")
    else:
        with st.spinner("Thinking..."):
            result = ask_ai(text, task)

        st.subheader("AI Result")
        st.write(result)

        st.download_button(
            "Download result",
            result,
            file_name="study_result.txt"
        )