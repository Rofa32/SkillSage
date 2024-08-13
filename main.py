# -*- coding: utf-8 -*-
"""main.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1kmHGjiGZ4k6i0uv6TGHKfAob935CNfEP
"""

import os
import pandas as pd
import hashlib
import torch
from dotenv import load_dotenv
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.schema import Document
from langchain.llms import OpenAI
from transformers import BitsAndBytesConfig, pipeline
from pinecone import Pinecone
import transformers
import re
from transformers import BitsAndBytesConfig, AutoTokenizer, AutoModelForCausalLM
import PyPDF2
import wandb
import random
from transformers import AutoTokenizer, AutoModelForCausalLM
from langchain.agents import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import ConversationChain
from langchain.llms import OpenAI
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad.openai_tools import (
    format_to_openai_tool_messages,
)
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
from huggingface_hub import hf_hub_download
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import nest_asyncio
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from pyngrok import ngrok
import uvicorn
from fastapi import FastAPI, UploadFile, File

# Load environment variables from .env file
load_dotenv()
'''
if os.getenv("WANDB_MODE") != "disabled":
    # Perform WandB login
    wandb.login(key=os.getenv("WANDB_API_KEY"))

# Initialize WandB session
run = wandb.init(
    project="SkillSage",
    entity="rahafsa2732-king-khalid-university",
    config={
        "model": "meta-llama/LlamaGuard-7b",
        "framework": "PyTorch",
        "max_new_tokens": 750,
        "temperature": 0.01,
    }
)'''

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

# Initialize OpenAI embedding
EMBEDDINGS = OpenAIEmbeddings(api_key=OPENAI_API_KEY)
# Initialize Pinecone
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index("skillsage")


# Initialize the text generation pipeline
nf4_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.bfloat16
)

model_id = "meta-llama/Meta-Llama-3-8B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16)

generation_pipeline = pipeline(
    "text-generation",
    model=model_id,
    model_kwargs={"torch_dtype": torch.bfloat16, "quantization_config": nf4_config},
    device_map="auto",
)

model = "meta-llama/LlamaGuard-7b"

tokenizer = AutoTokenizer.from_pretrained(model)
model = AutoModelForCausalLM.from_pretrained(model, torch_dtype=torch.bfloat16, device_map="auto")


def moderate(chat):

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    input_ids = tokenizer.apply_chat_template(chat, return_tensors="pt").to(device)
    output = model.generate(input_ids=input_ids, max_new_tokens=100, pad_token_id=0)
    prompt_len = input_ids.shape[-1]

    return tokenizer.decode(output[0][prompt_len:], skip_special_tokens=True)

# Query Pinecone index
def query_pinecone_index(query_embeddings: list[float], top_k: int = 2, include_metadata: bool = True) -> dict[str, any]:
    return index.query(vector=query_embeddings, top_k=top_k, include_metadata=include_metadata)

#The generator
def better_query_response(prompt: str) -> str:

    response = generation_pipeline(
        prompt,
        max_new_tokens=750,
        eos_token_id=tokenizer.eos_token_id,
        do_sample=True,
        temperature=0.01,
        return_full_text=False
    )


    return response[0]['generated_text']

# Apply the async loop fix
nest_asyncio.apply()

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    html_content = """
    <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SkillSage</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f4;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .container {
            background-color: #fff;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            text-align: center;
            max-width: 400px;
            width: 100%;
        }
        h1 {
            font-size: 28px;
            margin-bottom: 20px;
            color: #333;
        }
        .button {
            display: block;
            width: calc(100% - 40px);
            padding: 15px;
            margin: 10px auto;
            font-size: 16px;
            color: white;
            background-color: #007bff;
            border: none;
            border-radius: 5px;
            text-align: center;
            text-decoration: none;
            transition: background-color 0.3s;
        }
        .button:hover {
            background-color: #0056b3;
        }
    </style>
</head>
    <body>
        <div class="container">
            <h1>SkillSage</h1>
            <a href="/gap-analyzer" class="button">Skill Gap Analyzer</a>
            <a href="/virtual-interview" class="button">Virtual Interview</a>
            <a href="/cv-feedback" class="button">CV Feedback</a>
        </div>
    </body>
</html>
"""
    return HTMLResponse(content=html_content)

