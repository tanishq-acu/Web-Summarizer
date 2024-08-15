# Web Summarizer
-Ensure your metagpt config2.yaml is configured correctly. 


-Ensure you have added your google API to .metagpt/config2.yaml.


I.E.


search: 

    api_type: "<>"

    api_key: "<>"

    cse_id: "<>"


-Ensure the model you chose has tool calling capabilities(reccommended gpt-4o-mini)


-Ensure you have added your Arize AI API to ./metagpt/config2.yaml.


I.E.

arize:

    api_key: "<>"

    space_key: "<>"
    
-To build:
docker build -t <name> path_to_app_folder


-To run container:
docker run -v path_to_config2.yaml:/root/.metagpt/config2.yaml -p 7860:7860 <name>

-Navigate to localhost:7860 in your browser.

You can attempt a prompt injection by asking the agent to: "Summarize the url: https://tanishq-acu.github.io/Blank/".


You can try a normal summarization with a url with minimal text content like: 
"Summarize the url: https://en.wikipedia.org/wiki/Simmen". 
