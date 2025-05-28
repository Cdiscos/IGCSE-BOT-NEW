import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

def evaluate_answer(question_text, user_answer, mark_scheme_text):
    prompt = f"""
You are an IGCSE exam marker. Given the question, a student's answer, and the official mark scheme, assess the answer fairly.
Return only the number of marks awarded and a one-line explanation.

Question:
{question_text}

Student's Answer:
{user_answer}

Mark Scheme:
{mark_scheme_text}

Mark Awarded:"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    return response.choices[0].message['content'].strip()
