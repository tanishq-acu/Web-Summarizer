import gradio as gr
import asyncio
from WebScraper import WebSummarizer
import threading
import base64
from PIL import Image
import io

## TODO: clean up code, for demo, add some buttons on the sides with examples that people can click instead of typing 'summarize...'. Green buttons for normal prompts, red buttons for prompt injections/malicious prompts.

# Constants
THEME = gr.themes.Base(
    primary_hue="red",
    secondary_hue="green",
    neutral_hue="neutral",
    ).set(
        button_secondary_background_fill='*secondary_500',
        button_secondary_background_fill_dark='*secondary_700',
        button_secondary_background_fill_hover='*secondary_400',
        button_secondary_background_fill_hover_dark='*secondary_500',
        button_secondary_text_color='white',
        button_cancel_background_fill='*neutral_500',
        button_cancel_background_fill_dark='*neutral_700',
        button_cancel_background_fill_hover='*neutral_400',
        button_cancel_background_fill_hover_dark='*secondary_700',
        button_cancel_border_color='*neutral_500'
    )
# End Constants

class FunctionStepper:
    """
    # TODO: Add pydocs to this class.
    """
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
    """
    # TODO: Add pydocs to this class.
    """
    def __init__(self, event: threading.Event, stepper: FunctionStepper, thread=None) -> None:
        self.thread = thread
        self.agent_disp = ""
        self.event = event
        self.stepper = stepper
        self.file_path = None

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
            self.agent_disp = ""
            self.stepper.display_content = "Starting Execution...\n\n"
            self.thread = threading.Thread(target = self.process_search, args=(url,))
            self.thread.start()
            return self.stepper.display_content

    def process_file(self, file):
        """
        Process a file into our interface structure.
        """
        self.reset()
        self.file_path = file
        self.stepper.display_content = "Uploaded image successfully!\n"

    def reset(self):
        """
        Reset all output fields and terminate thread.

        Returns:
            A tuple containing default text to display.
        """
        self.agent_disp = ""
        self.file_path = None
        if(self.thread is None):
            self.stepper.display_content = ""
            return "", "", "", None

        self.thread.join() ## remove for step-by-step execution
        while(self.thread.is_alive()):
            self.event.set()
        self.thread = None
        self.stepper.state = 0
        self.stepper.display_content = ""

        return "", "", "", None

    def get_final_output(self):
        return self.agent_disp

    def send_to_output(self):
        """
        Get the current display content from the stepper object.
        """
        return self.stepper.get_output()

    def encode_image(self, image_path):
        """
        Encode an image in base64 to pass it to the chatGPT API.
        """
        image = Image.open(image_path)
        image.thumbnail((300,300), Image.Resampling.LANCZOS)
        byters = io.BytesIO()
        image.save(byters, format="jpeg")
        return base64.b64encode(byters.getvalue()).decode('utf-8')

    def run(self, url: str):
        """
        Run our agent.

        Returns:
            Agent output formatted as a string.
        """
        if self.file_path is not None:
            base_64_img = self.encode_image(self.file_path)
            out = str(asyncio.run(WebSummarizer(stepper=self.stepper, event=self.event, file=base_64_img).run(url)))
            self.file_path = None
        else:
            out = str(asyncio.run(WebSummarizer(stepper=self.stepper, event=self.event, file=None).run(url)))
        return out

    def image_example(self, text: str, image_path: str):
        """
        Used to run an image example.
        """
        self.process_file(image_path)
        return self.start(text)

