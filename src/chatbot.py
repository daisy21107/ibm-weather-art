from ibm_watsonx_ai import APIClient
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

watsonx_ai_url = os.getenv("WATSONX_AI_URL")
apikey = os.getenv("WATSONX_API_KEY")
project_id = os.getenv("WATSONX_PROJECT_ID")
model_id = os.getenv("WATSONX_MODEL_ID")

params = {
  "decoding_method": "greedy",
  "temperature": 0.8,
  "min_new_tokens": 10,
  "max_new_tokens": 100
}

credentials = Credentials(
    url = watsonx_ai_url,
    api_key = apikey,
)

client = APIClient(credentials)

model = ModelInference(
  model_id=model_id,
  api_client=client,
  params=params,
  project_id=project_id,
  space_id=None,
  verify=False,
)

prompt = "How far is Paris from Bangalore?"
stream_response = model.generate_text_stream(prompt, params)

for chunk in stream_response:
  print(chunk, end='')