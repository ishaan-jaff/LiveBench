import os
import time
from typing import TYPE_CHECKING

from tenacity import retry, stop_after_attempt, retry_if_exception_type, wait_fixed, after_log

import logging
import litellm
import sys
logging.basicConfig(stream=sys.stdout, level=logging.WARNING)

logger = logging.getLogger(__name__)
if TYPE_CHECKING:
    from livebench.model.models import Model

# API setting constants
API_MAX_RETRY = 12
API_RETRY_SLEEP = 10
API_ERROR_OUTPUT = "$ERROR$"

def retry_fail(_):
    print("all retries failed")
    return API_ERROR_OUTPUT, 0

def retry_log(retry_state):
    exception = retry_state.outcome.exception()
    logger.warning(f"{retry_state.fn.__name__}: attempt {retry_state.attempt_number} failed with {exception.__class__.__name__}: {exception}")

@retry(
    stop=stop_after_attempt(API_MAX_RETRY),
    wait=wait_fixed(API_RETRY_SLEEP),
    retry=retry_if_exception_type(Exception),
    after=retry_log,
    retry_error_callback=retry_fail
)
def chat_completion_openai(
    model: "Model", conv, temperature, max_tokens, api_dict=None
) -> tuple[str, int]:
    from livebench.model.models import OpenAIModel
    from openai import NOT_GIVEN

    api_dict = api_dict or {}
    api_key = api_dict.get("api_key")
    base_url = api_dict.get("api_base")
    
    messages = conv.to_openai_api_messages()
    for message in messages:
        if message["role"] == "system":
            message["role"] = "developer"
    response = litellm.completion(
        model=model.api_name,
        messages=messages,
        n=1,
        temperature=(
            temperature
            if isinstance(model, OpenAIModel) and not model.inference_api
            else NOT_GIVEN
        ),
        max_completion_tokens=(
            max_tokens
        ),
        api_key=api_key,
        base_url=base_url,
    )
    message = response.choices[0].message.content
    if message is None:
        raise Exception("No message returned from OpenAI")
    output = message
    num_tokens = response.usage.completion_tokens

    return output, num_tokens



@retry(
    stop=stop_after_attempt(API_MAX_RETRY),
    wait=wait_fixed(API_RETRY_SLEEP),
    retry=retry_if_exception_type(Exception),
    after=retry_log,
    retry_error_callback=retry_fail
)
def chat_completion_aws(model, conv, temperature, max_tokens, api_dict=None) -> tuple[str, int]:
    import boto3
    from botocore.exceptions import ClientError

    brt = boto3.client("bedrock-runtime", region_name="us-east-1")
    prompt = [text for role, text in conv.messages if role == "user"][0]

    response = brt.converse(
        modelId=model.api_name,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={
            "maxTokens": max_tokens,
            "temperature": temperature,
        },
    )
    output = response["output"]["message"]["content"][0]["text"]
    num_tokens = response["usage"]["output"]["totalTokens"]

    return output, num_tokens


@retry(
    stop=stop_after_attempt(API_MAX_RETRY),
    wait=wait_fixed(API_RETRY_SLEEP),
    retry=retry_if_exception_type(Exception),
    after=retry_log,
    retry_error_callback=retry_fail
)
def chat_completion_deepseek(model, conv, temperature, max_tokens, api_dict=None) -> tuple[str, int]:
    if api_dict is not None and "api_key" in api_dict:
        api_key = api_dict["api_key"]
    else:
        api_key = os.environ["DEEPSEEK_API_KEY"]

    print("sleeping for 3 sec")
    time.sleep(3)
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    messages = conv.to_openai_api_messages()
    response = client.chat.completions.create(
        model=model.api_name,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        n=1,
        stream=False,
    )
    message = response.choices[0].message.content
    if message is None:
        raise Exception("No message returned from DeepSeek")
    output = message
    num_tokens = response.usage.completion_tokens

    return output, num_tokens


@retry(
    stop=stop_after_attempt(API_MAX_RETRY),
    wait=wait_fixed(API_RETRY_SLEEP),
    retry=retry_if_exception_type(Exception),
    after=retry_log,
    retry_error_callback=retry_fail
)
def chat_completion_nvidia(model, conv, temperature, max_tokens, api_dict=None) -> tuple[str, int]:
    if api_dict is not None and "api_key" in api_dict:
        api_key = api_dict["api_key"]
    else:
        api_key = os.environ["NVIDIA_API_KEY"]

    print("sleeping for 2 sec")
    time.sleep(2)

    from openai import OpenAI

    client = OpenAI(
        api_key=api_key, base_url="https://integrate.api.nvidia.com/v1"
    )
    messages = conv.to_openai_api_messages()
    response = client.chat.completions.create(
        model=model.api_name,
        messages=messages,
        temperature=0.5,
        max_tokens=max_tokens,
        top_p=1,
        stream=False,
    )
    message = response.choices[0].message.content
    if message is None:
        raise Exception("No message returned from NVIDIA")
    
    return message, response.usage.completion_tokens


