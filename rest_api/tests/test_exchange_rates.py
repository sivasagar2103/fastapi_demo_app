import asyncio
import httpx
import pytest
from rest_api_server.services.exchange_rates import ExchangeRateClient, ExchangeRateError


def test_exchange_rate_provider_and_timeout(monkeypatch):
    captured = []
    def respond(request):
        captured.append(request)
        return httpx.Response(200,json={'result':'success','base_code':'USD','conversion_rates':{'USD':1,'EUR':0.9},'time_last_update_utc':'Demo'})
    original = httpx.AsyncClient
    def factory(**kwargs):
        assert kwargs['timeout']==10
        return original(transport=httpx.MockTransport(respond),**kwargs)
    monkeypatch.setattr(httpx,'AsyncClient',factory)
    result = asyncio.run(ExchangeRateClient('test-key').fetch())
    assert result['rates']['EUR']==0.9
    assert str(captured[0].url)=='https://v6.exchangerate-api.com/v6/test-key/latest/USD'
    with pytest.raises(ExchangeRateError,match='not configured'):
        asyncio.run(ExchangeRateClient('').fetch())


def test_exchange_rate_timeout_hides_key(monkeypatch):
    original = httpx.AsyncClient
    def respond(request):
        raise httpx.ReadTimeout('secret-key-in-url',request=request)
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    with pytest.raises(ExchangeRateError) as failure:
        asyncio.run(ExchangeRateClient('secret-key-in-url').fetch())
    assert failure.value.retry
    assert 'secret-key' not in str(failure.value)
