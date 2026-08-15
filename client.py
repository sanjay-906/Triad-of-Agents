import asyncio

from agents.agent_base import a2a_call
from dotenv import load_dotenv
from colorama import Fore, Style, init

init(autoreset=True)
load_dotenv()

WAITER_URL = "http://localhost:9001"


async def chat() -> None:
    print("Restaurant client")
    print("Type /exit to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if user_input == "/exit":
            print("Bye!")
            break

        if not user_input:
            continue

        try:
            response, _files = await a2a_call(
                WAITER_URL,
                user_input,
            )
            print(f"{Fore.YELLOW}Waiter Agent: {response}{Style.RESET_ALL}")

            # print(f"{os.getenv('YELLOW')}Waiter Agent: {response}{os.getenv('RESET')}")
        except Exception as exc:
            print(f"Error: {exc}\n")


if __name__ == "__main__":
    asyncio.run(chat())
