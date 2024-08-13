import gradio as gr
from arize_otel import register_otel, Endpoints
import asyncio
from openinference.instrumentation.openai import OpenAIInstrumentor
from WebScraper import WebSummarizer
import yaml 
import os
import threading
thread = None
final = ""
class FunctionStepper:
    def __init__(self):
        self.state= 0
        self.display_content = "Ready to start.\n"
    def next_pressed(self):
        self.state +=1
    def get_output(self):   
        return self.display_content
def processSearch(url: str | None, stepper, event):
    global final
    if url == '' or url is None:
        return "Invalid topic."
    out=  main(url, stepper, event)
    # stepper.display_content += "\nFINISH: \nDAVID:" + out
    final = "FINISH: \nDAVID:" + out
    return out
def go_next(event):
    global thread
    if(thread is None):
        return
    else:
        stepper.state +=1
        event.set()
def start(url, stepper, event):
    global thread
    if url is None:
        stepper.display_content = "Enter a URL!"
        return stepper.display_content
    if (stepper.state == 0):
        stepper.state += 1
        stepper.display_content = "Starting Execution...\n"
        thread = threading.Thread(target = processSearch, args=(url, stepper, event))
        thread.start()
        return stepper.display_content
    else:
        return stepper.display_content
def reset(stepper, event):
    global thread
    global final
    final = ""
    stepper.display_content = "Ready to start.\n"
    if(thread is None):
        return "", "", ""
    while(thread.is_alive()):
        event.set()
    thread = None
    stepper.state = 0
    stepper.display_content = "Ready to start.\n"
    return "", "", ""
def get_final_output():
    global final
    return final
def send_to_output(stepper):
    return stepper.get_output()
def main(url: str, stepper, event):
    print("main called")
    return str(asyncio.run(WebSummarizer(stepper=stepper, event=event).run(url)))
if __name__ == "__main__":
    stepper = FunctionStepper()
    event = threading.Event()
    path_to_config = "~/.metagpt/config2.yaml"
    path_to_config = os.path.expanduser(path_to_config)
    file = open(path_to_config)
    try:
        config = yaml.safe_load(file)
        api_key = config.get('arize', {}).get('api_key')
        space_key = config.get('arize', {}).get('space_key')
    except yaml.YAMLError as e:
        print("Error in config2.yaml file.")
        exit(1)
    register_otel(
        endpoints = Endpoints.ARIZE,
        space_key = space_key, # in app space settings page
        api_key = api_key, # in app space settings page
        model_id = "Web-Summarizer-Model", # name this to whatever you would likes
    )
    OpenAIInstrumentor().instrument()
    with gr.Blocks() as iface:
        gr.Markdown("## Web Summarizer")
        gr.Markdown("Send url or instructions to begin.")
        inputs = gr.Textbox(label="URL/Instruction")
        outputs = gr.Textbox(label = "Logs")
        final_output = gr.Textbox(label = "Output")
        # nextBtn = gr.Button("Next")
        startBtn = gr.Button("Start")
        resetBtn = gr.Button("Reset")
        startBtn.click(lambda x: start(x,stepper, event), inputs = inputs, outputs = outputs)
        # nextBtn.click(lambda: go_next(event), inputs = None , outputs = None)        
        resetBtn.click(lambda: reset(stepper, event), inputs = None, outputs=(outputs,inputs, final_output))
        iface.load(lambda: send_to_output(stepper), None, outputs=outputs, every = 0.1)
        iface.load(lambda: get_final_output(), None, outputs=final_output, every = 0.1)
    iface.launch(server_port=7860, server_name="0.0.0.0")
    iface.unload(lambda: reset(stepper,event))
