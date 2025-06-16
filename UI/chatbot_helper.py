import os, io, contextlib, logging
from dotenv import load_dotenv
from ibm_watsonx_ai import APIClient, Credentials

# ─── environment ------------------------------------------------------------
load_dotenv()

watsonx_ai_url = os.getenv("WATSONX_AI_URL")
apikey         = os.getenv("WATSONX_API_KEY")
project_id     = os.getenv("WATSONX_PROJECT_ID")
model_id       = os.getenv("WATSONX_MODEL_ID")

if not all([watsonx_ai_url, apikey, project_id, model_id]):
    raise ValueError("Missing required environment variables.")

credentials = Credentials(url=watsonx_ai_url, api_key=apikey)
client      = APIClient(credentials)

params = {
    "decoding_method": "greedy",
    "temperature": 0.7,
    "max_new_tokens": 1000,
}

# ─── build the model, silencing *stdout* and *stderr* ───────────────────────
def _make_model():
    buf = io.StringIO()
    # also damp the IBM SDK logger just in case
    logging.getLogger("ibm_watsonx_ai").setLevel(logging.ERROR)
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        # import *here* so the model-card print happens inside the redirect
        from ibm_watsonx_ai.foundation_models import ModelInference
        return ModelInference(
            model_id=model_id,
            api_client=client,
            project_id=project_id,
            space_id=None,
            verify=False,
            params=params,
        )

model = _make_model()  # global, reused by every call

# ─── public helper ----------------------------------------------------------
def get_response(prompt: str) -> str:
    """
    Send `prompt` to watsonx.ai and return the first non-blank line of the
    reply.  On failure, return a short apology string.
    """
    try:
        lines = model.generate_text(prompt=prompt).split("\n")
        cleaned = [ln for ln in lines if ln.strip()]
        return cleaned[0] if cleaned else ""
    except Exception as exc:
        print(f"[chatbot_helper] Error contacting watsonx.ai: {exc}")
        return "Sorry, I couldn't get a response from the AI service right now."
