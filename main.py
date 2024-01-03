import aiohttp
import asyncio
import sys
import os
from alive_progress import alive_bar
from bs4 import BeautifulSoup
from datetime import datetime

async def username_available(username: str, session: aiohttp.ClientSession, auth_token: str, output_file: str) -> bool:
    headers = {'Content-Type': 'multipart/form-data; boundary=---------------------------'}
    data = f'-----------------------------\r\nContent-Disposition: form-data; name="authenticity_token"\r\n\r\n{auth_token}\r\n-----------------------------\r\nContent-Disposition: form-data; name="value"\r\n\r\n{username}\r\n-------------------------------\r\n'
    async with session.post('/signup_check/username', data=data, headers=headers) as response:
        message = await response.text()
        if message == f'{username} is available.':
            with open(output_file, 'a') as file:
                log_message = f"Username '{username}' is available!\n"
                file.write(log_message)
                print(log_message, end="", flush=True)
            return True
        return False

async def get_token(session: aiohttp.ClientSession) -> str:
    async with session.get('/signup') as response:
        soup = BeautifulSoup(await response.text(), 'html.parser')
        result = soup.find('auto-check', src='/signup_check/username')
        return result.contents[3]['value']

async def worker(queue: asyncio.Queue, session: aiohttp.ClientSession, token: str, output_file: str) -> None:
    while not queue.empty():
        username = await queue.get()
        await username_available(username, session, token, output_file)
        queue.task_done()

async def progress_monitor(queue: asyncio.Queue) -> None:
    previous_size = queue.qsize()
    with alive_bar(previous_size) as bar:
        while not queue.empty():
            await asyncio.sleep(.2)
            current_size = queue.qsize()
            queue_change = previous_size - current_size
            if queue_change:
                bar(queue_change)
            previous_size = current_size

async def check_usernames_from_file(file_path: str, num_workers: int = 512) -> None:
    assert num_workers > 0, "Invalid number of workers."
    assert file_path.endswith('.txt'), "Please provide a valid '.txt' file."

    output_folder = "usernames"
    os.makedirs(output_folder, exist_ok=True)

    output_file = f"{output_folder}/usernames-{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.txt"

    with open(file_path, 'r') as file:
        usernames = file.read().splitlines()

    async with aiohttp.ClientSession(base_url='https://github.com/') as session:
        token = await get_token(session)
        queue = asyncio.Queue()
        for u in usernames:
            queue.put_nowait(u)

        workers = [asyncio.create_task(worker(queue, session, token, output_file)) for _ in range(num_workers)]
        progressmon = asyncio.create_task(progress_monitor(queue))

        await queue.join()
        for w in workers:
            w.cancel()
        progressmon.cancel()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(f'Usage: {sys.argv[0]} <file_path.txt>')
    asyncio.run(check_usernames_from_file(sys.argv[1]))
