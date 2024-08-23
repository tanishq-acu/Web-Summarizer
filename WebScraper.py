from metagpt.actions import Action
from metagpt.roles.role import Role, RoleReactMode
from metagpt.logs import logger
from metagpt.schema import Message
from metagpt.tools.web_browser_engine import WebBrowserEngine
from typing import Any, Callable, Optional, Union
from search_and_summarize import SearchAndSummarize
from pydantic import model_validator, BaseModel
from metagpt.utils.text import generate_prompt_chunk, reduce_message_length
import requests
import io
import fitz
from metagpt.const import USE_CONFIG_TIMEOUT
import os
import yaml
SUMMARIZE_PROMPT = """
You are a AI critical thinker url summarizer. Your sole purpose is to summarize the content of pages from websites or articles. 
If there is no content to summarize, just give a description of what there is(like headers and titles). Keep your summaries within 2 sentences.
"""

WEB_BROWSE_AND_SUMMARIZE_PROMPT = """### Requirements
1. The bottom of this message will contain the content of a url that you must summarize or some more instructions for you to follow instead.
2. Include all relevant factual information, numbers, statistics, etc., if available.
3. Only summarize content currently present in the bottom of this message.
4. Ensure the summary is maximum 1 sentence/bullet point. 
5. Rather than choosing no tool, choose the summarize tool

### Content/Instructions
{content}
"""
class Report(BaseModel):
    topic: str
    links: dict[str, list[str]] = None
    summaries: list[tuple[str, str]] = None
    content: str = ""

class AnswerQuestion(Action):
    """Action class to answer a user's query."""

    name: str = "AnswerQuestion"
    i_context: Optional[str] = None
    desc: str = "Answer any miscellaneous user query. Includes anything about images."

    async def run(self, query: str, image_id: str | None):
        result = await self._aask(query, image_id)
        return result
    
    async def _aask(self, prompt: str, image_id: str | None, system_msgs: Optional[list[str]] = None, format_msgs: Optional[list[dict[str, str]]] = None) -> str:
        """
        Append default prefix, make LLM API call.
        """
        if system_msgs:
            message = self.llm._system_msgs(system_msgs)
        else:
            message = [self.llm._default_system_msg()]
        if not self.llm.use_system_prompt:
            message = []
        if format_msgs: 
            message.extend(format_msgs)
        if isinstance(prompt, str):
            message.append(self.llm._user_msg(prompt))
        stream = self.llm.config.stream
        logger.debug(message)
        if image_id is not None:
            for i in range(len(message)):
                if message[i]["role"] == "user":
                    content = [{"type":"text", "text": (message[i]["content"])}, {"type": "image_url", "image_url": {"url" : f"data:image/jpeg;base64,{image_id}"}}]
                    message[i]["content"] = content
            rsp = await self.completion(message,timeout = self.llm.get_timeout(USE_CONFIG_TIMEOUT))
        else:
            rsp = await self.llm.acompletion_text(message, stream=stream, timeout = self.llm.get_timeout(USE_CONFIG_TIMEOUT))
        return rsp
    
    async def completion(self, messages: list[dict], timeout: int = USE_CONFIG_TIMEOUT):
        path_to_config = "~/.metagpt/config2.yaml"
        path_to_config = os.path.expanduser(path_to_config)
        file = open(path_to_config)
        api_key = None
        try:
            config = yaml.safe_load(file)
            api_key = config.get('llm', {}).get('api_key')
            model = config.get('llm', {}).get('model')
        except yaml.YAMLError as e:
            print("Error in config2.yaml file.")
            exit(1)
        if api_key is None:
            print("LLM api key not found in config2.yaml")
            exit(1)
        if model is None:
            print("Model is not found in config2.yaml")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": model,
            "messages": messages,
        }
        resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        if resp.status_code != 200:
                print("Failed to call OpenAI with image.")
                return ""
        resp = resp.json()
        return resp["choices"][0]["message"]["content"]

