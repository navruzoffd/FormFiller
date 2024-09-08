from src.yandex import YandexForm
from playwright.async_api import async_playwright
import asyncio

async def main():
    async with async_playwright() as playwright:
        form = YandexForm(playwright)
        await form.start("https://forms.yandex.ru/u/66dd673d5056905f78e71678/")
        # await form.get_form_json("forms/test.json")
        await form.fill_form("forms/test.json")
        await asyncio.sleep(3000)

if __name__ == "__main__":
    asyncio.run(main())