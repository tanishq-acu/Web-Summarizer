import gradio as gr
import asyncio

import asyncio

from WebScraper import WebSummarizer

def processSearch(url: str | None):
    if url == '' or url is None:
        return "Invalid topic."
    return asyncio.run(main(url))
async def main(url: str):
    return str(await WebSummarizer().run(url))


if __name__ == "__main__":
    iface = gr.Interface(
        fn = processSearch,  # Function to call
        inputs=[gr.Textbox(label="URL")],  # Input component for file upload
        outputs="text",  # Output component to display text
        title="Web Summarizer App",  # Title of the interface
        description="Send URL."  # Description
    )
    iface.launch(server_port=7860, server_name="0.0.0.0")
