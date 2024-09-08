from playwright.async_api import async_playwright, Playwright
from logger import logger
import asyncio
import json
import aiofiles

class YandexForm:

    def __init__(self,
                 playwright: Playwright,
                 useragent: str = None) -> None:
        
        self.playwright = playwright
        self.useragent = useragent

    async def _init_browser(self):
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled'
            ])
        
        self.context = await self.browser.new_context(
            user_agent=self.useragent
        )
        logger.debug("Browser initialized")

    async def start(self, url: str):
        await self._init_browser()
        self.page = await self.context.new_page()
        await self.page.goto(url)
        await self.page.wait_for_load_state("networkidle")

    async def get_form_json(self, json_name):
        form = await self.page.query_selector(".SurveyPage")

        form_name = await form.query_selector(".SurveyPage-Name")
        form_name_text = (await form_name.text_content()).strip()

        questions = await form.query_selector_all(".QuestionMarkup")

        form_data = {
            "formTitle": form_name_text,
            "questions": []
        }

        for question in questions:
            
            question_name_column = await question.query_selector(".QuestionMarkup-Column_column_left")
            question_name = await question_name_column.query_selector("p")
            question_name_text = await question_name.text_content()

            options = await question.query_selector_all("label")

            option_list = []

            for option in options:
                option_text = (await option.text_content()).strip()
                option_list.append(option_text)
            
            question_html = await question.inner_html()

            if "radiogroup" in question_html:
                question_type = "radiogroup"
            elif "checkbox" in question_html:
                question_type = "checkbox"
            else:
                question_type = "unknown"

            form_data["questions"].append({
                "questionText": question_name_text,
                "questionType": question_type,
                "options": option_list
            })

        json_data = json.dumps(form_data, ensure_ascii=False, indent=4)

        async with aiofiles.open(json_name, 'w', encoding='utf-8') as f:
            await f.write(json_data)