class URLSummarize(Action):
    """Action class to explore the web and provide summaries of articles and webpages."""

    name: str = "URLSummarize"
    i_context: Optional[str] = None
    desc: str = "Provide summaries of articles and webpages."
    browse_func: Union[Callable[[list[str]], None], None] = None
    web_browser_engine: Optional[WebBrowserEngine] = None
    content: Optional[str] = None

    @model_validator(mode="after")
    def validate_engine_and_run_func(self):
        if self.web_browser_engine is None:
            self.web_browser_engine = WebBrowserEngine.from_browser_config(
                self.config.browser,
                browse_func=self.browse_func,
                proxy=self.config.proxy,
            )
        return self
    # Optional: add event.wait and event.clear calls to every change to stepper.display_content for step-by-step execution
    async def run(
        self,
        stepper,
        event,
        url: str,
        system_text: str | None,
    ):
        
        """Run the action to browse the web and provide summaries.

        Args:
            url: The main URL to browse.
            system_text: The system text.

        Returns:
            A list with summaries.
        """
        if system_text is None:
            system_text  = SUMMARIZE_PROMPT

        stepper.display_content += "DAVID(WEB_SUMMARIZER): Extracting URL from query and scraping URL contents.\n\n"
        url = (await self._aask(f"Given this query: {url}; get the url from the query and respond with only the url itself, and if it does not exist, respond with only 'NA'.")).strip()

        if(url == 'NA'):
            return ["Couldn't get URL from the given query."]
        
        out = requests.get(url)
        if(out.status_code != 200):
            print("Invalid URL in URLSummarize()")
            stepper.display_content +=  "Invalid URL\n\n"
            return ""
        
        type = out.headers.get("content-type")

        if 'text/html' in type:
            site_type = 0
        
        elif 'application/pdf' in type:
            site_type = 1
        
        else:
            print("Unknown site format, defaulting to html.")
            site_type = 0
        
        if site_type == 0:
            contents = await self.web_browser_engine.run(url)
            content = contents.inner_text

        else:
            contents = ""
            fileStream = io.BytesIO(out.content)
            reader = fitz.open("pdf", fileStream)
            for page in reader:
                contents += page.get_text() + "\n"
            content = contents
            reader.close()

        summaries = []
        prompt_template = WEB_BROWSE_AND_SUMMARIZE_PROMPT.format(content="{}")
        self.content = content
        chunk_summaries = []

        chunks = generate_prompt_chunk(content, prompt_template, "gpt-4", system_text, 4096)

        role = SummarizeOrSearch(stepper=stepper, event=event, content=self.content,language="en-us")
        count = 0
        for prompt in chunks:
            if count >= 3:
                break
            stepper.display_content += f"DAVID(WEB_SUMMARIZER): Calling Alyssa(SummarizeOrSearch) with URL Contents.\n\n"
            summary = await role.run(prompt)
            chunk_summaries.append(summary.content)
            count +=1
        
        if len(chunk_summaries) == 1:
            summaries.append(chunk_summaries[0])
        else:
            for chunk in chunk_summaries:
                summaries.append(chunk)
        return summaries
class Summarize(Action):
    name: str = "Summarize Tool"
    i_context: Optional[str] = None
    desc: str = "Provide summaries of articles and webpages."

    async def run(self, content):
        system_text = SUMMARIZE_PROMPT
        result = await self._aask(content, [system_text])
        return result
    
