"""Tests for CORS support and rate limiting."""
import io
import logging
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock

from sql2api import cli, config, cors, create_app
from sql2api.ratelimit import RateLimiter

ORIGIN = 'https://app.example.com'


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {'SQL2API_HOME': self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in ('SQL2API_API_KEY', 'SQL2API_CORS_ORIGINS', 'SQL2API_RATE_LIMIT', 'SQL2API_TRUST_PROXY'):
            os.environ.pop(name, None)

    def client(self):
        return create_app().test_client()


class CorsTests(AppTestCase):
    def test_off_by_default_no_headers_even_when_an_origin_is_sent(self):
        res = self.client().get('/connections', headers={'Origin': ORIGIN})
        self.assertNotIn('Access-Control-Allow-Origin', res.headers)

    def test_listed_origin_is_echoed_with_vary_and_exposed_pagination_headers(self):
        os.environ['SQL2API_CORS_ORIGINS'] = f'{ORIGIN}, https://other.example.org'
        res = self.client().get('/connections', headers={'Origin': ORIGIN})
        self.assertEqual(res.headers['Access-Control-Allow-Origin'], ORIGIN)
        self.assertIn('Origin', res.headers['Vary'])
        for name in ('X-Page', 'X-Has-More', 'X-RateLimit-Remaining'):  # a page's JS cannot read them otherwise
            self.assertIn(name, res.headers['Access-Control-Expose-Headers'])
        self.assertNotIn('Access-Control-Allow-Credentials', res.headers)

    def test_unlisted_origins_get_nothing(self):
        os.environ['SQL2API_CORS_ORIGINS'] = ORIGIN
        client = self.client()
        for origin in ('https://evil.example.com', 'http://app.example.com', 'https://app.example.com:8443',
                       'https://app.example.com.evil.com', 'null', ''):
            res = client.get('/connections', headers={'Origin': origin})
            self.assertNotIn('Access-Control-Allow-Origin', res.headers, origin)
        self.assertNotIn('Access-Control-Allow-Origin', client.get('/connections').headers)  # no Origin at all

    def test_matching_ignores_case_and_a_trailing_slash(self):
        os.environ['SQL2API_CORS_ORIGINS'] = 'HTTPS://App.Example.com/'
        res = self.client().get('/connections', headers={'Origin': ORIGIN})
        self.assertEqual(res.headers['Access-Control-Allow-Origin'], ORIGIN)

    def test_wildcard(self):
        os.environ['SQL2API_CORS_ORIGINS'] = '*'
        res = self.client().get('/connections', headers={'Origin': 'https://anything.example'})
        self.assertEqual(res.headers['Access-Control-Allow-Origin'], '*')
        self.assertNotIn('Vary', res.headers)

    def test_preflight_is_answered_without_an_api_key(self):
        os.environ['SQL2API_CORS_ORIGINS'] = ORIGIN
        os.environ['SQL2API_API_KEY'] = 'k3y'  # browsers cannot attach the key to the permission check
        res = self.client().options('/execute_sql', headers={
            'Origin': ORIGIN, 'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'content-type, x-api-key'})
        self.assertEqual(res.status_code, 204)
        self.assertEqual(res.headers['Access-Control-Allow-Origin'], ORIGIN)
        self.assertIn('POST', res.headers['Access-Control-Allow-Methods'])
        self.assertIn('X-API-Key', res.headers['Access-Control-Allow-Headers'])
        self.assertEqual(res.headers['Access-Control-Max-Age'], '600')

    def test_preflight_from_an_unlisted_origin_grants_nothing(self):
        os.environ['SQL2API_CORS_ORIGINS'] = ORIGIN
        res = self.client().options('/execute_sql', headers={
            'Origin': 'https://evil.example.com', 'Access-Control-Request-Method': 'POST'})
        self.assertEqual(res.status_code, 204)
        self.assertNotIn('Access-Control-Allow-Origin', res.headers)
        self.assertNotIn('Access-Control-Allow-Methods', res.headers)

    def test_cors_is_not_authentication(self):
        os.environ['SQL2API_CORS_ORIGINS'] = ORIGIN
        os.environ['SQL2API_API_KEY'] = 'k3y'
        client = self.client()
        res = client.get('/connections', headers={'Origin': ORIGIN})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.headers['Access-Control-Allow-Origin'], ORIGIN)  # so the page can read the 401
        self.assertEqual(client.get('/connections', headers={'Origin': ORIGIN, 'X-API-Key': 'k3y'}).status_code, 200)

    def test_a_plain_options_request_is_not_mistaken_for_a_preflight(self):
        os.environ['SQL2API_CORS_ORIGINS'] = ORIGIN
        os.environ['SQL2API_API_KEY'] = 'k3y'
        self.assertEqual(self.client().options('/connections').status_code, 401)  # no Access-Control-Request-Method

    def test_wildcard_without_an_api_key_warns_loudly(self):
        os.environ['SQL2API_CORS_ORIGINS'] = '*'
        with self.assertLogs('sql2api', level=logging.WARNING) as logs:
            create_app()
        self.assertIn('without SQL2API_API_KEY', logs.output[0])
        os.environ['SQL2API_API_KEY'] = 'k3y'
        with mock.patch('sql2api.app.log.warning') as warning:  # assertNoLogs needs Python 3.10; CI also runs 3.9
            create_app()
        warning.assert_not_called()

    def test_helpers(self):
        self.assertIsNone(cors.allow_origin_value(ORIGIN))  # off
        self.assertIsNone(config.cors_origins())
        with mock.patch.dict(os.environ, {'SQL2API_CORS_ORIGINS': ' , '}):
            self.assertIsNone(config.cors_origins())


class RateLimitTests(AppTestCase):
    def test_off_by_default(self):
        client = self.client()
        for _ in range(20):
            res = client.get('/connections')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('X-RateLimit-Limit', res.headers)

    def test_requests_over_the_limit_get_429_with_retry_after(self):
        os.environ['SQL2API_RATE_LIMIT'] = '3/minute'
        client = self.client()
        remaining = []
        for _ in range(3):
            res = client.get('/connections')
            self.assertEqual((res.status_code, res.headers['X-RateLimit-Limit']), (200, '3'))
            remaining.append(int(res.headers['X-RateLimit-Remaining']))
        self.assertEqual(remaining, [2, 1, 0])
        res = client.get('/connections')
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res.get_json()['error'], 'Rate limit exceeded')
        self.assertTrue(1 <= int(res.headers['Retry-After']) <= 20)
        self.assertEqual(res.get_json()['retry_after'], int(res.headers['Retry-After']))
        self.assertEqual(res.headers['X-RateLimit-Remaining'], '0')

    def test_health_checks_and_preflights_are_never_throttled(self):
        os.environ['SQL2API_RATE_LIMIT'] = '1/minute'
        os.environ['SQL2API_CORS_ORIGINS'] = ORIGIN
        client = self.client()
        self.assertEqual(client.get('/connections').status_code, 200)
        self.assertEqual(client.get('/connections').status_code, 429)
        for _ in range(5):
            self.assertEqual(client.get('/health').status_code, 200)
            self.assertEqual(client.options('/connections', headers={
                'Origin': ORIGIN, 'Access-Control-Request-Method': 'GET'}).status_code, 204)

    def test_guessing_the_api_key_is_throttled_because_the_limit_comes_first(self):
        os.environ['SQL2API_RATE_LIMIT'] = '3/minute'
        os.environ['SQL2API_API_KEY'] = 'k3y'
        client = self.client()
        statuses = [client.get('/connections', headers={'X-API-Key': f'guess{i}'}).status_code for i in range(5)]
        self.assertEqual(statuses, [401, 401, 401, 429, 429])
        # ...and even the right key is refused while the client is being throttled
        self.assertEqual(client.get('/connections', headers={'X-API-Key': 'k3y'}).status_code, 429)

    def test_rejections_are_readable_by_a_browser(self):
        os.environ['SQL2API_RATE_LIMIT'] = '1/minute'
        os.environ['SQL2API_CORS_ORIGINS'] = ORIGIN
        client = self.client()
        client.get('/connections')
        res = client.get('/connections', headers={'Origin': ORIGIN})
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res.headers['Access-Control-Allow-Origin'], ORIGIN)
        self.assertIn('Retry-After', res.headers['Access-Control-Expose-Headers'])

    def test_clients_are_counted_separately_by_address(self):
        os.environ['SQL2API_RATE_LIMIT'] = '1/minute'
        client = self.client()
        get = lambda ip: client.get('/connections', environ_base={'REMOTE_ADDR': ip}).status_code  # noqa: E731
        self.assertEqual([get('10.0.0.1'), get('10.0.0.1'), get('10.0.0.2')], [200, 429, 200])

    def test_forwarded_headers_are_ignored_unless_a_proxy_is_trusted(self):
        os.environ['SQL2API_RATE_LIMIT'] = '1/minute'
        client = self.client()
        # a client cannot dodge the limit by inventing X-Forwarded-For values
        codes = [client.get('/connections', headers={'X-Forwarded-For': f'203.0.113.{i}'}).status_code
                 for i in range(3)]
        self.assertEqual(codes, [200, 429, 429])

    def test_behind_a_trusted_proxy_the_real_client_address_is_used(self):
        os.environ['SQL2API_RATE_LIMIT'] = '1/minute'
        os.environ['SQL2API_TRUST_PROXY'] = '1'
        client = self.client()
        get = lambda ip: client.get('/connections', headers={'X-Forwarded-For': ip},  # noqa: E731
                                    environ_base={'REMOTE_ADDR': '172.17.0.2'}).status_code  # the proxy itself
        self.assertEqual([get('203.0.113.1'), get('203.0.113.1'), get('203.0.113.2')], [200, 429, 200])

    def test_only_the_trusted_hop_is_believed(self):
        os.environ['SQL2API_RATE_LIMIT'] = '1/minute'
        os.environ['SQL2API_TRUST_PROXY'] = '1'
        client = self.client()
        # the proxy appends the address it actually saw; anything a client prepended is not trusted
        get = lambda forged: client.get('/connections',  # noqa: E731
                                        headers={'X-Forwarded-For': f'{forged}, 203.0.113.9'},
                                        environ_base={'REMOTE_ADDR': '172.17.0.2'}).status_code
        self.assertEqual([get('1.1.1.1'), get('2.2.2.2'), get('3.3.3.3')], [200, 429, 429])

    def test_malformed_setting_fails_at_startup_instead_of_silently_disabling_the_limit(self):
        for bad in ('fast', '0/minute', '10/week', '-5/second', '60', '/minute', '5 per minute'):
            with mock.patch.dict(os.environ, {'SQL2API_RATE_LIMIT': bad}):
                with self.assertRaises(ValueError, msg=bad):
                    create_app()

    def test_the_command_line_reports_a_malformed_setting_cleanly(self):
        os.environ['SQL2API_RATE_LIMIT'] = 'fast'
        err = io.StringIO()
        with redirect_stderr(err):
            code = cli.main(['serve', '--port', '5999'])
        self.assertEqual(code, 2)
        self.assertIn("SQL2API_RATE_LIMIT must look like '60/minute'", err.getvalue())

    def test_accepted_spellings(self):
        for text, expected in (('60/minute', (60, 60)), (' 5 / second ', (5, 1)), ('100/HOURS', (100, 3600)),
                               ('1/day', (1, 86400)), ('7/Minutes', (7, 60))):
            self.assertEqual(config.parse_rate_limit(text), expected, text)


