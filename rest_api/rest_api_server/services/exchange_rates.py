import math
from urllib.parse import quote
import httpx

DEFAULT_BASE_CURRENCY = 'USD'
REQUEST_TIMEOUT_IN_SECONDS = 10
EXCHANGE_RATES_API_URL = 'https://v6.exchangerate-api.com/v6/{api_key}/latest/{base_currency}'

class ExchangeRateError(Exception):
    def __init__(self, message, retry=False):
        super().__init__(message)
        self.retry = retry

class ExchangeRateClient:
    def __init__(self, api_key):
        self.api_key = api_key

    async def fetch(self, base_currency=DEFAULT_BASE_CURRENCY):
        if not self.api_key:
            raise ExchangeRateError('EXCHANGE_RATES_API_KEY is not configured')
        url = EXCHANGE_RATES_API_URL.format(api_key=quote(self.api_key,safe=''),base_currency=base_currency)
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_IN_SECONDS,follow_redirects=False) as client:
                response = await client.get(url)
            if response.status_code >= 500 or response.status_code == 429:
                raise ExchangeRateError('Exchange-rate provider temporarily unavailable',retry=True)
            if response.is_error:
                raise ExchangeRateError('Exchange-rate provider rejected request; check API key and base currency')
            body = response.json()
            rates = body.get('conversion_rates')
            if body.get('result') != 'success' or body.get('base_code') != base_currency or not isinstance(rates,dict) or not rates:
                raise ExchangeRateError('Exchange-rate provider returned unsuccessful or invalid data')
            if any(not isinstance(code,str) or len(code)!=3 or not isinstance(value,(float,int)) or isinstance(value,bool) or not math.isfinite(value) or value<=0 for code,value in rates.items()):
                raise ExchangeRateError('Exchange-rate provider returned invalid rates')
            return {'base_currency':base_currency,'rates':rates,'provider_updated_at':body.get('time_last_update_utc')}
        except (httpx.TimeoutException,httpx.NetworkError):
            raise ExchangeRateError('Exchange-rate request timed out or failed to connect',retry=True) from None
        except (httpx.HTTPError,ValueError,TypeError,AttributeError):
            raise ExchangeRateError('Exchange-rate provider returned invalid data') from None