@retry(
    stop=stop_after_attempt(API_MAX_RETRY),
    wait=wait_fixed(API_RETRY_SLEEP),
    retry=retry_if_exception_type(Exception),
    after=retry_log,
    retry_error_callback=retry_fail
)
def chat_completion_xai(model, conv, temperature, max_tokens, api_dict=None) -> tuple[str, int]:
    if api_dict is not None and "api_key" in api_dict:
        api_key = api_dict["api_key"]
    else:
        api_key = os.environ["XAI_API_KEY"]

    from openai import OpenAI

    client = OpenAI(base_url="https://api.x.ai/v1", api_key=api_key)
    messages = conv.to_openai_api_messages()

    response = client.chat.completions.create(
        model=model.api_name,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        n=1,
        stream=False,
    )
    message = response.choices[0].message.content
    if message is None:
        raise Exception("No message returned from X.AI")
        
    return message, response.usage.completion_tokens


@retry(
    stop=stop_after_attempt(API_MAX_RETRY),
    wait=wait_fixed(API_RETRY_SLEEP),
    retry=retry_if_exception_type(Exception),
    after=retry_log,
    retry_error_callback=retry_fail
)
def chat_completion_vertex(
    model, conv, temperature, max_tokens, api_dict=None, project_name="DEFAULT"
) -> tuple[str, int]:
    import vertexai
    from vertexai.preview.generative_models import GenerativeModel, Image

    print("sleeping for 5 sec")
    time.sleep(5)
    vertexai.init(project=project_name, location="us-central1")
    generative_multimodal_model = GenerativeModel(model.api_name)
    prompt = [text for role, text in conv.messages if role == "user"][0]
    response = generative_multimodal_model.generate_content([prompt])
    message = response.candidates[0].content.parts[0].text
    if message is None:
        raise Exception("No message returned from Vertex")

    return message.strip(), response.usage.output_tokens


@retry(
    stop=stop_after_attempt(API_MAX_RETRY),
    wait=wait_fixed(API_RETRY_SLEEP),
    retry=retry_if_exception_type(Exception),
    after=retry_log,
    retry_error_callback=retry_fail
)
def chat_completion_google_generativeai(
    model, conv, temperature, max_tokens, api_dict=None
) -> tuple[str, int]:
    import google.generativeai as genai

    if api_dict is not None and "api_key" in api_dict:
        api_key = api_dict["api_key"]
    else:
        api_key = os.environ["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    generation_config = {
        "temperature": temperature,
        "top_p": 1,
        "top_k": 1,
        "max_output_tokens": max_tokens,
    }

    gemini = genai.GenerativeModel(
        model_name=model.api_name,
        generation_config=generation_config,
        safety_settings=safety_settings,
    )

    convo = gemini.start_chat(history=[])
    prompt = [text for role, text in conv.messages if role == "user"][0]

    response = convo.send_message(prompt)
    return convo.last.text, response.usage_metadata.candidates_token_count


