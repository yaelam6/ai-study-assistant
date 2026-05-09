import requests


def ask_ai(text, task):
    prompt = f"""
You are an AI study assistant.
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

    if response.status_code != 200:
        return f"Error: {response.text}"

    return response.json()["response"]


def main():
    print("AI Study Assistant - Local Llama3")
    print("1. Summarize text")
    print("2. Create study questions")
    print("3. Explain like I'm a beginner")

    choice = input("Choose an option: ")

    print("\nPaste your text:")
    text = input("> ")

    if choice == "1":
        task = "Summarize the text in clear bullet points."
    elif choice == "2":
        task = "Create 5 study questions with answers."
    elif choice == "3":
        task = "Explain the text in simple beginner-friendly language."
    else:
        print("Invalid choice")
        return

    print("\nThinking...")

    result = ask_ai(text, task)

    print("\n--- AI RESULT ---")
    print(result)

    with open("result.txt", "w", encoding="utf-8") as file:
        file.write(result)

    print("\nSaved result to result.txt")


if __name__ == "__main__":
    main()