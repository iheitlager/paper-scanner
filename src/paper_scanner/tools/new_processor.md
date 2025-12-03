I MUST have a new file processor (paper-processor) that is quite flexible. Get inspirations from the other processors

Able to select:
- Anthropic model (provide a list of models)
- Max number of tokens
- Ability to either take the content of the complete record to the LLM or open the pdf and read that text and forward that to the LLM
- Apply an external prompt from a file
- Define the jsonkey in which the output should be produced
- Operate in add or add/replace mode
- Immediately output the records to output
- Output to file or stdout
- Input from file or stdin
- Use the output file as a filter for input record and only add the records not yet in the output file
- The system must process JSONLINES records and output augmented JSONLINES records
- Have the ability to use multple processes (--workers N:default is 1)
- Have an additional option to add processing metadata (like timings, file opened, number of characters/tokens) as subfield of the added key
- All off these should be arguments
- Also have an option to read everything from a YAML file, including the prompt as a definition file
- Output the available models in help output

CONSTRAINTS
- The processor must NEVER output the complete PDF in the jsonlines
- The LLM expects a prompt that always only outputs json, but it should be flexible like file_processor_references.py


EXAMPLE:
take this input

{"file_path": "/Users/iheitlager/wc/papers/5d8a6a01-35a7-754d-3b4a-1a69f593c6ca.pdf", "file_name": "5d8a6a01-35a7-754d-3b4a-1a69f593" ....
 
After processing have something like
{"file_path": "/Users/iheitlager/wc/papers/5d8a6a01-35a7-754d-3b4a-1a69f593c6ca.pdf", "file_name": "5d8a6a01-35a7-754d-3b4a-1a69f593", "ADDED_KEY": {"DATA": ....., "METADATA": ... }, ....