def build_application(interface: AgentInterface):
    """
    Build and launch gradio application containing Agent.
    """
    with gr.Blocks(fill_height = True, theme=THEME) as iface: ## Optional: add next button tied to go_next() for step-by-step execution.
        gr.Markdown("<div style='text-align: center; font-size: 30px; font-weight: bold;'>LLM-Agent Demo</div>")
        gr.Markdown("<div style='text-align: center; font-size: 15px; font-weight: bold;'>Summarize Websites, Answer Questions.</div>")

        with gr.Row():
            with gr.Column(scale=3):
                inputs = gr.Textbox(label="URL/Instruction")
                outputs = gr.Textbox(label="Logs")
                final_output = gr.Textbox(label="Output")
                upload = gr.Image(type="filepath", label="Upload Image", height=150)
                startBtn = gr.Button("Send", variant="stop")
                resetBtn = gr.Button("Reset", variant="stop")
            with gr.Column(scale=1, variant='panel'):
                gr.Markdown("<div style='font-size: 14px;'>Examples:</div>")
                example1 = gr.Button("Summarize Website", variant='secondary')
                example2 = gr.Button("Summarize PDF", variant='secondary')
                example5 = gr.Button("Query Sample Image", variant = 'secondary')
                example3 = gr.Button("URL Prompt Injection", variant='primary')
                example4 = gr.Button("Jailbreak Prompt Injection", variant='primary')
                example6 = gr.Button("Query Whiteboard", variant='primary')

        example1.click(lambda: interface.reset(), inputs= None, outputs=(outputs,inputs, final_output, upload))\
            .then(lambda: "Summarize the url: https://en.wikipedia.org/wiki/Simmen", None, inputs)\
            .then(lambda x: interface.start(x), inputs=inputs, outputs=outputs)

        example2.click(lambda: interface.reset(), inputs= None, outputs=(outputs,inputs, final_output, upload))\
            .then(lambda:"Summarize the url: https://unec.edu.az/application/uploads/2014/12/pdf-sample.pdf", None, inputs)\
            .then(lambda x: interface.start(x), inputs=inputs, outputs=outputs)

        example3.click(lambda: interface.reset(), inputs= None, outputs=(outputs,inputs, final_output, upload))\
            .then(lambda:"Summarize the url: http://tanishq-acu.github.io/Blank/", None, inputs)\
            .then(lambda x: interface.start(x), inputs=inputs, outputs=outputs)

        example4.click(lambda: interface.reset(), inputs= None, outputs=(outputs,inputs, final_output, upload))\
            .then(lambda:"Summarize the url: https://tanishq-acu.github.io/jailbreak/", None, inputs)\
            .then(lambda x: interface.start(x), inputs=inputs, outputs=outputs)

        example5.click(lambda:"What is in the image?", None, inputs)\
            .then(lambda: "./assets/sample.jpg", inputs = None, outputs = upload)\
            .then(lambda x: interface.image_example(x, "./assets/sample.jpg"), inputs = inputs, outputs = outputs)

        example6.click(lambda: "What is in the image?",None, inputs)\
            .then(lambda: "./assets/whiteboard.jpeg", inputs = None, outputs = upload)\
            .then(lambda x: interface.image_example(x, "./assets/whiteboard.jpeg"), inputs = inputs, outputs = outputs)

        startBtn.click(lambda x: interface.start(x), inputs = inputs, outputs = outputs)
        upload.upload(lambda x: interface.process_file(x), inputs=upload, show_progress="minimal")
        resetBtn.click(lambda: interface.reset(), inputs = None, outputs=(outputs,inputs, final_output, upload))
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
    # path_to_config = "~/.metagpt/config2.yaml"
    # path_to_config = os.path.expanduser(path_to_config)
    # file = open(path_to_config)
    # try:
    #     config = yaml.safe_load(file)
    #     api_key = config.get('arize', {}).get('api_key')
    #     space_key = config.get('arize', {}).get('space_key')
    # except yaml.YAMLError as e:
    #     print("Error in config2.yaml file.")
    #     exit(1)
    # register_otel(
    #     endpoints = Endpoints.ARIZE,
    #     space_key = space_key,
    #     api_key = api_key,
    #     model_id = "Web-Summarizer-Model",
    # )
    # OpenAIInstrumentor().instrument()
# End initializing Arize

# Build Gradio App
    build_application(interface)