import asyncio
import json
import httpx
from rest_api_server.globals import Settings
from rest_api_server.services.tenant_summaries import FoundrySummaryProvider


def test_foundry_streaming_request(monkeypatch):
    observed = []
    def respond(request):
        observed.append(request)
        return httpx.Response(200, headers={'content-type':'text/event-stream'}, text='data: {"choices":[{"delta":{"content":"Overview"}}]}\n\ndata: [DONE]\n\n')
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    settings = Settings(foundry_endpoint='https://example.services.ai.azure.com', foundry_api_key='test-resource-key', foundry_deployment='demo-chat')
    async def scenario():
        provider = FoundrySummaryProvider(settings)
        provider.validate()
        return [part async for part in provider.stream({'counts':{'employees':3}}, {'question':'How many employees?', 'history':[{'role':'user','content':'Show my tenant'}]})]
    assert asyncio.run(scenario()) == ['Overview']
    request = observed[0]
    assert str(request.url) == 'https://example.services.ai.azure.com/openai/v1/chat/completions'
    assert request.headers['api-key'] == 'test-resource-key'
    payload = json.loads(request.content)
    assert payload['stream'] is True
    assert payload['model'] == 'demo-chat'
    assert json.loads(payload['messages'][1]['content'].split(': ',1)[1])['counts']['employees'] == 3

    assert payload['messages'][-1] == {'role':'user','content':'How many employees?'}
    assert payload['messages'][-2] == {'role':'user','content':'Show my tenant'}