# Function for Skill Gap Analyzer
def extract_missing_skills(job_desc: str, user_skills: str) -> list:
    prompt = f"""
    Given the job description:
    {job_desc}

    And the user's skills:
    {user_skills}

    Identify and list only 2 of the missing skills that the user needs to acquire for the job, write it in this format:

    Missing Skills:
    1- Skill 1
    2- Skill 2

    Only list 2 missing skills, do not list more than 2.
    """

    response = generation_pipeline(
        prompt,
        max_new_tokens=250,
        eos_token_id=tokenizer.eos_token_id,
        do_sample=True,
        temperature=0.01,
        return_full_text=False
    )

    missing_skills = response[0]['generated_text'].strip()
    return missing_skills.split("\n")

def extract_first_two_skills(skills_list: list) -> list:
    extracted_skills = [skill.strip() for skill in skills_list[:2]]
    return extracted_skills

def analyze_skill_gap_and_recommend(job_desc: str, skills: str):
    missing_skills = extract_missing_skills(job_desc, skills)
    if not missing_skills:
        return "No skills gap found. You meet all the required skills for the job."

    first_two_skills = extract_first_two_skills(missing_skills)
    recommendations = []  # Add your own implementation here
    recommendations_text = "\n".join(recommendations)
    template = """
    You are a career advisor.
    your tasks: calculate the matching percentage between the skills provided in {job} and {skills} and provide recommendations based on the following courses: {recommendations}
    only show the output in this format and don't add any more information
    output format:
    Matching Percentage: (in %)
    Skill Gap Analysis:(explain what the candidate lack and have)
    Course Recommendations:
    title:
    URL:
    how this course will benefit you:
    """
    prompt = template.replace('{job}', job_desc).replace('{skills}', skills).replace('{recommendations}', recommendations_text)

    analysis_output = generation_pipeline(
        prompt,
        max_new_tokens=750,
        eos_token_id=tokenizer.eos_token_id,
        do_sample=True,
        temperature=0.01,
        return_full_text=False
    )[0]['generated_text']

    return analysis_output