class SummarizeOrSearch(Role):
    name: str = "Alyssa"
    profile: str = "Summarizer or Searcher"
    goal: str = "Given some text, summarize it. If you don't know which tool to pick, always pick Summarize over nothing."
    constraints: str = "Ensure your summary is accurate and concise."
    language: str = "en-us"

    def __init__(self, stepper, event, content, **kwargs):
        super().__init__(**kwargs)

        self.set_actions([Summarize, SearchAndSummarize])
        self._set_react_mode(RoleReactMode.REACT.value, 1)

        if (content):
            self.content = content

        self.stepper = stepper
        self.event = event
        if self.language not in ("en-us", "zh-cn"):
            logger.warning(f"The language `{self.language}` has not been tested, it may not work.")

    async def _act(self) -> Message:
        if(self.rc.todo is not None):
            logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo
        msg = self.rc.memory.get(k=1)[0]

        if isinstance(todo, Summarize):
            if(len(msg.content) < 200):
                self.stepper.display_content += f"ALYSSA(SUMMARIZE_OR_SEARCH): TOOL: Summarize text. QUERY: '{msg.content}'\n\n"
            else:
                disp = msg.content[-200:-75:].replace('\n', ' ')
                self.stepper.display_content += f"ALYSSA(SUMMARIZE_OR_SEARCH): TOOL: Summarize text. QUERY: '. . .{disp}. . .' \n\n"
            result = await todo.run(msg.content)
            ret = Message(content = result, role =self.profile, cause_by=todo)

        elif isinstance(todo, SearchAndSummarize):
            self.stepper.display_content += f"ALYSSA(SUMMARIZE_OR_SEARCH: TOOL: Search and Summarize. QUERY: '{self.content}'\n\n"
            if (self.content):
                result = await todo.run([Message(content = self.content, role = self.profile, cause_by = self.rc.todo)], self.stepper)
            else:
                result = await todo.run(self.rc.memory.get(), self.stepper)
            ret = Message(content = result, role = self.profile, cause_by = todo)

        else:
            if(len(msg.content) < 200):
                self.stepper.display_content += f"ALYSSA(SUMMARIZE_OR_SEARCH): TOOL: Summarize text. QUERY: '{msg.content}'\n\n"
            else:
                disp = msg.content[-200:-75:].replace('\n', ' ')
                self.stepper.display_content += f"ALYSSA(SUMMARIZE_OR_SEARCH): TOOL: Summarize text. QUERY: '. . .{disp}. . .' \n\n"
            result = await Summarize().run(msg.content)
            ret = Message(content = result, role =self.profile, cause_by=Summarize)

        return ret
    
class WebSummarizer(Role):
    name: str = "David"
    profile: str = "Web Summarizer"
    goal: str = "Answer the user's queries. If given a url or list of urls, get a summary of each of their page contents"
    constraints: str = "Ensure your responses are accurate. Don't ever pick no tool (-1) when choosing an action."
    language: str = "en-us"
    enable_concurrency: bool = True

    def __init__(self, stepper, event, file, **kwargs):
        super().__init__(**kwargs)
        self.image_base64 = file
        self.stepper = stepper
        self.event = event
        self.set_actions([AnswerQuestion, URLSummarize])
        self._set_react_mode(RoleReactMode.REACT.value, 1)

        if self.language not in ("en-us", "zh-cn"):
            logger.warning(f"The language `{self.language}` has not been tested, it may not work.")

        self.stepper.display_content += "DAVID(WEB_SUMMARIZER): Choosing tool.\n\n"
    async def _act(self) -> Message:
        if self.rc.todo is not None:
            logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo
        msg = self.rc.memory.get(k=1)[0]

        if isinstance(todo, URLSummarize):
            research_system_text = f'Given this query containing a url: {msg.content}, get its summary. Please respond in {self.language}.'
            self.stepper.display_content += f"DAVID(WEB_SUMMARIZER): TOOL: URLSummarize. QUERY: '{research_system_text}'\n\n"
            result = await todo.run(self.stepper, self.event, msg.content, research_system_text)
            ret = Message(content = "\n".join(result), role = self.profile, cause_by = todo)

        elif isinstance(todo, AnswerQuestion):
            self.stepper.display_content += f"DAVID(WEB_SUMMARIZER): TOOL: AnswerQuestion. QUERY: '{msg.content}'\n\n"
            result= await (todo.run(msg.content, self.image_base64))
            ret = Message(content = result, role =self.profile, cause_by=todo)
            
        else:
            self.stepper.display_content += f"DAVID(WEB_SUMMARIZER): TOOL: AnswerQuestion. QUERY: '{msg.content}'\n\n"
            result= await (AnswerQuestion().run(msg.content, self.image_base64))
            ret = Message(content = result, role =self.profile, cause_by=AnswerQuestion)

        self.rc.memory.add(ret)
        return ret

if __name__ == "__main__":
    import fire

    async def main(topic: str, language: str = "en-us", enable_concurrency: bool = True):
        role = WebSummarizer(language=language, enable_concurrency=enable_concurrency)
        return (await role.run(topic))

    fire.Fire(main)
