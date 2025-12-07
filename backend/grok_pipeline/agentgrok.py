import datetime
import os
from datetime import timedelta

from xai_sdk import Client
from xai_sdk.chat import system, user
from xai_sdk.tools import code_execution, web_search, x_search


def main():
    client = Client(api_key=os.getenv("GROK_API_KEY"))

    chat = client.chat.create(
        model="grok-4-latest",
        tools=[
            web_search(),
            x_search(
                from_date=datetime.datetime.now() - timedelta(days=30),
                to_date=datetime.datetime.now(),
            ),
            code_execution(),
        ],
    )



    # Seed with a system message if you want to steer behavior
    chat.append(
        system(
            "You are a helpful financial analyst aiming to give sentiment analysis on "
            "prediction market events. Search the web and tweets for the latest news "
            "and sentiment about the event, and come up with a verdict and percentage change."
            "After you are done all your thinking, ensure that all you output to the user is a structured JSON object with the following fields: percentage_chance, choice_name, and reasoning, sorted by percentage_chance in descending order."
        )
    )

    # Feel free to change the query here to a question of your liking
    chat.append(user(
        "What is the sentiment of the event 'What is the game of the year 2025? "
        "Possible outcomes: Claire obscure expedition 33, Hollow Knight: Silksong, "
        "Death Stranding 2: On the Beach, Donkey Kong Bananza, Hades II, "
        "Kingdom Come Deliverance II'"
    ))

    is_thinking = True
    final_response = None

    for response, chunk in chat.stream():
        final_response = response

        # Show server-side tool calls in real time
        for tool_call in chunk.tool_calls:
            print(f"\nCalling tool: {tool_call.function.name} with arguments: {tool_call.function.arguments}")

        # Show reasoning token count while the model is thinking
        if response.usage.reasoning_tokens and is_thinking:
            print(f"\rThinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)

        # Print final content when it starts streaming
        if chunk.content and is_thinking:
            print("\n\nFinal Response:")
            is_thinking = False

        # Stream the content chunks
        if chunk.content and not is_thinking:
            print(chunk.content, end="", flush=True)

    if not final_response:
        print("\nNo response received.")
        return

    print("\n\nCitations:")
    print(final_response.citations)

    print("\n\nUsage:")
    print(final_response.usage)
    print(final_response.server_side_tool_usage)

    print("\n\nServer Side Tool Calls:")
    print(final_response.tool_calls)


if __name__ == "__main__":
    main()