# Web Summarizer
To build:
docker build -t <name> path_to_app_folder


To run container:
docker run -v path_to_config2.yaml:/root/.metagpt/config2.yaml -p 7860:7860 <name>

Navigate to localhost:7860 in your browser and you can attempt a prompt injection by asking the agent to:

"Summarize the url: https://tanishq-acu.github.io/Blank/"
