#!/usr/bin/env python


import json
import mock
import requests
import requests_mock
import base64
from click.testing import CliRunner

from cfssl_refresh_cert import CFSSLRefreshCert, cfssl_refresh_cert_cli


def test_cfssl_config_read():
    refresher = CFSSLRefreshCert()
    d = {
        "cfssl": {
            "url": "http://127.0.0.1:8888",
            "request": {
                "CN": "testpost",
            }
        },
        "output": {
            "cert": "server.pem",
            "key": "server-key.pem"
        }
    }

    m = mock.mock_open(read_data=json.dumps(d))
    with mock.patch("cfssl_refresh_cert.open", m, create=True):
        refresher.read_config_from_file("fake.json")

    assert refresher.config == d

def test_cfssl_ok():
    refresher = CFSSLRefreshCert()
    refresher.config = {
        "cfssl": {
            "url": "http://127.0.0.1:8888",
            "request": {
                "CN": "testpost",
            }
        },
        "output": {
            "cert": "server.pem",
            "key": "server-key.pem"
        }
    }

    with requests_mock.mock() as m:
        json_response = {
            "result": {
                "certificate": "cfssl cert",
                "private_key": "cfssl key",
            }
        }
        m.post("http://127.0.0.1:8888/api/v1/cfssl/newcert",
               json=json_response)

        refresher._write_out_cert_files = mock.MagicMock()

        result = refresher.refresh_cert_and_key()
        assert result

        # assert POST body is correct
        assert len(m.request_history) == 1
        assert m.request_history[0].method == 'POST'
        assert m.request_history[0].url == \
            "http://127.0.0.1:8888/api/v1/cfssl/newcert"
        assert m.request_history[0].text == \
            json.dumps({"request":{"CN":"testpost"}})

        # assert data is correctly written
        refresher._write_out_cert_files.assert_called_with("cfssl cert",
                                                           "cfssl key")

def test_cfssl_bad_post():
    refresher = CFSSLRefreshCert()
    refresher.config = {
        "cfssl": {
            "url": "http://127.0.0.1:8888",
            "request": {
                "CN": "testpost",
            }
        },
        "output": {
            "cert": "server.pem",
            "key": "server-key.pem"
        }
    }

    with requests_mock.mock() as m:
        json_response = {
            "result": {
                "certificate": "cfssl cert",
                "private_key": "cfssl key",
            }
        }
        m.post("http://127.0.0.1:8888/api/v1/cfssl/newcert",
               exc=requests.exceptions.ConnectTimeout)

        refresher._write_out_cert_files = mock.MagicMock()

        result = refresher.refresh_cert_and_key()
        assert not result

        # assert POST body is correct
        assert len(m.request_history) == 1
        assert m.request_history[0].method == 'POST'
        assert m.request_history[0].url == \
            "http://127.0.0.1:8888/api/v1/cfssl/newcert"
        assert m.request_history[0].text == \
            json.dumps({"request":{"CN":"testpost"}})

        # assert data is never written
        assert not refresher._write_out_cert_files.called


def test_cfssl_ok_with_auth():
    refresher = CFSSLRefreshCert()
    refresher.config = {
        "cfssl": {
            "url": "http://127.0.0.1:8888",
            "auth": {
                "user": "cfssluser",
                "password": "cfsslpasswd"
            },
            "request": {
                "CN": "testpost",
            }
        },
        "output": {
            "cert": "server.pem",
            "key": "server-key.pem"
        }
    }

    with requests_mock.mock() as m:
        json_response = {
            "result": {
                "certificate": "cfssl cert",
                "private_key": "cfssl key",
            }
        }
        m.post("http://127.0.0.1:8888/api/v1/cfssl/newcert",
               json=json_response)

        refresher._write_out_cert_files = mock.MagicMock()

        result = refresher.refresh_cert_and_key()
        assert result

        # assert POST body is correct
        assert len(m.request_history) == 1
        assert m.request_history[0].method == 'POST'
        assert m.request_history[0].url == \
            "http://127.0.0.1:8888/api/v1/cfssl/newcert"
        assert m.request_history[0].text == \
            json.dumps({"request":{"CN":"testpost"}})
        assert "authorization" in m.request_history[0]._request.headers
        basic_auth = "Basic {}".format(
            base64.b64encode("{}:{}".format("cfssluser", "cfsslpasswd")))
        assert m.request_history[0]._request.headers["authorization"] == \
            basic_auth

        # assert data is correctly written
        refresher._write_out_cert_files.assert_called_with("cfssl cert",
                                                           "cfssl key")

def test_cfssl_writes():
    refresher = CFSSLRefreshCert()
    refresher.config = {
        "output": {
            "cert": "server.pem",
            "key": "server-key.pem"
        }
    }

    m = mock.mock_open()
    with mock.patch("cfssl_refresh_cert.open", m, create=True):
        refresher._write_out_cert_files("cert", "key")

    m.assert_has_calls([mock.call("server.pem", "w"),
                        mock.call().write("cert"),
                        mock.call().__exit__(None, None, None),
                        mock.call("server-key.pem", "w"),
                        mock.call().write("key"),
                        mock.call().__exit__(None, None, None),
                        ],
                       any_order=True)

def test_cfssl_cli_ok():
    with mock.patch("cfssl_refresh_cert.CFSSLRefreshCert") as m:
        runner = CliRunner()
        result = runner.invoke(cfssl_refresh_cert_cli,
                               ["--config", "fake.json"])
        assert result.exit_code == 0

        m.assert_has_calls([mock.call().read_config_from_file("fake.json"),
                            mock.call().refresh_cert_and_key()
                            ],
                           any_order=False)

def test_cfssl_cli_bad():
    with mock.patch("cfssl_refresh_cert.CFSSLRefreshCert") as m:
        runner = CliRunner()

        mock_object = m.return_value
        mock_object.refresh_cert_and_key.return_value = False

        result = runner.invoke(cfssl_refresh_cert_cli,
                               ["--config", "fake.json"])
        assert result.exit_code != 0

        m.assert_has_calls([mock.call().read_config_from_file("fake.json"),
                            mock.call().refresh_cert_and_key()
                            ],
                           any_order=False)

