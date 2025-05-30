from ibm_watsonx_ai import APIClient
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
import os
from dotenv import load_dotenv

load_dotenv()

watsonx_ai_url = os.getenv("WATSONX_AI_URL")
apikey = os.getenv("WATSONX_API_KEY")
project_id = os.getenv("WATSONX_PROJECT_ID")
model_id = os.getenv("WATSONX_MODEL_ID")

if not all([watsonx_ai_url, apikey, project_id, model_id]):
    raise ValueError("Missing required environment variables. Please check your .env file.")

credentials = Credentials(
    url = watsonx_ai_url,
    api_key = apikey,
)

client = APIClient(credentials)
    
params = {
    "decoding_method": "greedy",
    "temperature": 0.7,
    "max_new_tokens": 300
}

model = ModelInference(
    model_id=model_id,
    api_client=client,
    project_id=project_id,
    space_id=None,
    verify=False,
    params=params
)



def get_response(prompt: str) -> str:
    try:
        response = model.generate_text(
            prompt=prompt
        )
        response = response.split("\n")    
        # if the model only helps complete the prompt (not start with capital letter), 
        # then we need to include the next line
        if not response[0][0].isupper():
            return response[1]
        else:
            return response[0]
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return "An error occurred while generating the response."

if __name__ == "__main__":
    prompt = input("Enter your prompt: ")
    templated_prompt = f"Give your answer in 5 sentences. {prompt}"
    response = get_response(templated_prompt)
    print(f"\n\nResponse: \n{response}")