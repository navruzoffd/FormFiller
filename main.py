from src.yandex import YandexForm
from playwright.async_api import async_playwright
import asyncio
from logger import logger
from fake_useragent import UserAgent
from src.bot import main


# async def main():
    # async with async_playwright() as playwright:
    #     for i in range(1000):
    #         ua = UserAgent(browsers=['edge', 'chrome'],
    #            os=["windows", "android", "ios"])
    #         form = YandexForm(playwright, ua.random)
    #         await form.start("https://forms.yandex.ru/u/66dd673d5056905f78e71678/")
    #         # await form.get_form_json("forms/test.json")
    #         await form.fill_form("forms/test.json")
    #         logger.info(f"{i+1} итерация")

if __name__ == "__main__":
    asyncio.run(main())