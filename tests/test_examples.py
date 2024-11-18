from __future__ import annotations as _annotations

import asyncio
import re
import sys
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any

import httpx
import pytest
from devtools import debug
from pytest_examples import CodeExample, EvalExample, find_examples
from pytest_mock import MockerFixture

from pydantic_ai.messages import (
    ArgsObject,
    Message,
    ModelAnyResponse,
    ModelStructuredResponse,
    ModelTextResponse,
    ToolCall,
)
from pydantic_ai.models import KnownModelName, Model
from pydantic_ai.models.function import AgentInfo, DeltaToolCalls, FunctionModel
from pydantic_ai.models.test import TestModel
from tests.conftest import ClientWithHandler


@pytest.fixture(scope='module', autouse=True)
def register_modules():
    class FakeTable:
        def get(self, name: str) -> int | None:
            if name == 'John Doe':
                return 123

    @dataclass
    class DatabaseConn:
        users: FakeTable = field(default_factory=FakeTable)

    module_name = 'fake_database'
    sys.modules[module_name] = module = ModuleType(module_name)
    module.__dict__.update({'DatabaseConn': DatabaseConn})

    yield

    sys.modules.pop(module_name)


def find_filter_examples() -> Iterable[CodeExample]:
    for ex in find_examples('docs', 'pydantic_ai'):
        if ex.path.name != '_utils.py':
            yield ex


@pytest.mark.parametrize('example', find_filter_examples(), ids=str)
def test_docs_examples(
    example: CodeExample, eval_example: EvalExample, mocker: MockerFixture, client_with_handler: ClientWithHandler
):
    # debug(example)
    mocker.patch('pydantic_ai.agent.models.infer_model', side_effect=mock_infer_model)

    mocker.patch('httpx.Client.get', side_effect=http_request)
    mocker.patch('httpx.Client.post', side_effect=http_request)
    mocker.patch('httpx.AsyncClient.get', side_effect=async_http_request)
    mocker.patch('httpx.AsyncClient.post', side_effect=async_http_request)
    mocker.patch('random.randint', return_value=4)

    prefix_settings = example.prefix_settings()

    ruff_ignore: list[str] = ['D']
    if str(example.path).endswith('docs/index.md'):
        ruff_ignore.append('F841')
    eval_example.set_config(ruff_ignore=ruff_ignore, target_version='py39')

    eval_example.print_callback = print_callback

    call_name = 'main'
    if 'def test_application_code' in example.source:
        call_name = 'test_application_code'

    if eval_example.update_examples:
        eval_example.format(example)
        module_dict = eval_example.run_print_update(example, call=call_name)
    else:
        eval_example.lint(example)
        module_dict = eval_example.run_print_check(example, call=call_name)

    if title := prefix_settings.get('title'):
        if title.endswith('.py'):
            module_name = title[:-3]
            sys.modules[module_name] = module = ModuleType(module_name)
            module.__dict__.update(module_dict)


def print_callback(s: str) -> str:
    return re.sub(r'datetime.datetime\(.+?\)', 'datetime.datetime(...)', s, flags=re.DOTALL)


def http_request(url: str, **kwargs: Any) -> httpx.Response:
    # sys.stdout.write(f'GET {args=} {kwargs=}\n')
    request = httpx.Request('GET', url, **kwargs)
    return httpx.Response(status_code=202, content='', request=request)


async def async_http_request(url: str, **kwargs: Any) -> httpx.Response:
    return http_request(url, **kwargs)


text_responses: dict[str, str | ToolCall] = {
    'What is the weather like in West London and in Wiltshire?': 'The weather in West London is raining, while in Wiltshire it is sunny.',
    'Tell me a joke.': 'Did you hear about the toothpaste scandal? They called it Colgate.',
    'Explain?': 'This is an excellent joke invent by Samuel Colvin, it needs no explanation.',
    'What is the capital of France?': 'Paris',
    'What is the capital of Italy?': 'Rome',
    'What is the capital of the UK?': 'London',
    'Who was Albert Einstein?': 'Albert Einstein was a German-born theoretical physicist.',
    'What was his most famous equation?': "Albert Einstein's most famous equation is (E = mc^2).",
    'What is the date?': 'Hello Frank, the date today is 2032-01-02.',
    'Put my money on square eighteen': ToolCall(tool_name='roulette_wheel', args=ArgsObject({'square': 18})),
    'I bet five is the winner': ToolCall(tool_name='roulette_wheel', args=ArgsObject({'square': 5})),
    'My guess is 4': ToolCall(tool_name='roll_dice', args=ArgsObject({})),
    'Send a message to John Doe asking for coffee next week': ToolCall(
        tool_name='get_user_by_name', args=ArgsObject({'name': 'John'})
    ),
    'Please get me the volume of a box with size 6.': ToolCall(tool_name='calc_volume', args=ArgsObject({'size': 6})),
}


async def model_logic(messages: list[Message], info: AgentInfo) -> ModelAnyResponse:
    m = messages[-1]
    if m.role == 'user':
        if response := text_responses.get(m.content):
            if isinstance(response, str):
                return ModelTextResponse(content=response)
            else:
                return ModelStructuredResponse(calls=[response])

    elif m.role == 'tool-return' and m.tool_name == 'roulette_wheel':
        win = m.content == 'winner'
        return ModelStructuredResponse(calls=[ToolCall(tool_name='final_result', args=ArgsObject({'response': win}))])
    elif m.role == 'tool-return' and m.tool_name == 'roll_dice':
        return ModelStructuredResponse(calls=[ToolCall(tool_name='get_player_name', args=ArgsObject({}))])
    elif m.role == 'tool-return' and m.tool_name == 'get_player_name':
        return ModelTextResponse(content="Congratulations Adam, you guessed correctly! You're a winner!")
    if m.role == 'retry-prompt' and isinstance(m.content, str) and m.content.startswith("No user found with name 'Joh"):
        return ModelStructuredResponse(
            calls=[ToolCall(tool_name='get_user_by_name', args=ArgsObject({'name': 'John Doe'}))]
        )
    elif m.role == 'tool-return' and m.tool_name == 'get_user_by_name':
        args = {
            'message': 'Hello John, would you be free for coffee sometime next week? Let me know what works for you!',
            'user_id': 123,
        }
        return ModelStructuredResponse(calls=[ToolCall(tool_name='final_result', args=ArgsObject(args))])
    elif m.role == 'retry-prompt' and m.tool_name == 'calc_volume':
        return ModelStructuredResponse(calls=[ToolCall(tool_name='calc_volume', args=ArgsObject({'size': 6}))])
    else:
        sys.stdout.write(str(debug.format(messages, info)))
        raise RuntimeError(f'Unexpected message: {m}')


async def stream_model_logic(messages: list[Message], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
    m = messages[-1]
    if m.role == 'user':
        if response := text_responses.get(m.content):
            if isinstance(response, str):
                *words, last_word = response.split(' ')
                for work in words:
                    yield f'{work} '
                    await asyncio.sleep(0.05)
                yield last_word
                return
            else:
                raise NotImplementedError('todo')

    sys.stdout.write(str(debug.format(messages, info)))
    raise RuntimeError(f'Unexpected message: {m}')


def mock_infer_model(model: Model | KnownModelName) -> Model:
    if isinstance(model, (FunctionModel, TestModel)):
        return model
    else:
        return FunctionModel(model_logic, stream_function=stream_model_logic)