class TokenBucketTests(unittest.TestCase):
    """The limiter itself, driven by a fake clock."""

    def setUp(self):
        self.now = 1000.0
        self.limiter = RateLimiter(clock=lambda: self.now)

    def test_burst_then_steady_rate(self):
        results = [self.limiter.hit('a', 60, 60)[0] for _ in range(61)]
        self.assertEqual(results, [True] * 60 + [False])          # the whole quota may be used at once
        self.now += 1                                             # 60/minute refills one token per second
        self.assertTrue(self.limiter.hit('a', 60, 60)[0])
        self.assertFalse(self.limiter.hit('a', 60, 60)[0])

    def test_remaining_and_retry_after(self):
        self.assertEqual(self.limiter.hit('a', 2, 60), (True, 1, 0))
        self.assertEqual(self.limiter.hit('a', 2, 60), (True, 0, 0))
        allowed, remaining, retry_after = self.limiter.hit('a', 2, 60)
        self.assertEqual((allowed, remaining, retry_after), (False, 0, 30))  # one token every 30 s
        self.now += 10
        self.assertEqual(self.limiter.hit('a', 2, 60)[2], 20)                # the wait shrinks as time passes

    def test_tokens_never_exceed_the_quota(self):
        self.limiter.hit('a', 3, 60)
        self.now += 10_000
        self.assertEqual(self.limiter.hit('a', 3, 60), (True, 2, 0))

    def test_clients_are_independent(self):
        for _ in range(3):
            self.limiter.hit('a', 3, 60)
        self.assertFalse(self.limiter.hit('a', 3, 60)[0])
        self.assertTrue(self.limiter.hit('b', 3, 60)[0])

    def test_changing_the_limit_starts_fresh(self):
        for _ in range(3):
            self.limiter.hit('a', 3, 60)
        self.assertFalse(self.limiter.hit('a', 3, 60)[0])
        self.assertTrue(self.limiter.hit('a', 10, 60)[0])

    def test_idle_clients_are_forgotten_and_memory_is_bounded(self):
        for i in range(50):
            self.limiter.hit(f'c{i}', 5, 60)
        self.now += 61                                            # everyone is idle for more than a period
        self.limiter.hit('fresh', 5, 60)
        self.assertEqual(self.limiter.size(), 1)
        self.limiter.MAX_CLIENTS = 10
        for i in range(100):
            self.limiter.hit(f'flood{i}', 5, 60)
        self.assertLessEqual(self.limiter.size(), 10)             # least recently seen are dropped first

    def test_many_threads_cannot_exceed_the_quota(self):
        import threading
        allowed = []

        def worker():
            for _ in range(50):
                allowed.append(self.limiter.hit('shared', 100, 3600)[0])

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(allowed.count(True), 100)                # exactly the quota, no matter the interleaving


if __name__ == '__main__':
    unittest.main()
