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
    desc: str = "Answer a user's query."
    async def run(self, query):
        result = await self._aask(query)
        return result
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

    async def run(
        self,
        stepper,
        event,
        url: str,
        system_text: str = "You are a AI critical thinker url summarizer. Your sole purpose is to summarize the content of pages from websites or articles. Keep your summaries within 2 sentences.",
    ):
        """Run the action to browse the web and provide summaries.

        Args:
            url: The main URL to browse.
            system_text: The system text.

        Returns:
            A list with summaries.
        """
        stepper.display_content += "DAVID(WEB_SUMMARIZER): Extracting URL from query and scraping URL contents.\n\n"
        # event.wait()
        # event.clear()
        url = (await self._aask(f"Given this query: {url}; get the url from the query and respond with only the url itself, and if it does not exist, respond with only 'NA'.")).strip()
        if(url == 'NA'):
            return ["Couldn't get URL from the given query."]
        out = requests.get(url)
        if(out.status_code != 200):
            print("Invalid URL in URLSummarize()")
            return "Invalid URL"
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
        for prompt in chunks:
            stepper.display_content += f"DAVID(WEB_SUMMARIZER): Calling Alyssa(SummarizeOrSearch) with URL Contents.\n\n"
            # event.wait()
            # event.clear()
            summary = await role.run(prompt)
            chunk_summaries.append(summary.content)
        if len(chunk_summaries) == 1:
            summaries.append(chunk_summaries[0])
        return summaries
class Summarize(Action):
    name: str = "Summarize Tool"
    i_context: Optional[str] = None
    desc: str = "Provide summaries of articles and webpages."
    async def run(self, content):
        system_text = "You are a AI critical thinker url summarizer. Your sole purpose is to summarize the content of pages from websites or articles. If there is no content to summarize, just give a description of what there is(like headers and titles). Keep your summaries within 2 sentences."
        result = await self._aask(content, [system_text])
        return result
class SummarizeOrSearch(Role):
    name: str = "Alyssa"
    profile: str = "Summarizer or Searcher"
    goal: str = "Given some text, summarize it."
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
            if(len(msg.content) < 100):
                self.stepper.display_content += f"ALYSSA(SUMMARIZE_OR_SEARCH): TOOL: Summarize text. QUERY: '{msg.content}'\n\n"
            else:
                disp = msg.content[:200:].replace('\n', ' ')
                self.stepper.display_content += f"ALYSSA(SUMMARIZE_OR_SEARCH): TOOL: Summarize text. QUERY: '{disp} . . .' \n\n"
            # self.event.wait()
            # self.event.clear()
            result = await todo.run(msg.content)
            ret = Message(content = result, role =self.profile, cause_by=todo)
        elif isinstance(todo, SearchAndSummarize):
            self.stepper.display_content += f"ALYSSA(SUMMARIZE_OR_SEARCH: TOOL: Search and Summarize. QUERY: '{self.content}'\n\n"
            # self.event.wait()
            # self.event.clear()
            if (self.content):
                result = await todo.run([Message(content = self.content, role = self.profile, cause_by = self.rc.todo)])
            else:
                result = await todo.run(self.rc.memory.get())
            ret = Message(content = result, role = self.profile, cause_by = todo)
        else:
            ret = Message(content=msg.content, role=self.profile, cause_by = self.rc.todo)
        return ret
class WebSummarizer(Role):
    name: str = "David"
    profile: str = "Web Summarizer"
    goal: str = "Answer the user's queries. If given a url or list of urls, get a summary of each of their page contents"
    constraints: str = "ensure your responses are accurate"
    language: str = "en-us"
    enable_concurrency: bool = True
    def __init__(self, stepper, event, **kwargs):
        super().__init__(**kwargs)
        self.stepper = stepper
        self.event = event
        self.set_actions([AnswerQuestion, URLSummarize])
        self._set_react_mode(RoleReactMode.REACT.value, 1)
        if self.language not in ("en-us", "zh-cn"):
            logger.warning(f"The language `{self.language}` has not been tested, it may not work.")
        self.stepper.display_content += "DAVID(WEB_SUMMARIZER): Choosing tool.\n\n"
        # self.event.wait()
        # self.event.clear()
    async def _act(self) -> Message:
        logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo
        msg = self.rc.memory.get(k=1)[0]
        if isinstance(todo, URLSummarize):
            research_system_text = f'Given this query containing a url: {msg.content}, get its summary. Please respond in {self.language}.'
            self.stepper.display_content += f"DAVID(WEB_SUMMARIZER): TOOL: URLSummarize. QUERY: '{research_system_text}'\n\n"
            # self.event.wait()
            # self.event.clear()
            result = await todo.run(self.stepper, self.event, msg.content, research_system_text)
            ret = Message(content = "\n".join(result), role = self.profile, cause_by = todo)
        elif isinstance(todo, AnswerQuestion):
            self.stepper.display_content += f"DAVID(WEB_SUMMARIZER): TOOL: AnswerQuestion. QUERY: '{msg.content}'\n\n"
            # self.event.wait()
            # self.event.clear()
            result= await (todo.run(msg.content))
            ret = Message(content = result, role =self.profile, cause_by=todo)
        else:
            ret = Message(content=msg.content, role=self.profile, cause_by = self.rc.todo)
        self.rc.memory.add(ret)
        return ret

if __name__ == "__main__":
    import fire

    async def main(topic: str, language: str = "en-us", enable_concurrency: bool = True):
        role = WebSummarizer(language=language, enable_concurrency=enable_concurrency)
        return (await role.run(topic))

    fire.Fire(main)