@retry(
    stop=stop_after_attempt(API_MAX_RETRY),
    wait=wait_fixed(API_RETRY_SLEEP),
    retry=retry_if_exception_type(Exception),
    after=retry_log,
    retry_error_callback=retry_fail
)
def chat_completion_together(model, conv, temperature, max_tokens, api_dict=None) -> tuple[str, int]:
    from together import Together

    if api_dict is not None and "api_key" in api_dict:
        api_key = api_dict["api_key"]
    else:
        api_key = os.environ["TOGETHER_API_KEY"]
    client = Together(api_key=api_key)
    
    prompt = [text for role, text in conv.messages if "user" in role][0]

    response = client.chat.completions.create(
        model=model.api_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    
    return response.choices[0].message.content, response.usage.completion_tokens


@retry(
    stop=stop_after_attempt(API_MAX_RETRY),
    wait=wait_fixed(API_RETRY_SLEEP),
    retry=retry_if_exception_type(Exception),
    after=retry_log,
    retry_error_callback=retry_fail
)
def chat_completion_openai_azure(model, conv, temperature, max_tokens, api_dict=None) -> tuple[str, int]:
    openai.api_type = "azure"
    openai.api_version = "2023-07-01-preview"
    if api_dict is not None:
        openai.base_url = api_dict["api_base"]
        openai.api_key = api_dict["api_key"]
    else:
        openai.base_url = os.environ["AZURE_OPENAI_ENDPOINT"]
        openai.api_key = os.environ["AZURE_OPENAI_KEY"]

    if "azure-" in model:
        model = model[6:]

    from openai import OpenAI
    client = OpenAI()

    messages = conv.to_openai_api_messages()
    response = client.chat.completions.create(
        engine=model.api_name,
        messages=messages,
        n=1,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    output = response.choices[0].message.content
    if output is None:
        raise Exception("No message returned from Azure OpenAI")
    
    return output, response.usage.completion_tokens


@retry(
    stop=stop_after_attempt(API_MAX_RETRY),
    wait=wait_fixed(API_RETRY_SLEEP),
    retry=retry_if_exception_type(Exception),
    after=retry_log,
    retry_error_callback=retry_fail
)
def chat_completion_anthropic(model, conv, temperature, max_tokens, api_dict=None) -> tuple[str, int]:
    if api_dict is not None and "api_key" in api_dict:
        api_key = api_dict["api_key"]
    else:
        api_key = os.environ["ANTHROPIC_API_KEY"]

    from anthropic import Anthropic
    c = Anthropic(api_key=api_key)
    prompt = [text for role, text in conv.messages if role == "Human"][0]
    response = c.messages.create(
        model=model.api_name,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
        ],
    )
    if response.content[0].text is None:
        raise Exception("No message returned from Anthropic")
        
    return response.content[0].text.strip(), response.usage.output_tokens


@retry(
    stop=stop_after_attempt(API_MAX_RETRY),
    wait=wait_fixed(API_RETRY_SLEEP),
    retry=retry_if_exception_type(Exception),
    after=retry_log,
    retry_error_callback=retry_fail
)
def chat_completion_mistral(model, conv, temperature, max_tokens, api_dict=None) -> tuple[str, int]:
    if api_dict is not None and "api_key" in api_dict:
        api_key = api_dict["api_key"]
    else:
        api_key = os.environ["MISTRAL_API_KEY"]

    from mistralai import Mistral
    client = Mistral(api_key=api_key)

    messages = conv.to_openai_api_messages()
    chat_response = client.chat.complete(
        model=model.api_name,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=messages,
    )

    if chat_response.choices[0].message.content is None:
        raise Exception("No message returned from Mistral")
        
    return chat_response.choices[0].message.content.strip(), chat_response.usage.output_tokens


@retry(
    stop=stop_after_attempt(API_MAX_RETRY),
    wait=wait_fixed(API_RETRY_SLEEP),
    retry=retry_if_exception_type(Exception),
    after=retry_log,
    retry_error_callback=retry_fail
)
def chat_completion_cohere(model, conv, temperature, max_tokens, api_dict=None) -> tuple[str, int]:
    if api_dict is not None and "api_key" in api_dict:
        api_key = api_dict["api_key"]
    else:
        api_key = os.environ["CO_API_KEY"]

    import cohere
    co = cohere.Client(api_key=api_key)
    prompt = [text for role, text in conv.messages if role == "user"][0]

    response = co.chat(
        model=model.api_name,
        max_tokens=min(max_tokens, 4000),
        temperature=temperature,
        message=prompt,
    )
    if response.text is None:
        raise Exception("No message returned from Cohere")
        
    return response.text.strip(), response.usage.output_tokens


@retry(
    stop=stop_after_attempt(API_MAX_RETRY),
    wait=wait_fixed(API_RETRY_SLEEP),
    retry=retry_if_exception_type(Exception),
    after=retry_log,
    retry_error_callback=retry_fail
)
def chat_completion_palm(chat_state, model, conv, temperature, max_tokens) -> tuple[str, int]:
    from fastchat.serve.api_provider import init_palm_chat

    assert model.api_name == "palm-2-chat-bison-001"

    if chat_state is None:
        chat_state = init_palm_chat("chat-bison@001")

    parameters = {
        "temperature": temperature,
        "top_p": 0.8,
        "top_k": 40,
        "max_output_tokens": max_tokens,
    }
    
    response = chat_state.send_message(conv.messages[-2][1], **parameters)
    if response.text is None:
        raise Exception("No message returned from PaLM")
        
    return chat_state, response.text, response.usage.output_tokens
