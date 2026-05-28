import google.generativeai as genai
from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

# model = genai.GenerativeModel("gemini-2.5-flash-lite")

model = genai.GenerativeModel("gemini-3.1-flash-lite")