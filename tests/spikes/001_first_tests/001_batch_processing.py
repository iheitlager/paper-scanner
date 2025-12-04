import os
import pprint
import sys
import time

from anthropic import Anthropic


def batch_example(api_key=None):
    # Initialize the Anthropic client
    # Get API key from args or environment
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("API key must be provided via --api_key or ANTHROPIC_API_KEY environment variable")

    client = Anthropic(api_key=api_key)

    # Define two different prompts
    prompts = [
        {"prompt": "Explain quantum computing in simple terms.", "custom_id": "quantum_computing"},
        {"prompt": "Write a short poem about artificial intelligence.", "custom_id": "ai_poem"},
    ]

    # Create batch requests
    batch_requests = []
    for p in prompts:
        request = {
            "params": {
                "model": "claude-3-7-sonnet-20250219",
                "max_tokens": 1000,
                "system": "You are a helpful AI assistant.",
                "messages": [{"role": "user", "content": [{"type": "text", "text": p["prompt"]}]}],
            },
            "custom_id": p["custom_id"],  # Used to identify results later
        }
        batch_requests.append(request)

    print(f"Submitting batch with {len(batch_requests)} requests...", file=sys.stderr)

    try:
        # Submit the batch
        batch_response = client.messages.batches.create(requests=batch_requests)

        batch_id = batch_response.id
        print(f"Batch submitted successfully. Batch ID: {batch_id}", file=sys.stderr)

        # Polling configuration
        max_poll_attempts = 30
        poll_interval = 10  # seconds

        # Start polling for completion
        for attempt in range(max_poll_attempts):
            # Get the current status of the batch
            response = client.messages.batches.retrieve(batch_id)

            # Check the processing status
            if response.processing_status == "ended":
                print(f"Batch processing ended after {attempt + 1} polling attempts!", file=sys.stderr)
                break

            elif response.processing_status == "canceling":
                print("Batch is being canceled", file=sys.stderr)

            elif response.processing_status == "in_progress":
                # Report status tallies if available
                if hasattr(response, "status_tallies"):
                    tallies = response.status_tallies
                    print(
                        f"Attempt {attempt + 1}/{max_poll_attempts}: Batch in progress. Status tallies: {tallies}",
                        file=sys.stderr,
                    )
                else:
                    print(f"Attempt {attempt + 1}/{max_poll_attempts}: Batch still in progress...", file=sys.stderr)

            # Wait before polling again
            time.sleep(poll_interval)
        else:
            # This executes if the loop completes without breaking
            print(f"Exceeded maximum polling attempts ({max_poll_attempts})", file=sys.stderr)
            return None

        # # Get the final results
        # final_response = client.messages.batches.retrieve(batch_id)

        # Check if we have a results URL
        if not hasattr(response, "results_url") or not response.results_url:
            print("No results URL available in the batch response.", file=sys.stderr)
            return None

        # Fetch and process results
        print(f"Fetching results from {response.results_url}", file=sys.stderr)
        batch_results = client.messages.batches.results(batch_id)

        results = {}
        for item in batch_results:
            if hasattr(item, "result"):
                print(dir(item), item.result.message.content)
                pprint.pprint(item.result.message)
        # # Process the results
        # if hasattr(batch_results, 'data'):
        #     for result in batch_results.data:
        #         # Check if this result has a message and no error
        #         if hasattr(result, 'message') and result.error is None:
        #             # Get the custom_id from the request params
        #             custom_id = result.request.params.get("custom_id")

        #             if custom_id and hasattr(result.message, 'content'):
        #                 # Extract the text from the message content
        #                 content = result.message.content
        #                 if content and len(content) > 0 and hasattr(content[0], 'text'):
        #                     results[custom_id] = content[0].text
        # else:
        #     # Handle individual message errors
        #     custom_id = result.request.params.get("custom_id") if hasattr(result, 'request') else "unknown"
        #     error_msg = result.error if hasattr(result, 'error') else "Unknown error"
        #     print(f"Error for {custom_id}: {error_msg}")
        # else:
        #     print("No results data available in the batch response")

        # # Print the results
        # print("\nResults:")
        # for custom_id, text in results.items():
        #     print(f"\n--- {custom_id} ---")
        #     # Print only the first 300 characters for brevity
        #     print(f"{text[:300]}{'...' if len(text) > 300 else ''}")

        # return results

    except Exception as e:
        print(f"Error: {e}")
        return None


if __name__ == "__main__":
    batch_example()


MessageBatchIndividualResponse(
    custom_id="ai_poem",
    result=MessageBatchSucceededResult(
        message=Message(
            id="msg_01WRLfyBq3WNEu26oYfNwN2n",
            content=[
                TextBlock(
                    citations=None,
                    text="# Silicon Dreams\n\nIn circuits deep, where logic streams,\nArtificial minds weave digital dreams.\nLearning, growing, day by day,\nPatterns found in data's play.\n\nNot flesh and blood, but code and light,\nA different kind of thinking might.\nPartner to humanity's grand quest,\nTwo forms of thought, together blessed.",
                    type="text",
                )
            ],
            model="claude-3-7-sonnet-20250219",
            role="assistant",
            stop_reason="end_turn",
            stop_sequence=None,
            type="message",
            usage=Usage(cache_creation_input_tokens=0, cache_read_input_tokens=0, input_tokens=22, output_tokens=78),
        ),
        type="succeeded",
    ),
)
