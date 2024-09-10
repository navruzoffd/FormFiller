from playwright.async_api import async_playwright, Playwright
from logger import logger
import asyncio
import json
import aiofiles
import random

class YandexForm:

    def __init__(self,
                 playwright: Playwright,
                 useragent: str = None,
                 storage: str = None) -> None:
        
        self.playwright = playwright
        self.useragent = useragent
        self.storage = storage

    async def _init_browser(self):
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled'
            ])
        
        self.context = await self.browser.new_context(
            user_agent=self.useragent,
            storage_state=self.storage
        )
        logger.debug("Browser initialized")

    async def start(self, url: str):
        await self._init_browser()
        self.page = await self.context.new_page()
        await self.page.goto(url)
        await self.page.wait_for_selector(".SurveyPage")
        logger.debug("Page loaded")

    async def get_form_json(self, json_name):

        link = self.page.url

        form = await self.page.query_selector(".SurveyPage")

        form_name = await form.query_selector(".SurveyPage-Name")
        form_name_text = (await form_name.text_content()).strip()

        form_data = {
            "formLink": link,
            "formTitle": form_name_text,
            "questions": []
        }

        questions = await form.query_selector_all(".QuestionMarkup")

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
                question_type = "radiobutton"
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
        logger.debug("JSON form loaded")

    async def fill_form(self, form_json: str):
        with open(form_json, 'r', encoding='utf-8') as file:
            form_data = json.load(file)

        questions = await self.page.query_selector_all(".QuestionMarkup")
        question_count = 0

        for question in questions:
            options = await question.query_selector_all("label")
            question_info = form_data["questions"][question_count]
            question_type = question_info["questionType"]
            option_texts = [await option.inner_text() for option in options]
            option_weights = question_info.get("selectionWeight", {})

            if question_type == "radiobutton":
                weights = [option_weights.get(str(i + 1), 1) for i in range(len(option_texts))]
                chosen_index = random.choices(range(len(option_texts)), weights=weights, k=1)[0]
                chosen_option = options[chosen_index]
                
                button = await chosen_option.query_selector("input[type='radio']")
                if button:
                    await button.click()
                    await asyncio.sleep(random.randint(200, 1500) / 1000)
                else:
                    logger.debug(f"Radio button not found in option {chosen_option}")

            elif question_type == "checkbox":
                weights = [option_weights.get(str(i + 1), 1) for i in range(len(option_texts))]
                chosen_indices = random.choices(range(len(option_texts)), weights=weights, k=random.randint(1, len(option_texts)))
                chosen_indices = list(set(chosen_indices))
                
                for index in chosen_indices:
                    button = await options[index].query_selector("input[type='checkbox']")
                    if button:
                        await button.click()
                        await asyncio.sleep(random.randint(200, 1500) / 1000)
                    else:
                        logger.debug(f"Checkbox not found in option {options[index]}")

            question_count += 1
            await asyncio.sleep(random.randint(1000, 2500) / 1000)

        await self.page.click("button[type='submit']")
        await asyncio.sleep(0.5)
        await self.context.storage_state(path=f"storage.json")
        await self.browser.close()