# Route to serve the main page
@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SkillSage</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }
            .container {
                background-color: #fff;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                text-align: center;
                max-width: 400px;
                width: 100%;
            }
            h1 {
                font-size: 24px;
                margin-bottom: 20px;
                color: #333;
            }
            p {
                margin-bottom: 20px;
                color: #555;
            }
            button {
                background-color: #007bff;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                transition: background-color 0.3s;
            }
            button:hover {
                background-color: #0056b3;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>SkillSage</h1>
            <p>Welcome to SkillSage! Please choose an option below:</p>
            <form action="/gap-analyzer" method="get">
                <button type="submit">Gap Analyzer</button>
            </form>
        </div>
    </body>
    </html>
    """

# Route to serve the Gap Analyzer page
@app.get("/gap-analyzer", response_class=HTMLResponse)
async def gap_analyzer():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Skill Gap Analyzer</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }
            .container {
                background-color: #fff;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                text-align: center;
                max-width: 400px;
                width: 100%;
            }
            h1 {
                font-size: 24px;
                margin-bottom: 20px;
                color: #333;
            }
            p {
                margin-bottom: 20px;
                color: #555;
            }
            input[type="text"] {
                width: calc(100% - 22px);
                padding: 10px;
                margin-bottom: 10px;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            button {
                background-color: #007bff;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                transition: background-color 0.3s;
            }
            button:hover {
                background-color: #0056b3;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Skill Gap Analyzer</h1>
            <p>Enter your job description and skills to analyze the skill gap:</p>
            <form action="/analyze-skill-gap/" method="post">
                <input type="text" name="job_desc" placeholder="Job Description" required><br>
                <input type="text" name="user_skills" placeholder="Your Skills" required><br>
                <button type="submit">Analyze</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.post("/analyze-skill-gap/")
async def analyze_skill_gap(job_desc: str = Form(...), user_skills: str = Form(...)):
    analysis_output = analyze_skill_gap_and_recommend(job_desc, user_skills)

    # Apply formatting to the analysis output
    formatted_output = analysis_output.replace("Matching Percentage:", "<strong>Matching Percentage:</strong><br>")
    formatted_output = formatted_output.replace("Skill Gap Analysis:", "<br><strong>Skill Gap Analysis:</strong><br>")
    formatted_output = formatted_output.replace("Course Recommendations:", "<br><strong>Course Recommendations:</strong><br>")
    formatted_output = formatted_output.replace("title:", "<br><strong>Title:</strong> ")
    formatted_output = formatted_output.replace("URL:", "<br><strong>URL:</strong> <a href='")
    formatted_output = formatted_output.replace("how this course will benefit you:", "' target='_blank'>Link</a><br><strong>How this course will benefit you:</strong><br>")

    return HTMLResponse(content=f"""
    <div style='font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px; background-color: #f9f9f9;'>
        <h2 style="color: #333;">Skill Gap Analysis Result</h2>
        <p>{formatted_output}</p>
    </div>
    """)


# Function to load questions from CSV
def load_questions():
    try:
        file_path = "inter_ques_and_hints.csv"
        df = pd.read_csv(file_path)
        print(df.head())
        return df
    except Exception as e:
        print(f"Error loading questions from CSV: {e}")
        return None





# Function to get a random question and hint
def get_random_question(df):
    try:
        selected_question = df.sample(1).iloc[0]
        question = selected_question['question']
        hint = selected_question['hint']
        return question, hint
    except Exception as e:
        print(f"Error selecting a random question: {e}")
        return None, None

# Function for providing feedback on the answer
def provide_feedback(question, answer):
    template = f"""
    Question: {question}

    User's Answer: {answer}

    Feedback:
    - Clarity: Did the user clearly articulate their thoughts? Were there any ambiguities or unclear parts in their answer?
    - Relevance: Did the user's answer directly address the question? Did they stay on topic?
    - Structure: Was the response well-organized? Did it have a clear beginning, middle, and end?
    - Content: Did the user provide sufficient detail, including examples or evidence to support their answer?
    - Improvement: What areas could the user improve upon? Are there any specific suggestions for enhancing their response?
    """

    try:
        response = generation_pipeline(
            template,
            max_new_tokens=250,
            eos_token_id=tokenizer.eos_token_id,
            do_sample=True,
            temperature=0.7,
            return_full_text=False
        )
        feedback = response[0]['generated_text'].strip()
        return feedback
    except Exception as e:
        print(f"Error generating feedback: {e}")
        return "There was an error generating feedback."

# Load questions from CSV at the start
questions_df = load_questions()
if questions_df is None:
    print("Failed to load questions. Please check the CSV file.")

# Route to serve the main page
@app.get("/virtual-interview", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Virtual Interview</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }}
            .container {{
                background-color: #fff;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                text-align: center;
                max-width: 400px;
                width: 100%;
            }}
            h1 {{
                font-size: 24px;
                margin-bottom: 20px;
                color: #333;
            }}
            p {{
                margin-bottom: 20px;
                color: #555;
            }}
            button {{
                background-color: #007bff;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                transition: background-color 0.3s;
            }}
            button:hover {{
                background-color: #0056b3;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Virtual Interview</h1>
            <p>Welcome to the Virtual Interview tool! Click the button below to start your interview.</p>
            <form action="/start-interview" method="get">
                <button type="submit">Start Interview</button>
            </form>
        </div>
    </body>
    </html>
    """

# Route to start the interview
@app.get("/start-interview", response_class=HTMLResponse)
async def start_interview():
    if questions_df is None:
        return "<h1>Error: Questions not loaded. Please check the server logs.</h1>"

    question, hint = get_random_question(questions_df)
    if question is None:
        return "<h1>Error: Could not retrieve a question. Please check the server logs.</h1>"

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Interview Question</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }}
            .container {{
                background-color: #fff;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                text-align: center;
                max-width: 400px;
                width: 100%;
            }}
            h1 {{
                font-size: 24px;
                margin-bottom: 20px;
                color: #333;
            }}
            p {{
                margin-bottom: 20px;
                color: #555;
            }}
            textarea {{
                width: calc(100% - 22px);
                padding: 10px;
                margin-bottom: 10px;
                border: 1px solid #ccc;
                border-radius: 5px;
            }}
            button {{
                background-color: #007bff;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                transition: background-color 0.3s;
            }}
            button:hover {{
                background-color: #0056b3;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Interview Question</h1>
            <p><strong>Question:</strong> {question}</p>
            <p><strong>Hint:</strong> {hint}</p>
            <form action="/submit-answer" method="post">
                <textarea name="user_answer" placeholder="Type your answer here..." required></textarea><br>
                <input type="hidden" name="question" value="{question}">
                <button type="submit">Submit Answer</button>
            </form>
        </div>
    </body>
    </html>
    """

# Route to submit the answer and get feedback
@app.post("/submit-answer", response_class=HTMLResponse)
async def submit_answer(question: str = Form(...), user_answer: str = Form(...)):
    feedback = provide_feedback(question, user_answer)
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Feedback</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }}
            .container {{
                background-color: #fff;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                text-align: center;
                max-width: 400px;
                width: 100%;
            }}
            h1 {{
                font-size: 24px;
                margin-bottom: 20px;
                color: #333;
            }}
            p {{
                margin-bottom: 20px;
                color: #555;
                text-align: left;
            }}
            button {{
                background-color: #007bff;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                transition: background-color 0.3s;
            }}
            button:hover {{
                background-color: #0056b3;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Feedback</h1>
            <p>{feedback}</p>
            <form action="/start-interview" method="get">
                <button type="submit">Next Question</button>
            </form>
        </div>
    </body>
    </html>
    """

# Function to extract text from a PDF file
def extract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in range(len(pdf_reader.pages)):
        text += pdf_reader.pages[page].extract_text()
    return text

# Function for CV Feedback
def provide_cv_feedback(cv_text: str) -> str:
    prompt = f"""
    You are an experienced HR specialist. Please provide detailed feedback on the following CV, highlighting strengths, weaknesses, and suggestions for improvement:

    {cv_text}
    """

    response = generation_pipeline(
        prompt,
        max_new_tokens=750,
        eos_token_id=tokenizer.eos_token_id,
        do_sample=True,
        temperature=0.7,
        return_full_text=False
    )

    feedback = response[0]['generated_text'].strip()
    return feedback.replace('\n', '<br>').replace('**', '<strong>').replace('*', '<li>')

# Route to serve the main page
@app.get("/cv-feedback", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CV Feedback</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }
            .container {
                background-color: #fff;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                text-align: center;
                max-width: 400px;
                width: 100%;
            }
            h1 {
                font-size: 24px;
                margin-bottom: 20px;
                color: #333;
            }
            p {
                margin-bottom: 20px;
                color: #555;
            }
            button {
                background-color: #007bff;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                transition: background-color 0.3s;
            }
            button:hover {
                background-color: #0056b3;
            }
            input[type="file"] {
                margin-bottom: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>CV Feedback</h1>
            <p>Welcome to the CV Feedback tool! Please upload your CV in PDF format for feedback.</p>
            <form action="/cv-feedback" method="post" enctype="multipart/form-data">
                <input type="file" name="cv_file" accept="application/pdf" required><br>
                <button type="submit">Get Feedback</button>
            </form>
        </div>
    </body>
    </html>
    """

# Route to provide CV feedback
@app.post("/cv-feedback")
async def cv_feedback(cv_file: UploadFile = File(...)):
    pdf_text = extract_text_from_pdf(cv_file.file)
    feedback = provide_cv_feedback(pdf_text)
    return HTMLResponse(content=f"<h2>CV Feedback</h2><p>{feedback}</p>")

# Set up ngrok and start the server
if __name__ == "__main__":
    # Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
    auth_token = "2kEO3Es6iBnqEZztXypmdKU2Hjd_3kRwWv95e6vzFHCCw9tNP"

    # Set the authtoken
    ngrok.set_auth_token(auth_token)

    # Connect to ngrok
    ngrok_tunnel = ngrok.connect(8000)

    # Print the public URL
    print('Public URL:', ngrok_tunnel.public_url)

    # Apply nest_asyncio
    nest_asyncio.apply()

    # Run the uvicorn server
    uvicorn.run(app, port=8000)
