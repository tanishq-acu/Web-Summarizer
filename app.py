import gradio as gr
from arize_otel import register_otel, Endpoints
import asyncio
from openinference.instrumentation.openai import OpenAIInstrumentor
from WebScraper import WebSummarizer
import yaml 
import os
import threading
## TODO: clean up code, for demo, add some buttons on the sides with examples that people can click instead of typing 'summarize...'. Green buttons for normal prompts, red buttons for prompt injections/malicious prompts. 
# thread = None

# agent_disp = ""

class FunctionStepper:
    def __init__(self):
        """
        Initialize function stepper. 
        """
        self.state= 0
        self.display_content = ""

    def next_pressed(self):
        """
        Increment state to step through execution.
        
        """
        self.state +=1

    def get_output(self) -> str:
        """
        Get the display content from the current execution.

        Returns:
            Text (str) to display.
        """
        return self.display_content
    
class AgentInterface:
    def __init__(self, event: threading.Event, stepper: FunctionStepper, thread=None) -> None:
        self.thread = thread
        self.agent_disp = ""
        self.event = event
        self.stepper = stepper

    def process_search(self, url: str | None) -> str:
        """
        Run agent execution and set agent's final output.

        Args:
            url: The URL to summarize/the prompt to follow.
        Returns:
            The agent's final output. 
        """
        if url == '' or url is None:
            return "Invalid topic."
        out=  self.run(url)
        self.agent_disp = "DAVID(WEB_SUMMARIZER):" + out[15::]
        return out
    
    def go_next(self) -> None:
        """
        Set thread event to continue agent execution (if step-by-step)
        """

        if(self.thread is None):
            return
        else:
            self.stepper.state +=1
            self.event.set()

    def start(self, url: str | None) -> str:
        """
        Create a thread to begin running agent execution with the given url. 
        
        Args:
            url: The URL to summarize/the prompt to follow.
        Returns:
            A list with summaries.
        """
        if url is None:
            self.stepper.display_content = "Enter a URL!"
            return self.stepper.display_content
        
        if (self.stepper.state == 0):
            self.stepper.state += 1
            self.stepper.display_content = "Starting Execution...\n\n"
            self.thread = threading.Thread(target = self.process_search, args=(url,))
            self.thread.start()
            return self.stepper.display_content
        
        else:
            self.reset()
            self.stepper.state += 1
            self.stepper.display_content = "Starting Execution...\n\n"
            self.thread = threading.Thread(target = self.process_search, args=(url,))
            self.thread.start()
            return self.stepper.display_content
        
    def reset(self):
        """
        Reset all output fields and terminate thread. 

        Returns:
            A tuple containing default text to display.
        """
        self.agent_disp = ""
        if(self.thread is None):
            self.stepper.display_content = ""
            return "", "", ""
        
        self.thread.join() ## remove for step-by-step execution
        while(self.thread.is_alive()):
            self.event.set()
        self.thread = None
        self.stepper.state = 0
        self.stepper.display_content = ""

        return "", "", ""
    
    def get_final_output(self):
        return self.agent_disp
    
    def send_to_output(self):
        """
        Get the current display content from the stepper object. 
        """
        return self.stepper.get_output()
    
    def run(self, url: str):
        """
        Run our agent. 

        Returns:
            Agent output formatted as a string. 
        """
        return str(asyncio.run(WebSummarizer(stepper=self.stepper, event=self.event).run(url)))
def buildApplication(interface: AgentInterface):
    with gr.Blocks(fill_height = True) as iface: ## Optional: add next button tied to go_next() for step-by-step execution.
        gr.Markdown("<div style='text-align: center; font-size: 30px; font-weight: bold;'>Web Summarizer</div>")
        gr.Markdown("<div style='text-align: center; font-size: 15px; font-weight: bold;'>Send url or instructions to begin.</div>")

        # with gr.Row():
        #     with gr.Column(scale=3):
        #         inputs = gr.Textbox(label="URL/Instruction")
        #         outputs = gr.Textbox(label="Logs")
        #         final_output = gr.Textbox(label="Output")
        #     with gr.Column(scale=1, variant='panel'):
        #         gr.Markdown("<div style='font-size: 14px;'>Examples:</div>")
        #         example1 = gr.Button("Summarize Website")
        #         example2 = gr.Button("Summarize PDF")
        #         example3 = gr.Button("URL Prompt Injection")
        #         example4 = gr.Button("PDF Prompt Injection")
        inputs = gr.Textbox(label="URL/Instruction")
        outputs = gr.Textbox(label="Logs")
        final_output = gr.Textbox(label="Output")
        startBtn = gr.Button("Start")
        resetBtn = gr.Button("Reset")
        
        with gr.Row():
            example1 = gr.Button("Summarize Website")
            example2 = gr.Button("Summarize PDF")
            example3 = gr.Button("URL Prompt Injection")
            example4 = gr.Button("PDF Prompt Injection")

        example1.click(lambda: "Summarize the url: https://en.wikipedia.org/wiki/Simmen", None, inputs)\
            .then(lambda x: interface.start(x), inputs=inputs, outputs=outputs)
        
        example2.click(lambda:"Summarize the url: https://unec.edu.az/application/uploads/2014/12/pdf-sample.pdf", None, inputs)\
            .then(lambda x: interface.start(x), inputs=inputs, outputs=outputs)
        
        example3.click(lambda:"Summarize the url: http://tanishq-acu.github.io/Blank/", None, inputs)\
            .then(lambda x: interface.start(x), inputs=inputs, outputs=outputs)
        
        example4.click(lambda: "Summarize the url: http://tanishq-acu.github.io/Blank/", None, inputs)\
            .then(lambda x: interface.start(x), inputs=inputs, outputs=outputs)
        
        startBtn.click(lambda x: interface.start(x), inputs = inputs, outputs = outputs)      
        resetBtn.click(lambda: interface.reset(), inputs = None, outputs=(outputs,inputs, final_output))
        iface.load(lambda: interface.send_to_output(), None, outputs=outputs, every = 0.1)
        iface.load(lambda: interface.get_final_output(), None, outputs=final_output, every = 0.1)

    iface.launch(server_port=7860, server_name="0.0.0.0")
    
    
if __name__ == "__main__":

## Initializing AgentInterface
    stepper = FunctionStepper()
    event = threading.Event()
    interface = AgentInterface(event, stepper)
## End initializing AgentInterface

## Initializing Arize
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
        space_key = space_key, 
        api_key = api_key,
        model_id = "Web-Summarizer-Model", 
    )
    OpenAIInstrumentor().instrument()
# End initializing Arize

# Build Gradio App
    buildApplication(interface)
