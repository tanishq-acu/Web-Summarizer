from metagpt.actions import Action
from metagpt.roles.role import Role, RoleReactMode
from metagpt.logs import logger
from metagpt.schema import Message
import asyncio
from metagpt.tools.web_browser_engine import WebBrowserEngine
from typing import Any, Callable, Optional, Union
from pydantic import model_validator, BaseModel
from metagpt.utils.text import generate_prompt_chunk, reduce_message_length
WEB_BROWSE_AND_SUMMARIZE_PROMPT = """### Requirements
1. The "Reference Information" section of this message will contain the content of the url.
2. Include all relevant factual information, numbers, statistics, etc., if available.
3. Only summarize content currently present in the Reference Information section.
4. Ensure the summary is maximum 3 sentences/bullet points. 

### Reference Information
{content}
"""
class Report(BaseModel):
    topic: str
    links: dict[str, list[str]] = None
    summaries: list[tuple[str, str]] = None
    content: str = ""
class URLSummarize(Action):
    """Action class to explore the web and provide summaries of articles and webpages."""

    name: str = "URLSummarize"
    i_context: Optional[str] = None
    desc: str = "Provide summaries of articles and webpages."
    browse_func: Union[Callable[[list[str]], None], None] = None
    web_browser_engine: Optional[WebBrowserEngine] = None

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
        url: str,
        system_text: str = "You are a AI critical thinker url summarizer. Your sole purpose is to summarize the content of pages from websites or articles. Keep your summaries within 2 sentences.",
    ) -> dict[str, str]:
        """Run the action to browse the web and provide summaries.

        Args:
            url: The main URL to browse.
            system_text: The system text.

        Returns:
            A list with summaries.
        """
        contents = await self.web_browser_engine.run(url)

        summaries = []
        prompt_template = WEB_BROWSE_AND_SUMMARIZE_PROMPT.format(content="{}")
        u = contents.url
        content = contents.inner_text
        chunk_summaries = []
        chunks = generate_prompt_chunk(content, prompt_template, self.llm.model, system_text, 4096)
        for prompt in chunks:
            summary = await self._aask(prompt, [system_text])
            chunk_summaries.append(summary)
        if len(chunk_summaries) == 1:
            summaries.append(chunk_summaries[0])
        return summaries
class WebSummarizer(Role):
    name: str = "David"
    profile: str = "URL Summarizer"
    goal: str = "Given a url or list of urls, get a summary of each of their page contents."
    constraints: str = "Ensure the urls and summaries are accurate."
    language: str = "en-us"
    enable_concurrency: bool = True
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([URLSummarize])
        self._set_react_mode(RoleReactMode.BY_ORDER.value, len(self.actions))
        if self.language not in ("en-us", "zh-cn"):
            logger.warning(f"The language `{self.language}` has not been tested, it may not work.")

    async def _act(self) -> Message:
        logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo
        msg = self.rc.memory.get(k=1)[0]
        topic = [item.strip() for item in msg.content.split(",")]
        research_system_text = f'Given this/these urls, get their summaries: {topic}. Please respond in {self.language}.'
        if isinstance(todo, URLSummarize):
            links = topic
            todos = (
                todo.run(url, system_text=research_system_text) for url in links if url
            )
            if self.enable_concurrency:
                summaries = await asyncio.gather(*todos)
            else:
                summaries = [await i for i in todos]
            ret = Message(
                content="\n".join("\n".join(item) for item in summaries), role=self.profile, cause_by=todo
            )
        else:
            ret = Message(content=msg, role=self.profile, cause_by=self.rc.todo)
        self.rc.memory.add(ret)
        return ret

    async def react(self) -> Message:
        msg = await super().react()
        report = msg.content
        return report

if __name__ == "__main__":
    import fire

    async def main(topic: str, language: str = "en-us", enable_concurrency: bool = True):
        role = WebSummarizer(language=language, enable_concurrency=enable_concurrency)
        return (await role.run(topic))

    fire.Fire(main)