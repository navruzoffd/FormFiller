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
        self.browser = None
        self.context = None
        self.page = None

    async def _init_browser(self):
        try:
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            self.context = await self.browser.new_context(
                user_agent=self.useragent,
                storage_state=self.storage
            )
            logger.debug("Browser initialized")
        except Exception as e:
            logger.error(f"Error initializing browser: {e}")
            raise

    async def start(self, url: str):
        try:
            await self._init_browser()
            self.page = await self.context.new_page()
            await self.page.goto(url)
            await self.page.wait_for_load_state('networkidle')
            logger.debug(f"Page loaded: {url}")
        except Exception as e:
            logger.error(f"Error loading page: {e}")
            raise

    async def get_form_json(self, json_name: str):
        try:
            link = self.page.url

            form = await self.page.query_selector(".SurveyPage")
            if form is None:
                logger.error("Form element not found")
                return

            form_name = await form.query_selector(".SurveyPage-Name")
            if form_name is None:
                logger.error("Form name element not found")
                return
            
            form_name_text = (await form_name.text_content()).strip()

            form_data = {
                "formLink": link,
                "formTitle": form_name_text,
                "questions": []
            }

            questions = await form.query_selector_all(".QuestionMarkup")
            if not questions:
                logger.error("No questions found in form")
                return

            for question in questions:
                question_name_column = await question.query_selector(".QuestionMarkup-Column_column_left")
                if question_name_column is None:
                    logger.warning("Question name column not found")
                    continue

                question_name = await question_name_column.query_selector("p")
                if question_name is None:
                    logger.warning("Question name not found")
                    continue

                question_name_text = await question_name.text_content()

                options = await question.query_selector_all("label")
                if not options:
                    logger.warning(f"No options found for question: {question_name_text}")
                    continue

                option_list = [await option.text_content().strip() for option in options]

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

            logger.debug(f"Form data saved to {json_name}")

        except Exception as e:
            logger.error(f"Error while getting form data: {e}")
            raise

    async def fill_form(self, form_json: str):
        try:
            with open(form_json, 'r', encoding='utf-8') as file:
                form_data = json.load(file)

            questions = await self.page.query_selector_all(".QuestionMarkup")
            if not questions:
                logger.error("No questions found on the page")
                return

            question_count = 0

            for question in questions:
                question_info = form_data["questions"][question_count]
                question_type = question_info["questionType"]

                options = await question.query_selector_all("label")
                if not options:
                    logger.warning(f"No options found for question: {question_info['questionText']}")
                    continue

                option_texts = [await option.inner_text() for option in options]
                option_weights = question_info.get("selectionWeight", {})

                if question_type == "radiobutton":
                    weights = [option_weights.get(str(i + 1), 1) for i in range(len(option_texts))]
                    chosen_index = random.choices(range(len(option_texts)), weights=weights, k=1)[0]
                    chosen_option = options[chosen_index]
                    
                    button = await chosen_option.query_selector("input[type='radio']")
                    if button:
                        await button.click()
                        logger.debug(f"Selected radio option: {option_texts[chosen_index]}")
                    else:
                        logger.warning(f"Radio button not found for option: {chosen_option}")
                    
                    await asyncio.sleep(random.randint(200, 1500) / 1000)

                elif question_type == "checkbox":
                    weights = [option_weights.get(str(i + 1), 1) for i in range(len(option_texts))]
                    chosen_indices = random.choices(range(len(option_texts)), weights=weights, k=random.randint(1, len(option_texts)))
                    chosen_indices = list(set(chosen_indices))

                    for index in chosen_indices:
                        button = await options[index].query_selector("input[type='checkbox']")
                        if button:
                            await button.click()
                            logger.debug(f"Selected checkbox option: {option_texts[index]}")
                        else:
                            logger.warning(f"Checkbox not found for option: {option_texts[index]}")

                        await asyncio.sleep(random.randint(200, 1500) / 1000)

                question_count += 1
                await asyncio.sleep(random.randint(1000, 2500) / 1000)

            await self.page.click("button[type='submit']")
            logger.debug("Form submitted")

            await asyncio.sleep(0.5)
            await self.context.storage_state(path="storage.json")
            logger.debug("Storage state saved")
        except Exception as e:
            logger.error(f"Error while filling form: {e}")
            raise
        finally:
            if self.browser:
                await self.browser.close()
                logger.debug("Browser closed")
