#! /bin/bash

conda create -n iwa python=3.11

conda activate iwa

pip install -r requirements.txt

# create empty .env file
if [ ! -f .env ]; then
    echo "Creating empty .env file"
    touch .env

    echo "WATSONX_AI_URL=" >> .env
    echo "WATSONX_API_KEY=" >> .env
    echo "WATSONX_PROJECT_ID=" >> .env
    echo "WATSONX_MODEL_ID=" >> .env
    echo "OPENWEATHER_API_KEY=" >> .env
    echo "GUARDIAN_API_KEY=" >> .env
    echo "Completed creating .env file"
fi

# create empty data/ directory
mkdir -p data/

echo "Setup complete"
